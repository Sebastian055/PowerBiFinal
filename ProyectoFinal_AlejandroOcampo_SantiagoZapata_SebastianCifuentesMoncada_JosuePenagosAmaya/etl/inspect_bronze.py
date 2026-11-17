import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("data/opencem-v1.0.0.sqlite").resolve()

if not DB_PATH.exists():
    raise FileNotFoundError(f"No se encontró el archivo en: {DB_PATH}")

print(f"Conectando a: {DB_PATH} ({DB_PATH.stat().st_size / (1024**2):.2f} MB)")

# Conexión en modo solo lectura (uri=True)
conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
cursor = conn.cursor()

# 1. Listar tablas
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [t[0] for t in cursor.fetchall()]
print("\n=== 1. TABLAS EN OPENCEM ===")
print(tables)

# 2. Inventario detallado por tabla
for table in tables:
    print(f"\n==================== TABLA: {table} ====================")
    cols = pd.read_sql_query(f"PRAGMA table_info({table});", conn)
    print(cols[['cid', 'name', 'type']].to_string(index=False))
    
    count = pd.read_sql_query(f"SELECT COUNT(*) as total FROM {table};", conn)['total'][0]
    print(f"\nTotal de filas: {count:,}")
    
    time_cols = [c for c in cols['name'] if any(k in c.lower() for k in ['time', 'date', 'ts', 'stamp'])]
    if time_cols:
        tc = time_cols[0]
        rango = pd.read_sql_query(f"SELECT MIN({tc}) AS inicio, MAX({tc}) AS fin FROM {table};", conn)
        print(f"Cobertura temporal ({tc}): {rango['inicio'][0]}  -->  {rango['fin'][0]}")

    print("\nPrimeras 3 filas de muestra:")
    sample = pd.read_sql_query(f"SELECT * FROM {table} LIMIT 3;", conn)
    print(sample.to_string(index=False))

conn.close()