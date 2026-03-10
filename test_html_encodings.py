import pandas as pd
import io
import os

file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"

def test_encodings(path):
    with open(path, 'rb') as f:
        content = f.read()

    for enc in ['latin-1', 'utf-16le', 'utf-8']:
        print(f"\n--- Testing Encoding: {enc} ---")
        try:
            # Intentar decodificar y pasar como StringIO
            decoded = content.decode(enc, errors='ignore')
            # Buscar <table> tag
            if '<table' in decoded.lower():
                print(f"Found <table> tag with {enc} decoding!")
                dfs = pd.read_html(io.StringIO(decoded), flavor='lxml')
                print(f"Extracted {len(dfs)} tables.")
                for i, df in enumerate(dfs):
                    print(f"Table {i} rows: {len(df)}")
            else:
                print(f"No <table> tag found with {enc}.")
        except Exception as e:
            print(f"Error with {enc}: {e}")

test_encodings(file_path)
