import streamlit as st
import pandas as pd
from engine import AcademicEngine
import io
import copy

st.set_page_config(page_title="UNM - Programador Académico", layout="wide", page_icon="🎓")

# Design & Styles
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    .stMetric { background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    h1, h2, h3 { color: #1a1a1a; }
</style>
""", unsafe_allow_html=True)

# Initialize Engine
@st.cache_resource
def get_engine():
    return AcademicEngine()

engine = get_engine()

# Initialize session state for tracking estados_modificados
if 'estados_modificados' not in st.session_state:
    st.session_state.estados_modificados = {}

# --- PANEL PRINCIPAL ---
st.title("🎓 Programador de Plan de Estudios - Contador Público")

# Cargar archivo en la parte superior
st.subheader("1️⃣ Carga tu archivo de plan de estudios")

with st.expander("ℹ️ ¿Cómo descargar mi archivo desde el SIU?", expanded=False):
    st.markdown("""
    Sigue estos pasos para obtener tu archivo correctamente:
    1. Ingresa a **[Gestión Online UNM (SIU-Guaraní)](https://gestiononline.unm.edu.ar/unm3w/)**.
    2. Inicia sesión con tu usuario y contraseña.
    3. Dirígete a la sección **Reportes** en el menú superior.
    4. Selecciona **Plan de Estudio**.
    5. Haz clic en el botón de **Descarga de Excel** (icono de Excel en la parte superior derecha de la tabla).
    """)
    st.image("assets/instruction_excel.png", caption="Referencia: Botón de descarga en el SIU-Guaraní")

uploaded_file = st.file_uploader("Subir plan_estudios.xls", type=["xls", "xlsx"])

if not uploaded_file:
    st.warning("⚠️ Por favor, sube tu archivo `plan_estudios.xls` extraído del SIU para comenzar.")
    st.info("💡 Este MVP procesará tus correlativas y proyectará los próximos cuatrimestres basándose en la oferta académica real de la UNM.")
else:
    # Procesar archivo
    file_bytes = uploaded_file.getvalue()
    estados_alumno, error = engine.process_student_excel(file_bytes)
    
    if error:
        st.error(error)
    else:
        # Aplicar cambios almacenados en session_state
        for id_m, estado in st.session_state.estados_modificados.items():
            estados_alumno[id_m] = estado
        
        # Crear tabs
        tab_config, tab_audit, tab_ruta = st.tabs(["⚙️ Configuración", "📋 Auditoría Actual", "🚀 Hoja de Ruta Sugerida"])
        
        # ========== TAB: CONFIGURACIÓN ==========
        with tab_config:
            st.header("Configuración de Proyección")
            
            st.subheader("📅 Disponibilidad Horaria")
            st.info("Marca los turnos en los que podrías cursar cada día.")
            
            dias = ["LUN", "MAR", "MIE", "JUE", "VIE", "SAB"]
            turnos = ["Mañana", "Tarde", "Noche"]
            
            disponibilidad = {}
            for dia in dias:
                with st.expander(f"📅 {dia}"):
                    selected_turnos = []
                    for t in turnos:
                        is_default = (t in ["Mañana", "Tarde"]) if dia == "SAB" else (t == "Noche")
                        if st.checkbox(t, value=is_default, key=f"{dia}_{t}"):
                            selected_turnos.append(t)
                    disponibilidad[dia] = selected_turnos
            
            st.divider()
            st.subheader("📊 Límites de Proyección")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                max_materias = st.slider("Máximo de materias por cuatrimestre", 1, 5, 3,
                                        help="El perfil respetará este límite como máximo")
            
            with col2:
                max_dias = st.slider("Máximo de días con clases por semana", 1, 6, 5,
                                    help="No se agendan clases en más días que lo indicado")
            
            with col3:
                max_libres = st.slider("Máximo de materias 'Voy a darla libre' por cuatrimestre", 0, 3, 1,
                                      help="Materias que cursarás solo para rendir libre (no ocupan días ni límite de materias)")
            
            st.info("✅ Configuración lista. Diríjete a 'Auditoría Actual' o 'Hoja de Ruta Sugerida'")
        
        # ========== TAB: AUDITORÍA ACTUAL ==========
        with tab_audit:
            st.header("Situación Académica Detallada")
            
            # Instrucciones para cambiar estados
            st.info("📌 **Editar tu situación académica**:\n\n"
                   "Usa el dropdown **Estado** para indicar tu situación en cada materia:\n"
                   "- **Aprobado**: Ya cursaste y aprobaste\n"
                   "- **Regular**: Cursaste pero no aprobaste (examen pendiente)\n"
                   "- **Voy a darla libre**: No cursarás (solo para rendir libre)\n"
                   "- **No cursada**: Aún no cumples correlativas\n"
                   "- **Aplazada por Abandono**: Abandonaste (bloquea siguiente cuatrimestre)\n\n"
                   "📝 _Las materias en 'Voy a darla libre' se excluyen de los límites de materias y días_")
            
            # Mostrar tabla de materias agrupadas por ciclo
            for ciclo in engine.materias_df['ciclo'].unique():
                with st.expander(f"📌 {ciclo}", expanded=True):
                    m_ciclo = engine.materias_df[engine.materias_df['ciclo'] == ciclo]
                    
                    for _, m in m_ciclo.iterrows():
                        id_m = m['id_materia']
                        estado_original = estados_alumno.get(id_m, "No cursada")
                        
                        # Usar estado modificado si existe
                        estado_actual = st.session_state.estados_modificados.get(id_m, estado_original)
                        
                        # Crear columnas: código, materia, selector estado
                        col_cod, col_mat, col_est = st.columns([0.8, 3, 2.5])
                        
                        # ===== COLUMNA 1: CÓDIGO =====
                        col_cod.write(f"**{m['codigo']}**")
                        
                        # ===== COLUMNA 2: NOMBRE DE MATERIA =====
                        col_mat.write(m['nombre'])
                        
                        # ===== COLUMNA 3: SELECTOR DE ESTADO =====
                        opciones_estado = ["Aprobado", "Regular", "Voy a darla libre", "No cursada", "Aplazada por Abandono"]
                        
                        estado_nuevo = col_est.selectbox(
                            "Estado",
                            options=opciones_estado,
                            index=opciones_estado.index(estado_actual) if estado_actual in opciones_estado else opciones_estado.index("No cursada"),
                            key=f"estado_{id_m}",
                            label_visibility="collapsed"
                        )
                        
                        # Guardar cambio en session_state
                        if estado_nuevo != estado_original:
                            st.session_state.estados_modificados[id_m] = estado_nuevo
                            estado_actual = estado_nuevo
                        else:
                            # Si vuelve al original, limpiar del session_state
                            if id_m in st.session_state.estados_modificados:
                                del st.session_state.estados_modificados[id_m]
                            estado_actual = estado_original
                        
                        # Actualizar estados_alumno para que se use en la proyección
                        estados_alumno[id_m] = estado_actual
        
        # ========== TAB: HOJA DE RUTA ==========
        with tab_ruta:
            # Estrategia por defecto: Equilibrado
            strategy = "Equilibrado"
            
            st.header("Plan de Cursada: Proyección")
            with st.spinner("Calculando mejor ruta..."):
                proyeccion = engine.get_proyected_plan(copy.deepcopy(estados_alumno), disponibilidad, max_materias, strategy, max_dias, max_libres)
            
            if not proyeccion:
                st.success("🎉 ¡Felicidades! Según el análisis, ya has completado todas las materias o no hay oferta compatible disponible.")
            else:
                # Botón de impresión
                col_print, col_spacer = st.columns([1, 5])
                with col_print:
                    if st.button("🖨️ Imprimir Plan", use_container_width=True):
                        # Generar contenido imprimible
                        html_content = "<html><head><meta charset='utf-8'><style>"
                        html_content += "body { font-family: Arial, sans-serif; margin: 20px; }"
                        html_content += "h1 { color: #1a1a1a; text-align: center; }"
                        html_content += "h2 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 5px; margin-top: 20px; }"
                        html_content += "table { width: 100%; border-collapse: collapse; margin: 15px 0; }"
                        html_content += "th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }"
                        html_content += "th { background-color: #007bff; color: white; }"
                        html_content += ".code { font-weight: bold; }"
                        html_content += ".docente { font-style: italic; font-size: 0.9em; }"
                        html_content += ".horarios { color: #666; }"
                        html_content += ".libre { background-color: #fff3cd; }"
                        html_content += "</style></head><body>"
                        html_content += "<h1>Plan de Cursada - Proyección</h1>"
                        
                        for cuat in proyeccion:
                            html_content += f"<h2>{cuat['ciclo']}</h2>"
                            html_content += "<table><tr><th>Código</th><th>Materia</th><th>Docente</th><th>Horarios</th><th>Comisión</th></tr>"
                            
                            for m in cuat['materias']:
                                es_libre = "Materia de libre" in m['horarios']
                                row_class = ' class="libre"' if es_libre else ''
                                html_content += f"<tr{row_class}>"
                                html_content += f"<td class='code'>{m['codigo']}</td>"
                                html_content += f"<td>{m['nombre']}</td>"
                                html_content += f"<td class='docente'>{m['docente']}</td>"
                                html_content += f"<td class='horarios'>{m['horarios']}</td>"
                                html_content += f"<td>{m['comision']}</td>"
                                html_content += "</tr>"
                            
                            html_content += "</table>"
                        
                        html_content += "</body></html>"
                        
                        # Crear un iframe para imprimir
                        st.markdown(
                            f"""
                            <iframe srcdoc="{html_content.replace('"', '&quot;')}" style="width:100%; height:600px; border:none;"></iframe>
                            """,
                            unsafe_allow_html=True
                        )
                
                for cuat in proyeccion:
                    st.subheader(f"📅 {cuat['ciclo']}")
                    
                    for m in cuat['materias']:
                        with st.container():
                            c1, c2 = st.columns([3, 1])
                            c1.markdown(f"**[{m['codigo']}] {m['nombre']}**")
                            c1.caption(f"👨‍🏫 {m['docente']} | 🕓 {m['horarios']}")
                            
                            badge_color = "orange" if "⚠️" in m['nota'] else "green"
                            c2.markdown(f'<span style="background-color: {badge_color}; color: white; padding: 5px 10px; border-radius: 15px; font-size: 0.8em;">{m["comision"]}</span>', unsafe_allow_html=True)
                            if m['nota']:
                                st.warning(m['nota'])
                    st.divider()
