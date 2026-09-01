"""
listar_colunas.py — Carrera Signature

Lista as colunas reais das tabelas usadas em pages/performance_bd.py,
para confirmar/corrigir os nomes assumidos na seção CONFIG.

Uso (a partir da pasta Propostas/):
    streamlit run Dados/listar_colunas.py
ou, mais simples, direto no terminal (usa o mesmo secrets.toml):
    python -m streamlit run Dados/listar_colunas.py

Ele lê a MESMA seção [azure_sql] do .streamlit/secrets.toml,
então precisa ser executado de um jeito que o Streamlit encontre
o secrets.toml (rodando de dentro da pasta Propostas/).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pages"))

import streamlit as st
from performance_bd import _engine
import sqlalchemy as sa

st.title("🔎 Colunas reais no Azure SQL")

TABELAS = [
    "dbo.tbConsolidaSalesforce",
    "mkt.ConsolidadoCampanhas",
    "dbo.tbColaboradores",
]

sql = """
    SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA + '.' + TABLE_NAME = :tabela
    ORDER BY ORDINAL_POSITION
"""

for tabela in TABELAS:
    st.subheader(tabela)
    try:
        with _engine().connect() as conn:
            import pandas as pd
            df = pd.read_sql(sa.text(sql), conn, params={"tabela": tabela})
        if df.empty:
            st.warning(
                f"Nenhuma coluna encontrada para `{tabela}`. "
                "Verifique se o schema/nome da tabela está correto "
                "(ou se o usuário tem permissão de leitura nela)."
            )
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Erro ao consultar `{tabela}`: {e}")

st.divider()
st.caption(
    "Copie os nomes de coluna corretos e me envie — vou atualizar a seção "
    "CONFIG no topo de pages/performance_bd.py de uma vez."
)
