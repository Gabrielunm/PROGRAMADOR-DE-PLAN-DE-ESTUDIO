import os
import re

file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"

def diagnostic():
    with open(file_path, 'rb') as f:
        content = f.read()

    results = []
    for enc in ['latin-1', 'utf-16le']:
        print(f"\n--- DIAGNOSTIC: {enc} ---")
        try:
            text = content.decode(enc, errors='ignore')
            clean_text = "".join([c if (c.isalnum() or c in "()/- ,.;\n\r") else " " for c in text])
            
            targets = ["1022", "1024", "1025", "1026", "Constitucional", "Laboral"]
            for t in targets:
                idx = clean_text.upper().find(t.upper())
                if idx != -1:
                    print(f"Found {t} at {idx}")
                    ctx = clean_text[max(0, idx-100):min(len(clean_text), idx+1000)]
                    print(f"Neighborhood: {repr(ctx)}")
                    # Buscar estados en este neighborhood
                    states = ["APROBADO", "REGULAR", "PROMOCION", "EXAMEN"]
                    for s in states:
                        if s in ctx.upper():
                            print(f"  -> Match found: {s}")
                else:
                    print(f"{t} not found.")

        except Exception as e:
            print(f"Error: {e}")

diagnostic()
