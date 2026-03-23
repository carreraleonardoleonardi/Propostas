from fpdf import FPDF
from datetime import datetime
import requests
from io import BytesIO
from utils import limpar_texto

# --- CONFIG ---
COR_AZUL_CARRERA = (33, 49, 68)
COR_CINZA_CLARO = (245, 245, 245)

URL_LOGO = "https://i.postimg.cc/HWrrsnvR/LOGO-SIGNATURE-AZUL-E-DOURADO.png"

# --- ICONES ---
ICON_INSTA = "https://cdn-icons-png.flaticon.com/512/174/174855.png"
ICON_WAPP = "https://cdn-icons-png.flaticon.com/512/3670/3670051.png"
ICON_YOUTUBE = "https://cdn-icons-png.flaticon.com/512/174/174883.png"

LINK_INSTA = "https://www.instagram.com/carrerasignature/"
LINK_WAPP = "https://wa.me/551140037214"
LINK_YOUTUBE = "https://www.youtube.com/@CarreraSignature"

# --- PDF ---
class PropostaPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_margins(10, 10, 10)
        self.fonte_principal = "Arial"

        try:
            self.add_font("Montserrat", "", "assets/Montserrat-Regular.ttf")
            self.add_font("Montserrat", "B", "assets/Montserrat-Bold.ttf")
            self.fonte_principal = "Montserrat"
        except:
            self.fonte_principal = "Arial"

    def header(self):
        # fundo
        self.set_fill_color(*COR_CINZA_CLARO)
        self.rect(0, 0, 210, 297, 'F')

        # logo
        try:
            res = requests.get(URL_LOGO, timeout=5)
            self.image(BytesIO(res.content), 75, 10, 60, type='PNG')
        except:
            self.set_font(self.fonte_principal, 'B', 12)
            self.cell(0, 10, "CARRERA SIGNATURE", ln=True, align='C')

        # linha
        self.set_draw_color(180, 180, 180)
        self.set_line_width(0.3)
        self.line(10, 45, 200, 45)

    def footer(self):
        self.set_y(-28)

        # --- FUNÇÃO LOAD IMG ---
        def load_img(url):
            try:
                res = requests.get(url, timeout=5)
                return BytesIO(res.content)
            except:
                return None

        icon_size = 6
        spacing = 10

        page_width = 210
        total_width = (icon_size * 3) + (spacing * 2)
        start_x = (page_width - total_width) / 2

        y_icons = self.get_y()

        # Instagram
        img = load_img(ICON_INSTA)
        if img:
            self.image(img, x=start_x, y=y_icons, w=icon_size, type='PNG', link=LINK_INSTA)

        # WhatsApp
        img = load_img(ICON_WAPP)
        if img:
            self.image(img, x=start_x + icon_size + spacing, y=y_icons, w=icon_size, type='PNG', link=LINK_WAPP)

        # YouTube
        img = load_img(ICON_YOUTUBE)
        if img:
            self.image(img, x=start_x + (icon_size + spacing) * 2, y=y_icons, w=icon_size, type='PNG', link=LINK_YOUTUBE)

        # --- TEXTO ---
        self.ln(8)

        self.set_font(self.fonte_principal, '', 6)
        self.set_text_color(140, 140, 140)

        agora = datetime.now().strftime("%d/%m/%Y %H:%M")

        texto = (
            f"Proposta gerada em {agora}. Valores sujeitos a alteração sem aviso prévio por parte do fornecedor.\n"
            "Não constitui reserva de veículo. Condições válidas mediante assinatura de contrato e disponibilidade de estoque.\n"
            "Carrera Signature - Seu jeito inteligente de andar de carro"
        )

        self.multi_cell(0, 3, texto, align='C')

