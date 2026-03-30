import streamlit as st
import pandas as pd
import requests
import json
import datetime
import time
from pdf_generator import gerar_pdf

# --- CONFIG ---
st.set_page_config(
    page_title="Gerador de Propostas",
    page_icon="🚗",
    layout="wide"
)

# --- ESCONDER MENU ---
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- WEBHOOK ---
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxzzTh8nlzwFmAdrB7-qXrhUiEeWGGOwH7ZGAuQeaGZHcTVRa1jASmrpU-ADQcCLZgTKw/exec"

# --- PLANILHA RELATÓRIO ---
URL_RELATORIO = "https://docs.google.com/spreadsheets/d/1bxjKSfD2MpBpV4swaBCjkhi8ElHV_8M97zxI6jgtv0w/export?format=csv"

# --- BASES ---
BASES = {
    "Sign & Drive": "https://docs.google.com/spreadsheets/d/1PfEemQ0vJ4TlS-q-x9hfU-IK1AqUVPun8It_Wi7pzgE/export?format=csv&gid=2034069788",
    "Sign & Drive Empresas": "https://docs.google.com/spreadsheets/d/1puuB21uOsC8-UXe4MpuGE_oSpgyj-tyoihT6u68InMk/export?format=csv",
    "Assine Car GWM": "https://docs.google.com/spreadsheets/d/1y9wBzxq6mb3OItBQ6IjrOpGW2t5QV8EADekDfLtkbRw/export?format=csv&gid=676006877",
    "Assine Car GWM - Blindado": "https://docs.google.com/spreadsheets/d/1zJB5EBhtB78RtJhqHSP6OQDX1_s0wrmMsz1C_tUKsMI/export?format=csv&gid=1332991446",
    "GAC Go and Drive": "https://docs.google.com/spreadsheets/d/1xvD_QyO9opePn2X-Z2fHZGySOPm9AgQ7EbUcwoddjPo/export?format=csv&gid=676006877",
    "Assine Car One": "https://docs.google.com/spreadsheets/d/1FgVXCyGyhqXyeXz3cYePDSZjRGgmJu9Jj6rAmasjeQQ/export?format=csv&gid=676006877",
    "Nissan Move": "https://docs.google.com/spreadsheets/d/1pmK--_5SGVKW-LRXUK7TIjptP5DNxfYQMHS-cXA_rzw/export?format=csv&gid=1044813671",
    "Assine Car Multbrand": "https://docs.google.com/spreadsheets/d/1l6exo6brmYVMm-16zhIt7MDiJp7YxGrGZd2-kYk4a7k/export?format=csv&gid=1489579420",
    "GM Fleet Rede": "https://docs.google.com/spreadsheets/d/1AZiK2C7FjZ_-lNSJ-3fICfWB7hzRnEU8a_WCGgmubak/export?format=csv&gid=1332991446",
    "GM Fleet PF": "https://docs.google.com/spreadsheets/d/153a41nRCYW65S1AtODo3u9aIJp2co20K2lAexpYHoGc/export?format=csv&gid=1332991446",
    "GM Fleet Elétricos": "https://docs.google.com/spreadsheets/d/1-Tnbo6s8QXew8gz8xAWwklusMgtB3KbfRU9DYuA90NI/export?format=csv&gid=1332991446"
}

# =========================
# FUNÇÕES
# =========================

@st.cache_data
def carregar_base(url):
    df = pd.read_csv(url)

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.normalize('NFKD')
        .str.encode('ascii', errors='ignore')
        .str.decode('utf-8')
        .str.replace(" ", "")
    )

    return df


