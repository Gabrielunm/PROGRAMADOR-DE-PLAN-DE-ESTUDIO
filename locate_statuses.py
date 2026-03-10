import os
import re
from engine import AcademicEngine

file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"
out_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\status_dump.txt"

def locate_all_statuses():
    with open(file_path, 'rb') as f:
        content = f.read()

    packed = content.decode('latin-1', errors='ignore').replace('\x00', '')
    clean_packed = "".join([c if (c.isalnum() or c in "()/- ,.;\n\r") else " " for c in packed])
    clean_packed_up = clean_packed.upper()

    statuses = ['APROBADO', 'PROMOCION', 'PROMOCI N', 'PROMOC.', 'EXAMEN', 'EQUIVALENCIA', 'EQUIV.', 'APROBADA', 'APROB.', 'REGULAR', 'CURSADA', 'REGULARE', 'REGUL.', 'VIGENTE', 'ACEPTADA']
    
    matches = []
    for s in statuses:
        for m in re.finditer(rf'\b{s}\b', clean_packed_up):
            start = max(0, m.start() - 150)
            end = min(len(clean_packed_up), m.end() + 50)
            context = clean_packed[start:end]
            matches.append((m.start(), s, context))

    matches.sort()
    
    with open(out_path, 'w', encoding='utf-8') as f_out:
        f_out.write(f"Total status occurrences found: {len(matches)}\n\n")
        for pos, s, ctx in matches:
            str_match = f"--- MATCH: {s} ---\n"
            ctx_clean = ctx.replace('\n', ' ').replace('\r', '')
            str_match += ctx_clean.strip() + "\n\n"
            f_out.write(str_match)

locate_all_statuses()
