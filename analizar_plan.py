import sqlite3
import pandas as pd

DB_NAME = 'plan_estudios.sqlite'

def analizar_estado_alumno(user_id=1):
    conn = sqlite3.connect(DB_NAME)
    
    # 1. Obtener todas las materias del plan
    materias_df = pd.read_sql_query("""
        SELECT m.id_materia, m.codigo, m.nombre, c.nombre as ciclo 
        FROM materias m
        JOIN ciclos_formacion c ON m.id_ciclo = c.id_ciclo
        ORDER BY c.id_ciclo, m.codigo
    """, conn)
    
    # 2. Obtener estado actual del alumno
    estado_df = pd.read_sql_query("""
        SELECT id_materia, estado 
        FROM estado_materias_usuario 
        WHERE id_usuario = ?
    """, conn, params=(user_id,))
    
    # Convertir el estado en un diccionario para rapido acceso
    estados_alumno = dict(zip(estado_df['id_materia'], estado_df['estado']))
    
    # 3. Obtener correlatividades
    correlativas_df = pd.read_sql_query("SELECT id_materia_destino, id_materia_requisito FROM correlatividades", conn)
    
    reqs_por_materia = {}
    for _, row in correlativas_df.iterrows():
        dest = row['id_materia_destino']
        req = row['id_materia_requisito']
        if dest not in reqs_por_materia:
            reqs_por_materia[dest] = []
        reqs_por_materia[dest].append(req)
        
    print("# 🎓 REPORTE ACADÉMICO INTEGRAL - CONTADOR PÚBLICO (UNM)")
    print(f"\n## 📊 Resumen de Progreso")
    
    total_materias = len(materias_df)
    aprobadas_count = sum(1 for e in estados_alumno.values() if e == 'Aprobado')
    regulares_count = sum(1 for e in estados_alumno.values() if e == 'Regular')
    cursado_total = aprobadas_count + regulares_count
    
    print(f"- **Total de Materias del Plan:** {total_materias}")
    print(f"- **Materias Aprobadas/Eximidas:** {aprobadas_count} ({round(aprobadas_count/total_materias*100, 1)}%)")
    print(f"- **Materias Regulares (Final Pendiente):** {regulares_count}")
    print(f"- **Avance Total (Aprobadas + Regulares):** {cursado_total} ({round(cursado_total/total_materias*100, 1)}%)")

    # Por Ciclos
    print("\n### 📉 Avance por Ciclo de Formación")
    for ciclo in materias_df['ciclo'].unique():
        mats_ciclo = materias_df[materias_df['ciclo'] == ciclo]
        total_ciclo = len(mats_ciclo)
        id_mats_ciclo = mats_ciclo['id_materia'].tolist()
        aprob_ciclo = sum(1 for mid in id_mats_ciclo if estados_alumno.get(mid) == 'Aprobado')
        perc = round(aprob_ciclo/total_ciclo*100, 1) if total_ciclo > 0 else 0
        print(f"- **{ciclo}:** {aprob_ciclo}/{total_ciclo} ({perc}%)")

    print("\n---")
    print("\n## 📑 Detalle Completo de Materias")
    
    for ciclo in materias_df['ciclo'].unique():
        print(f"\n### {ciclo}")
        mats_ciclo = materias_df[materias_df['ciclo'] == ciclo]
        
        for _, m in mats_ciclo.iterrows():
            id_m = m['id_materia']
            cod = m['codigo']
            nom = m['nombre']
            est = estados_alumno.get(id_m, "🔴 No iniciada")
            
            icono = "🟢" if est == "Aprobado" else "🟡" if est == "Regular" else "🔴"
            print(f"{icono} **[{cod}] {nom}** | Estado: *{est}*")
            
            # Si no está aprobada, mostrar qué falta
            if est != "Aprobado":
                requisitos = reqs_por_materia.get(id_m, [])
                if requisitos:
                    reqs_out = []
                    for r_id in requisitos:
                        r_est = estados_alumno.get(r_id, "No cursada")
                        # fetch nombre del req
                        row = conn.execute("SELECT nombre FROM materias WHERE id_materia=?", (r_id,)).fetchone()
                        r_nom = row[0] if row else f"ID {r_id}"
                        chk = "✅" if r_est in ["Aprobado", "Regular"] else "❌"
                        reqs_out.append(f"{chk} {r_nom} ({r_est})")
                    print(f"  > *Correlativas:* {', '.join(reqs_out)}")

    print("\n## 🚀 3. Hoja de Ruta: Próxima Inscripción (1er Cuatrimestre 2026)")
    
    # Buscamos qué materias puede cursar
    habilitadas = []
    for _, m in materias_df.iterrows():
        id_m = m['id_materia']
        # Si ya la aprobó o regularizó, no la sugerimos para cursar de cero
        if id_m in estados_alumno and estados_alumno[id_m] in ['Aprobado', 'Regular']:
            continue
            
        reqs = reqs_por_materia.get(id_m, [])
        if all(estados_alumno.get(rid) in ['Aprobado', 'Regular'] for rid in reqs):
            habilitadas.append(m)
            
    if habilitadas:
        print("Tienes las siguientes opciones disponibles:")
        for h in habilitadas:
            id_m = h['id_materia']
            print(f"\n### 📖 [{h['codigo']}] {h['nombre']}")
            
            # Consultar oferta para esta materia en 1er cuatrimestre
            oferta = pd.read_sql_query("""
                SELECT comision, docente, horarios, turno, modalidad 
                FROM oferta_academica 
                WHERE id_materia = ? AND cuatrimestre = 1
            """, conn, params=(id_m,))
            
            if oferta.empty:
                print("  ⚠️ *(No hay oferta registrada para el 1er cuatrimestre)*")
            else:
                for _, of in oferta.iterrows():
                    print(f"  - **Comisión {of['comision']}** | {of['turno']}")
                    print(f"    - 🕓 {of['horarios']} ({of['modalidad']})")
                    print(f"    - 👨‍🏫 Docente: {of['docente']}")
    else:
        print("No tienes nuevas materias habilitadas para cursar en este momento.")

    print("\n## ⚠️ 4. Requisitos Especiales y Alertas")
    
    # Regla: Ciclo Básico aprobado (ID 1 es Ciclo Común) o 21 materias
    ciclo_basico_df = materias_df[materias_df['ciclo'].str.contains('Común', case=False)]
    total_basico = len(ciclo_basico_df)
    aprob_basico = sum(1 for mid in ciclo_basico_df['id_materia'] if estados_alumno.get(mid) == 'Aprobado')
    
    ciclo_basico_completo = (aprob_basico == total_basico)
    
    if ciclo_basico_completo or aprobadas_count >= 21:
        print(f"- ✅ **Idiomas:** Cumples el requisito ({'Ciclo Básico completo' if ciclo_basico_completo else '21 materias'}). Puedes cursar Nivel 1 y 2.")
    else:
        faltan = 21 - aprobadas_count
        print(f"- ❌ **Idiomas:** Te faltan {faltan} materias aprobadas para llegar a las 21 (o terminar el Ciclo Básico) y habilitar Idiomas.")
    
    # Nota sobre optativas (mismo requisito de 21 materias)
    if ciclo_basico_completo or aprobadas_count >= 21:
        print(f"- ✅ **Seminarios Optativos:** Habilitado para cursar.")
    else:
        print(f"- ❌ **Seminarios Optativos:** Te faltan {21 - aprobadas_count} materias para habilitar seminarios.")

    conn.close()

if __name__ == '__main__':
    analizar_estado_alumno(1)
