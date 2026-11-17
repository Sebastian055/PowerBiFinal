-- ============================================================================
-- CONSULTAS ANALÍTICAS (CTEs, FUNCIONES DE VENTANA Y KPIs DE BATERÍA)
-- ============================================================================

-- 1. KPI Resumen por Inversor: SoC promedio, mínimo, máximo y horas en zona crítica (<20%)
SELECT
    i.nombre_equipo,
    COUNT(*) AS total_lecturas,
    ROUND(AVG(f.soc_pct), 2) AS soc_promedio_pct,
    MIN(f.soc_pct) AS soc_minimo_pct,
    MAX(f.soc_pct) AS soc_maximo_pct,
    ROUND(100.0 * SUM(CASE WHEN f.soc_pct < 20 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_tiempo_critico
FROM fact_telemetria_energia f
JOIN dim_inversor i ON f.sk_inversor = i.sk_inversor
WHERE f.es_dato_simulado = FALSE
GROUP BY i.nombre_equipo;

-- 2. Perfil Horario de Carga/Descarga y Balance Energético (Generación PV vs Consumo vs Red)
SELECT
    fh.hora,
    fh.franja_operativa,
    ROUND(AVG(f.soc_pct), 1) AS soc_medio_pct,
    ROUND(AVG(f.potencia_pv_w) / 1000.0, 3) AS pv_medio_kw,
    ROUND(AVG(f.potencia_consumo_w) / 1000.0, 3) AS consumo_medio_kw,
    ROUND(AVG(f.potencia_red_w) / 1000.0, 3) AS red_medio_kw
FROM fact_telemetria_energia f
JOIN dim_franja_horaria fh ON f.sk_franja = fh.sk_franja
WHERE f.es_dato_simulado = FALSE
GROUP BY fh.hora, fh.franja_operativa
ORDER BY fh.hora;

-- 3. CTE + Window Function: Profundidad de Descarga Diaria (DoD) y Media Móvil de 7 días del SoC
WITH diario_bateria AS (
    SELECT
        d.fecha,
        i.nombre_equipo,
        MAX(f.soc_pct) - MIN(f.soc_pct) AS dod_diario_pct,
        ROUND(AVG(f.soc_pct), 2) AS soc_promedio_dia,
        ROUND(AVG(f.temp_inversor_c), 1) AS temp_media_c
    FROM fact_telemetria_energia f
    JOIN dim_fecha d ON f.sk_fecha = d.sk_fecha
    JOIN dim_inversor i ON f.sk_inversor = i.sk_inversor
    WHERE f.es_dato_simulado = FALSE
    GROUP BY d.fecha, i.nombre_equipo
)
SELECT
    fecha,
    nombre_equipo,
    dod_diario_pct,
    soc_promedio_dia,
    ROUND(AVG(soc_promedio_dia) OVER (
        PARTITION BY nombre_equipo ORDER BY fecha ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 2) AS media_movil_7d_soc,
    temp_media_c
FROM diario_bateria
ORDER BY fecha DESC, nombre_equipo
LIMIT 30;

-- 4. Ranking de Fallas y Eventos Operativos por Categoría
SELECT
    i.nombre_equipo,
    e.codigo_evento,
    e.categoria,
    e.severidad,
    COUNT(*) AS total_ocurrencias
FROM fact_eventos_operativos fe
JOIN dim_inversor i ON fe.sk_inversor = i.sk_inversor
JOIN dim_tipo_evento e ON fe.sk_tipo_evento = e.sk_tipo_evento
GROUP BY i.nombre_equipo, e.codigo_evento, e.categoria, e.severidad
ORDER BY total_ocurrencias DESC;

-- 5. Auditoría de Calidad de Datos (Bronze -> Gold)
SELECT * FROM audit_calidad_etl ORDER BY id_ejecucion DESC;