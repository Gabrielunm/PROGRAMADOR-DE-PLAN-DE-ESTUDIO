import xlrd
import pandas as pd

file_path = r"c:\Users\Gabriel\Desktop\PROGRAMADOR DE PLAN DE ESTUDIO\docs\plan_estudios.xls"

def test_xlrd_bypass():
    print("--- Testing xlrd with ignore_workbook_corruption=True ---")
    try:
        wb = xlrd.open_workbook(file_path, ignore_workbook_corruption=True)
        print(f"Success! Found {wb.nsheets} sheets.")
        
        for sheet_idx in range(wb.nsheets):
            sheet = wb.sheet_by_index(sheet_idx)
            print(f"Sheet {sheet_idx}: {sheet.name} - {sheet.nrows} rows")
            
            # Convert to DataFrame just to see
            data = []
            for rowx in range(sheet.nrows):
                row = sheet.row_values(rowx)
                data.append(row)
            
            df = pd.DataFrame(data)
            print(df.head())
            print("...")
            
    except Exception as e:
        print(f"xlrd failed: {e}")

test_xlrd_bypass()
