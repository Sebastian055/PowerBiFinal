import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import psycopg

SQLITE_PATH = Path(os.getenv("SQLITE_PATH", "/data/opencem-v1.0.0.sqlite"))
PG_DSN = (
    f"host={os.getenv('POSTGRES_HOST', 'postgres')} "
    f"port={os.getenv('POSTGRES_PORT', '5432')} "
    f"dbname={os.getenv('POSTGRES_DB', 'solar_db')} "
    f"user={os.getenv('POSTGRES_USER', 'solar_user')} "
    f"password={os.getenv('POSTGRES_PASSWORD', 'solar_pass')}"
)
# Por defecto submuestrea cada 60 segundos para carga ágil (~50k registros/año) o pon SAMPLE_STEP=1 para cargar los 2.98M completos
SAMPLE_STEP = int(os.getenv("SAMPLE_STEP", "60"))
CHUNK_SIZE = 100_000

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

def upsert_fechas(cur, fechas_series):
    fechas_unicas = pd.to_datetime(fechas_series).dt.date.unique()
    rows = []
    for f in fechas_unicas:
        sk = int(f.strftime("%Y%m%d"))
        dow = f.isoweekday()
        rows.append((sk, f, f.year, f.month, MESES_ES[f.month], f.day, dow, dow >= 6))
    cur.executemany("""
        INSERT INTO dim_fecha (sk_fecha, fecha, anio, mes, nombre_mes, dia, dia_semana, es_fin_de_semana)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sk_fecha) DO NOTHING;
    """, rows)

def cargar_analog_measurements(sqlite_conn, pg_conn):
    print(f"[ETL] Leyendo analog_measurements (SAMPLE_STEP={SAMPLE_STEP})...")
    query = f"""
        SELECT rowid, read_ts, inverter, battsoc, battvolt, battcurr,
               battchgpower, pv1power, outw_a, gridpowerw_a, temper1
        FROM analog_measurements
        WHERE rowid % {SAMPLE_STEP} = 0
    """
    total_leidos = 0
    total_cargados = 0
    nulos_soc = 0
    fuera_rango = 0

    with pg_conn.cursor() as cur:
        cur.execute("SELECT inverter_id, sk_inversor FROM dim_inversor;")
        inv_map = dict(cur.fetchall())

        for chunk in pd.read_sql_query(query, sqlite_conn, chunksize=CHUNK_SIZE):
            total_leidos += len(chunk)

            # 1. Auditoría y limpieza de SoC nulo o fuera de [0, 100]
            mask_null = chunk["battsoc"].isna()
            nulos_soc += int(mask_null.sum())
            chunk = chunk[~mask_null].copy()

            mask_range = (chunk["battsoc"] < 0) | (chunk["battsoc"] > 100) | (chunk["battvolt"] < 10) | (chunk["battvolt"] > 80)
            fuera_rango += int(mask_range.sum())
            chunk = chunk[~mask_range].copy()

            if chunk.empty:
                continue

            # 2. Transformación temporal UTC y llaves dimensionales
            ts = pd.to_datetime(chunk["read_ts"], unit="s", utc=True)
            chunk["ts_utc"] = ts
            chunk["sk_fecha"] = ts.dt.strftime("%Y%m%d").astype(int)
            chunk["sk_franja"] = ts.dt.hour.astype(int)
            chunk["sk_inversor"] = chunk["inverter"].map(inv_map).fillna(1).astype(int)

            upsert_fechas(cur, ts)

            # 3. Preparar registros limpios
            records = []
            for r in chunk.itertuples(index=False):
                records.append((
                    r.ts_utc.to_pydatetime(),
                    int(r.sk_inversor),
                    int(r.sk_fecha),
                    int(r.sk_franja),
                    round(float(r.battsoc), 2),
                    round(float(r.battvolt), 2) if pd.notna(r.battvolt) else None,
                    round(float(r.battcurr), 2) if pd.notna(r.battcurr) else None,
                    int(r.battchgpower) if pd.notna(r.battchgpower) else 0,
                    int(r.pv1power) if pd.notna(r.pv1power) else 0,
                    int(r.outw_a) if pd.notna(r.outw_a) else 0,
                    int(r.gridpowerw_a) if pd.notna(r.gridpowerw_a) else 0,
                    round(float(r.temper1), 2) if pd.notna(r.temper1) else None,
                    False
                ))

            cur.executemany("""
                INSERT INTO fact_telemetria_energia (
                    ts_utc, sk_inversor, sk_fecha, sk_franja,
                    soc_pct, voltaje_bat_v, corriente_bat_a,
                    potencia_carga_bat_w, potencia_pv_w, potencia_consumo_w,
                    potencia_red_w, temp_inversor_c, es_dato_simulado
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT ON CONSTRAINT uq_telemetria_ts_inv DO NOTHING;
            """, records)
            total_cargados += len(records)
            pg_conn.commit()
            print(f"   -> Procesadas {total_leidos:,} filas | Cargadas: {total_cargados:,}")

        cur.execute("""
            INSERT INTO audit_calidad_etl (
                tabla_origen, registros_leidos, registros_cargados,
                nulos_soc_descartados, fuera_rango_limpios, observaciones
            ) VALUES (%s, %s, %s, %s, %s, %s);
        """, (
            "analog_measurements", total_leidos, total_cargados,
            nulos_soc, fuera_rango,
            f"Extracción Bronze->Gold con SAMPLE_STEP={SAMPLE_STEP}. Limpieza de battsoc NULL y voltaje fuera de rango."
        ))
        pg_conn.commit()

