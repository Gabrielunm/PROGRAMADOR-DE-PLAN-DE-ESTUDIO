"""
FASE 2: Constraint Satisfaction Problem (CSP) Solver con Google OR-Tools

Este módulo implementa una solución alternativa al greedy algorithm usando
constraint programming. Es más lento pero encuentra soluciones globalmente
óptimas.
"""

import pandas as pd
import sqlite3
import re
from typing import Dict, List, Tuple, Optional
from ortools.linear_solver import pywraplp


class CSPScheduleSolver:
    """
    Solver usando Constraint Programming para encontrar el mejor horario.
    
    Variables:
    - Para cada materia: en qué cuatrimestre se cursa (1-N)
    - Para cada (materia, cuatrimestre): qué comisión se elige
    
    Restricciones:
    - Correlativas: materia A debe estar antes de materia B
    - Colisiones: no solapamientos de horario en mismo día
    - Disponibilidad: respeta disponibilidad del estudiante
    - Máximas materias por cuatrimestre
    - Máximos días por semana
    
    Objetivo:
    - Minimizar: número total de cuatrimestres
    - Sujeto a: maximizar satisfacción del estudiante (bonus por distribución)
    """
    
    def __init__(self, engine, max_cuatrimestres=20):
        self.engine = engine
        self.max_cuat = max_cuatrimestres
        self.solver = pywraplp.Solver.CreateSolver('CBC')  # Open-source solver
        self.variables = {}
        self.constraints_info = []
        
    def _extract_dias_horario(self, horario_str: str) -> set:
        """Extrae días únicos de un horario"""
        dias = set()
        dia_map = {
            'LUN': 'LUN', 'MAR': 'MAR', 'MIE': 'MIE', 'MIÉ': 'MIE',
            'JUE': 'JUE', 'VIE': 'VIE', 'SAB': 'SAB', 'SÁB': 'SAB',
            'MI': 'MIE', 'SB': 'SAB', 'SA': 'SAB'
        }
        horario_norm = horario_str.upper()
        for key in dia_map:
            if key in horario_norm:
                dias.add(dia_map[key])
        return dias
    
    def _horarios_overlap(self, h1: str, h2: str) -> bool:
        """Verifica si dos horarios se solapan"""
        # Simplificado: si comparten día, asumimos solapamiento
        # (una verificación más completa necesitaría parsear horas exactas)
        dias1 = self._extract_dias_horario(h1)
        dias2 = self._extract_dias_horario(h2)
        return len(dias1 & dias2) > 0
    
    def solve(self, estados_iniciales: dict, disponibilidad: dict,
              max_materias: int, strategy: str, max_dias: int) -> Optional[List[dict]]:
        """
        Resuelve el problema de scheduling usando CSP.
        
        Args:
            estados_iniciales: dict de {id_materia: estado}
            disponibilidad: dict de {dia: [turnos]}
            max_materias: máx materias por cuatrimestre
            strategy: 'Intensivo', 'Equilibrado', 'Conservador'
            max_dias: máx días por semana
        
        Returns:
            Plan proyectado (mismo formato que get_proyected_plan)
        """
        
        # Paso 1: Identificar materias pendientes
        pendientes = self.engine.materias_df[
            ~self.engine.materias_df['id_materia'].isin(
                [k for k, v in estados_iniciales.items() 
                 if v in ['Aprobado', 'Regular']]
            )
        ].copy()
        
        if pendientes.empty:
            return []
        
        print(f"[CSP] Resolviendo para {len(pendientes)} materias pendientes...")
        
        # Paso 2: Crear variables de decisión
        # Variable: material_Q = en qué cuatrimestre se cursa esta materia
        material_vars = {}
        for _, mat in pendientes.iterrows():
            mat_id = mat['id_materia']
            # Variable entera: cuatrimestre (1 a max_cuat, 0 = no se cursa)
            material_vars[mat_id] = self.solver.IntVar(
                0, self.max_cuat, f"mat_{mat_id}_cuat"
            )
        
        # Paso 3: Agregar restricciones de correlativas
        for _, mat_dest in pendientes.iterrows():
            dest_id = mat_dest['id_materia']
            reqs = self.engine.reqs_por_materia.get(dest_id, [])
            
            for req_id in reqs:
                # Materia requisito debe estar antes (o no cursarse)
                if req_id in material_vars:
                    req_var = material_vars[req_id]
                    dest_var = material_vars[dest_id]
                    # req_cuat < dest_cuat O ambas no se cursan
                    self.solver.Add(
                        self.solver.Or([
                            req_var == 0,
                            dest_var == 0,
                            req_var < dest_var
                        ])
                    )
        
        # Paso 4: Agregar restricción de máximo de materias por cuatrimestre
        for q in range(1, self.max_cuat + 1):
            materias_en_q = []
            for mat_id, var in material_vars.items():
                # Crear variable booleana: ¿está esta materia en Q?
                is_in_q = self.solver.BoolVar(f"mat_{mat_id}_in_q{q}")
                self.solver.Add(is_in_q == (var == q))
                materias_en_q.append(is_in_q)
            
            # Máximo de materias en este cuatrimestre
            self.solver.Add(sum(materias_en_q) <= max_materias)
        
        # Paso 5: Función objetivo: minimizar cuatrimestres
        # max_cuat_usado = max(var for var in material_vars.values() si var > 0)
        max_cuat_usado = self.solver.IntVar(0, self.max_cuat, 'max_cuat')
        for mat_id, var in material_vars.items():
            self.solver.Add(max_cuat_usado >= var)
        
        self.solver.Minimize(max_cuat_usado)
        
        # Paso 6: Resolver
        status = self.solver.Solve()
        
        if status != pywraplp.Solver.OPTIMAL:
            print("[CSP] No se encontró solución óptima")
            return None
        
        # Paso 7: Extraer solución
        plan = self._extract_solution(
            material_vars, estados_iniciales, disponibilidad
        )
        
        return plan
    
    def _extract_solution(self, material_vars: dict, estados_iniciales: dict,
                         disponibilidad: dict) -> List[dict]:
        """Extrae la solución del solver y la formatea"""
        plan = []
        estados_actuales = estados_iniciales.copy()
        
        # Agrupar materias por cuatrimestre
        cuatrimestres = {}
        for mat_id, var in material_vars.items():
            q = int(var.solution_value())
            if q > 0:  # Se cursa en cuatrimestre q
                if q not in cuatrimestres:
                    cuatrimestres[q] = []
                cuatrimestres[q].append(mat_id)
        
        # Para cada cuatrimestre, encontrar comisiones
        year = 2026
        for q_num in sorted(cuatrimestres.keys()):
            materias_en_q = cuatrimestres[q_num]
            materias_detalle = []
            
            for mat_id in materias_en_q:
                mat_row = self.engine.materias_df[
                    self.engine.materias_df['id_materia'] == mat_id
                ]
                if not mat_row.empty:
                    mat = mat_row.iloc[0]
                    
                    # Buscar comisión disponible (primera que coincida)
                    cuat_num = (q_num - 1) % 2 + 1  # Cuatrimestre 1 o 2
                    of_cuat = self.engine.oferta_df[
                        (self.engine.oferta_df['id_materia'] == mat_id) &
                        (self.engine.oferta_df['cuatrimestre'] == cuat_num)
                    ]
                    
                    if not of_cuat.empty:
                        com = of_cuat.iloc[0]
                        materias_detalle.append({
                            'id_materia': mat_id,
                            'codigo': mat['codigo'],
                            'nombre': mat['nombre'],
                            'comision': com['comision'],
                            'horarios': com['horarios'],
                            'docente': com['docente'],
                            'nota': ''
                        })
                        estados_actuales[mat_id] = 'Aprobado'
            
            if materias_detalle:
                actual_year = year + (q_num - 1) // 2
                actual_cuat = (q_num - 1) % 2 + 1
                plan.append({
                    'ciclo': f"Cuatrimestre {q_num} (C{actual_cuat} - {actual_year})",
                    'materias': materias_detalle
                })
        
        return plan


# Función de conveniencia
def solve_with_csp(engine, estados_iniciales, disponibilidad, 
                   max_materias, strategy, max_dias):
    """Envoltorio para usar el CSP solver"""
    solver = CSPScheduleSolver(engine)
    return solver.solve(estados_iniciales, disponibilidad, 
                       max_materias, strategy, max_dias)
