import os
from engine import AcademicEngine

engine = AcademicEngine()
file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\plan_estudios.pdf"

print(f"Testing PDF extraction with updated AcademicEngine...")
try:
    with open(file_path, 'rb') as f:
        content = f.read()
    
    estados, error = engine.process_student_excel(content, file_name="plan_estudios.pdf")
    
    if error:
        print(f"Error: {error}")
    else:
        print(f"\nTotal Detectadas: {len(estados)}")
        id_to_codigo = {row['id_materia']: row['codigo'] for _, row in engine.materias_df.iterrows()}
        id_to_name = {row['id_materia']: row['nombre'] for _, row in engine.materias_df.iterrows()}

        for id_m, estado in sorted(estados.items()):
            cod = id_to_codigo.get(id_m, "NA")
            nom = id_to_name.get(id_m, "NA")
            print(f"[{cod}] {nom}: {estado}")
            
except Exception as e:
    print(f"Failed to run test: {e}")
