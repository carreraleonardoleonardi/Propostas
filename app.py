import streamlit as st
import pandas as pd
from pdf_generator import gerar_pdf

# --- CONFIG ---
st.set_page_config(
    page_title="Gerador de Propostas",
    layout="wide"
)

URL_LOGO = "https://i.postimg.cc/HWrrsnvR/LOGO-SIGNATURE-AZUL-E-DOURADO.png"

# 🔗 GOOGLE SHEETS (ABA PLANOS)
URL_SHEET = "https://docs.google.com/spreadsheets/d/1PfEemQ0vJ4TlS-q-x9hfU-IK1AqUVPun8It_Wi7pzgE/export?format=csv&gid=2034069788"

# --- CACHE DE DADOS ---
@st.cache_data(show_spinner=False)
def carregar_dados():
    df = pd.read_csv(URL_SHEET)
    df.columns = df.columns.str.strip()  # limpa espaços invisíveis
    return df

# --- APP ---
try:
    df = carregar_dados()

    # --- SIDEBAR ---
    with st.sidebar:
        st.image(URL_LOGO, width=150)
        st.markdown("### 👤 Dados da Proposta")

        vendedor = st.text_input("Consultor", "")
        cliente = st.text_input("Cliente", "")

        st.divider()

        qtd_ofertas = st.selectbox(
            "Quantidade de ofertas",
            [1, 2, 3],
            index=2
        )

    # --- HEADER ---
    st.title("🚗 Gerador de Propostas da Carrera Signature")
    st.caption("Monte propostas personalizadas em segundos")

    cotacoes = []

    cols = st.columns(qtd_ofertas)

    # --- CARDS DINÂMICOS ---
    for i in range(qtd_ofertas):
        with cols[i]:
            st.markdown(f"### Oferta {i+1}")

            veiculo = st.selectbox(
                "Veículo",
                df['nome'].dropna().unique(),
                key=f"veiculo_{i}"
            )

            dados = df[df['nome'] == veiculo].iloc[0]

            # imagem
            st.image(dados['imagem'], use_container_width=True)

            # seleções
            prazo = st.selectbox(
                "Prazo (meses)",
                [12, 18, 24, 36],
                key=f"prazo_{i}"
            )

            km = st.selectbox(
                "KM mensal",
                [500, 1000, 1500, 2000],
                key=f"km_{i}"
            )

            # preço dinâmico
            col_preco = f"preço{km}{prazo}"

            if col_preco in df.columns:
                valor = dados[col_preco]
            else:
                valor = "Sob consulta"

            valor_limpo = str(valor).strip()

            st.success(f"{valor_limpo}")

            # salva cotação
            cotacoes.append({
                "modelo": veiculo,
                "prazo": prazo,
                "km": km,
                "valor": valor_limpo,
                "url_foto": dados['imagem']
            })

    st.divider()

    # --- BOTÃO PDF ---
    if st.button("🚀 Gerar PDF", use_container_width=True):
        if not cotacoes:
            st.warning("Selecione pelo menos uma oferta.")
        else:
            pdf = gerar_pdf(cliente, vendedor, cotacoes)

            st.download_button(
                label="📥 Baixar PDF",
                data=pdf,
                file_name=f"Proposta_Carrera_Signature_{cliente}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

# --- ERRO ---
except Exception as e:
    st.error("❌ Erro ao carregar dados da planilha.")
    st.exception(e)
