import os
import platform
import io

# Forzar simulación de Linux
platform.system = lambda: 'Linux'

from engine import AcademicEngine

def main():
    engine = AcademicEngine()
    file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"

    if not os.path.exists(file_path):
        print("Error: No se encontró plan_estudios.xls")
        return

    with open(file_path, 'rb') as f:
        content = f.read()

    print("=== TEST DE PARIDAD LINUX (OBJETIVO: 22 MATERIAS) ===")
    estados, error = engine.process_student_excel(content)

    if error:
        print(f"Error del motor: {error}")
        return

    # Mapeo de nombres
    id_to_name = {row['id_materia']: row['nombre'] for _, row in engine.materias_df.iterrows()}
    
    print(f"\nMATERIAS DETECTADAS ({len(estados)}/22):")
    print("-" * 50)
    
    # Ordenar por ID para consistencia
    for id_m in sorted(estados.keys()):
        name = id_to_name.get(id_m, "Nombre no encontrado")
        print(f"[{id_m}] {name} -> {estados[id_m]}")

    print("-" * 50)
    if len(estados) == 22:
        print("¡ÉXITO! Se alcanzaron las 22 materias.")
    else:
        print(f"Faltan {22 - len(estados)} materias para el objetivo.")

if __name__ == "__main__":
    main()
