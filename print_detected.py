import os
import platform
platform.system = lambda: 'Linux'
from engine import AcademicEngine

engine = AcademicEngine()
file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"
out_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\detected_list.txt"

with open(file_path, 'rb') as f:
    content = f.read()

estados, error = engine.process_student_excel(content)

id_to_codigo = {row['id_materia']: row['codigo'] for _, row in engine.materias_df.iterrows()}
id_to_name = {row['id_materia']: row['nombre'] for _, row in engine.materias_df.iterrows()}

with open(out_path, 'w', encoding='utf-8') as f_out:
    f_out.write(f"Total Detectadas: {len(estados)}\n")
    for id_m, estado in sorted(estados.items()):
        cod = id_to_codigo.get(id_m, "NA")
        nom = id_to_name.get(id_m, "NA")
        f_out.write(f"[{cod}] {nom}: {estado}\n")

