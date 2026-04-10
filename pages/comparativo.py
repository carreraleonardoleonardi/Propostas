import streamlit as st
import pandas as pd

from data import BASES, carregar_base, _is_disponivel
from utils import formatar_valor_brl, valor_para_float


def render():
    st.title("🔍 Comparativo de Planos")
    st.caption("Filtre por segmento, prazo, KM e faixa de preço. Deixe qualquer filtro vazio para buscar em todos.")

    segmentos_selecionados = st.multiselect(
        "Segmento",
        options=list(BASES.keys()),
        default=[],
        placeholder="Todos os segmentos"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        prazos_selecionados = st.multiselect(
            "Prazo (meses)",
            options=[12, 18, 24, 36, 48],
            default=[],
            placeholder="Todos os prazos"
        )

    with col2:
        kms_selecionados = st.multiselect(
            "KM por mês",
            options=[500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000],
            default=[],
            placeholder="Todos os KMs"
        )

    with col3:
        preco_min = st.number_input("Preço mínimo (R$)", min_value=0, max_value=99999, value=0,     step=100)

    with col4:
        preco_max = st.number_input("Preço máximo (R$)", min_value=0, max_value=99999, value=99999, step=100)

    st.divider()

    if st.button("🔍 Buscar ofertas", use_container_width=True):

        bases_busca  = {k: v for k, v in BASES.items() if k in segmentos_selecionados} if segmentos_selecionados else BASES
        prazos_busca = prazos_selecionados if prazos_selecionados else [12, 18, 24, 36, 48]
        kms_busca    = kms_selecionados    if kms_selecionados    else [500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000]

        resultados = []

        with st.spinner("Buscando..."):
            for segmento, url in bases_busca.items():
                try:
                    df_comp = carregar_base(url)

                    if "nome" not in df_comp.columns:
                        continue

                    for _, row in df_comp.iterrows():
                        nome = row.get("nome", "")
                        if pd.isna(nome) or not str(nome).strip():
                            continue

                        if "disponibilidade" in df_comp.columns:
                            if not _is_disponivel(row.get("disponibilidade", True)):
                                continue

                        for prazo in prazos_busca:
                            for km in kms_busca:
                                col_preco = f"preco{km}{prazo}"

                                if col_preco not in df_comp.columns:
                                    continue

                                valor_raw = row.get(col_preco, None)
                                if pd.isna(valor_raw):
                                    continue

                                valor_str = str(valor_raw).strip()
                                if not valor_str or valor_str.lower() == "nan":
                                    continue
                                if "nao disponivel" in valor_str.lower():
                                    continue
                                if "sob consulta" in valor_str.lower():
                                    continue

                                valor_num = valor_para_float(valor_str)
                                if valor_num is None:
                                    continue

                                if preco_min <= valor_num <= preco_max:
                                    resultados.append({
                                        "Segmento":   segmento,
                                        "Modelo":     str(nome).strip(),
                                        "Prazo":      f"{prazo} meses",
                                        "KM/mês":     f"{km} km",
                                        "Valor":      valor_num,
                                        "Valor (R$)": formatar_valor_brl(valor_num)
                                    })

                except Exception as e:
                    st.warning(f"Erro ao carregar {segmento}: {e}")
                    continue

        if not resultados:
            st.info("Nenhuma oferta encontrada com os filtros selecionados.")
        else:
            df_resultado = (
                pd.DataFrame(resultados)
                .sort_values("Valor")
                .reset_index(drop=True)
            )
            df_exibir = df_resultado.drop(columns=["Valor"])
            st.success(f"{len(df_resultado)} oferta(s) encontrada(s)")
            st.dataframe(df_exibir, width="stretch", hide_index=True)