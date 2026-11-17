-- ============================================================================
-- CAPA GOLD / SILVER - ESQUEMA DIMENSIONAL (SOLAR / BATERÍAS - OPENCEM)
-- ============================================================================

CREATE TABLE IF NOT EXISTS dim_inversor (
    sk_inversor        SERIAL PRIMARY KEY,
    inverter_id        INTEGER UNIQUE NOT NULL,
    nombre_equipo      VARCHAR(60) NOT NULL,
    rol_microrred      VARCHAR(60) NOT NULL,
    capacidad_bat_kwh  NUMERIC(6,2) NOT NULL DEFAULT 15.00,
    voltaje_nominal_v  NUMERIC(6,2) NOT NULL DEFAULT 51.20
);

CREATE TABLE IF NOT EXISTS dim_fecha (
    sk_fecha           INTEGER PRIMARY KEY, -- Formato YYYYMMDD
    fecha              DATE UNIQUE NOT NULL,
    anio               SMALLINT NOT NULL,
    mes                SMALLINT NOT NULL,
    nombre_mes         VARCHAR(15) NOT NULL,
    dia                SMALLINT NOT NULL,
    dia_semana         SMALLINT NOT NULL,
    es_fin_de_semana   BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_franja_horaria (
    sk_franja          SMALLINT PRIMARY KEY, -- 0 a 23
    hora               SMALLINT UNIQUE NOT NULL,
    franja_operativa   VARCHAR(30) NOT NULL,
    tarifa_referencia  VARCHAR(20) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_tipo_evento (
    sk_tipo_evento     SERIAL PRIMARY KEY,
    codigo_evento      INTEGER UNIQUE NOT NULL,
    categoria          VARCHAR(40) NOT NULL,
    descripcion        VARCHAR(120) NOT NULL,
    severidad          VARCHAR(20) NOT NULL
);

-- Tabla de Hechos 1: Telemetría Energética (Grano: 1 medición limpia por inversor y segundo)
CREATE TABLE IF NOT EXISTS fact_telemetria_energia (
    id_telemetria        BIGSERIAL PRIMARY KEY,
    ts_utc               TIMESTAMPTZ NOT NULL,
    sk_inversor          INTEGER NOT NULL REFERENCES dim_inversor(sk_inversor),
    sk_fecha             INTEGER NOT NULL REFERENCES dim_fecha(sk_fecha),
    sk_franja            SMALLINT NOT NULL REFERENCES dim_franja_horaria(sk_franja),
    soc_pct              NUMERIC(5,2),
    voltaje_bat_v        NUMERIC(6,2),
    corriente_bat_a      NUMERIC(7,2),
    potencia_carga_bat_w INTEGER,
    potencia_pv_w        INTEGER,
    potencia_consumo_w   INTEGER,
    potencia_red_w       INTEGER,
    temp_inversor_c      NUMERIC(5,2),
    es_dato_simulado     BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_telemetria_ts_inv UNIQUE (ts_utc, sk_inversor, es_dato_simulado)
);

CREATE INDEX IF NOT EXISTS idx_fact_tel_fecha ON fact_telemetria_energia(sk_fecha);
CREATE INDEX IF NOT EXISTS idx_fact_tel_inv   ON fact_telemetria_energia(sk_inversor);
CREATE INDEX IF NOT EXISTS idx_fact_tel_ts    ON fact_telemetria_energia(ts_utc DESC);

-- Tabla de Hechos 2: Eventos y Fallas de Batería/Inversor
CREATE TABLE IF NOT EXISTS fact_eventos_operativos (
    id_evento          BIGSERIAL PRIMARY KEY,
    ts_evento_utc      TIMESTAMPTZ NOT NULL,
    sk_inversor        INTEGER NOT NULL REFERENCES dim_inversor(sk_inversor),
    sk_fecha           INTEGER NOT NULL REFERENCES dim_fecha(sk_fecha),
    sk_tipo_evento     INTEGER NOT NULL REFERENCES dim_tipo_evento(sk_tipo_evento),
    trama_cruda        TEXT,
    CONSTRAINT uq_evento_ts_inv_cod UNIQUE (ts_evento_utc, sk_inversor, sk_tipo_evento)
);

-- Tabla de Auditoría de Calidad de Datos (Capa Bronze -> Silver -> Gold)
CREATE TABLE IF NOT EXISTS audit_calidad_etl (
    id_ejecucion         SERIAL PRIMARY KEY,
    fecha_ejecucion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tabla_origen         VARCHAR(50) NOT NULL,
    registros_leidos     BIGINT NOT NULL,
    registros_cargados   BIGINT NOT NULL,
    nulos_soc_descartados BIGINT NOT NULL DEFAULT 0,
    fuera_rango_limpios  BIGINT NOT NULL DEFAULT 0,
    observaciones        TEXT
);

-- Semillas iniciales de dimensiones estáticas
INSERT INTO dim_inversor (inverter_id, nombre_equipo, rol_microrred, capacidad_bat_kwh, voltaje_nominal_v)
VALUES
    (1, 'Inversor Híbrido Principal #1', 'Maestro / Banco LiFePO4 Principal', 15.00, 51.20),
    (2, 'Inversor Híbrido Secundario #2', 'Esclavo / Respaldo Cargas Críticas', 15.00, 51.20)
ON CONFLICT (inverter_id) DO NOTHING;

INSERT INTO dim_franja_horaria (sk_franja, hora, franja_operativa, tarifa_referencia)
SELECT
    h,
    h,
    CASE
        WHEN h BETWEEN 0 AND 5   THEN 'Madrugada (Descarga Base)'
        WHEN h BETWEEN 6 AND 11  THEN 'Mañana (Carga Solar Inicial)'
        WHEN h BETWEEN 12 AND 17 THEN 'Tarde (Pico Solar / Flotación)'
        ELSE                          'Noche (Pico Demanda / Descarga)'
    END,
    CASE WHEN h BETWEEN 18 AND 22 THEN 'Hora Punta' ELSE 'Hora Valle' END
FROM generate_series(0, 23) AS h
ON CONFLICT (sk_franja) DO NOTHING;