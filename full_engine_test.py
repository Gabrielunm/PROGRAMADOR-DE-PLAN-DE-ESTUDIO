import sys
import os
import sqlite3

# Importar la clase desde el archivo local
from engine import AcademicEngine

# Mock de materias si no hay DB, pero mejor usar la DB real
engine = AcademicEngine()

file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"

if not os.path.exists(file_path):
    print("Test file not found.")
    sys.exit(1)

with open(file_path, 'rb') as f:
    content = f.read()

print("--- Testing engine.process_student_excel ---")
estados, error = engine.process_student_excel(content)

if error:
    print(f"Error: {error}")
else:
    # Buscar las materias específicas del usuario
    # Mapeo invertido para imprimir nombres
    id_to_name = {row['id_materia']: row['nombre'] for _, row in engine.materias_df.iterrows()}
    
    print("\nResultados detectados (TODOS):")
    for id_m, estado in estados.items():
        name = id_to_name.get(id_m, f"Unknown ID {id_m}")
        print(f"- [{id_m}] {name}: {estado}")
            
    # También imprimir un resumen de cuántas materias en total
    print(f"\nTotal materias detectadas: {len(estados)}")
    
    # Ver si hay materias detectadas varias veces o algo raro
    # El engine ya maneja la prioridad en _parse_row_to_status
