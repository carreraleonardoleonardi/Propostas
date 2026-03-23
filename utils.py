import pandas as pd

def limpar_texto(txt):
    if pd.isna(txt):
        return ""
    return str(txt).encode('latin-1', 'replace').decode('latin-1')
