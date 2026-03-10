import pandas as pd
import io
import os
import sys

file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"

if not os.path.exists(file_path):
    print("File not found.")
    sys.exit(1)

with open(file_path, 'rb') as f:
    content = f.read()

print(f"File Size: {len(content)} bytes")

# Intentar leer como HTML directamente
try:
    print("\n--- Intentando leer como HTML (pd.read_html) ---")
    # Usamos io.BytesIO o io.StringIO dependiendo de cómo lo trate el motor
    # Pero primero probamos con el archivo directamente como sugiere el usuario
    tablas = pd.read_html(file_path, flavor="lxml")
    print(f"Se encontraron {len(tablas)} tablas.")
    total_filas = 0
    for i, df in enumerate(tablas):
        print(f"Tabla {i}: {len(df)} filas, {len(df.columns)} columnas")
        total_filas += len(df)
        # Mostrar una muestra si parece tener datos
        if len(df) > 0:
            print(df.head(2))
    
    print(f"\nTotal filas en todas las tablas: {total_filas}")

except Exception as e:
    print(f"Error al leer como HTML: {e}")

# Si falla o da pocas tablas, probar con otros flavors
try:
    print("\n--- Intentando con flavor='bs4' ---")
    tablas = pd.read_html(file_path, flavor="bs4")
    print(f"Se encontraron {len(tablas)} tablas con bs4.")
except Exception as e:
    print(f"Error con bs4: {e}")
