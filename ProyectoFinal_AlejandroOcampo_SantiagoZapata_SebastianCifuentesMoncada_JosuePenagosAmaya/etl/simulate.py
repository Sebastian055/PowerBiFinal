import os
import time
import math
import random
from datetime import datetime, timezone
import psycopg

PG_DSN = (
    f"host={os.getenv('POSTGRES_HOST', 'postgres')} "
    f"port={os.getenv('POSTGRES_PORT', '5432')} "
    f"dbname={os.getenv('POSTGRES_DB', 'solar_db')} "
    f"user={os.getenv('POSTGRES_USER', 'solar_user')} "
    f"password={os.getenv('POSTGRES_PASSWORD', 'solar_pass')}"
)
INTERVAL_SEC = int(os.getenv("SIM_INTERVAL_SEC", "5"))

def main():
    print(f"[SIMULATOR] Iniciando inyección en tiempo real cada {INTERVAL_SEC}s...")
    soc_inv1 = 68.0
    soc_inv2 = 24.0  # Inicia cerca del umbral crítico (<20%) para probar alertas

    while True:
        try:
            now = datetime.now(timezone.utc)
            sk_fecha = int(now.strftime("%Y%m%d"))
            sk_franja = now.hour

            # Simulación física coherente: generación solar pico al mediodía, descarga en la noche
            factor_solar = max(0.0, math.sin((now.hour - 6) * math.pi / 12))
            pv_w = int(3800 * factor_solar + random.uniform(-120, 120)) if factor_solar > 0 else 0
            consumo_w = int(1100 + 600 * (1 if 18 <= now.hour <= 22 else 0.3) + random.uniform(-80, 150))

            # Variación realista de SoC
            delta_soc = ((pv_w - consumo_w) / 15000.0) * 0.25
            soc_inv1 = max(12.0, min(100.0, round(soc_inv1 + delta_soc + random.uniform(-0.15, 0.15), 2)))
            soc_inv2 = max(10.0, min(95.0, round(soc_inv2 + delta_soc - 0.12 + random.uniform(-0.2, 0.1), 2)))

            with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO dim_fecha (sk_fecha, fecha, anio, mes, nombre_mes, dia, dia_semana, es_fin_de_semana)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (sk_fecha) DO NOTHING;
                """, (sk_fecha, now.date(), now.year, now.month, now.strftime("%B"), now.day, now.isoweekday(), now.isoweekday() >= 6))

                for sk_inv, soc in [(1, soc_inv1), (2, soc_inv2)]:
                    volt = round(48.0 + (soc / 100.0) * 6.4, 2)
                    curr = round((pv_w - consumo_w) / volt, 2)
                    red_w = max(0, consumo_w - pv_w) if soc < 20 else 0
                    temp = round(34.0 + (abs(curr) * 0.35) + random.uniform(-0.5, 0.8), 2)

                    cur.execute("""
                        INSERT INTO fact_telemetria_energia (
                            ts_utc, sk_inversor, sk_fecha, sk_franja,
                            soc_pct, voltaje_bat_v, corriente_bat_a,
                            potencia_carga_bat_w, potencia_pv_w, potencia_consumo_w,
                            potencia_red_w, temp_inversor_c, es_dato_simulado
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                        ON CONFLICT ON CONSTRAINT uq_telemetria_ts_inv DO NOTHING;
                    """, (now, sk_inv, sk_fecha, sk_franja, soc, volt, curr, max(0, pv_w - consumo_w), pv_w, consumo_w, red_w, temp))
                conn.commit()
            print(f"[SIM] {now.strftime('%H:%M:%S')} | Inv1 SoC={soc_inv1}% | Inv2 SoC={soc_inv2}% | PV={pv_w}W")
        except Exception as e:
            print(f"[SIM ERROR] {e}")
        time.sleep(INTERVAL_SEC)

if __name__ == "__main__":
    main()