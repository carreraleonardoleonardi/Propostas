from fpdf import FPDF
from datetime import datetime
from zoneinfo import ZoneInfo
from utils import limpar_texto
import requests
import tempfile
import os

# --- CONFIG ---
COR_AZUL_CARRERA = (33, 49, 68)
COR_CINZA_CLARO = (245, 245, 245)

URL_LOGO = "https://i.postimg.cc/HWrrsnvR/LOGO-SIGNATURE-AZUL-E-DOURADO.png"

ICON_INSTA = "https://cdn-icons-png.flaticon.com/512/174/174855.png"
ICON_WAPP = "https://cdn-icons-png.flaticon.com/512/3670/3670051.png"
ICON_YOUTUBE = "https://cdn-icons-png.flaticon.com/512/174/174883.png"

LINK_INSTA = "https://www.instagram.com/carrerasignature/"
LINK_WAPP = "https://wa.me/551140037214"
LINK_YOUTUBE = "https://www.youtube.com/@CarreraSignature"


def baixar_imagem_temp(url: str):
    """
    Baixa uma imagem da URL e salva em arquivo temporário.
    Retorna o caminho do arquivo temporário ou None.
    """
    if not url:
        return None

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()
        if "png" in content_type:
            suffix = ".png"
        elif "jpeg" in content_type or "jpg" in content_type:
            suffix = ".jpg"
        elif "webp" in content_type:
            suffix = ".webp"
        else:
            # fallback simples
            if ".png" in url.lower():
                suffix = ".png"
            elif ".webp" in url.lower():
                suffix = ".webp"
            else:
                suffix = ".jpg"

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_file.write(response.content)
        temp_file.flush()
        temp_file.close()
        return temp_file.name

    except Exception as e:
        print(f"Erro ao baixar imagem {url}: {e}")
        return None


