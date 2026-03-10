import os
from engine import AcademicEngine

file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"

def generic_scan():
    engine = AcademicEngine()
    with open(file_path, 'rb') as f:
        content = f.read()

    # Get packed text
    packed = content.decode('latin-1', errors='ignore').replace('\x00', '')
    
    # Todos los códigos de Idioma y Optativos
    genericos = ["1161", "1261", "1361", "1461", "1162", "1262", "1362", "1462", "1463", "1464"]
    
    for c in genericos:
        if c in packed:
            idx = packed.find(c)
            ctx = packed[max(0, idx-150):min(len(packed), idx+800)]
            temp = {}
            engine._parse_row_to_status(ctx, temp, id_m_hint=None)
            status = list(temp.values())[0] if temp else "NONE"
            print(f"[{c}] -> {status}")

generic_scan()
