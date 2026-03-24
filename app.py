import streamlit as st
import pandas as pd
from pdf_generator import gerar_pdf
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Gerador de Propostas",
    page_icon="favicon.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESCONDER MENU E FOOTER (SEM REMOVER HEADER) ---
hide_st_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- SEGMENTOS (BASES) ---
SEGMENTOS = {
    "Sign & Drive": {
        "url": "https://docs.google.com/spreadsheets/d/1PfEemQ0vJ4TlS-q-x9hfU-IK1AqUVPun8It_Wi7pzgE/export?format=csv&gid=2034069788",
    },
    "Sign & Drive Empresas": {
        "url": "https://docs.google.com/spreadsheets/d/1puuB21uOsC8-UXe4MpuGE_oSpgyj-tyoihT6u68InMk/export?format=csv&gid=0",
    },
    "Assine Car GWM": {
        "url": "https://docs.google.com/spreadsheets/d/1zJB5EBhtB78RtJhqHSP6OQDX1_s0wrmMsz1C_tUKsMI/export?format=csv&gid=1332991446",
    },
    "GAC Go and Drive": {
        "url": "https://docs.google.com/spreadsheets/d/1xvD_QyO9opePn2X-Z2fHZGySOPm9AgQ7EbUcwoddjPo/export?format=csv&gid=676006877",
    },
    "Assine Car One": {
        "url": "https://docs.google.com/spreadsheets/d/1FgVXCyGyhqXyeXz3cYePDSZjRGgmJu9Jj6rAmasjeQQ/export?format=csv&gid=676006877",
    },
    "Nissan Move": {
        "url": "https://docs.google.com/spreadsheets/d/1pmK--_5SGVKW-LRXUK7TIjptP5DNxfYQMHS-cXA_rzw/export?format=csv&gid=1044813671",
    },
    "Assine Car Multbrand": {
        "url": "https://docs.google.com/spreadsheets/d/1l6exo6brmYVMm-16zhIt7MDiJp7YxGrGZd2-kYk4a7k/export?format=csv&gid=1489579420",
    },
    "GM Fleet Rede": {
        "url": "https://docs.google.com/spreadsheets/d/1AZiK2C7FjZ_-lNSJ-3fICfWB7hzRnEU8a_WCGgmubak/export?format=csv&gid=1332991446",
    },
    "GM Fleet (Estoque)": {
        "url": "https://docs.google.com/spreadsheets/d/153a41nRCYW65S1AtODo3u9aIJp2co20K2lAexpYHoGc/export?format=csv&gid=1332991446",
    },

    "GM Fleet - Eletricos": {
        "url": "https://docs.google.com/spreadsheets/d/1-Tnbo6s8QXew8gz8xAWwklusMgtB3KbfRU9DYuA90NI/export?format=csv&gid=1332991446",
    }
}

# --- FUNÇÃO DE CARREGAMENTO ---
@st.cache_data(ttl=600)
def carregar_dados(url):
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


# --- SIDEBAR ---
with st.sidebar:
    st.image("https://i.postimg.cc/HWrrsnvR/LOGO-SIGNATURE-AZUL-E-DOURADO.png", width=200)

    vendedor = st.text_input("Consultor", "")
    cliente = st.text_input("Cliente", "")

    qtd = st.selectbox(
        "Quantas ofertas deseja montar?",
        [3, 2, 1]
    )

    progress_container = st.empty()


# --- TÍTULO ---
st.title("🚗 Gerador de Propostas da Carrera Signature")

# --- CONSTRUÇÃO DAS OFERTAS ---
try:
    cotacoes = []
    cols = st.columns(3)

    for i in range(3):
        with cols[i]:
            if i < qtd:

                st.subheader(f"Oferta {i+1}:")

                # 🔥 SEGMENTO POR OFERTA
                segmento = st.selectbox(
                    "Segmento",
                    sorted(SEGMENTOS.keys()),
                    key=f"segmento_{i}"
                )

                # 🔥 CARREGA BASE
                df = carregar_dados(SEGMENTOS[segmento]["url"])

                # 🔥 VEÍCULO
                veiculo = st.selectbox(
                    "Veículo",
                    df['nome'].dropna().unique(),
                    key=f"veiculo_{i}"
                )

                dados = df[df['nome'] == veiculo].iloc[0]

                # IMAGEM
                if 'imagem' in df.columns:
                    st.image(dados['imagem'], use_container_width=True)

                # 🔥 REGRAS POR SEGMENTO
                if "Fleet" in segmento:
                    prazos = [12, 24, 36, 48]
                    kms = [500, 1000, 1500, 2000, 2500, 3000]
                else:
                    prazos = [12, 18, 24, 36]
                    kms = [500, 1000, 1500, 2000]

                prazo = st.selectbox("Prazo", prazos, key=f"prazo_{i}")
                km = st.selectbox("KM", kms, key=f"km_{i}")

                # 🔥 BUSCA PREÇO
                col_preco = f"preco{km}{prazo}"

                if col_preco in df.columns:
                    valor = dados[col_preco]
                else:
                    valor = "Sob consulta"

                valor_limpo = str(valor).strip()

                st.success(f"{valor_limpo}")

                cotacoes.append({
                    "segmento": segmento,
                    "modelo": veiculo,
                    "prazo": prazo,
                    "km": km,
                    "valor": valor_limpo,
                    "url_foto": dados.get('imagem', '')
                })

            else:
                st.empty()

    st.divider()

    # --- GERAR PDF ---
    if st.button("🚀 Gerar PDF da proposta", use_container_width=True):

        progress_bar = progress_container.progress(0, text="Iniciando...")

        progress_bar.progress(20, text="Preparando dados...")
        time.sleep(0.2)

        progress_bar.progress(40, text="Montando ofertas...")
        time.sleep(0.2)

        progress_bar.progress(60, text="Carregando imagens...")
        time.sleep(0.2)

        progress_bar.progress(80, text="Gerando PDF...")

        pdf = gerar_pdf(cliente, vendedor, cotacoes)

        progress_bar.progress(100, text="Finalizado!")

        st.download_button(
            "📥 Baixar PDF",
            data=pdf,
            file_name=f"Proposta Carrera Signature - {cliente}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

except Exception as e:
    st.error("❌ Erro ao carregar dados.")
    st.exception(e)
