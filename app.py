import streamlit as st
import pandas as pd
from engine import AcademicEngine
import io
import copy

st.set_page_config(page_title="UNM - Programador Académico", layout="wide", page_icon="🎓")

# Design & Styles - Usando elementos nativos para compatibilidad con temas (Claro/Oscuro)
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    /* No forzamos colores de fondo ni de texto para permitir que el modo oscuro funcione correctamente */
</style>
""", unsafe_allow_html=True)

# Initialize Engine
@st.cache_resource
def get_engine():
    return AcademicEngine()

engine = get_engine()

# Initialize session state for tracking estados_modificados and UI profiles
if 'estados_modificados' not in st.session_state:
    st.session_state.estados_modificados = {}

if 'perfil_selector' not in st.session_state:
    st.session_state.perfil_selector = "Equilibrado"
    st.session_state.slider_mat = 3
    st.session_state.slider_dia = 5
    st.session_state.slider_lib = 1

# Garantizar que slider_mat y dial_dia siempre existan (fallback)
if 'slider_mat' not in st.session_state: st.session_state.slider_mat = 3
if 'slider_dia' not in st.session_state: st.session_state.slider_dia = 5
if 'slider_lib' not in st.session_state: st.session_state.slider_lib = 1

def update_profile():
    p = st.session_state.perfil_selector
    if p == "Equilibrado":
        st.session_state.slider_mat, st.session_state.slider_dia, st.session_state.slider_lib = 3, 5, 1
    elif p == "Estándar":
        st.session_state.slider_mat, st.session_state.slider_dia, st.session_state.slider_lib = 3, 4, 1
    elif p == "Intensivo":
        st.session_state.slider_mat, st.session_state.slider_dia, st.session_state.slider_lib = 5, 6, 1

# --- PANEL PRINCIPAL ---
st.title("🎓 Programador de Plan de Estudios - Contador Público")
st.warning("""
**⚠️ Aviso de Fase Beta / Prototipo:**  
Esta aplicación es un concepto experimental en etapa de desarrollo. Su propósito es estrictamente de prueba y demostración. Las proyecciones, la evaluación de correlatividades y la disponibilidad de la oferta académica pueden contener imperfecciones, estar desactualizadas o presentar omisiones.  
*Por favor, verifica siempre de forma fehaciente tu situación académica mediante los canales oficiales y el SIU-Guaraní de la Universidad Nacional de Moreno.*

