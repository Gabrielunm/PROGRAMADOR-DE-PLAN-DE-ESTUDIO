import os
import pandas as pd
import io
from bs4 import BeautifulSoup

file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"

def dump_tables_all_enc():
    with open(file_path, 'rb') as f:
        content = f.read()

    with open("raw_tables_dump.txt", "w", encoding='utf-8') as f_out:
        for enc in ['latin-1', 'utf-8', 'utf-16', 'utf-16le']:
            try:
                raw_text = content.decode(enc, errors='ignore')
                if '<table' in raw_text.lower():
                    f_out.write(f"\n======================\n")
                    f_out.write(f"Encoding: {enc}\n")
                    f_out.write(f"======================\n")
                    soup = BeautifulSoup(raw_text, "lxml")
                    dfs = pd.read_html(io.StringIO(str(soup)), flavor=['lxml', 'html5lib', 'bs4'])
                    f_out.write(f"Found {len(dfs)} tables\n\n")
                    for i, df in enumerate(dfs):
                        f_out.write(f"--- Table {i} ---\n")
                        f_out.write(df.to_string())
                        f_out.write("\n\n")
            except Exception as e:
                f_out.write(f"Encoding {enc} failed: {e}\n")

dump_tables_all_enc()
