import streamlit as st
import pandas as pd
import datetime

from data import carregar_relatorio


def render():
    col_title, col_btn = st.columns([6, 1])

    with col_title:
        st.title("📊 Dashboard")
        if st.session_state["ultima_atualizacao"] is not None:
            st.caption(f"Última atualização: {st.session_state['ultima_atualizacao'].strftime('%H:%M:%S')}")

    with col_btn:
        if st.button("🔄 Atualizar"):
            carregar_relatorio.clear()
            st.rerun()

    df = carregar_relatorio()
    st.session_state["ultima_atualizacao"] = datetime.datetime.now()

    if df.empty:
        st.warning("Sem dados ainda...")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        data_min    = df["data"].min() if "data" in df.columns and not df["data"].dropna().empty else datetime.datetime.now().date()
        data_inicio = st.date_input("Data início", data_min)
    with col2:
        data_max = df["data"].max() if "data" in df.columns and not df["data"].dropna().empty else datetime.datetime.now().date()
        data_fim = st.date_input("Data fim", data_max)
    with col3:
        lista_consultores = ["Todos"]
        if "consultor" in df.columns:
            lista_consultores += list(df["consultor"].dropna().unique())
        consultor = st.selectbox("Consultor", lista_consultores)

    df_filtro = df.copy()
    if "data" in df_filtro.columns:
        df_filtro = df_filtro[
            (df_filtro["data"] >= pd.to_datetime(data_inicio)) &
            (df_filtro["data"] <= pd.to_datetime(data_fim))
        ]
    if consultor != "Todos" and "consultor" in df_filtro.columns:
        df_filtro = df_filtro[df_filtro["consultor"] == consultor]

    col1, col2, col3, col4 = st.columns(4)
    propostas     = df_filtro["proposta_id"].nunique() if "proposta_id" in df_filtro.columns else 0
    veiculos_qtd  = len(df_filtro)
    top_consultor = df_filtro["consultor"].mode()[0] if ("consultor" in df_filtro.columns and not df_filtro.empty and not df_filtro["consultor"].dropna().empty) else "-"
    top_modelo    = df_filtro["modelo"].mode()[0]    if ("modelo"    in df_filtro.columns and not df_filtro.empty and not df_filtro["modelo"].dropna().empty)    else "-"

    col1.metric("Propostas",     propostas)
    col2.metric("Veículos",      veiculos_qtd)
    col3.metric("Top Consultor", top_consultor)
    col4.metric("Top Modelo",    top_modelo)
    st.divider()

    if not df_filtro.empty and "data" in df_filtro.columns and "proposta_id" in df_filtro.columns:
        st.subheader("📈 Propostas por dia")
        st.bar_chart(df_filtro.groupby(df_filtro["data"].dt.date)["proposta_id"].nunique())

    if not df_filtro.empty and "consultor" in df_filtro.columns:
        st.subheader("🏆 Ranking Consultores")
        st.bar_chart(df_filtro["consultor"].value_counts())

    if not df_filtro.empty and "segmento" in df_filtro.columns:
        st.subheader("🚗 Segmentos")
        st.bar_chart(df_filtro["segmento"].value_counts())

    if not df_filtro.empty and "modelo" in df_filtro.columns and "proposta_id" in df_filtro.columns:
        st.subheader("🔥 Modelos mais ofertados")
        st.bar_chart(df_filtro.groupby("modelo")["proposta_id"].nunique().sort_values(ascending=False))