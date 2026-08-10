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
# =========================================================

BASES = {
    "Sign & Drive": "https://docs.google.com/spreadsheets/d/1PfEemQ0vJ4TlS-q-x9hfU-IK1AqUVPun8It_Wi7pzgE/export?format=csv&gid=2034069788",

    "Sign & Drive Blindados": "https://docs.google.com/spreadsheets/d/1YeG9PSVHPF2xELbqjsGFbFUbKN_AI0GvwY1U0cq9mKE/export?format=csv&gid=2034069788",

    "Sign & Drive Empresas": "https://docs.google.com/spreadsheets/d/1puuB21uOsC8-UXe4MpuGE_oSpgyj-tyoihT6u68InMk/export?format=csv",

    "Assine Car GWM": "https://docs.google.com/spreadsheets/d/1y9wBzxq6mb3OItBQ6IjrOpGW2t5QV8EADekDfLtkbRw/export?format=csv&gid=676006877",

    "Assine Car GWM - Blindado": "https://docs.google.com/spreadsheets/d/1zJB5EBhtB78RtJhqHSP6OQDX1_s0wrmMsz1C_tUKsMI/export?format=csv&gid=1332991446",

    "GAC Go and Drive": "https://docs.google.com/spreadsheets/d/1xvD_QyO9opePn2X-Z2fHZGySOPm9AgQ7EbUcwoddjPo/export?format=csv&gid=676006877",

    "Assine Car One": "https://docs.google.com/spreadsheets/d/1FgVXCyGyhqXyeXz3cYePDSZjRGgmJu9Jj6rAmasjeQQ/export?format=csv&gid=676006877",

    "Nissan Move": "https://docs.google.com/spreadsheets/d/1pmK--_5SGVKW-LRXUK7TIjptP5DNxfYQMHS-cXA_rzw/export?format=csv&gid=1044813671",

    "Renault OnDemand": "https://docs.google.com/spreadsheets/d/1DCdRVsXEhDoelR9emH7q2J1vFnvAu4EDc6Lm-wceWZM/export?format=csv&gid=1489579420",

    "Assine Car Multbrand": "https://docs.google.com/spreadsheets/d/1l6exo6brmYVMm-16zhIt7MDiJp7YxGrGZd2-kYk4a7k/export?format=csv&gid=1489579420",

    "GM Fleet Rede": "https://docs.google.com/spreadsheets/d/1AZiK2C7FjZ_-lNSJ-3fICfWB7hzRnEU8a_WCGgmubak/export?format=csv&gid=1332991446",

    "GM Fleet Estoque": "https://docs.google.com/spreadsheets/d/1yDTeD6pH-TSUEo_F21bkej_oxpKn2fTZp_B15FSFgpQ/export?format=csv&gid=1332991446#gid=1332991446",

    "GM Fleet PF": "https://docs.google.com/spreadsheets/d/153a41nRCYW65S1AtODo3u9aIJp2co20K2lAexpYHoGc/export?format=csv&gid=1332991446",

    "GM Fleet Elétricos": "https://docs.google.com/spreadsheets/d/1-Tnbo6s8QXew8gz8xAWwklusMgtB3KbfRU9DYuA90NI/export?format=csv&gid=1332991446",

    "Arval": "https://docs.google.com/spreadsheets/d/12fxyRpNCbUB73I5-rjCEs3d_tpg0gYw0Ihd87KiCWOg/export?format=csv&gid=691004799#gid=691004799"
}


# =========================================================
# URL DA PLANILHA DE RELATÓRIO / DASHBOARD
# =========================================================

URL_RELATORIO = (
    "https://docs.google.com/spreadsheets/d/"
    "1bxjKSfD2MpBpV4swaBCjkhi8ElHV_8M97zxI6jgtv0w/"
    "export?format=csv"
)


# =========================================================
# HELPER — verifica se um valor representa "disponível"
# =========================================================

def _is_disponivel(valor) -> bool:
    """
    Retorna True se o valor indica disponibilidade.

    Aceita:
    True (bool)
    'true'
    '1'
    'yes'
    'sim'
    'verdadeiro'

    Ausência da coluna também é tratada como disponível.
    """

    if valor is None or (
        isinstance(valor, float) and pd.isna(valor)
    ):
        return True

    if isinstance(valor, bool):
        return valor

    texto = str(valor).strip().lower()

    if texto in {"", "nan", "none"}:
        return True

    return texto in {
        "true",
        "1",
        "yes",
        "sim",
        "verdadeiro"
    }


