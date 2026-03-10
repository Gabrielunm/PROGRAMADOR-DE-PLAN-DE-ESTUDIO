import sqlite3
import pandas as pd
import io
import os

db_path = r'c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\plan_estudios.sqlite'
file_path = r'c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls'

# 1. Check DB
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    codes = ['1011', '1021', '1022', '1025', '1026']
    print("--- Database Check ---")
    conn.row_factory = sqlite3.Row
    for c in codes:
        row = conn.execute("SELECT id_materia, nombre, codigo FROM materias WHERE codigo=?", (c,)).fetchone()
        if row:
            print(f"Code {c}: ID={row['id_materia']}, Name={row['nombre']}")
        else:
            print(f"Code {c}: NOT FOUND IN DB")
    conn.close()
else:
    print("DB not found at", db_path)

# 2. Dump XLS rows for targets or first few
if os.path.exists(file_path):
    print("\n--- XLS Row Dump (First 100) ---")
    try:
        dict_dfs = pd.read_excel(file_path, sheet_name=None)
        for sheet_name, df in dict_dfs.items():
            print(f"\nSheet: {sheet_name}")
            for i, row in df.iterrows():
                row_str = ' | '.join(str(x) for x in row if pd.notna(x)).strip()
                # Check if it contains any of the target codes
                if any(c in row_str for c in ['1011', '1021', '1022', '1025', '1026']):
                    print(f"Row {i}: {row_str}")
                elif i < 5: # Show at least headers
                    print(f"Row {i}: {row_str}")
                if i > 250: # Limit output
                    break
    except Exception as e:
        print(f"Error reading XLS: {e}")
else:
    print("XLS not found at", file_path)
