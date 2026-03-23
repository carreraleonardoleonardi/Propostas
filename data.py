import pandas as pd

def carregar_dados(caminho):
    return pd.read_excel(caminho, sheet_name='planos')

def obter_dados_veiculo(df, nome):
    return df[df['nome'] == nome].iloc[0]

def calcular_valor(dados, km, prazo, df):
    col_p = f"preço{km}{prazo}"
    return dados[col_p] if col_p in df.columns else "Sob consulta"
