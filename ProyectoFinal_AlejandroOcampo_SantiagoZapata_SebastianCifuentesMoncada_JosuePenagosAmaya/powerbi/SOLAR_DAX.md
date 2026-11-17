// 1. Estado de Carga Promedio (%)
SoC Promedio (%) = AVERAGE(fact_telemetria_energia[soc_pct])

// 2. SoC Mínimo Registrado (%)
SoC Minimo (%) = MIN(fact_telemetria_energia[soc_pct])

// 3. Profundidad de Descarga Promedio (DoD %)
DoD Promedio (%) = 100 - [SoC Minimo (%)]

// 4. Porcentaje de Tiempo en Zona Crítica (SoC < 20%)
Tiempo Critico (%) = 
DIVIDE(
    CALCULATE(COUNTROWS(fact_telemetria_energia), fact_telemetria_energia[soc_pct] < 20),
    COUNTROWS(fact_telemetria_energia),
    0
) * 100

// 5. Energía Solar Generada Estimada (kWh) (grano de 60s = 1/60 hora)
Energia PV (kWh) = SUMX(fact_telemetria_energia, (fact_telemetria_energia[potencia_pv_w] / 1000) * (1/60))

// 6. Energía Consumida (kWh)
Energia Consumo (kWh) = SUMX(fact_telemetria_energia, (fact_telemetria_energia[potencia_consumo_w] / 1000) * (1/60))

// 7. Tasa de Autosuficiencia Energética (%)
Autosuficiencia (%) = 
VAR ImportadoRed = SUMX(fact_telemetria_energia, (fact_telemetria_energia[potencia_red_w] / 1000) * (1/60))
RETURN DIVIDE([Energia Consumo (kWh)] - ImportadoRed, [Energia Consumo (kWh)], 0) * 100

// 8. Total Eventos / Fallas BMS
Total Fallas = COUNTROWS(fact_eventos_operativos)

// 9. Simulación What-If (Requiere Parámetro Numérico 'Capacidad Banco kWh' de 5 a 50, paso 5)
Autonomia Respaldo (Horas) = 
VAR ConsumoMedioKW = AVERAGE(fact_telemetria_energia[potencia_consumo_w]) / 1000
VAR EnergiaDisponibleKWh = 'Capacidad Banco kWh'[Capacidad Banco kWh Valor] * ([SoC Promedio (%)] / 100)
RETURN DIVIDE(EnergiaDisponibleKWh, ConsumoMedioKW, 0)