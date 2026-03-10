import pandas as pd
import sqlite3
import re
import io
import json
import unicodedata
import os
import platform # Para detectar si es Windows o Linux

DB_NAME = 'plan_estudios.sqlite'

class AcademicEngine:
    def __init__(self, db_path=DB_NAME):
        self.db_path = db_path
        self._load_base_data()

    # ------------------------------------------------------------------
    # utilidades de texto / parsing
    # ------------------------------------------------------------------
    def _normalize_horario(self, horario_str: str) -> str:
        """Limpia y normaliza un string de horario para facilitar el parsing.

        - Convierte a mayúsculas.
        - Elimina tildes/diacríticos usando NFKD -> ASCII (ignora los caracteres no mapeables).
        - Reduce espacios repetidos a uno solo.
        """
        # aplicar normalización unicode
        txt = unicodedata.normalize('NFKD', horario_str or '')
        # eliminar caracteres que no se pueden representar en ascii (incluye �)
        txt = txt.encode('ascii', 'ignore').decode('ascii')
        # mayúsculas y limpieza de espacios
        txt = txt.upper()
        txt = re.sub(r"\s+", " ", txt)
        return txt

    # ------------------------------------------------------------------
    # FASE 1: SCORING DE COMISIONES (Greedy Mejorado)
    # ------------------------------------------------------------------
    def _extract_days_from_horario(self, horario_str: str) -> set:
        """Extrae los días únicos de un string de horario"""
        dias = set()
        dia_map = {'LUN': 'LUN', 'MAR': 'MAR', 'MIE': 'MIE', 'MIÉ': 'MIE',
                   'JUE': 'JUE', 'VIE': 'VIE', 'SAB': 'SAB', 'SÁB': 'SAB',
                   'MI': 'MIE', 'SB': 'SAB', 'SA': 'SAB'}
        for key in dia_map:
            if key in horario_str:
                dias.add(dia_map[key])
        return dias

    def _extract_hours_from_horario(self, horario_str: str) -> list:
        """Extrae horas de inicio de un string de horario"""
        horas = []
        matches = re.finditer(r'(\d{1,2})(?::\d{2})?\s*A\s*(\d{1,2})', horario_str)
        for m in matches:
            horas.append(int(m.group(1)))
        return horas

    def _score_comision(self, comision_horarios: str, dias_usados: set, 
                       bloques_agendados: list, max_dias: int) -> float:
        """
        Puntúa una comisión por su optimalidad.
        
        Score más alto = mejor comisión
        
        Factores considerados:
        1. Agregar días nuevos (penaliza)
        2. Distribución horaria (bonifica si distribuye)
        3. Densidad (bonifica clases consecutivas)
        4. Conflictos con horarios existentes (penaliza mucho)
        """
        score = 100.0  # Puntaje base
        
        # Normalizar
        horario_norm = self._normalize_horario(comision_horarios)
        dias_comision = self._extract_days_from_horario(horario_norm)
        horas_comision = self._extract_hours_from_horario(horario_norm)
        
        # Factor 1: Cantidad de días nuevos (penaliza agregar muchos)
        nuevos_dias = dias_comision - dias_usados
        if len(nuevos_dias) > 0:
            if len(dias_usados) + len(nuevos_dias) > max_dias:
                return -1000  # No cabe
            # Penalizar cada día nuevo: -15 puntos
            score -= len(nuevos_dias) * 15
        
        # Factor 2: Distribución horaria (preferir distribuida vs concentrada)
        if len(horas_comision) > 1:
            variance = pd.Series(horas_comision).std()
            # Mayor varianza = mejor distribución
            score += variance * 5
        else:
            # Clases en bloque único: pequeño bonus
            score += 5
        
        # Factor 3: Horario "razonable" (bonificar si no es hora pico)
        # Evitar: 8am, 3pm, 6pm (hora pico típica)
        picos = [8, 15, 18]
        for h in horas_comision:
            if h not in picos:
                score += 3
        
        # Factor 4: Verificar colisiones (penalizar fuerte)
        for (_, d_ag, ini_ag, fin_ag) in bloques_agendados:
            for d_com in dias_comision:
                if d_com == d_ag:
                    # Checar si hay overlap en horas
                    for h_com in horas_comision:
                        if h_com < fin_ag and (h_com + 3) > ini_ag:
                            return -1000  # Colisión dura
        
        return score

    def _score_materia(self, materia_id: int, estados_actuales: dict, 
                      bloques_agendados_cuat: list) -> float:
        """
        Puntúa una materia por su urgencia/optimalidad.
        
        Score más alto = más urgente cursar
        
        Factores:
        1. "Madurez": cuántas materias dependen de esta (peso de bloqueo)
        2. Cuántas correlativas necesita (menos = más madura)
        3. Cuántas comisiones disponibles tiene (menos = más urgente)
        """
        score = 100.0
        
        # Factor 1: Peso de bloqueo (cuántas materias dependen)
        # De la BD correlativas: correlativas_df[correlativas_df['id_materia_requisito'] == materia_id]
        depende_count = len(self.correlativas_df[
            self.correlativas_df['id_materia_requisito'] == materia_id
        ])
        score += depende_count * 20  # Muy importante si bloquea muchas
        
        # Factor 2: Cuántas correlativas necesita (madurez)
        reqs = self.reqs_por_materia.get(materia_id, [])
        reqs_sin_hacer = sum(1 for r in reqs 
                            if estados_actuales.get(r) not in ['Aprobado', 'Regular', 'Voy a darla libre'])
        score -= reqs_sin_hacer * 30  # Penaliza si tiene muchos requisitos sin hacer
        
        # Factor 3: Disponibilidad futura (si hay pocas comisiones, es urgente)
        # Contar comisiones en Q1 y Q2 próximos
        comisiones_futuro = len(self.oferta_df[
            self.oferta_df['id_materia'] == materia_id
        ])
        if comisiones_futuro < 2:
            score += 50  # Urgente si hay poca oferta
        
        return score

    def _load_base_data(self):
        """Carga materias, ciclos y correlativas desde la DB para procesar en memoria."""
        conn = sqlite3.connect(self.db_path)
        self.materias_df = pd.read_sql_query("SELECT m.*, cf.nombre as ciclo FROM materias m JOIN ciclos_formacion cf ON m.id_ciclo = cf.id_ciclo", conn)
        self.correlativas_df = pd.read_sql_query("SELECT * FROM correlatividades", conn)
        self.oferta_df = pd.read_sql_query("SELECT * FROM oferta_academica", conn)
        conn.close()
        
        # Mapeos rápidos
        self.reqs_por_materia = {}
        for _, row in self.correlativas_df.iterrows():
            dest = row['id_materia_destino']
            req = row['id_materia_requisito']
            if dest not in self.reqs_por_materia:
                self.reqs_por_materia[dest] = []
            self.reqs_por_materia[dest].append(req)

    def process_student_excel(self, file_content):
        """Procesa el contenido del archivo subido (BytesIO) usando una estrategia híbrida."""
        df_html = None
        estados_alumno = {}

        # 1. Intento 1: Excel estándar (Pandas nativo)
        try:
            dict_dfs = pd.read_excel(io.BytesIO(file_content), sheet_name=None)
            for sheet_name, df in dict_dfs.items():
                if df is not None:
                    for _, row in df.iterrows():
                        row_str = ' '.join(str(x) for x in row if pd.notna(x)).strip()
                        self._parse_row_to_status(row_str, estados_alumno)
        except Exception:
            pass

        # 2. Intento 2: Reparación nativa con Excel (SOLO EN WINDOWS)
        # Esto soluciona los archivos "corruptos" del SIU que Windows sí puede abrir.
        if not estados_alumno and platform.system() == 'Windows':
            try:
                import win32com.client as win32 # type: ignore
                import tempfile
                import pythoncom # type: ignore
                
                pythoncom.CoInitialize()
                fd, temp_xls = tempfile.mkstemp(suffix='.xls')
                with os.fdopen(fd, 'wb') as f:
                    f.write(file_content)
                temp_xlsx = temp_xls + 'x'
                
                excel = win32.Dispatch('Excel.Application')
                excel.Visible = False
                excel.DisplayAlerts = False
                try:
                    wb = excel.Workbooks.Open(temp_xls)
                    wb.SaveAs(temp_xlsx, FileFormat=51) 
                    wb.Close()
                    df_fixed = pd.read_excel(temp_xlsx)
                    for _, row in df_fixed.iterrows():
                        row_str = ' '.join(str(x) for x in row if pd.notna(x)).strip()
                        self._parse_row_to_status(row_str, estados_alumno)
                finally:
                    excel.Quit()
                
                if os.path.exists(temp_xls): os.remove(temp_xls)
                if os.path.exists(temp_xlsx): os.remove(temp_xlsx)
            except Exception:
                pass

        # 3. Intento 3: HTML Encubierto (SIU Guaraní común)
        # Probamos con varios motores (lxml es el más robusto)
        try:
            for enc in ['utf-8', 'latin-1', 'utf-16']:
                try:
                    html_str = file_content.decode(enc)
                    # Forzar lxml si está disponible, sino bs4
                    dfs = pd.read_html(io.StringIO(html_str), flavor=['lxml', 'html5lib', 'bs4'])
                    if dfs:
                        df_merged = pd.concat(dfs, ignore_index=True)
                        for _, row in df_merged.iterrows():
                            row_str = ' '.join(str(x) for x in row if pd.notna(x)).strip()
                            self._parse_row_to_status(row_str, estados_alumno)
                        break # Si tuvo éxito con un encoding, paramos
                except Exception:
                    continue
        except Exception:
            pass

        # 4. Intento 4: Escaneo Binario/Regex Agresivo (Salvavidas para Linux)
        # Si no recuperamos suficientes materias, usamos fuerza bruta binaria.
        if len(estados_alumno) < 15: # Umbral de lo esperado en este plan de estudios
            all_text_fallback = ""
            for enc in ['latin-1', 'utf-16le', 'utf-8']:
                try:
                    raw_text = file_content.decode(enc, errors='ignore')
                    # No colapsar espacios aún para visualizar la estructura original
                    clean_text = "".join([c if (c.isalnum() or c in "()/- ,.;") else " " for c in raw_text])
                    all_text_fallback += " [SEP] " + clean_text
                except Exception:
                    continue
            
            all_text_fallback_up = all_text_fallback.upper()
            
            # A. Buscar por CÓDIGOS (Contexto muy amplio)
            matches_cod = re.finditer(r'\((\d{4})\)|(?<!\d)(\d{4})(?:[/-]\d+)?(?!\d)', all_text_fallback)
            for m in matches_cod:
                codigo = m.group(1) if m.group(1) else m.group(2)
                # Ventana de 500 caracteres para atrapar el estado en archivos dispersos
                contexto = all_text_fallback[max(0, m.start()-50):min(len(all_text_fallback), m.start()+450)]
                self._parse_row_to_status(contexto, estados_alumno)

            # B. Buscar por NOMBRES (Eficaz contra corrupción del código)
            for _, row_m in self.materias_df.iterrows():
                nombre_m = row_m['nombre'].upper()
                if len(nombre_m) > 12: # Solo nombres distintivos
                    start_search = 0
                    while True:
                        idx = all_text_fallback_up.find(nombre_m, start_search)
                        if idx == -1: break
                        contexto = all_text_fallback[max(0, idx-20):min(len(all_text_fallback), idx+500)]
                        self._parse_row_to_status(contexto, estados_alumno, id_m_hint=int(row_m['id_materia']))
                        start_search = idx + 1
        return estados_alumno, None if estados_alumno else "No se pudo extraer ningún estado. El archivo parece no contener datos académicos válidos o el formato no es soportado."

    def _parse_row_to_status(self, row_str, estados_dict, id_m_hint=None):
        """Identifica código/nombre y estado con prioridad absoluta para 'Aprobado'."""
        id_m = id_m_hint
        
        if id_m is None:
            # Buscar el código en el string proporcionado
            match_cod = re.search(r'\((\d{4})\)|(?<!\d)(\d{4})(?!\d)', row_str)
            if not match_cod: return
            codigo = match_cod.group(1) if match_cod.group(1) else match_cod.group(2)
            
            # Mapeo especial para códigos genéricos de la UNM
            codigo_a_buscar = codigo
            if codigo in ['1161', '1261', '1361', '1461']: codigo_a_buscar = 'IDIOMA_NIVEL_1'
            elif codigo in ['1162', '1262', '1362', '1462']: codigo_a_buscar = 'IDIOMA_NIVEL_2'
            elif codigo in ['1163', '1263', '1363', '1463']: codigo_a_buscar = '1163/1263/1363/1463'

            m_row = self.materias_df[self.materias_df['codigo'] == codigo_a_buscar]
            if m_row.empty: return
            id_m = int(m_row.iloc[0]['id_materia'])
        
        row_clean = row_str.upper()
        
        # PRIORIDAD INTERNA DE LA FILA
        aprobado_keys = ['APROBADO', 'PROMOCION', 'PROMOCI N', 'PROMOC.', 'EXAMEN', 'EQUIVALENCIA', 'EQUIV.', 'APROBADA', 'APROB.']
        regular_keys = ['REGULAR', 'CURSADA', 'REGULARE', 'REGUL.']
        
        estado_detectado = None
        if any(re.search(rf'\b{k}', row_clean) for k in aprobado_keys):
            estado_detectado = 'Aprobado'
        elif any(re.search(rf'\b{k}', row_clean) for k in regular_keys):
            estado_detectado = 'Regular'
        elif 'ABANDONO' in row_clean or 'ABANDONADA' in row_clean:
            estado_detectado = 'Aplazada por Abandono'
        elif 'LIBRE' in row_clean:
            estado_detectado = 'Voy a darla libre'

        if estado_detectado:
            # PRIORIDAD GLOBAL
            if id_m not in estados_dict:
                estados_dict[id_m] = estado_detectado
            else:
                estado_actual = estados_dict[id_m]
                if estado_detectado == 'Aprobado' and estado_actual != 'Aprobado':
                    estados_dict[id_m] = 'Aprobado'
                elif estado_detectado == 'Regular' and estado_actual not in ['Aprobado', 'Regular']:
                    estados_dict[id_m] = 'Regular'


    def get_proyected_plan(self, estados_iniciales, disponibilidad, max_materias=3, strategy="Intensivo", max_dias=6, max_libres=1):
        """
        Algoritmo de Proyección con Estrategias:
        - Intensivo: Usa toda la disponibilidad y max_materias al máximo
        - Equilibrado: Usa max_materias sin restricciones adicionales
        - Conservador: Reduce materias (máx 1 menos) y aplica restricción de 1 materia/día
        
        Args:
            max_materias: Máximo de materias por cuatrimestre (slider del usuario)
            max_dias: Máximo de días con clases por semana (slider del usuario)
            strategy: Perfil de cursada (Intensivo/Equilibrado/Conservador)
        """
        # Determinar max_m_ajustada basado en estrategia
        # El slider siempre es respetado como límite superior
        disp_ajustada = disponibilidad.copy()
        max_m_ajustada = max_materias
        
        if strategy == "Conservador":
            # Conservador: reducir a máximo 1 menos que lo indicado, pero respetando el mínimo de 1
            max_m_ajustada = max(1, max_materias - 1)
            # Nota: La restricción Conservadora de "1 materia por día" se aplica dinámicamente en selección
                    
        elif strategy == "Equilibrado":
            # Equilibrado: usar max_materias tal como está
            # Sin restricciones adicionales
            max_m_ajustada = max_materias
            
        elif strategy == "Intensivo":
            # Intensivo: usar max_materias al máximo, sin restricciones
            max_m_ajustada = max_materias

        plan_proyectado = []
        estados_actuales = estados_iniciales.copy()
        
        # Materias pendientes (no aprobadas)
        # Nota: 'Regular' y 'Voy a darla libre' se consideran PENDIENTES de rendir final/examen
        materias_restantes = self.materias_df[~self.materias_df['id_materia'].isin([k for k, v in estados_actuales.items() if v == 'Aprobado'])].copy()
        
        # Calcular "Peso de Bloqueo"
        bloqueo_counts = self.correlativas_df['id_materia_requisito'].value_counts().to_dict()
        materias_restantes['peso'] = materias_restantes['id_materia'].map(lambda x: bloqueo_counts.get(x, 0))
        
        current_cuat = 1
        current_year = 2026
        stagnant_count = 0
        
        for i in range(40): # Ampliado para carreras que se extienden (Max 20 años)
            if materias_restantes.empty: break
            
            habilitadas = []
            aprobadas_count = sum(1 for estado in estados_actuales.values() if estado == 'Aprobado')
            
            for _, m in materias_restantes.sort_values(by=['peso', 'id_materia'], ascending=[False, True]).iterrows():
                id_m = m['id_materia']
                codigo_m = str(m['codigo']).strip()
                
                # Evitar duplicados en la proyección misma
                if any(h['id_materia'] == id_m for p in plan_proyectado for h in p['materias']):
                    continue
                
                # Regla especial (2): 21 materias aprobadas mínimas (Seminarios y Talleres)
                # Basado en la nota (2) de la oferta académica y solicitud del usuario
                nombre_m = str(m['nombre']).upper()
                es_seminario_taller = 'SEMINARIO' in nombre_m or 'TALLER' in nombre_m or codigo_m == '1464'
                
                if es_seminario_taller:
                    if aprobadas_count < 21:
                        continue
                
                # NUEVA REGLA: Si hay materias abandonadas, bloquear cursada en próximo cuatrimestre
                # (Reglamento: No se puede cursar el próximo cuatrimestre si se abandona una materia)
                hay_abandono = any(estado == 'Aplazada por Abandono' for estado in estados_actuales.values())
                if hay_abandono and i > 0:  # i=0 es el cuatrimestre actual
                    continue
                
                reqs = self.reqs_por_materia.get(id_m, [])
                if all(estados_actuales.get(r) in ['Aprobado', 'Regular', 'Voy a darla libre'] for r in reqs):
                    habilitadas.append(m)

            seleccionadas = []
            seleccionadas_libres = []  # Materias "Voy a darla libre" (sin horarios)
            bloques_agendados_cuat = []
            
            for h in habilitadas:
                # Separar materias en estado "Voy a darla libre" o "Regular" (pendientes de final)
                id_m = h['id_materia']
                if estados_actuales.get(id_m) in ["Voy a darla libre", "Regular"]:
                    # Limitar cantidad de libres por cuatrimestre
                    if len(seleccionadas_libres) < max_libres:
                        estado_label = estados_actuales.get(id_m)
                        nota_final = "📚 Rendirás final regular" if estado_label == "Regular" else "📚 Rendirás libre esta materia"
                        seleccionadas_libres.append({
                            'id_materia': h['id_materia'],
                            'codigo': h['codigo'],
                            'nombre': h['nombre'],
                            'comision': '-',
                            'horarios': f'({estado_label})',
                            'docente': '-',
                            'nota': nota_final
                        })
                        # Actualizar estado a Aprobado tras "rendirla" en la proyección
                        estados_actuales[id_m] = 'Aprobado'
                    continue
                
                # Resto de materias (que se agendarán)
                if len(seleccionadas) >= max_m_ajustada: break
                
                # Reiniciar comisión elegida para cada materia
                comision_elegida = None
                
                # Mapeo de códigos a códigos con oferta real (Idiomas y Seminarios)
                id_m_buscar = h['id_materia']
                if h['codigo'] in ['1161', '1261', '1361', '1461']:
                    m_gen = self.materias_df[self.materias_df['codigo'] == 'IDIOMA_NIVEL_1']
                    if not m_gen.empty: id_m_buscar = m_gen.iloc[0]['id_materia']
                elif h['codigo'] in ['1162', '1262', '1362', '1462']:
                    m_gen = self.materias_df[self.materias_df['codigo'] == 'IDIOMA_NIVEL_2']
                    if not m_gen.empty: id_m_buscar = m_gen.iloc[0]['id_materia']
                elif h['codigo'] in ['1163', '1263', '1363', '1463']:
                    m_gen = self.materias_df[self.materias_df['codigo'] == '1163/1263/1363/1463']
                    if not m_gen.empty: id_m_buscar = m_gen.iloc[0]['id_materia']
                
                of_cuat = self.oferta_df[(self.oferta_df['id_materia'] == id_m_buscar) & (self.oferta_df['cuatrimestre'] == current_cuat)]
                if of_cuat.empty: continue
                
                # FASE 1: Compilar opciones de comisión con scores
                opciones_comision = []
                
                for _, com in of_cuat.iterrows():
                    horario_str = self._normalize_horario(com.get('horarios', ''))
                    # Normalizar separadores usando regex para ser resistente a espacios variables
                    h_norm = re.sub(r'\s+(Y/O|Y|AND|-|/)\s+', ' | ', horario_str)
                    # Caso especial: "LUN Y JUE" sin tanto espacio
                    h_norm = re.sub(r'(\b[A-ZÉÁÍÓÚ]{3,})\s+Y\s+([A-ZÉÁÍÓÚ]{3,}\b)', r'\1 | \2', h_norm)
                    
                    bloques = [b.strip() for b in h_norm.split('|')]
                    
                    parsed_bloques = []
                    last_time = None
                    for b in reversed(bloques):
                        hora_match = re.search(r'(\d{1,2})(?::\d{2})?\s*A\s*(\d{1,2})(?::\d{2})?', b)
                        hora_simple = re.search(r'\b(\d{1,2})\b', b)
                        if hora_match:
                            last_time = (int(hora_match.group(1)), int(hora_match.group(2)))
                        elif hora_simple and not ("NIVEL" in b or "IDIOMA" in b):
                            last_time = (int(hora_simple.group(1)), int(hora_simple.group(1)) + 3)
                        
                        dia_map = {
                            'LUN': 'LUN',
                            'MAR': 'MAR',
                            'MIE': 'MIE',
                            'MIÉ': 'MIE',
                            'JUE': 'JUE',
                            'VIE': 'VIE',
                            'SAB': 'SAB',
                            'SÁB': 'SAB',
                        }
                        # variantes corruptas / truncadas que pueden aparecer tras
                        # la normalización (ej. "MI�" -> "MI", "S�B" -> "SB").
                        # Simplemente las apuntamos al valor correcto.
                        dia_map.update({'MI': 'MIE', 'SB': 'SAB', 'SA': 'SAB'})
                        dias_en_bloque = []
                        for key, val in dia_map.items():
                            if key in b:
                                dias_en_bloque.append(val)
                                
                        if last_time:
                            for d in set(dias_en_bloque):
                                parsed_bloques.append({'dia': d, 'inicio': last_time[0], 'fin': last_time[1]})
                                
                    parsed_bloques.reverse()
                    
                    match_ok = True
                    dias_evaluados = 0
                    bloques_temporales = []
                    
                    for pb in parsed_bloques:
                        dia_bloque = pb['dia']
                        hora_inicio = pb['inicio']
                        hora_fin = pb['fin']
                        dias_evaluados += 1
                        
                        if hora_inicio < 13: t_req = 'Mañana'
                        elif hora_inicio < 18: t_req = 'Tarde'
                        else: t_req = 'Noche'
                        
                        if t_req not in disp_ajustada.get(dia_bloque, []):
                            match_ok = False
                            break
                        
                        # Restricción Conservadora: Máximo 1 materia por día
                        if strategy == "Conservador":
                            if any(d_agendado == dia_bloque for (_, d_agendado, _, _) in bloques_agendados_cuat):
                                match_ok = False
                                break
                        
                        # Verificar que no se exceda el máximo de días permitidos
                        dias_agendados = set(d for (_, d, _, _) in bloques_agendados_cuat)
                        dias_en_esta_comision = set(d for pb_t in bloques_temporales for d in [pb_t[1]])
                        dias_totales_con_nuevo = dias_agendados | dias_en_esta_comision | {dia_bloque}
                        if len(dias_totales_con_nuevo) > max_dias:
                            match_ok = False
                            break
                            
                        # Detección de Colisiones (Superposición horaria)
                        for (diag_m_cod, d_agendado, ini_agendado, fin_agendado) in bloques_agendados_cuat:
                            if d_agendado == dia_bloque:
                                # Overlap: inicio1 < fin2 and fin1 > inicio2
                                if hora_inicio < fin_agendado and hora_fin > ini_agendado:
                                    match_ok = False
                                    break
                                    
                        if not match_ok:
                            break
                        
                        bloques_temporales.append((h['codigo'], dia_bloque, hora_inicio, hora_fin))
                    
                    if dias_evaluados == 0:
                        match_ok = True
                        
                    if match_ok:
                        # NUEVA LÓGICA: Calcular score en lugar de tomar la primera
                        dias_usados = set(d for (_, d, _, _) in bloques_agendados_cuat)
                        score = self._score_comision(
                            horario_str,
                            dias_usados,
                            bloques_agendados_cuat,
                            max_dias
                        )
                        opciones_comision.append({
                            'score': score,
                            'com': com.to_dict(),
                            'bloques': bloques_temporales
                        })
                
                # Seleccionar LA MEJOR comisión según score
                if opciones_comision:
                    opciones_comision.sort(key=lambda x: -x['score'])  # Descending
                    mejor_opcion = opciones_comision[0]
                    comision_elegida = mejor_opcion['com']
                    comision_elegida['nota'] = ""
                    bloques_agendados_cuat.extend(mejor_opcion['bloques'])
                
                # Evitar agregar materia si ya fue seleccionada en este cuatrimestre
                if comision_elegida:
                    ya_seleccionada = any(s['id_materia'] == h['id_materia'] for s in seleccionadas)
                    if not ya_seleccionada:
                        seleccionadas.append({
                            'id_materia': h['id_materia'],
                            'codigo': h['codigo'],
                            'nombre': h['nombre'],
                            'comision': comision_elegida['comision'],
                            'horarios': comision_elegida['horarios'],
                            'docente': comision_elegida['docente'],
                            'nota': comision_elegida['nota']
                        })

            if seleccionadas:
                plan_proyectado.append({'ciclo': f"Cuatrimestre {len(plan_proyectado)+1} (C{current_cuat} - {current_year})", 'materias': seleccionadas})
                for s in seleccionadas:
                    estados_actuales[s['id_materia']] = 'Aprobado'
                    # Quitar de restantes para acelerar
                    materias_restantes = materias_restantes[materias_restantes['id_materia'] != s['id_materia']]
                
                # Agregar materias libres al mismo cuatrimestre
                if seleccionadas_libres:
                    # Agregar las libres al final de la lista de materias del cuatrimestre
                    plan_proyectado[-1]['materias'].extend(seleccionadas_libres)
                    for lib in seleccionadas_libres:
                        estados_actuales[lib['id_materia']] = 'Aprobado'
                        materias_restantes = materias_restantes[materias_restantes['id_materia'] != lib['id_materia']]
                
                stagnant_count = 0
            elif seleccionadas_libres:
                # Si solo hay libres pero no hay materias normales, crear cuatrimestre solo con libres
                plan_proyectado.append({'ciclo': f"Cuatrimestre {len(plan_proyectado)+1} (C{current_cuat} - {current_year})", 'materias': seleccionadas_libres})
                for lib in seleccionadas_libres:
                    estados_actuales[lib['id_materia']] = 'Aprobado'
                    materias_restantes = materias_restantes[materias_restantes['id_materia'] != lib['id_materia']]
                stagnant_count = 0
            else:
                stagnant_count += 1
                if stagnant_count >= 2:
                    # Pasó un año entero sin matchear nada. Bloqueo de carrera.
                    blocked_mats = []
                    for _, m in materias_restantes.iterrows():
                        id_m_block = m['id_materia']
                        # Verificar por qué se bloqueó
                        reqs = self.reqs_por_materia.get(id_m_block, [])
                        faltan_reqs = [r for r in reqs if estados_actuales.get(r) not in ['Aprobado', 'Regular']]
                        
                        m_nombre_upper = str(m['nombre']).upper()
                        m_codigo_stripped = str(m['codigo']).strip()
                        es_sem_tall = 'SEMINARIO' in m_nombre_upper or 'TALLER' in m_nombre_upper or m_codigo_stripped == '1464'
                        
                        nota_bloqueo = ""
                        if es_sem_tall and aprobadas_count < 21:
                            nota_bloqueo = f"⚠️ Requiere 21 materias aprobadas (tienes {aprobadas_count})."
                        elif faltan_reqs:
                            nombres_reqs = self.materias_df[self.materias_df['id_materia'].isin(faltan_reqs)]['codigo'].tolist()
                            nota_bloqueo = f"⚠️ Bloqueada por correlativas anteriores estancadas (requieren final o cursada): {', '.join(nombres_reqs)}"
                        else:
                            # Buscar oferta disponible para esta materia
                            of_disp = self.oferta_df[self.oferta_df['id_materia'] == id_m_block]
                            if of_disp.empty:
                                nota_bloqueo = "⚠️ Sin oferta académica en la base de datos."
                            else:
                                horarios_disp = of_disp['horarios'].unique()
                                nota_bloqueo = f"💡 Destrábala habilitando tu día para: {' | '.join(horarios_disp)}"
                                
                        blocked_mats.append({
                            'id_materia': id_m_block,
                            'codigo': m['codigo'],
                            'nombre': m['nombre'],
                            'comision': '-',
                            'horarios': '-',
                            'docente': '-',
                            'nota': nota_bloqueo
                        })
                    plan_proyectado.append({'ciclo': "Materias Estancadas / Imposibles de Cursar", 'materias': blocked_mats})
                    break
            
            if current_cuat == 1:
                current_cuat = 2
            else:
                current_cuat = 1
                current_year += 1
        
        # Deduplicar materias dentro de cada cuatrimestre (por id_materia)
        # En caso de haber duplicados accidentales
        for cuat in plan_proyectado:
            if 'materias' in cuat and cuat['materias']:
                visto = set()
                materias_unicas = []
                for mat in cuat['materias']:
                    id_m = mat.get('id_materia')
                    if id_m not in visto:
                        visto.add(id_m)
                        materias_unicas.append(mat)
                cuat['materias'] = materias_unicas
            
        return plan_proyectado