# --- GERAR PDF ---
def gerar_pdf(cliente, vendedor, cotacoes):
    pdf = PropostaPDF()
    f = pdf.fonte_principal

    pdf.add_page()

    # --- TÍTULO ---
    pdf.set_y(55)
    pdf.set_font(f, 'B', 14)
    pdf.set_text_color(*COR_AZUL_CARRERA)
    pdf.cell(
        0, 8,
        f"Olá {cliente}, a Carrera Signature tem uma proposta especial para você!",
        ln=True, align='C'
    )

    pdf.ln(2)

    # --- TEXTO ---
    pdf.set_font(f, '', 11)
    pdf.set_text_color(60, 60, 60)

    texto = f"{vendedor} preparou uma seleção exclusiva de planos pensados no seu perfil:"
    pdf.multi_cell(0, 6, limpar_texto(texto), align='C')

    pdf.ln(6)

    # --- CARDS ---
    y_topo = pdf.get_y()
    largura = 60
    altura_card = 80
    espacamento = 5

    for i, c in enumerate(cotacoes):
        x = 10 + i * (largura + espacamento)
        y = y_topo

        pdf.set_fill_color(230, 230, 230)
        pdf.rect(x+1, y+1, largura, altura_card, 'F')

        pdf.set_fill_color(255, 255, 255)
        pdf.set_draw_color(220, 220, 220)
        pdf.rect(x, y, largura, altura_card, 'FD')

        pdf.set_xy(x, y + 4)
        pdf.set_font(f, 'B', 9)
        pdf.set_text_color(*COR_AZUL_CARRERA)
        pdf.multi_cell(largura, 5, limpar_texto(c['modelo'])[:60], align='C')

        # imagem
        y_img = y + 18
        try:
            res = requests.get(c['url_foto'], timeout=5)
            pdf.image(BytesIO(res.content), x=x + 5, y=y_img, w=50, type='PNG')
        except:
            pass

        pdf.set_xy(x, y + 52)
        pdf.set_font(f, '', 8)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(largura, 5, f"{c['prazo']} meses | {c['km']} km", align='C', ln=True)

        pdf.set_xy(x, y + 60)
        pdf.set_font(f, 'B', 16)
        pdf.set_text_color(*COR_AZUL_CARRERA)

        valor_limpo = str(c['valor']).strip()
        pdf.cell(largura, 6, valor_limpo, align='C', ln=True)

        pdf.set_font(f, '', 8)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(largura, 4, "/mês", align='C', ln=True)

    # --- BLOCO FINAL ---
    pdf.set_y(y_topo + 95)
    y_inicio = pdf.get_y()

    pdf.set_font(f, 'B', 11)
    pdf.set_text_color(*COR_AZUL_CARRERA)

    pdf.set_xy(15, y_inicio)
    pdf.cell(80, 6, "O que está incluso:")

    pdf.set_xy(110, y_inicio)
    pdf.cell(80, 6, "Proximos passos:")

    pdf.set_draw_color(*COR_AZUL_CARRERA)
    pdf.set_line_width(0.5)

    pdf.line(15, y_inicio + 7, 85, y_inicio + 7)
    pdf.line(110, y_inicio + 7, 190, y_inicio + 7)

    beneficios = [
        "Documentação completa",
        "Manutenções preventivas inclusas",
        "Assistência 24h nacional",
        "Gestão de multas",
        "Proteção completa ao veículo e terceiros"
    ]

    condicoes = [
        "Envio da documentação",
        "Analise de crédito",
        "Assinatura do contrato",
        "Aguardar o veículo chegar",
        "Agendamento da retirada",
        "Pronto é só aproveitar!"
    ]

    pdf.set_font(f, '', 9)
    pdf.set_text_color(80, 80, 80)

    y_texto = y_inicio + 12

    for i in range(max(len(beneficios), len(condicoes))):

        if i < len(beneficios):
            pdf.set_xy(15, y_texto + i * 6)
            pdf.cell(80, 5, f"• {beneficios[i]}")

        if i < len(condicoes):
            pdf.set_xy(110, y_texto + i * 6)
            pdf.cell(80, 5, f"• {condicoes[i]}")

    # CTA
    pdf.set_xy(10, y_texto + max(len(beneficios), len(condicoes)) * 6 + 4)

    pdf.set_font(f, 'B', 11)
    pdf.set_text_color(*COR_AZUL_CARRERA)
    pdf.cell(
        190,
        8,
        "Fale com seu consultor e garanta sua condição especial.",
        align='C'
    )

    return bytes(pdf.output())
