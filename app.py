import streamlit as st
import pandas as pd
from pdf_generator import gerar_pdf

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Gerador de Propostas da Carrera Signature",
    page_icon="favicon.png",
    layout="wide",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": None
    }
)

# --- ESCONDER MENU E FOOTER ---
hide_st_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- GOOGLE SHEETS ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1PfEemQ0vJ4TlS-q-x9hfU-IK1AqUVPun8It_Wi7pzgE/export?format=csv&gid=2034069788"

@st.cache_data
def carregar_dados():
    return pd.read_csv(SHEET_URL)

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://i.postimg.cc/HWrrsnvR/LOGO-SIGNATURE-AZUL-E-DOURADO.png", width=200)
    vendedor = st.text_input("Consultor", "")
    cliente = st.text_input("Cliente", "")

# --- TÍTULO ---
st.title("🚗 Gerador de Propostas da Carrera Signature")

# --- CARREGAR DADOS ---
try:
    df = carregar_dados()

    # --- SELEÇÃO DE QUANTIDADE ---
    qtd = st.selectbox(
        "Quantas ofertas deseja montar?",
        [1, 2, 3]
    )

    cotacoes = []
    cols = st.columns(3)

    for i in range(3):
        with cols[i]:
            st.subheader(f"Oferta {i+1}:")

            veiculo = st.selectbox(
                "Veículo",
                df['nome'].unique(),
                key=f"veiculo_{i}"
            )

            dados = df[df['nome'] == veiculo].iloc[0]

            st.image(dados['imagem'], use_container_width=True)

            prazo = st.selectbox("Prazo", [12, 18, 24, 36], key=f"prazo_{i}")
            km = st.selectbox("KM", [500, 1000, 1500, 2000], key=f"km_{i}")

            col_preco = f"preco{km}{prazo}"

            if col_preco in df.columns:
                valor = dados[col_preco]
            else:
                valor = "Sob consulta"

            valor_limpo = str(valor).strip()

            st.success(f"{valor_limpo}/mês")

            cotacoes.append({
                "modelo": veiculo,
                "prazo": prazo,
                "km": km,
                "valor": valor_limpo,
                "url_foto": dados['imagem']
            })

    st.divider()

    # --- BOTÃO GERAR PDF ---
    if st.button("🚀 Gerar PDF", use_container_width=True):
        pdf = gerar_pdf(cliente, vendedor, cotacoes)

        st.download_button(
            "📥 Baixar PDF",
            data=pdf,
            file_name=f"Proposta_{cliente}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

except Exception as e:
    st.error("❌ Erro ao carregar dados da planilha.")
    st.exception(e)
