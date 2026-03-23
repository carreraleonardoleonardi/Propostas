import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import requests
from io import BytesIO

# --- CONFIG ---
COR_AZUL_CARRERA = (33, 49, 68)
COR_CINZA_CLARO = (245, 245, 245)

URL_LOGO = "https://i.postimg.cc/HWrrsnvR/LOGO-SIGNATURE-AZUL-E-DOURADO.png"
NOME_ARQUIVO_EXCEL = "Planos - VW.xlsx"

# --- PDF ---
class PropostaPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_margins(10, 10, 10)
        self.fonte_principal = "Arial"

        try:
            self.add_font("Montserrat", "", "Montserrat-Regular.ttf")
            self.add_font("Montserrat", "B", "Montserrat-Bold.ttf")
            self.fonte_principal = "Montserrat"
        except:
            self.fonte_principal = "Arial"

    def header(self):
        self.set_fill_color(*COR_CINZA_CLARO)
        self.rect(0, 0, 210, 297, 'F')

        try:
            res = requests.get(URL_LOGO, timeout=5)
            self.image(BytesIO(res.content), 75, 10, 60)
        except:
            self.set_font(self.fonte_principal, 'B', 12)
            self.cell(0, 10, "CARRERA SIGNATURE", ln=True, align='C')

        self.set_draw_color(180, 180, 180)
        self.set_line_width(0.3)
        self.line(10, 45, 200, 45)

    def footer(self):
        self.set_y(-15)
        self.set_font(self.fonte_principal, '', 6)
        self.set_text_color(120, 120, 120)

        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.cell(0, 4, f"Proposta gerada em {agora} - Simulacao.", align='C')

# --- LIMPEZA ---
def limpar_texto(txt):
    if pd.isna(txt):
        return ""
    return str(txt).encode('latin-1', 'replace').decode('latin-1')

# --- GERAR PDF ---
def gerar_pdf(cliente, vendedor, cotacoes):
    pdf = PropostaPDF()
    f = pdf.fonte_principal

    pdf.add_page()

    # --- TÍTULO ---
    pdf.set_y(55)
    pdf.set_font(f, 'B', 14)
    pdf.set_text_color(*COR_AZUL_CARRERA)
    pdf.cell(0, 8, f"Olá {cliente}, a Carrera Signature tem uma proposta especial para você!", ln=True, align='C')

    pdf.ln(2)

    # --- COPY ---
    pdf.set_font(f, '', 11)
    pdf.set_text_color(60, 60, 60)

    texto = f"""{vendedor} Preparou uma seleção exclusiva de planos pensados no seu perfil:"""
    pdf.multi_cell(0, 6, limpar_texto(texto), align='C')

    pdf.ln(6)

    # --- CARDS (ORIGINAL) ---
    y_topo = pdf.get_y()
    largura = 60
    altura_card = 80
    espacamento = 5

    for i, c in enumerate(cotacoes):
        x = 10 + i * (largura + espacamento)
        y = y_topo

        # sombra
        pdf.set_fill_color(230, 230, 230)
        pdf.rect(x+1, y+1, largura, altura_card, 'F')

        # card
        pdf.set_fill_color(255, 255, 255)
        pdf.set_draw_color(220, 220, 220)
        pdf.rect(x, y, largura, altura_card, 'FD')

        # título
        pdf.set_xy(x, y + 4)
        pdf.set_font(f, 'B', 9)
        pdf.set_text_color(*COR_AZUL_CARRERA)
        pdf.multi_cell(largura, 5, limpar_texto(c['modelo'])[:60], align='C')

        # imagem
        y_img = y + 18
        try:
            res = requests.get(c['url_foto'], timeout=5)
            pdf.image(BytesIO(res.content), x=x + 5, y=y_img, w=50)
        except:
            pass

        # info
        pdf.set_xy(x, y + 52)
        pdf.set_font(f, '', 8)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(largura, 5, f"{c['prazo']} meses | {c['km']} km", align='C', ln=True)

        # preço
        pdf.set_xy(x, y + 60)
        pdf.set_font(f, 'B', 16)
        pdf.set_text_color(*COR_AZUL_CARRERA)

        valor_limpo = str(c['valor']).strip()
        pdf.cell(largura, 6, valor_limpo, align='C', ln=True)

        pdf.set_font(f, '', 8)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(largura, 4, "/mes", align='C', ln=True)

    # --- BENEFÍCIOS ---
    pdf.set_y(y_topo + 95)

    pdf.set_font(f, 'B', 11)
    pdf.set_text_color(*COR_AZUL_CARRERA)
    pdf.cell(0, 6, "O que esta incluso:", ln=True)

    pdf.ln(2)

    pdf.set_font(f, '', 9)
    pdf.set_text_color(70, 70, 70)

    beneficios = [
        "- Documentação",
        "- Manutenções preventivas",
        "- Assistência 24h",
        "- Gestão de multas",
        "- Proteção completa ao veículo e a terceiros"
    ]

    for b in beneficios:
        pdf.cell(0, 5, b, ln=True)

    # --- SEGURO ---
    pdf.ln(4)

    pdf.set_font(f, 'B', 11)
    pdf.set_text_color(*COR_AZUL_CARRERA)
    pdf.cell(0, 6, "Condicoes de protecao:", ln=True)

    pdf.ln(2)

    seguro = [
        "Sinistro: ate 5% do valor do veiculo",
        "Furto / Roubo / PT: ate 5%",
        "Protecao para terceiros: R$ 5.000,00",
        "Vidros: R$ 400,00",
        "Reboque: 100 km ida + 100 km volta"
    ]

    pdf.set_font(f, '', 8)
    pdf.set_text_color(100, 100, 100)

    for item in seguro:
        pdf.multi_cell(0, 5, item)
        pdf.ln(1)

    # --- FINAL ---
    pdf.ln(4)
    pdf.set_font(f, 'B', 10)
    pdf.set_text_color(*COR_AZUL_CARRERA)
    pdf.cell(0, 6, "Fale com seu consultor e garanta sua condicao especial.", align='C')

    return bytes(pdf.output())

