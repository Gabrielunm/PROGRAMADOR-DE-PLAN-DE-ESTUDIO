import pandas as pd
import sqlite3
import re
import io
import json
import unicodedata

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
                            if estados_actuales.get(r) not in ['Aprobado', 'Regular'])
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
        """Procesa el contenido del archivo subido (BytesIO)."""
        df = None
        
        # Intento 1: Excel estándar en memoria
        try:
            df = pd.read_excel(io.BytesIO(file_content))
        except Exception:
            pass

        # Intento 2: Reparación nativa con Excel (Win32com) - Específico para SIU Guaraní corrupto
        if df is None:
            try:
                import win32com.client as win32  # type: ignore
                import tempfile
                import os
                import pythoncom  # type: ignore
                
                # Inicializar COM para soporte de multi-threading (necesario en Streamlit)
                pythoncom.CoInitialize()
                
                # Guardar el contenido en un archivo temporal .xls
                fd, temp_xls = tempfile.mkstemp(suffix='.xls')
                with os.fdopen(fd, 'wb') as f:
                    f.write(file_content)
                
                temp_xlsx = temp_xls + 'x'
                
                # Invocar Excel nativo para reparar y re-guardar
                excel = win32.Dispatch('Excel.Application')
                excel.Visible = False
                excel.DisplayAlerts = False
                try:
                    wb = excel.Workbooks.Open(temp_xls)
                    wb.SaveAs(temp_xlsx, FileFormat=51) # 51 = xlsx format
                    wb.Close()
                finally:
                    excel.Quit()
                
                # Leer el archivo ya reparado
                df = pd.read_excel(temp_xlsx)
                
                # Limpieza
                if os.path.exists(temp_xls): os.remove(temp_xls)
                if os.path.exists(temp_xlsx): os.remove(temp_xlsx)
            except Exception as e_com:
                print(f"Error en Win32com fallback: {e_com}")
        
        # Intento 3: HTML Encubierto
        if df is None:
            try:
                html_str = file_content.decode('utf-8', errors='ignore')
                dfs = pd.read_html(io.StringIO(html_str))
                if dfs: df = dfs[0]
            except Exception:
                pass

        estados_alumno = {}
        
        # 1. Búsqueda estructurada (Si hubo éxito con pandas)
        all_text = ""
        if df is not None:
            for _, row in df.iterrows():
                row_str = ' '.join(str(x) for x in row if pd.notna(x)).strip()
                # El SIU a veces exporta '(1011)' o simplemente el número como ID.
                self._parse_row_to_status(row_str, estados_alumno)
                all_text += " " + row_str
        
        # 2. Extracción Binaria Extrema de Respaldo
        if not estados_alumno:
            for enc in ['utf-16le', 'latin-1']:
                try:
                    raw_text = file_content.decode(enc, errors='ignore')
                    clean_text = "".join([c if (c.isalnum() or c in "()/- ,.;") else " " for c in raw_text])
                    all_text += " [SEP] " + re.sub(r'\s+', ' ', clean_text)
                except Exception:
                    continue
            
            matches = re.finditer(r'\((\d{4})\)|\b(\d{4})\b', all_text)
            for m in matches:
                codigo = m.group(1) if m.group(1) else m.group(2)
                contexto = all_text[max(0, m.start()-50):min(len(all_text), m.start()+200)]
                self._parse_row_to_status(codigo + " " + contexto, estados_alumno)

        return estados_alumno, None if estados_alumno else "No se pudo extraer ningún estado. El archivo parece no contener datos académicos válidos."

    def _parse_row_to_status(self, row_str, estados_dict):
        """Identifica código y estado en contexto."""
        # Buscar el primer código de 4 dígitos
        match_cod = re.search(r'\((\d{4})\)|\b(\d{4})\b', row_str)
        if not match_cod: return
        codigo = match_cod.group(1) if match_cod.group(1) else match_cod.group(2)
        
        # Limpieza de estados (sacar espacios para detectar coincidencias parciales)
        row_clean = row_str.upper()
        estado = None
        if any(s in row_clean for s in ['APROBADO', 'PROMOCION', 'EXAMEN', 'EQUIVALENCIA', 'APROBADA']):
            estado = 'Aprobado'
        elif any(s in row_clean for s in ['ABANDONO', 'ABANDONADA', 'APLAZADA POR ABANDONO']):
            estado = 'Aplazada por Abandono'
        elif any(s in row_clean for s in ['REGULAR', 'CURSADA']):
            estado = 'Regular'
        elif 'LIBRE' in row_clean:
            estado = 'Voy a darla libre'

        if estado:
            # Mapeo especial
            codigo_a_buscar = codigo
            if codigo in ['1161', '1261', '1361', '1461']: codigo_a_buscar = 'IDIOMA_NIVEL_1'
            elif codigo in ['1162', '1262', '1362', '1462']: codigo_a_buscar = 'IDIOMA_NIVEL_2'
            elif codigo in ['1163', '1263', '1363', '1463']: codigo_a_buscar = '1163/1263/1363/1463'

            m_row = self.materias_df[self.materias_df['codigo'] == codigo_a_buscar]
            if not m_row.empty:
                id_m = int(m_row.iloc[0]['id_materia'])
                if id_m not in estados_dict or (estado == 'Aprobado' and estados_dict[id_m] != 'Aprobado'):
                    estados_dict[id_m] = estado

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
        
        # Materias pendientes (no aprobadas ni regulares)
        materias_restantes = self.materias_df[~self.materias_df['id_materia'].isin([k for k, v in estados_actuales.items() if v in ['Aprobado', 'Regular']])].copy()
        
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
                if all(estados_actuales.get(r) in ['Aprobado', 'Regular'] for r in reqs):
                    habilitadas.append(m)

            seleccionadas = []
            seleccionadas_libres = []  # Materias "Voy a darla libre" (sin horarios)
            bloques_agendados_cuat = []
            
            for h in habilitadas:
                # Separar materias en estado "Voy a darla libre"
                id_m = h['id_materia']
                if estados_actuales.get(id_m) == "Voy a darla libre":
                    # Limitar cantidad de libres por cuatrimestre
                    if len(seleccionadas_libres) < max_libres:
                        seleccionadas_libres.append({
                            'id_materia': h['id_materia'],
                            'codigo': h['codigo'],
                            'nombre': h['nombre'],
                            'comision': '-',
                            'horarios': '(Materia de libre)',
                            'docente': '-',
                            'nota': '📚 Rendirás libre esta materia'
                        })
                        # Actualizar estado
                        estados_actuales[id_m] = 'Voy a darla libre'
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
                            nota_bloqueo = f"⚠️ Bloqueada por correlativas anteriores estancadas: {', '.join(nombres_reqs)}"
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
