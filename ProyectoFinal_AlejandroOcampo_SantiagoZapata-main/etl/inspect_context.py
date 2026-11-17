import sqlite3, pandas as pd
from pathlib import Path

DB_PATH = Path("data/opencem-v1.0.0.sqlite").resolve()
conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)

print("=== CONTEXT ===")
print(pd.read_sql_query("SELECT * FROM context LIMIT 5;", conn).to_string(index=False))

print("\n=== INVERSORES DISTINTOS Y RANGO FECHAS ===")
print(pd.read_sql_query("""
    SELECT inverter, COUNT(*) AS filas,
           datetime(MIN(read_ts), 'unixepoch') AS inicio_utc,
           datetime(MAX(read_ts), 'unixepoch') AS fin_utc,
           SUM(CASE WHEN battsoc IS NULL THEN 1 ELSE 0 END) AS soc_nulos
    FROM analog_measurements
    GROUP BY inverter;
""", conn).to_string(index=False))

print("\n=== FALLAS NO VACIAS (MUESTRA) ===")
print(pd.read_sql_query("""
    SELECT read_ts, inverter, faulthistoryrecord00, faulthistoryrecord00_time
    FROM fault_history
    WHERE faulthistoryrecord00 IS NOT NULL AND faulthistoryrecord00 != '' AND faulthistoryrecord00 != '[0,0,0,0]'
    LIMIT 5;
""", conn).to_string(index=False))
conn.close()