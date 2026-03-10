import os
import re

file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"

def final_recovery():
    with open(file_path, 'rb') as f:
        content = f.read()

    # Pack Latin-1 (Best for BIFF)
    text = content.decode('latin-1', errors='ignore').replace('\x00', '')
    clean_text = "".join([c if (c.isalnum() or c in "()/- ,.;\n\r") else " " for c in text])
    clean_text_up = clean_text.upper()

    # Intentar encontrar TODO
    found = {}
    
    # Lista de códigos sospechosos
    for i in range(1011, 1030):
        c = str(i)
        if c in clean_text:
            idx = clean_text.find(c)
            # Contexto amplio
            ctx = clean_text[max(0, idx-50):min(len(clean_text), idx+600)].upper()
            status = "Unknown"
            if "APROBADO" in ctx or "PROMOCION" in ctx or "EXAMEN" in ctx: status = "Aprobado"
            elif "REGULAR" in ctx: status = "Regular"
            elif "LIBRE" in ctx: status = "Libre"
            
            found[c] = status
            print(f"[{c}] -> {status}")

    print(f"\nTotal materias encontradas : {len(found)}")

final_recovery()
