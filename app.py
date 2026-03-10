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

# Sidebar - Información del Desarrollador
with st.sidebar:
    st.markdown("---")
    st.markdown("### 👨‍💻 Desarrollador")
    st.markdown(
        """
        <div style="display: flex; flex-direction: column; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <img src="https://upload.wikimedia.org/wikipedia/commons/e/e7/Instagram_logo_2016.svg" width="18" height="18">
                <a href="https://www.instagram.com/gabriel96h1" target="_blank" style="text-decoration: none; color: #E1306C; font-weight: bold;">
                    @gabriel96h1
                </a>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.2em;">🌐</span>
                <a href="https://agentia.ar/" target="_blank" style="text-decoration: none; color: #007bff; font-weight: bold;">
                    agentia.ar
                </a>
            </div>
        </div>
        <p style="margin-top: 15px; margin-bottom: 0px; font-weight: bold; font-size: 1.1em;">Gabriel Quiroga</p>
        <p style="margin-top: 0px; color: #666; font-style: italic;">Agentia Developer</p>
        """,
        unsafe_allow_html=True
    )
    st.markdown("---")

# Cargar archivo en la parte superior
st.subheader("1️⃣ Carga tu archivo de plan de estudios")

with st.expander("ℹ️ ¿Cómo descargar mi archivo desde el SIU?", expanded=False):
    st.markdown("""
    Sigue estos pasos para obtener tu archivo correctamente:
    1. Ingresa a **[Gestión Online UNM (SIU-Guaraní)](https://gestiononline.unm.edu.ar/unm3w/)**.
    2. Inicia sesión con tu usuario y contraseña.
    3. Dirígete a la sección **Reportes** en el menú superior.
    4. Selecciona **Plan de Estudio**.
    5. Haz clic en el botón de **Descarga de PDF** (icono de PDF en la parte superior derecha de la tabla).
    """)
    st.image("assets/instruction_excel.png", caption="Referencia: Botones de descarga en el SIU-Guaraní")

uploaded_file = st.file_uploader("Subir plan_estudios.pdf", type=["pdf"])

if not uploaded_file:
    st.warning("⚠️ Por favor, sube tu archivo `plan_estudios.pdf` extraído del SIU para comenzar.")
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
        
        # --- ESTADÍSTICAS EN SIDEBAR ---
        total_materias = len(engine.materias_df)
        aprobadas = sum(1 for e in estados_alumno.values() if e == "Aprobado")
        regulares = sum(1 for e in estados_alumno.values() if e == "Regular")
        porcentaje = (aprobadas / total_materias) * 100 if total_materias > 0 else 0
        
        with st.sidebar:
            st.markdown("### 📊 Tu Progreso")
            st.sidebar.progress(porcentaje / 100)
            
            c1, c2 = st.sidebar.columns(2)
            c1.metric("Avance", f"{porcentaje:.1f}%")
            c2.metric("Aprobadas", f"{aprobadas}/{total_materias}")
            
            st.sidebar.metric("Finales Pendientes (Regulares)", regulares)
            st.markdown("---")
        
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
                # El usuario prefiere imprimir directamente desde el navegador, así que quitamos el botón custom
                
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
