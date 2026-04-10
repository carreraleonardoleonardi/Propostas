import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from data import BASES, carregar_base, obter_veiculos, extrair_planos_modelo


def render(gerar_card_plano_html, gerar_card_png):
    st.title("🧮 Simulador de Plano")
    st.caption("Selecione o segmento e o modelo para montar o card comercial do plano.")

    col1, col2 = st.columns(2)

    with col1:
        segmento_sim = st.selectbox("Segmento", list(BASES.keys()), key="sim_segmento")

    df_sim              = carregar_base(BASES[segmento_sim])
    modelos_disponiveis = obter_veiculos(df_sim)

    with col2:
        modelo_sim = st.selectbox("Modelo", modelos_disponiveis, key="sim_modelo", index=0)

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        gerar = st.button("✨ Montar card do plano", use_container_width=True)

    if gerar:
        planos, imagem, nome_mod, versao_mod = extrair_planos_modelo(df_sim, modelo_sim)
        if not planos:
            st.warning("Não foram encontrados planos para este modelo.")
        else:
            st.session_state["sim_planos"]     = planos
            st.session_state["sim_imagem"]     = imagem
            st.session_state["sim_nome_mod"]   = nome_mod
            st.session_state["sim_versao_mod"] = versao_mod
            st.session_state["sim_seg_salvo"]  = segmento_sim

    if "sim_planos" in st.session_state and st.session_state["sim_planos"]:
        planos     = st.session_state["sim_planos"]
        imagem     = st.session_state["sim_imagem"]
        nome_mod   = st.session_state["sim_nome_mod"]
        versao_mod = st.session_state["sim_versao_mod"]
        seg        = st.session_state["sim_seg_salvo"]

        png_bytes = gerar_card_png(nome_mod, planos, imagem, seg, versao_mod)

        with col_btn2:
            st.download_button(
                "📥 Baixar card em PNG",
                data=png_bytes,
                file_name=f"Card Plano - {modelo_sim}.png",
                mime="image/png",
                use_container_width=True
            )

        st.divider()

        with st.expander("Ver estrutura dos planos encontrados"):
            linhas = [
                {"Prazo": prazo, "KM por mês": item["km"], "Valor": item["valor"]}
                for prazo, itens in planos.items()
                for item in itens
            ]
            if linhas:
                st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True)