# =========================================================
# HELPER — formata a data de validade
# =========================================================

def _formatar_valido_ate(valor) -> str:
    """
    Converte o valor da coluna validoAte para dd/mm/yyyy.

    Exemplos aceitos:
    2026-08-31
    31/08/2026
    2026-08-31 00:00:00

    Retorna string vazia quando não houver data.
    """

    if valor is None:
        return ""

    if pd.isna(valor):
        return ""

    texto = str(valor).strip()

    if not texto or texto.lower() in {
        "nan",
        "none",
        "nat"
    }:
        return ""

    # Tenta converter a data
    data = pd.to_datetime(
        valor,
        dayfirst=True,
        errors="coerce"
    )

    if pd.isna(data):
        # Caso não consiga converter,
        # mantém o valor original
        return texto

    return data.strftime("%d/%m/%Y")


# =========================================================
# FUNÇÕES DE CARGA
# =========================================================

@st.cache_data(ttl=300)
def carregar_base(url: str) -> pd.DataFrame:
    """
    Lê uma base CSV de um segmento pelo URL.

    Padroniza os nomes das colunas:
    - minúsculas
    - sem acento
    - sem espaços
    """

    df = pd.read_csv(url)

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.normalize("NFKD")
        .str.encode(
            "ascii",
            errors="ignore"
        )
        .str.decode("utf-8")
        .str.replace(
            " ",
            "",
            regex=False
        )
    )

    return df


# =========================================================
# CARREGAR RELATÓRIO
# =========================================================

@st.cache_data(ttl=300)
def carregar_relatorio() -> pd.DataFrame:
    """
    Lê a base do dashboard.

    Faz:
    - limpeza de colunas duplicadas
    - padronização
    - conversão de tipos
    """

    df = pd.read_csv(URL_RELATORIO)

    df = df.loc[
        :,
        ~df.columns.duplicated()
    ]

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.normalize("NFKD")
        .str.encode(
            "ascii",
            errors="ignore"
        )
        .str.decode("utf-8")
        .str.replace(
            " ",
            "",
            regex=False
        )
    )

    colunas_esperadas = [
        "data",
        "proposta_id",
        "consultor",
        "cliente",
        "segmento",
        "modelo",
        "prazo",
        "km",
        "valor"
    ]

    df = df[
        [
            c
            for c in colunas_esperadas
            if c in df.columns
        ]
    ]

    if "data" in df.columns:

        df["data"] = pd.to_datetime(
            df["data"],
            dayfirst=True,
            errors="coerce"
        )

    if "valor" in df.columns:

        df["valor"] = (
            df["valor"]
            .astype(str)
            .str.replace(
                "R$",
                "",
                regex=False
            )
            .str.replace(
                ".",
                "",
                regex=False
            )
            .str.replace(
                ",",
                ".",
                regex=False
            )
            .str.strip()
        )

        df["valor"] = pd.to_numeric(
            df["valor"],
            errors="coerce"
        )

    return df


# =========================================================
# FUNÇÕES DE CONSULTA
# =========================================================

def obter_veiculos(df: pd.DataFrame) -> list:
    """
    Retorna a lista de veículos disponíveis numa base.

    Se a coluna 'disponibilidade' existir,
    filtra apenas os veículos disponíveis.
    """

    if "nome" not in df.columns:
        return []

    if "disponibilidade" in df.columns:

        df = df[
            df["disponibilidade"].apply(
                _is_disponivel
            )
        ]

    return sorted(
        df["nome"]
        .dropna()
        .unique()
        .tolist()
    )


# =========================================================
# OBTER DADOS DO VEÍCULO
# =========================================================

def obter_dados_veiculo(
    df: pd.DataFrame,
    nome: str
) -> pd.Series | None:
    """
    Retorna a linha de dados de um veículo pelo nome.

    Retorna None se não encontrado.
    """

    filtrado = df[
        df["nome"] == nome
    ]

    if filtrado.empty:
        return None

    return filtrado.iloc[0]


# =========================================================
# CALCULAR VALOR
# =========================================================