# --- PDF ---
class PropostaPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_margins(10, 10, 10)
        self.fonte_principal = "Arial"
        self.temp_files = []

        try:
            self.add_font("Montserrat", "", "assets/Montserrat-Regular.ttf")
            self.add_font("Montserrat", "B", "assets/Montserrat-Bold.ttf")
            self.fonte_principal = "Montserrat"
        except Exception as e:
            print(f"Erro ao carregar fonte Montserrat: {e}")

    def registrar_temp(self, caminho):
        if caminho:
            self.temp_files.append(caminho)

    def limpar_temporarios(self):
        for arquivo in self.temp_files:
            try:
                if os.path.exists(arquivo):
                    os.remove(arquivo)
            except Exception as e:
                print(f"Erro ao remover temporário {arquivo}: {e}")
        self.temp_files = []

    def header(self):
        # fundo
        self.set_fill_color(*COR_CINZA_CLARO)
        self.rect(0, 0, 210, 297, 'F')

        # logo
        try:
            logo_temp = baixar_imagem_temp(URL_LOGO)
            self.registrar_temp(logo_temp)

            if logo_temp:
                self.image(logo_temp, 75, 10, 60)
            else:
                self.set_font(self.fonte_principal, 'B', 12)
                self.set_text_color(0, 0, 0)
                self.cell(0, 10, "CARRERA SIGNATURE", new_x="LMARGIN", new_y="NEXT", align='C')

        except Exception as e:
            print(f"Erro ao renderizar logo: {e}")
            self.set_font(self.fonte_principal, 'B', 12)
            self.set_text_color(0, 0, 0)
            self.cell(0, 10, "CARRERA SIGNATURE", new_x="LMARGIN", new_y="NEXT", align='C')

        # linha
        self.set_draw_color(180, 180, 180)
        self.set_line_width(0.3)
        self.line(10, 45, 200, 45)

    def footer(self):
        self.set_y(-28)

        icon_size = 6
        spacing = 10

        page_width = 210
        total_width = (icon_size * 3) + (spacing * 2)
        start_x = (page_width - total_width) / 2

        y_icons = self.get_y()

        # Ícones clicáveis
        try:
            insta_temp = baixar_imagem_temp(ICON_INSTA)
            wapp_temp = baixar_imagem_temp(ICON_WAPP)
            yt_temp = baixar_imagem_temp(ICON_YOUTUBE)

            self.registrar_temp(insta_temp)
            self.registrar_temp(wapp_temp)
            self.registrar_temp(yt_temp)

            if insta_temp:
                self.image(insta_temp, start_x, y_icons, icon_size, link=LINK_INSTA)
            if wapp_temp:
                self.image(wapp_temp, start_x + icon_size + spacing, y_icons, icon_size, link=LINK_WAPP)
            if yt_temp:
                self.image(yt_temp, start_x + (icon_size + spacing) * 2, y_icons, icon_size, link=LINK_YOUTUBE)

        except Exception as e:
            print(f"Erro ao renderizar ícones do footer: {e}")

        self.ln(8)

        self.set_font(self.fonte_principal, '', 6)
        self.set_text_color(140, 140, 140)

        agora = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")

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

    try:
        pdf.add_page()

        # --- TÍTULO ---
        pdf.set_y(55)
        pdf.set_font(f, 'B', 14)
        pdf.set_text_color(*COR_AZUL_CARRERA)
        pdf.cell(
            0, 8,
            f"Olá {cliente}, a Carrera Signature tem uma proposta especial para você!",
            new_x="LMARGIN",
            new_y="NEXT",
            align='C'
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

            # sombra
            pdf.set_fill_color(230, 230, 230)
            pdf.rect(x + 1, y + 1, largura, altura_card, 'F')

            # card
            pdf.set_fill_color(255, 255, 255)
            pdf.set_draw_color(220, 220, 220)
            pdf.rect(x, y, largura, altura_card, 'FD')

            # título
            pdf.set_xy(x, y + 4)
            pdf.set_font(f, 'B', 9)
            pdf.set_text_color(*COR_AZUL_CARRERA)
            modelo = limpar_texto(str(c.get("modelo", "")))[:60]
            pdf.multi_cell(largura, 5, modelo, align='C')

            # imagem do carro
            try:
                url_foto = c.get("url_foto", "")
                foto_temp = baixar_imagem_temp(url_foto)
                pdf.registrar_temp(foto_temp)

                if foto_temp:
                    pdf.image(foto_temp, x + 5, y + 18, 50)
            except Exception as e:
                print(f"Erro ao renderizar imagem do carro: {e}")

            # info
            pdf.set_xy(x, y + 52)
            pdf.set_font(f, '', 8)
            pdf.set_text_color(90, 90, 90)
            pdf.cell(
                largura,
                5,
                f"{c.get('prazo', '')} meses | {c.get('km', '')} km",
                new_x="LMARGIN",
                new_y="NEXT",
                align='C'
            )

            # preço
            pdf.set_xy(x, y + 60)
            pdf.set_font(f, 'B', 16)
            pdf.set_text_color(*COR_AZUL_CARRERA)

            valor_limpo = str(c.get("valor", "")).strip()
            pdf.cell(largura, 6, valor_limpo, new_x="LMARGIN", new_y="NEXT", align='C')

            pdf.set_font(f, '', 8)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(largura, 4, "", new_x="LMARGIN", new_y="NEXT", align='C')

        # --- BLOCO FINAL ---
        pdf.set_y(y_topo + 95)
        y_inicio = pdf.get_y()

        pdf.set_font(f, 'B', 11)
        pdf.set_text_color(*COR_AZUL_CARRERA)

        pdf.set_xy(15, y_inicio)
        pdf.cell(80, 6, "O que está incluso:")

        pdf.set_xy(110, y_inicio)
        pdf.cell(80, 6, "Próximos passos:")

        pdf.set_draw_color(*COR_AZUL_CARRERA)
        pdf.set_line_width(0.5)

        pdf.line(15, y_inicio + 7, 85, y_inicio + 7)
        pdf.line(110, y_inicio + 7, 190, y_inicio + 7)

        beneficios = [
            "Documentação completa",
            "Manutenções preventivas inclusas",
            "Assistência 24h nacional",
            "Gestão de multas",
            "Condutores ilimitados",
            "Proteção completa ao veículo e terceiros"
        ]

        condicoes = [
            "Envio da documentação",
            "Análise de crédito",
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
        pdf.set_xy(10, y_texto + max(len(beneficios), len(condicoes)) * 10 + 6)

        pdf.set_font(f, 'B', 11)
        pdf.set_text_color(*COR_AZUL_CARRERA)
        pdf.multi_cell(
            190,
            8,
            "Fale com seu consultor e garanta sua condição especial.\n(11) 4003-7214",
            align='C'
        )

        conteudo = bytes(pdf.output())
        return conteudo

    finally:
        pdf.limpar_temporarios()