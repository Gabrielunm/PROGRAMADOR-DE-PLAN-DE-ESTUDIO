from bs4 import BeautifulSoup
import pandas as pd
import io
import os

file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"

def test_soup_salvage(path):
    if not os.path.exists(path):
        print("File not found.")
        return

    # Intentar leer con diferentes encodings e ignorando errores
    for enc in ['latin-1', 'utf-8', 'utf-16le']:
        print(f"\n--- Testing BeautifulSoup with {enc} ---")
        try:
            with open(path, "rb") as f:
                content = f.read()
            
            # Decodificar ignorando caracteres basura (común en archivos binarios que tienen HTML dentro)
            text = content.decode(enc, errors="ignore")
            
            # 2. Parseamos con BeautifulSoup para que arregle el HTML roto
            soup = BeautifulSoup(text, "lxml") 

            # 3. Intentar extraer tablas
            tablas = pd.read_html(io.StringIO(str(soup)), flavor="lxml")
            
            if tablas:
                print(f"¡Éxito! Se encontraron {len(tablas)} tablas.")
                total_materias = 0
                for i, df in enumerate(tablas):
                    # Buscar columnas que parezcan de materias (Código, Materia, Estado)
                    row_str = df.to_string().upper()
                    if "APROBADO" in row_str or "REGULAR" in row_str or "PROMOCION" in row_str:
                        print(f"Tabla {i} parece tener datos académicos ({len(df)} filas).")
                        total_materias += len(df)
                print(f"Total potencial de materias: {total_materias}")
            else:
                print("No se encontraron tablas con este encoding.")

        except Exception as e:
            print(f"Error con {enc}: {e}")

test_soup_salvage(file_path)
