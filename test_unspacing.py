import os
import re

file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"

def test_unspacing():
    with open(file_path, 'rb') as f:
        content = f.read()

    print("--- Testing Unspacing on Latin-1 ---")
    # Decode as latin-1 to keep null bytes as \x00
    text_latin = content.decode('latin-1', errors='ignore')
    
    # Pack: Remove nulls to join characters
    packed_text = text_latin.replace('\x00', '')
    
    # Check if target subjects are found in PACKED text
    targets = ["1022", "1024", "1025", "1026", "Constitucional", "Laboral"]
    for t in targets:
        if t.upper() in packed_text.upper():
            idx = packed_text.upper().find(t.upper())
            print(f"FOUND {t} in PACKED text at {idx}!")
            ctx = packed_text[max(0, idx-50):min(len(packed_text), idx+500)]
            print(f"Context: {repr(ctx)}")
        else:
            print(f"{t} NOT found in packed text.")

test_unspacing()