def calcular_valor(
    df: pd.DataFrame,
    dados: pd.Series,
    km: int,
    prazo: int
) -> str:
    """
    Busca o valor de um plano conforme KM e prazo.

    Retorna:
    - valor formatado
    - Sob consulta
    - Não disponível
    """

    col_preco = f"preco{km}{prazo}"

    if col_preco not in df.columns:
        return "Sob consulta"

    valor = dados.get(
        col_preco,
        None
    )

    if valor is None or pd.isna(valor):
        return "Sob consulta"

    valor_str = str(valor).strip()

    if (
        not valor_str
        or valor_str.lower() == "nan"
    ):
        return "Sob consulta"

    if "nao disponivel" in valor_str.lower():
        return "Não disponível"

    return formatar_valor_brl(valor)


# =========================================================
# EXTRAIR PLANOS DO MODELO
# =========================================================

def extrair_planos_modelo(
    df: pd.DataFrame,
    modelo: str
) -> tuple[dict, str, str, str]:
    """
    Lê a linha do modelo e identifica automaticamente
    todos os planos disponíveis com base nas colunas
    da base.

    Retorna:

    planos:
        {
            prazo: [
                {
                    "km": km,
                    "valor": valor,
                    "validoAte": valido_ate
                }
            ]
        }

    imagem:
        URL da imagem do veículo

    nome_modelo:
        nome curto do modelo

    versao:
        versão completa
    """

    # =====================================================
    # LOCALIZA O VEÍCULO
    # =====================================================

    dados = obter_dados_veiculo(
        df,
        modelo
    )

    if dados is None:
        return {}, "", "", ""

    # =====================================================
    # VERIFICA DISPONIBILIDADE
    # =====================================================

    if "disponibilidade" in df.columns:

        if not _is_disponivel(
            dados.get(
                "disponibilidade",
                True
            )
        ):
            return {}, "", "", ""

    # =====================================================
    # DADOS BÁSICOS
    # =====================================================

    imagem = dados.get(
        "imagem",
        ""
    )

    nome_modelo = str(
        dados.get(
            "modelo",
            modelo
        )
    ).strip()

    versao = str(
        dados.get(
            "versao",
            ""
        )
    ).strip()

    # =====================================================
    # DATA DE VALIDADE
    #
    # IMPORTANTE:
    # Aqui pegamos o validoAte DA MESMA LINHA
    # do veículo selecionado.
    # =====================================================

    valido_ate = ""

    if "validoate" in df.columns:

        valido_ate = _formatar_valido_ate(
            dados.get(
                "validoate",
                ""
            )
        )

    # =====================================================
    # PLANOS
    # =====================================================

    planos = {}

    # Detecta colunas:
    #
    # preco100012
    # preco100024
    # preco150012
    #
    # KM + PRAZO

    padrao = re.compile(
        r"^preco(\d+)(\d{2})$"
    )

    for col in df.columns:

        match = padrao.match(
            str(col)
        )

        if not match:
            continue

        km = int(
            match.group(1)
        )

        prazo = int(
            match.group(2)
        )

        valor = dados.get(
            col,
            None
        )

        # =================================================
        # IGNORA VALORES VAZIOS
        # =================================================

        if pd.isna(valor):
            continue

        valor_str = str(
            valor
        ).strip()

        if (
            not valor_str
            or valor_str.lower() == "nan"
        ):
            continue

        # =================================================
        # IGNORA NÃO DISPONÍVEL
        # =================================================

        if "nao disponivel" in valor_str.lower():
            continue

        # =================================================
        # CRIA PRAZO
        # =================================================

        if prazo not in planos:

            planos[prazo] = []

        # =================================================
        # ADICIONA PLANO
        # =================================================

        planos[prazo].append(
            {
                "km": km,
                "valor": formatar_valor_brl(
                    valor
                ),
                "validoAte": valido_ate
            }
        )

    # =====================================================
    # ORDENA PLANOS
    # =====================================================

    planos_ordenados = {}

    for prazo in sorted(
        planos.keys()
    ):

        planos_ordenados[prazo] = sorted(
            planos[prazo],
            key=lambda x: x["km"]
        )

    # =====================================================
    # RETORNO
    # =====================================================

    return (
        planos_ordenados,
        imagem,
        nome_modelo,
        versao
    )