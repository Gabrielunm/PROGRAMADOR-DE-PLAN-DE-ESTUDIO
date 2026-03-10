import os
import re
from engine import AcademicEngine

file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"

def test_nearest_status():
    engine = AcademicEngine()
    with open(file_path, 'rb') as f:
        content = f.read()

    packed = content.decode('latin-1', errors='ignore').replace('\x00', '')
    clean_packed = "".join([c if (c.isalnum() or c in "()/- ,.;\n\r") else " " for c in packed])
    text_up = clean_packed.upper()

    aprobado_keys = ['APROBADO', 'PROMOCION', 'PROMOCI N', 'PROMOC.', 'EQUIVALENCIA', 'EQUIV.', 'APROBADA', 'APROB.']
    regular_keys = ['REGULAR', 'CURSADA', 'REGULARE', 'REGUL.', 'VIGENTE', 'ACEPTADA']
    # Elimino 'EXAMEN' porque es genérico y roba estados

    # Encontramos todos los "targets" (materias y codigos)
    subjects_found = {}

    pattern_cod = r'\(?(\d{4})\)?'
    # Buscar codigos
    for m in re.finditer(pattern_cod, text_up):
        codigo = m.group(1)
        # Verify valid cod
        m_row = engine.materias_df[engine.materias_df['codigo'] == codigo]
        if not m_row.empty:
            id_m = int(m_row.iloc[0]['id_materia'])
            subjects_found[id_m] = m.start()

    # Buscar nombres
    for _, row_m in engine.materias_df.iterrows():
        nom = row_m['nombre'].upper()
        if len(nom) > 10:
            idx = text_up.find(nom)
            if idx != -1:
                id_m = int(row_m['id_materia'])
                if id_m not in subjects_found or idx < subjects_found[id_m]:
                    subjects_found[id_m] = idx

    print(f"Materias extraidas del binario: {len(subjects_found)}")

    # Encontramos todos los estados
    status_positions = []
    for k in aprobado_keys:
        for m in re.finditer(rf'\b{k}\b', text_up):
            status_positions.append((m.start(), 'Aprobado', k))
    for k in regular_keys:
        for m in re.finditer(rf'\b{k}\b', text_up):
            status_positions.append((m.start(), 'Regular', k))

    status_positions.sort()

    # Asignar a cada materia el estado más cercano que esté ADELANTE de la materia
    # (o un poquito atrás si es la misma celda)
    final_estados = {}
    for id_m, pos in subjects_found.items():
        nom = engine.materias_df[engine.materias_df['id_materia'] == id_m].iloc[0]['nombre']
        best_dist = 500  # Max distance (500 chars)
        best_status = None
        best_k = None
        for s_pos, s_val, s_k in status_positions:
            dist = s_pos - pos
            # If status is within -50 to +500 chars
            if -50 <= dist <= best_dist:
                best_dist = dist
                best_status = s_val
                best_k = s_k
        
        if best_status:
            final_estados[id_m] = best_status
            print(f"[{id_m}] {nom} -> {best_status} (via '{best_k}' at dist {best_dist})")
        else:
            print(f"[{id_m}] {nom} -> NO STATUS FOUND within 500 chars limit")

    print(f"\nTotal clasificados: {len(final_estados)}")

test_nearest_status()