@st.cache_data
def carregar_relatorio():
    df = pd.read_csv(URL_RELATORIO)

    df = df.loc[:, ~df.columns.duplicated()]

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.normalize('NFKD')
        .str.encode('ascii', errors='ignore')
        .str.decode('utf-8')
        .str.replace(" ", "")
    )

    colunas_esperadas = [
        "data", "proposta_id", "consultor", "cliente",
        "segmento", "modelo", "prazo", "km", "valor"
    ]

    df = df[[c for c in colunas_esperadas if c in df.columns]]

    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")

    if "valor" in df.columns:
        df["valor"] = (
            df["valor"].astype(str)
            .str.replace("R$", "", regex=False)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")

    return df


def salvar_proposta(cotacoes, vendedor, cliente):
    proposta_id = "CS" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")

    for c in cotacoes:
        payload = {
            "consultor": vendedor,
            "cliente": cliente,
            "segmento": c["segmento"],
            "modelo": c["modelo"],
            "prazo": c["prazo"],
            "km": c["km"],
            "valor": c["valor"],
            "proposta_id": proposta_id
        }

        try:
            requests.post(
                WEBHOOK_URL,
                data=json.dumps(payload),
                headers={"Content-Type": "text/plain"}
            )
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

    return proposta_id


# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.image("https://i.postimg.cc/HWrrsnvR/LOGO-SIGNATURE-AZUL-E-DOURADO.png", width=180)

    st.markdown("### 👤 Dados da Proposta")
    vendedor = st.text_input("Consultor *")
    cliente = st.text_input("Cliente *")

    qtd = st.selectbox("Qtd ofertas", [1, 2, 3], index=2)

    progress_container = st.empty()


# =========================
# ABAS
# =========================
tab1, tab2 = st.tabs(["🚗 Propostas", "📊 Relatório"])


# =========================
# 🚗 PROPOSTAS
# =========================
with tab1:

    st.title("🚗 Gerador de Propostas da Carrera Signature")

    cotacoes = []
    cols = st.columns(3)

    for i in range(3):
        with cols[i]:
            if i < qtd:

                st.subheader(f"Oferta {i+1}:")

                segmento = st.selectbox("Segmento", list(BASES.keys()), key=f"seg_{i}")
                df = carregar_base(BASES[segmento])

                veiculo = st.selectbox("Veículo", df['nome'].dropna().unique(), key=f"vei_{i}")
                dados = df[df['nome'] == veiculo].iloc[0]

                st.image(dados['imagem'], use_container_width=True)

                prazo = st.selectbox("Prazo", [12, 18, 24, 36, 48], key=f"prazo_{i}")
                km = st.selectbox("KM", [500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000], key=f"km_{i}")

                col_preco = f"preco{km}{prazo}"
                valor = dados[col_preco] if col_preco in df.columns else "Sob consulta"

                st.success(str(valor))

                cotacoes.append({
                    "segmento": segmento,
                    "modelo": veiculo,
                    "prazo": prazo,
                    "km": km,
                    "valor": str(valor),
                    "url_foto": dados['imagem']
                })

    st.divider()

    if st.button("🚀 Gerar PDF da proposta", use_container_width=True):

        if not vendedor or not cliente:
            st.error("⚠️ Preencha os campos obrigatórios: Consultor e Cliente.")
            st.stop()

        progress = progress_container.progress(0, text="Iniciando...")

        progress.progress(30, text="Salvando proposta...")
        proposta_id = salvar_proposta(cotacoes, vendedor, cliente)

        time.sleep(0.3)

        progress.progress(70, text="Gerando PDF...")
        pdf = gerar_pdf(cliente, vendedor, cotacoes)

        time.sleep(0.3)

        progress.progress(100, text="Finalizado!")

        st.success(f"Proposta gerada: {cliente} - {proposta_id}")

        st.download_button(
            "📥 Baixar PDF",
            data=pdf,
            file_name=f"Proposta Carrera Signature - {cliente}.pdf",
            mime="application/pdf",
            use_container_width=True
        )


# =========================
# 📊 RELATÓRIO
# =========================
with tab2:

    col_title, col_btn = st.columns([6,1])

    with col_title:
        st.title("📊 Dashboard")

        if "ultima_atualizacao" in st.session_state:
            st.caption(
                f"Última atualização: {st.session_state['ultima_atualizacao'].strftime('%H:%M:%S')}"
            )

    with col_btn:
        if st.button("🔄 Atualizar"):
            carregar_relatorio.clear()
            st.rerun()

    df = carregar_relatorio()

    # ⏱️ salva horário da atualização
    st.session_state["ultima_atualizacao"] = datetime.datetime.now()

    if df.empty:
        st.warning("Sem dados ainda...")
        st.stop()

    col1, col2, col3 = st.columns(3)

    with col1:
        data_inicio = st.date_input("Data início", df["data"].min())

    with col2:
        data_fim = st.date_input("Data fim", df["data"].max())

    with col3:
        consultor = st.selectbox("Consultor", ["Todos"] + list(df["consultor"].dropna().unique()))

    df_filtro = df[
        (df["data"] >= pd.to_datetime(data_inicio)) &
        (df["data"] <= pd.to_datetime(data_fim))
    ]

    if consultor != "Todos":
        df_filtro = df_filtro[df_filtro["consultor"] == consultor]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Propostas", df_filtro["proposta_id"].nunique())
    col2.metric("Veículos", len(df_filtro))
    col3.metric("Top Consultor", df_filtro["consultor"].mode()[0] if not df_filtro.empty else "-")
    col4.metric("Top Modelo", df_filtro["modelo"].mode()[0] if not df_filtro.empty else "-")

    st.divider()

    st.subheader("📈 Propostas por dia")
    df_dia = df_filtro.groupby(df_filtro["data"].dt.date)["proposta_id"].nunique()
    st.bar_chart(df_dia)

    st.subheader("🏆 Ranking Consultores")
    st.bar_chart(df_filtro["consultor"].value_counts())

    st.subheader("🚗 Segmentos")
    st.bar_chart(df_filtro["segmento"].value_counts())

    st.subheader("🔥 Modelos mais ofertados")
    df_carro = df_filtro.groupby("modelo")["proposta_id"].nunique().sort_values(ascending=False)
    st.bar_chart(df_carro)