# --- STREAMLIT ---
st.set_page_config(layout="wide")

try:
    df = pd.read_excel(NOME_ARQUIVO_EXCEL, sheet_name='planos')

    with st.sidebar:
        st.image(URL_LOGO, width=150)
        vendedor = st.text_input("Consultor", "Leonardo")
        cliente = st.text_input("Cliente", "Cliente")

    st.title("🚗 Gerador de Propostas Premium")

    # --- CONTROLE DE 1 A 3 ---
    if "qtd_ofertas" not in st.session_state:
        st.session_state.qtd_ofertas = 0

    col1, col2 = st.columns(2)

    with col1:
        if st.session_state.qtd_ofertas < 3:
            if st.button("➕ Adicionar oferta"):
                st.session_state.qtd_ofertas += 1

    with col2:
        if st.session_state.qtd_ofertas > 0:
            if st.button("❌ Remover última"):
                st.session_state.qtd_ofertas -= 1

    st.divider()

    cotacoes = []

    # --- MANTÉM 3 COLUNAS FIXAS ---
    cols = st.columns(3)

    for i in range(st.session_state.qtd_ofertas):
        with cols[i]:
            veiculo = st.selectbox(f"Veículo {i+1}", df['nome'].unique(), key=i)
            dados = df[df['nome'] == veiculo].iloc[0]

            st.image(dados['imagem'], use_container_width=True)

            prazo = st.selectbox("Prazo", [12,18,24,36], key=f"p{i}")
            km = st.selectbox("KM", [500,1000,1500,2000], key=f"k{i}")

            col_p = f"preço{km}{prazo}"
            valor = dados[col_p] if col_p in df.columns else "Sob consulta"

            valor_limpo = str(valor).strip()
            st.success(f"{valor_limpo}")

            cotacoes.append({
                "modelo": veiculo,
                "prazo": prazo,
                "km": km,
                "valor": valor_limpo,
                "url_foto": dados['imagem']
            })

    st.divider()

    if st.session_state.qtd_ofertas > 0:
        if st.button("🚀 Gerar PDF Premium", use_container_width=True):
            pdf = gerar_pdf(cliente, vendedor, cotacoes)

            st.download_button(
                "📥 Baixar PDF",
                data=pdf,
                file_name=f"Proposta Carrera Signature - {cliente}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

except Exception as e:
    st.error(f"Erro: {e}")