**🔒 Privacidad de Datos:** Esta aplicación no recopila, almacena ni comparte tu información personal ni tu plan de estudios. Todos los cálculos se realizan de forma temporal durante tu sesión.
""", icon="🚧")

# Sidebar - Información del Desarrollador
with st.sidebar:
    st.markdown("---")
    st.markdown("### 👨‍💻 Desarrollador")
    st.markdown(
        """
        <div style="display: flex; flex-direction: column; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <img src="https://upload.wikimedia.org/wikipedia/commons/e/e7/Instagram_logo_2016.svg" width="18" height="18">
                <a href="https://www.instagram.com/gabriel96hq" target="_blank" style="text-decoration: none; color: #E1306C; font-weight: bold;">
                    @gabriel96hq
                </a>
            </div>
        </div>
        <p style="margin-top: 15px; margin-bottom: 0px; font-weight: bold; font-size: 1.1em;">Gabriel Quiroga</p>
        <p style="margin-top: 0px; color: #666; font-style: italic;">Desarrollador de Software y Analista de Datos</p>
        """,
        unsafe_allow_html=True
    )
    st.markdown("---")

# Cargar archivo en la parte superior
st.subheader("1️⃣ Carga tu archivo de plan de estudios")

st.info("""
**📌 Instrucciones:**
1. Ingresa al SIU Guaraní de la UNM.
2. Ve a **Reportes > Plan de Estudios**.
3. Haz clic en el botón **Descargar** (Arriba a la derecha).
4. Selecciona la opción **PDF** (icono rojo).
5. Sube ese archivo aquí abajo.
""")

with st.expander("🖼️ Ver captura de referencia"):
    st.image("assets/instruction_excel.png", caption="Busca el botón de descarga en el menú Plan de Estudios")

uploaded_file = st.file_uploader("Sube tu Plan de Estudios (PDF)", type=["pdf"])

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
            
            st.sidebar.metric("Avance", f"{porcentaje:.1f}%")
            st.sidebar.metric("Aprobadas", f"{aprobadas}/{total_materias}")
            st.sidebar.metric("Finales Pendientes (Regulares)", regulares)
            st.markdown("---")
        
        # Crear tabs
        tab_config, tab_audit, tab_ruta = st.tabs(["⚙️ Configuración", "📋 Situación Actual", "🚀 Hoja de Ruta Sugerida"])
        
        # ========== TAB: CONFIGURACIÓN ==========
        with tab_config:
            st.header("Configuración de Proyección")
            
            st.subheader("📅 Disponibilidad Horaria")
            st.info("Marca los turnos en los que podrías cursar cada día.")
            
            dias = ["LUN", "MAR", "MIE", "JUE", "VIE", "SAB"]
            turnos = ["Mañana", "Tarde", "Noche"]
            
            disponibilidad = {}
            cols_dias = st.columns(3)
            for idx, dia in enumerate(dias):
                with cols_dias[idx % 3]:
                    st.markdown(f"**📅 {dia}**")
                    selected_turnos = []
                    for t in turnos:
                        is_default = (t in ["Mañana", "Tarde"]) if dia == "SAB" else (t == "Noche")
                        if st.checkbox(t, value=is_default, key=f"{dia}_{t}"):
                            selected_turnos.append(t)
                    disponibilidad[dia] = selected_turnos
                    st.markdown("---")
            
            st.divider()
            st.subheader("📊 Límites de Proyección")
            
            st.markdown("**1. Elige un perfil rápido:**")
            st.radio("Perfil de Cursada", 
                     ["Equilibrado", "Estándar", "Intensivo", "Personalizado"], 
                     key="perfil_selector", 
                     on_change=update_profile, 
                     horizontal=True,
                     index=0, # Equilibrado por defecto
                     label_visibility="collapsed")
            
            st.markdown("<br>**2. Ajuste Fino (Opcional):**", unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            
            with col1:
                max_materias = st.slider("Máximo de materias por cuatrimestre", 1, 5, value=st.session_state.slider_mat, help="El perfil respetará este límite como máximo", key="slider_mat")
            
            with col2:
                max_dias = st.slider("Máximo de días con clases por semana", 1, 6, value=st.session_state.slider_dia, help="No se agendan clases en más días que lo indicado", key="slider_dia")
            
            with col3:
                max_libres = st.slider("Máximo de Finales a rendir (Libres/Pendientes) por cuatrimestre", 1, 3, value=st.session_state.slider_lib, help="Exámenes finales que rendirás en los llamados (materias libres o regulares previas). No te exigen asistir a clases ni ocupan días disponibles.", key="slider_lib")
            
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
            # Obtenemos TODOS los ciclos definidos en la base de datos
            ciclo_nombres = {1: "Ciclo Común", 2: "Tecnicatura / Grado Profesional", 3: "Idiomas", 4: "Optativas"}
            
            for ciclo_id in sorted(ciclo_nombres.keys()):
                label = ciclo_nombres[ciclo_id]
                st.subheader(f"📌 {label}")
                
                # Mostramos TODAS las materias de este ciclo que están en la base de datos
                mats_ciclo = engine.materias_df[engine.materias_df['id_id_ciclo'] == ciclo_id] if 'id_id_ciclo' in engine.materias_df.columns else engine.materias_df[engine.materias_df['id_ciclo'] == ciclo_id]
                
                for _, m in mats_ciclo.iterrows():
                    id_m = m['id_materia']
                    
                    # El estado original es lo que vino del PDF o 'No cursada' por defecto
                    estado_original = estados_alumno.get(id_m, "No cursada")
                    
                    # El estado actual es lo que el usuario haya movido en el selectbox (si existe en st.session_state)
                    estado_actual = st.session_state.estados_modificados.get(id_m, estado_original)
                    
                    with st.container():
                        col_cod, col_mat, col_est = st.columns([0.8, 3, 2.5])
                        col_cod.write(f"**{m['codigo']}**")
                        col_mat.write(m['nombre'])
                        
                        # Definición de colores para estados
                        color_map = {
                            "Aprobado": "#28a745",
                            "Regular": "#fd7e14",
                            "Voy a darla libre": "#17a2b8",
                            "No cursada": "#6c757d",
                            "Aplazada por Abandono": "#dc3545"
                        }
                        color = color_map.get(estado_actual, "#6c757d")
                        
                        # Mostrar el selectbox junto con una "píldora" de color
                        col_est.markdown(f'<div style="background-color: {color}; color: white; padding: 2px 10px; border-radius: 12px; font-size: 0.75em; font-weight: bold; width: fit-content; margin-bottom: 4px;">{estado_actual.upper()}</div>', unsafe_allow_html=True)
                        
                        opciones_estado = ["Aprobado", "Regular", "Voy a darla libre", "No cursada", "Aplazada por Abandono"]
                        
                        estado_nuevo = col_est.selectbox(
                            "Estado",
                            options=opciones_estado,
                            index=opciones_estado.index(estado_actual) if estado_actual in opciones_estado else opciones_estado.index("No cursada"),
                            key=f"estado_{id_m}",
                            label_visibility="collapsed"
                        )
                        
                        if estado_nuevo != estado_original:
                            st.session_state.estados_modificados[id_m] = estado_nuevo
                            estado_actual = estado_nuevo
                        else:
                            if id_m in st.session_state.estados_modificados:
                                del st.session_state.estados_modificados[id_m]
                            estado_actual = estado_original
                        
                        estados_alumno[id_m] = estado_actual
                st.divider()
        
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
