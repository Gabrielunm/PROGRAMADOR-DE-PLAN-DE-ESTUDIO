import xlrd
import pandas as pd
from engine import AcademicEngine

file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"

def evaluate_xlrd():
    engine = AcademicEngine()
    print("--- Evaluating xlrd approach ---")
    try:
        wb = xlrd.open_workbook(file_path, ignore_workbook_corruption=True)
        sheet = wb.sheet_by_index(0)
        
        # Parse into string rows like the engine expects
        estados_alumno = {}
        for rowx in range(sheet.nrows):
            row = sheet.row_values(rowx)
            # Some cells might be float (like 1022.0), convert safely
            row_clean = []
            for cell in row:
                if isinstance(cell, float) and cell.is_integer():
                    row_clean.append(str(int(cell)))
                else:
                    row_clean.append(str(cell))
            
            row_str = " | ".join(row_clean).strip()
            # Feed it to our row parser
            engine._parse_row_to_status(row_str, estados_alumno)
            
        print(f"\nMaterias extraidas con xlrd: {len(estados_alumno)}")
        for id_m, estado in sorted(estados_alumno.items()):
            nom = engine.materias_df[engine.materias_df['id_materia'] == id_m].iloc[0]['nombre']
            print(f"[{id_m}] {nom} -> {estado}")
            
    except Exception as e:
        print(f"Error: {e}")

evaluate_xlrd()
