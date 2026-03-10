import pdfplumber

file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\plan_estudios.pdf"
out_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\pdf_output.txt"

with pdfplumber.open(file_path) as pdf:
    with open(out_path, 'w', encoding='utf-8') as f:
        for i, page in enumerate(pdf.pages):
            f.write(f"\n--- Page {i+1} ---\n")
            text = page.extract_text()
            if text:
                f.write(text)
            else:
                f.write("[No text found]\n")
            if i >= 2: break

print("Wrote PDF text to pdf_output.txt")
