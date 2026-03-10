import pandas as pd
import io
import os
import re

file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"

def force_html_extract(path):
    with open(path, 'rb') as f:
        content = f.read()
    
    # 1. Intentar decodificar como latin-1 (común en SIU)
    try:
        html_text = content.decode('latin-1', errors='ignore')
        print(f"--- Forcing HTML (latin-1) ---")
        if '<table' in html_text.lower():
            # Intentar leer todas las tablas
            dfs = pd.read_html(io.StringIO(html_text), flavor='lxml')
            print(f"Successfully extracted {len(dfs)} tables.")
            for i, df in enumerate(dfs):
                print(f"Table {i} rows: {len(df)}")
                # Buscar palabras clave en las tablas
                # ...
        else:
            print("No <table> tag found in forced HTML scan.")
    except Exception as e:
        print(f"Forced HTML failed: {e}")

force_html_extract(file_path)
