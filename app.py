import streamlit as st
import pandas as pd
from pdf_generator import gerar_pdf

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Gerador de Propostas",
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
    df = pd.read_csv(SHEET_URL)

    # 🔥 NORMALIZAÇÃO (RESOLVE O "SOB CONSULTA")
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
    st.image("https://i.postimg.cc/HWrrsnvR/LOGO-SIGNATURE-AZUL-E-DOURADO.png", width=150)
    vendedor = st.text_input("Consultor", "Leonardo")
    cliente = st.text_input("Cliente", "Cliente")
    # --- SELEÇÃO DE QUANTIDADE ---
    qtd = st.selectbox(
        "Quantas ofertas deseja montar?",
        [3, 2, 1]
    )

# --- LOGO CENTRALIZADO ---
st.markdown("<br>", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1,2,1])
with col2:
    st.image("https://i.postimg.cc/HWrrsnvR/LOGO-SIGNATURE-AZUL-E-DOURADO.png", width=220)

st.markdown("<br>", unsafe_allow_html=True)

# --- TÍTULO ---
st.title("🚗 Gerador de Propostas da Carrera Signature")

# --- CARREGAR DADOS ---
try:
    df = carregar_dados()

    cotacoes = []
    cols = st.columns(3)  # 👈 mantém layout original

    for i in range(3):
        with cols[i]:
            if i < qtd:

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

                # 🔥 BUSCA DO PREÇO (AGORA FUNCIONA)
                col_preco = f"preco{km}{prazo}"

                if col_preco in df.columns:
                    valor = dados[col_preco]
                else:
                    valor = "Sob consulta"

                valor_limpo = str(valor).strip()

                st.success(f"{valor_limpo}")

                cotacoes.append({
                    "modelo": veiculo,
                    "prazo": prazo,
                    "km": km,
                    "valor": valor_limpo,
                    "url_foto": dados['imagem']
                })

            else:
                st.empty()  # mantém alinhamento visual

    st.divider()

    # --- BOTÃO GERAR PDF ---
    if st.button("🚀 Gerar PDF da proposta", use_container_width=True):
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
