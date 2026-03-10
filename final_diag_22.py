import os
from engine import AcademicEngine

file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"

def final_diag():
    engine = AcademicEngine()
    with open(file_path, 'rb') as f:
        content = f.read()

    # Get packed text
    packed = content.decode('latin-1', errors='ignore').replace('\x00', '')
    
    targets = ["1021", "1022", "1023", "1024", "1025", "1026", "1027", "1431", "1432"]
    
    for t in targets:
        m_row = engine.materias_df[engine.materias_df['codigo'] == t]
        if m_row.empty: continue
        id_m = int(m_row.iloc[0]['id_materia'])
        
        idx = packed.upper().find(t.upper())
        if idx != -1:
            ctx = packed[max(0, idx-100):min(len(packed), idx+800)]
            temp_dict = {}
            engine._parse_row_to_status(ctx, temp_dict, id_m_hint=id_m)
            status = temp_dict.get(id_m, "NOT DETECTED")
            print(f"[{t}] {m_row.iloc[0]['nombre']} -> {status}")
            if status == "NOT DETECTED":
                print(f"  Neighborhood: {repr(ctx.upper())}")
        else:
            print(f"[{t}] NOT FOUND IN BINARY")

final_diag()