def cargar_fallas(sqlite_conn, pg_conn):
    print("[ETL] Extrayendo fallas únicas desde fault_history...")
    df = pd.read_sql_query("""
        SELECT DISTINCT inverter, faulthistoryrecord00, faulthistoryrecord00_time
        FROM fault_history
        WHERE faulthistoryrecord00 IS NOT NULL
          AND faulthistoryrecord00 NOT IN ('', '[null]', '[0,0,0,0]')
          AND faulthistoryrecord00_time IS NOT NULL;
    """, sqlite_conn)

    if df.empty:
        return

    with pg_conn.cursor() as cur:
        cur.execute("SELECT inverter_id, sk_inversor FROM dim_inversor;")
        inv_map = dict(cur.fetchall())

        ts = pd.to_datetime(df["faulthistoryrecord00_time"], unit="s", utc=True)
        upsert_fechas(cur, ts)

        cargados = 0
        for idx, row in df.iterrows():
            try:
                arr = json.loads(row["faulthistoryrecord00"])
                cod = int(arr[0]) if isinstance(arr, list) and arr and arr[0] is not None else 0
            except Exception:
                cod = 0
            if cod == 0:
                continue

            cur.execute("""
                INSERT INTO dim_tipo_evento (codigo_evento, categoria, descripcion, severidad)
                VALUES (%s, 'Alarma BMS / Inversor', %s, CASE WHEN %s >= 40 THEN 'Alta' ELSE 'Media' END)
                ON CONFLICT (codigo_evento) DO UPDATE SET codigo_evento = EXCLUDED.codigo_evento
                RETURNING sk_tipo_evento;
            """, (cod, f"Código de evento Modbus #{cod}", cod))
            sk_ev = cur.fetchone()[0]

            dt_utc = ts.iloc[idx].to_pydatetime()
            sk_fecha = int(dt_utc.strftime("%Y%m%d"))
            sk_inv = inv_map.get(int(row["inverter"]), 1)

            cur.execute("""
                INSERT INTO fact_eventos_operativos (ts_evento_utc, sk_inversor, sk_fecha, sk_tipo_evento, trama_cruda)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT ON CONSTRAINT uq_evento_ts_inv_cod DO NOTHING;
            """, (dt_utc, sk_inv, sk_fecha, sk_ev, str(row["faulthistoryrecord00"])))
            cargados += 1

        cur.execute("""
            INSERT INTO audit_calidad_etl (tabla_origen, registros_leidos, registros_cargados, observaciones)
            VALUES ('fault_history', %s, %s, 'Deduplicación de arreglos JSON fault_history y exclusión de [null]');
        """, (len(df), cargados))
        pg_conn.commit()
    print(f"[ETL] Fallas deduplicadas cargadas: {cargados}")

def main():
    if not SQLITE_PATH.exists():
        raise FileNotFoundError(f"No se encontró la capa Bronze en {SQLITE_PATH}")
    sqlite_conn = sqlite3.connect(f"file:{SQLITE_PATH.as_posix()}?mode=ro", uri=True)
    with psycopg.connect(PG_DSN) as pg_conn:
        cargar_analog_measurements(sqlite_conn, pg_conn)
        cargar_fallas(sqlite_conn, pg_conn)
    sqlite_conn.close()
    print("[ETL] Proceso finalizado exitosamente.")

if __name__ == "__main__":
    main()