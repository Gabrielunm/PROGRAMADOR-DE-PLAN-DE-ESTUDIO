import sys
import os
import sqlite3
import re
import io

# Importar la clase, pero parchear platform para que parezca Linux
import platform
platform.system = lambda: 'Linux'

from engine import AcademicEngine

engine = AcademicEngine()
file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"

with open(file_path, 'rb') as f:
    content = f.read()

print("--- Simulating Linux Environment (Force Binary/HTML Fallback) ---")
estados, error = engine.process_student_excel(content)

if error:
    print(f"Error: {error}")
else:
    id_to_name = {row['id_materia']: row['nombre'] for _, row in engine.materias_df.iterrows()}
    print("\nResultados detectados en 'Linux':")
    for id_m, estado in sorted(estados.items()):
        name = id_to_name.get(id_m, f"Unknown ID {id_m}")
        print(f"- [{id_m}] {name}: {estado}")
            
    print(f"\nTotal materias detectadas: {len(estados)}")
