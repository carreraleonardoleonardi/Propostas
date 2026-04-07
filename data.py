# =========================================================
# data.py
# Responsável por carregar e tratar os dados das bases CSV
# Centraliza aqui tudo que antes estava espalhado no app.py
# =========================================================

import pandas as pd
import streamlit as st
import re
from utils import formatar_valor_brl


# =========================================================
# BASES DE DADOS POR SEGMENTO
# Cada segmento aponta para uma planilha Google Sheets em CSV
# =========================================================
BASES = {
    "Sign & Drive": "https://docs.google.com/spreadsheets/d/1PfEemQ0vJ4TlS-q-x9hfU-IK1AqUVPun8It_Wi7pzgE/export?format=csv&gid=2034069788",
    "GAC Go and Drive": "https://docs.google.com/spreadsheets/d/1xvD_QyO9opePn2X-Z2fHZGySOPm9AgQ7EbUcwoddjPo/export?format=csv&gid=676006877",
    "Assine Car One": "https://docs.google.com/spreadsheets/d/1FgVXCyGyhqXyeXz3cYePDSZjRGgmJu9Jj6rAmasjeQQ/export?format=csv&gid=676006877",
    "Nissan Move": "https://docs.google.com/spreadsheets/d/1pmK--_5SGVKW-LRXUK7TIjptP5DNxfYQMHS-cXA_rzw/export?format=csv&gid=1044813671",
    "Assine Car Multbrand": "https://docs.google.com/spreadsheets/d/1l6exo6brmYVMm-16zhIt7MDiJp7YxGrGZd2-kYk4a7k/export?format=csv&gid=1489579420",
    "GM Fleet Rede": "https://docs.google.com/spreadsheets/d/1AZiK2C7FjZ_-lNSJ-3fICfWB7hzRnEU8a_WCGgmubak/export?format=csv&gid=1332991446",
    "GM Fleet PF": "https://docs.google.com/spreadsheets/d/153a41nRCYW65S1AtODo3u9aIJp2co20K2lAexpYHoGc/export?format=csv&gid=1332991446",
    "GM Fleet Elétricos": "https://docs.google.com/spreadsheets/d/1-Tnbo6s8QXew8gz8xAWwklusMgtB3KbfRU9DYuA90NI/export?format=csv&gid=1332991446"
}

# URL da planilha de relatório/dashboard
URL_RELATORIO = "https://docs.google.com/spreadsheets/d/1bxjKSfD2MpBpV4swaBCjkhi8ElHV_8M97zxI6jgtv0w/export?format=csv"


# =========================================================
# FUNÇÕES DE CARGA
# =========================================================

@st.cache_data(ttl=300)  # cache de 5 minutos — atualiza automaticamente
def carregar_base(url: str) -> pd.DataFrame:
    """
    Lê uma base CSV de um segmento pelo URL.
    Padroniza os nomes das colunas:
    - minúsculas, sem acento, sem espaços
    """
    df = pd.read_csv(url)

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("utf-8")
        .str.replace(" ", "", regex=False)
    )

    return df


@st.cache_data(ttl=300)  # cache de 5 minutos
def carregar_relatorio() -> pd.DataFrame:
    """
    Lê a base do dashboard.
    Faz limpeza de colunas duplicadas, padronização e conversão de tipos.
    """
    import datetime

    df = pd.read_csv(URL_RELATORIO)
    df = df.loc[:, ~df.columns.duplicated()]

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("utf-8")
        .str.replace(" ", "", regex=False)
    )

    colunas_esperadas = [
        "data", "proposta_id", "consultor", "cliente",
        "segmento", "modelo", "prazo", "km", "valor"
    ]
    df = df[[c for c in colunas_esperadas if c in df.columns]]

    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")

    if "valor" in df.columns:
        df["valor"] = (
            df["valor"].astype(str)
            .str.replace("R$", "", regex=False)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.strip()
        )
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")

    return df


# =========================================================
# FUNÇÕES DE CONSULTA
# =========================================================

def obter_veiculos(df: pd.DataFrame) -> list:
    """
    Retorna a lista de veículos disponíveis numa base.
    """
    if "nome" not in df.columns:
        return []
    return sorted(df["nome"].dropna().unique().tolist())


def obter_dados_veiculo(df: pd.DataFrame, nome: str) -> pd.Series | None:
    """
    Retorna a linha de dados de um veículo pelo nome.
    Retorna None se não encontrado.
    """
    filtrado = df[df["nome"] == nome]
    if filtrado.empty:
        return None
    return filtrado.iloc[0]


def calcular_valor(df: pd.DataFrame, dados: pd.Series, km: int, prazo: int) -> str:
    """
    Busca o valor de um plano conforme KM e prazo.
    Retorna o valor formatado ou "Sob consulta" se não disponível.

    Exemplo de coluna esperada: preco50024 (500 km, 24 meses)
    """
    col_preco = f"preco{km}{prazo}"

    if col_preco not in df.columns:
        return "Sob consulta"

    valor = dados.get(col_preco, None)

    if valor is None or pd.isna(valor):
        return "Sob consulta"

    valor_str = str(valor).strip()

    if not valor_str or valor_str.lower() == "nan":
        return "Sob consulta"

    if "nao disponivel" in valor_str.lower():
        return "Não disponível"

    return formatar_valor_brl(valor)


def extrair_planos_modelo(df: pd.DataFrame, modelo: str) -> tuple[dict, str]:
    """
    Lê a linha do modelo e identifica automaticamente
    todos os planos disponíveis com base nas colunas da base.

    Retorna:
    - planos: dict { prazo: [ { km, valor } ] }
    - imagem: URL da imagem do veículo
    """
    dados = obter_dados_veiculo(df, modelo)

    if dados is None:
        return {}, ""

    imagem = dados.get("imagem", "")
    planos = {}
    padrao = re.compile(r"^preco(\d+)(\d{2})$")

    for col in df.columns:
        match = padrao.match(str(col))
        if not match:
            continue

        km = int(match.group(1))
        prazo = int(match.group(2))
        valor = dados.get(col, None)

        if pd.isna(valor):
            continue

        valor_str = str(valor).strip()
        if not valor_str or valor_str.lower() == "nan":
            continue
        if "nao disponivel" in valor_str.lower():
            continue

        if prazo not in planos:
            planos[prazo] = []

        planos[prazo].append({
            "km": km,
            "valor": formatar_valor_brl(valor)
        })

    # Ordena prazos e kms
    planos_ordenados = {}
    for prazo in sorted(planos.keys()):
        planos_ordenados[prazo] = sorted(planos[prazo], key=lambda x: x["km"])

    return planos_ordenados, imagem
