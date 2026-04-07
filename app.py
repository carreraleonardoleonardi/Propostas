# =========================================================
# IMPORTAÇÕES DO PROJETO
# =========================================================
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import json
import datetime
import time
import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# Módulos do projeto
from pdf_generator import gerar_pdf
from utils import formatar_valor_brl, valor_para_float, data_validade_mes_atual
from data import (
    BASES,
    carregar_base,
    carregar_relatorio,
    obter_veiculos,
    obter_dados_veiculo,
    calcular_valor,
    extrair_planos_modelo
)


# =========================================================
# CONFIGURAÇÃO INICIAL DA PÁGINA
# =========================================================
st.set_page_config(
    page_title="Gerador de Propostas",
    page_icon="favicon.png",
    layout="wide"
)


# =========================================================
# CONFIGURAÇÕES DE SEGURANÇA
# =========================================================
SENHA_DESATIVAR = st.secrets["SENHA_DESATIVAR"]
SENHA_ATIVAR    = st.secrets["SENHA_ATIVAR"]

ARQUIVO_STATUS = "status_sistema.json"


# =========================================================
# INTEGRAÇÕES EXTERNAS
# =========================================================
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxzzTh8nlzwFmAdrB7-qXrhUiEeWGGOwH7ZGAuQeaGZHcTVRa1jASmrpU-ADQcCLZgTKw/exec"


# =========================================================
# ASSETS VISUAIS REMOTOS
# =========================================================
URL_LOGO_CARRERA = "https://i.postimg.cc/HWrrsnvR/LOGO-SIGNATURE-AZUL-E-DOURADO.png"
URL_ICON_WPP     = "https://cdn-icons-png.flaticon.com/512/3670/3670051.png"


# =========================================================
# PALETA DE CORES
# =========================================================
AZUL_CARRERA     = (33, 49, 68)
AZUL_CARRERA_HEX = "#213144"


# =========================================================
# CSS GLOBAL DO APP
# =========================================================
st.markdown("""
<style>
#MainMenu {display: none;}
footer {display: none;}
[data-testid="stDecoration"] {display: none;}

.block-container {
    padding-top: 2.5rem;
}

.manutencao-wrapper {
    min-height: 72vh;
    display: flex;
    align-items: center;
    justify-content: center;
}

.manutencao-card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 22px;
    padding: 42px 32px;
    text-align: center;
    max-width: 760px;
    width: 100%;
    box-shadow: 0 10px 30px rgba(0,0,0,0.08);
}

.manutencao-titulo {
    font-size: 40px;
    font-weight: 700;
    color: #213144;
    margin-bottom: 12px;
}

.manutencao-subtitulo {
    font-size: 18px;
    color: #6B7280;
    line-height: 1.6;
    margin-bottom: 10px;
}

.card-gerenciamento {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 18px;
    padding: 24px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.06);
    margin-bottom: 20px;
}

.status-card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 18px;
    padding: 24px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.06);
    margin-bottom: 20px;
}

.small-muted {
    color: #6B7280;
    font-size: 0.92rem;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# ESTADOS DA SESSÃO
# =========================================================
if "abrir_confirmacao_desativar" not in st.session_state:
    st.session_state.abrir_confirmacao_desativar = False

if "abrir_confirmacao_reativar" not in st.session_state:
    st.session_state.abrir_confirmacao_reativar = False

if "ultima_atualizacao" not in st.session_state:
    st.session_state["ultima_atualizacao"] = None


# =========================================================
# FUNÇÕES DE MANUTENÇÃO DO SISTEMA
# =========================================================
def salvar_status_manutencao(status: bool, responsavel: str = "") -> None:
    dados = {
        "modo_manutencao": status,
        "atualizado_em": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "atualizado_por": responsavel
    }
    with open(ARQUIVO_STATUS, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)


def carregar_status_manutencao() -> dict:
    if not os.path.exists(ARQUIVO_STATUS):
        salvar_status_manutencao(False, "")
        return {"modo_manutencao": False, "atualizado_em": "", "atualizado_por": ""}
    try:
        with open(ARQUIVO_STATUS, "r", encoding="utf-8") as f:
            dados = json.load(f)
            return {
                "modo_manutencao": bool(dados.get("modo_manutencao", False)),
                "atualizado_em":   dados.get("atualizado_em", ""),
                "atualizado_por":  dados.get("atualizado_por", "")
            }
    except Exception:
        return {"modo_manutencao": False, "atualizado_em": "", "atualizado_por": ""}


# =========================================================
# FUNÇÃO DE SALVAR PROPOSTA
# =========================================================
def salvar_proposta(cotacoes, vendedor, cliente):
    proposta_id = "CS" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")

    for c in cotacoes:
        payload = {
            "consultor":  vendedor,
            "cliente":    cliente,
            "segmento":   c["segmento"],
            "modelo":     c["modelo"],
            "prazo":      c["prazo"],
            "km":         c["km"],
            "valor":      c["valor"],
            "proposta_id": proposta_id
        }
        try:
            requests.post(
                WEBHOOK_URL,
                data=json.dumps(payload),
                headers={"Content-Type": "text/plain"},
                timeout=30
            )
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

    return proposta_id


# =========================================================
# FUNÇÕES AUXILIARES DO PNG
# =========================================================
def baixar_imagem_pil(url):
    if not isinstance(url, str) or not url.strip().startswith("http"):
        return None
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGBA")
    except Exception:
        return None


def get_font(size=20, bold=False):
    candidatos = [
        "assets/Montserrat-Bold.ttf" if bold else "assets/Montserrat-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for caminho in candidatos:
        try:
            return ImageFont.truetype(caminho, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def medir_texto(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_text_center(draw, box_x1, box_x2, y, text, font, fill):
    w, _ = medir_texto(draw, text, font)
    x = box_x1 + ((box_x2 - box_x1) - w) / 2
    draw.text((x, y), text, font=font, fill=fill)


# =========================================================
# GERAÇÃO DO CARD HTML
# =========================================================
def gerar_card_plano_html(modelo, planos, imagem_url, segmento=""):
    validade    = data_validade_mes_atual()
    qtd_colunas = max(1, len(planos))
    nome_modelo = str(modelo).strip().upper()
    marca       = str(segmento).strip().upper() if segmento else str(modelo).split()[0].upper()

    if qtd_colunas <= 3:
        prazo_font = 26; km_font = 14; valor_font = 18
        bloco_padding = "18px 14px"; bloco_min_height = "220px"; gap_grid = "18px"
    elif qtd_colunas <= 5:
        prazo_font = 22; km_font = 13; valor_font = 16
        bloco_padding = "16px 12px"; bloco_min_height = "220px"; gap_grid = "14px"
    else:
        prazo_font = 18; km_font = 11; valor_font = 14
        bloco_padding = "14px 10px"; bloco_min_height = "220px"; gap_grid = "10px"

    html_planos = ""
    for prazo, itens in planos.items():
        linhas = ""
        for item in itens:
            linhas += f"""
                <div class="plano-linha">
                    <div class="plano-km">{item['km']} km/mês</div>
                    <div class="plano-valor">{item['valor']}</div>
                </div>
            """
        html_planos += f"""
            <div class="plano-coluna">
                <div class="plano-prazo">{prazo} meses</div>
                <div class="plano-bloco">{linhas}</div>
            </div>
        """

    imagem_html = ""
    if isinstance(imagem_url, str) and imagem_url.strip().startswith("http"):
        imagem_html = f'<img src="{imagem_url}" alt="Imagem do veículo">'

    return f"""
    <html>
    <head>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap" rel="stylesheet">
        <style>
            body {{ margin: 0; padding: 14px; background: #f3f3f3; font-family: 'Montserrat', Arial, sans-serif; }}
            .plano-card {{ background: #ffffff; border: 1px solid #d9d9d9; border-radius: 16px; overflow: hidden; box-shadow: 0 8px 24px rgba(0,0,0,0.08); }}
            .plano-header {{ background: linear-gradient(135deg, {AZUL_CARRERA_HEX} 0%, #2e4663 100%); color: #ffffff; padding: 24px 28px; display: flex; justify-content: space-between; align-items: center; gap: 20px; }}
            .plano-header-left {{ flex: 1; }}
            .plano-marca {{ font-size: 15px; font-weight: 700; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.4px; }}
            .plano-modelo {{ font-size: 32px; font-weight: 800; line-height: 1.1; text-transform: uppercase; }}
            .plano-header img {{ max-width: 320px; max-height: 170px; object-fit: contain; }}
            .plano-body {{ background: #f7f7f7; padding: 18px 18px 8px 18px; }}
            .plano-caption {{ color: #3f3f3f; font-size: 20px; font-weight: 800; margin-bottom: 16px; text-transform: uppercase; }}
            .plano-grid {{ display: grid; grid-template-columns: repeat({qtd_colunas}, minmax(140px, 1fr)); gap: {gap_grid}; align-items: start; }}
            .plano-coluna {{ text-align: center; }}
            .plano-prazo {{ font-size: {prazo_font}px; font-weight: 800; color: {AZUL_CARRERA_HEX}; margin-bottom: 10px; }}
            .plano-bloco {{ background: rgba(35, 35, 35, 0.88); color: white; border-radius: 20px; padding: {bloco_padding}; min-height: {bloco_min_height}; box-shadow: 0 8px 18px rgba(0,0,0,0.16); }}
            .plano-linha {{ margin-bottom: 12px; }}
            .plano-km {{ font-size: {km_font}px; opacity: 0.95; font-weight: 500; }}
            .plano-valor {{ font-size: {valor_font}px; font-weight: 800; }}
            .plano-footer {{ padding: 18px 18px 22px 18px; background: #f7f7f7; }}
            .plano-aviso {{ font-size: 14px; color: #4d4d4d; margin-bottom: 10px; font-weight: 500; }}
            .plano-validade {{ font-size: 14px; color: #4d4d4d; margin-bottom: 16px; font-weight: 800; }}
            .plano-contato {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }}
            .plano-telefone-wrap {{ display: flex; align-items: center; gap: 10px; }}
            .plano-wpp {{ width: 28px; height: 28px; object-fit: contain; }}
            .plano-telefone {{ font-size: 24px; font-weight: 800; color: {AZUL_CARRERA_HEX}; }}
            .plano-logo-final-img {{ height: 36px; object-fit: contain; }}
        </style>
    </head>
    <body>
        <div class="plano-card">
            <div class="plano-header">
                <div class="plano-header-left">
                    <div class="plano-marca">{marca}</div>
                    <div class="plano-modelo">{nome_modelo}</div>
                </div>
                {imagem_html}
            </div>
            <div class="plano-body">
                <div class="plano-caption">PLANOS DISPONÍVEIS:</div>
                <div class="plano-grid">{html_planos}</div>
            </div>
            <div class="plano-footer">
                <div class="plano-aviso">A cor escolhida pode alterar o preço. Consulte disponibilidade e condições vigentes.</div>
                <div class="plano-validade">Planos válidos até {validade}</div>
                <div class="plano-contato">
                    <div class="plano-telefone-wrap">
                        <img class="plano-wpp" src="{URL_ICON_WPP}" alt="WhatsApp">
                        <div class="plano-telefone">4003.7214</div>
                    </div>
                    <div>
                        <img class="plano-logo-final-img" src="{URL_LOGO_CARRERA}" alt="Carrera Signature">
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


# =========================================================
# GERAÇÃO DO CARD PNG
# =========================================================
def gerar_card_png(modelo, planos, imagem_url, segmento=""):
    largura = 1800
    margem  = 18
    card_x1, card_x2 = margem, largura - margem
    qtd_colunas = max(1, len(planos))

    if qtd_colunas <= 3:
        prazo_font_sz = 28; km_font_sz = 18; valor_font_sz = 24
        linha_gap = 72; gap = 18; bloco_padding_top = 24; bloco_padding_bottom = 24
    elif qtd_colunas <= 5:
        prazo_font_sz = 24; km_font_sz = 16; valor_font_sz = 21
        linha_gap = 66; gap = 14; bloco_padding_top = 22; bloco_padding_bottom = 22
    else:
        prazo_font_sz = 20; km_font_sz = 14; valor_font_sz = 18
        linha_gap = 58; gap = 10; bloco_padding_top = 18; bloco_padding_bottom = 18

    header_h         = 260
    body_caption_h   = 70
    prazo_area_h     = 52
    maior_qtd_linhas = max(len(itens) for itens in planos.values()) if planos else 1
    bloco_h          = bloco_padding_top + bloco_padding_bottom + (maior_qtd_linhas * linha_gap)
    footer_top_gap   = 34
    footer_h         = footer_top_gap + 28 + 28 + 62 + 60

    altura = margem * 2 + header_h + body_caption_h + prazo_area_h + bloco_h + footer_h

    bg   = Image.new("RGBA", (largura, altura), (243, 243, 243, 255))
    draw = ImageDraw.Draw(bg)

    card_y1, card_y2 = margem, altura - margem

    draw.rounded_rectangle([card_x1, card_y1, card_x2, card_y2], radius=22,
        fill=(255, 255, 255, 255), outline=(217, 217, 217, 255), width=2)
    draw.rounded_rectangle([card_x1, card_y1, card_x2, card_y1 + header_h], radius=22,
        fill=(*AZUL_CARRERA, 255))
    draw.rectangle([card_x1, card_y1 + 30, card_x2, card_y1 + header_h],
        fill=(*AZUL_CARRERA, 255))

    nome_modelo = str(modelo).strip().upper()
    marca       = str(segmento).strip().upper() if segmento else str(modelo).split()[0].upper()

    draw.text((card_x1 + 28, card_y1 + 48), marca,       font=get_font(35, bold=True),  fill=(255, 255, 255, 255))
    draw.text((card_x1 + 28, card_y1 + 90), nome_modelo, font=get_font(40, bold=False), fill=(255, 255, 255, 255))

    foto = baixar_imagem_pil(imagem_url)
    if foto:
        foto.thumbnail((360, 190))
        bg.paste(foto, (card_x2 - foto.width - 28, card_y1 + 30), foto)

    body_top = card_y1 + header_h + 24
    draw.text((card_x1 + 22, body_top), "Planos Disponíveis:", font=get_font(34, bold=False), fill=(66, 66, 66, 255))

    grid_top   = body_top + 62
    grid_left  = card_x1 + 22
    grid_right = card_x2 - 22
    col_w      = int((grid_right - grid_left - gap * (qtd_colunas - 1)) / qtd_colunas)

    for i, (prazo, itens) in enumerate(planos.items()):
        x = grid_left + i * (col_w + gap)
        draw_text_center(draw, x, x + col_w, grid_top, f"{prazo} meses",
            get_font(prazo_font_sz, bold=True), AZUL_CARRERA + (255,))

        bloco_y = grid_top + prazo_area_h
        draw.rounded_rectangle([x, bloco_y, x + col_w, bloco_y + bloco_h],
            radius=22, fill=(56, 56, 56, 235))

        cursor_y = bloco_y + bloco_padding_top
        for item in itens:
            draw_text_center(draw, x, x + col_w, cursor_y,
                f"{item['km']} km/mês", get_font(km_font_sz), (240, 240, 240, 255))
            draw_text_center(draw, x, x + col_w, cursor_y + 24,
                f"{item['valor']}", get_font(valor_font_sz, bold=True), (255, 255, 255, 255))
            cursor_y += linha_gap

    footer_y = grid_top + prazo_area_h + bloco_h + footer_top_gap
    validade  = data_validade_mes_atual()

    draw.text((card_x1 + 22, footer_y),
        "A cor escolhida pode alterar o preço. Consulte disponibilidade e condições vigentes.",
        font=get_font(22), fill=(66, 66, 66, 255))
    draw.text((card_x1 + 22, footer_y + 34),
        f"Planos válidos até {validade}, valores sujeitos a alteração.",
        font=get_font(22, bold=True), fill=(66, 66, 66, 255))

    icon  = baixar_imagem_pil(URL_ICON_WPP)
    y_tel = footer_y + 72
    x_tel = card_x1 + 21
    if icon:
        icon.thumbnail((34, 34))
        bg.paste(icon, (x_tel, y_tel - 2), icon)
        x_tel += 44
    draw.text((x_tel, y_tel), "4003-7214", font=get_font(34, bold=True), fill=AZUL_CARRERA + (255,))

    logo = baixar_imagem_pil(URL_LOGO_CARRERA)
    if logo:
        logo.thumbnail((220, 70))
        bg.paste(logo, (card_x2 - logo.width - 22, footer_y + 58), logo)

    out = BytesIO()
    bg.convert("RGB").save(out, format="PNG")
    out.seek(0)
    return out.getvalue()


# =========================================================
# LEITURA DO STATUS ATUAL DO SISTEMA
# =========================================================
status_sistema  = carregar_status_manutencao()
modo_manutencao = status_sistema.get("modo_manutencao", False)


# =========================================================
# SIDEBAR PRINCIPAL
# =========================================================
with st.sidebar:
    st.image(URL_LOGO_CARRERA, width=180)

    if not modo_manutencao:
        st.markdown("### 👤 Dados da Proposta")
        vendedor           = st.text_input("Consultor *")
        cliente            = st.text_input("Cliente *")
        qtd                = st.selectbox("Qtd ofertas", [1, 2, 3], index=2)
        progress_container = st.empty()
    else:
        vendedor           = ""
        cliente            = ""
        qtd                = 3
        progress_container = st.empty()


# =========================================================
# TELA DE MANUTENÇÃO
# =========================================================
if modo_manutencao:
    st.markdown("""
    <div class="manutencao-wrapper">
        <div class="manutencao-card">
            <div class="manutencao-titulo">🚧 Sistema em manutenção</div>
            <div class="manutencao-subtitulo">
                Estamos atualizando a base de dados.<br>
                O sistema será reativado em breve.
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("🔓 Reativar sistema")
    responsavel_reativar = st.text_input("Nome do responsável",
        value=status_sistema.get("atualizado_por", "") or "Administrador",
        key="responsavel_reativar")

    if st.button("🟢 Reativar sistema", use_container_width=True):
        st.session_state.abrir_confirmacao_reativar = True

    if st.session_state.abrir_confirmacao_reativar:
        senha_ativar = st.text_input("Senha de reativação", type="password", key="senha_ativar_input")
        col_a, col_b = st.columns(2)

        with col_a:
            if st.button("Confirmar reativação", use_container_width=True, key="confirmar_reativar"):
                if senha_ativar == SENHA_ATIVAR:
                    salvar_status_manutencao(False, responsavel_reativar or "Administrador")
                    st.session_state.abrir_confirmacao_reativar = False
                    st.success("Sistema reativado com sucesso.")
                    st.rerun()
                else:
                    st.error("Senha incorreta.")

        with col_b:
            if st.button("Cancelar", use_container_width=True, key="cancelar_reativar"):
                st.session_state.abrir_confirmacao_reativar = False
                st.rerun()

    st.stop()


# =========================================================
# ABAS PRINCIPAIS
# =========================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🚗 Propostas", "📊 Relatório", "🛠️ Gerenciamento", "🧮 Simulador", "🔍 Comparativo"
])


# =========================================================
# ABA 1 - PROPOSTAS
# =========================================================
with tab1:
    st.title("🚗 Gerador de Propostas da Carrera Signature")

    cotacoes = []
    cols     = st.columns(3)

    for i in range(3):
        with cols[i]:
            if i < qtd:
                st.subheader(f"Oferta {i + 1}:")

                segmento = st.selectbox("Segmento", list(BASES.keys()), key=f"seg_{i}")
                df       = carregar_base(BASES[segmento])

                if "nome" not in df.columns:
                    st.error(f"A base '{segmento}' não possui a coluna 'nome'.")
                    continue

                veiculos = obter_veiculos(df)

                if not veiculos:
                    st.warning(f"Sem veículos para {segmento}.")
                    continue

                veiculo = st.selectbox("Veículo", veiculos, key=f"vei_{i}", index=1)
                dados   = obter_dados_veiculo(df, veiculo)

                if dados is None:
                    st.warning("Veículo não encontrado.")
                    continue

                if "imagem" in dados.index and pd.notna(dados["imagem"]):
                    st.image(dados["imagem"], width="stretch")

                prazo = st.selectbox("Prazo", [12, 18, 24, 36, 48], key=f"prazo_{i}")
                km    = st.selectbox("KM", [500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000], key=f"km_{i}")

                valor = calcular_valor(df, dados, km, prazo)
                st.success(str(valor))

                cotacoes.append({
                    "segmento": segmento,
                    "modelo":   veiculo,
                    "prazo":    prazo,
                    "km":       km,
                    "valor":    str(valor),
                    "url_foto": dados["imagem"] if "imagem" in dados.index else ""
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


# =========================================================
# ABA 2 - RELATÓRIO / DASHBOARD
# =========================================================
with tab2:
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
        st.stop()

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
    top_modelo    = df_filtro["modelo"].mode()[0]    if ("modelo" in df_filtro.columns    and not df_filtro.empty and not df_filtro["modelo"].dropna().empty)    else "-"

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


# =========================================================
# ABA 3 - GERENCIAMENTO
# =========================================================
with tab3:
    st.title("🛠️ Gerenciamento")
    st.caption("Área administrativa para controle do sistema.")

    col_status_1, col_status_2 = st.columns([1, 4])

    with col_status_1:
        if modo_manutencao:
            st.error("🔴 Offline")
        else:
            st.success("🟢 Online")

    with col_status_2:
        atualizado_por = status_sistema.get("atualizado_por", "-") or "-"
        atualizado_em  = status_sistema.get("atualizado_em",  "-") or "-"
        st.write("O sistema está em modo manutenção." if modo_manutencao else "O sistema está ativo e disponível normalmente.")
        st.markdown(
            f"<div class='small-muted'><b>Última alteração:</b> {atualizado_em} | <b>Por:</b> {atualizado_por}</div>",
            unsafe_allow_html=True
        )

    st.subheader("Controle do sistema")

    responsavel_admin = st.text_input("Nome do responsável",
        value=status_sistema.get("atualizado_por", "") or "Administrador",
        key="responsavel_admin")

    if not modo_manutencao:
        st.warning("Ao desativar o sistema, todos os usuários verão a tela de manutenção.")

        if st.button("🔴 Tirar sistema do ar", use_container_width=True):
            st.session_state.abrir_confirmacao_desativar = True

        if st.session_state.abrir_confirmacao_desativar:
            senha_desativar = st.text_input("Senha de desativação", type="password", key="senha_desativacao_gerenciamento")
            col1, col2 = st.columns(2)

            with col1:
                if st.button("Confirmar desativação", use_container_width=True, key="btn_desativar_gerenciamento"):
                    if senha_desativar == SENHA_DESATIVAR:
                        salvar_status_manutencao(True, responsavel_admin or "Administrador")
                        st.session_state.abrir_confirmacao_desativar = False
                        st.success("Sistema colocado em manutenção.")
                        st.rerun()
                    else:
                        st.error("Senha incorreta.")
            with col2:
                if st.button("Cancelar", use_container_width=True, key="btn_cancelar_desativacao_gerenciamento"):
                    st.session_state.abrir_confirmacao_desativar = False
                    st.rerun()
    else:
        st.info("O sistema já está em manutenção. A reativação deve ser feita pela tela principal.")


# =========================================================
# ABA 4 - SIMULADOR
# =========================================================
with tab4:
    st.title("🧮 Simulador de Plano")
    st.caption("Selecione o segmento e o modelo para montar o card comercial do plano.")

    col1, col2 = st.columns(2)

    with col1:
        segmento_sim = st.selectbox("Segmento", list(BASES.keys()), key="sim_segmento")

    df_sim              = carregar_base(BASES[segmento_sim])
    modelos_disponiveis = obter_veiculos(df_sim)

    with col2:
        modelo_sim = st.selectbox("Modelo", modelos_disponiveis, key="sim_modelo", index=0)

    if st.button("✨ Montar card do plano", use_container_width=True):
        planos, imagem = extrair_planos_modelo(df_sim, modelo_sim)

        if not planos:
            st.warning("Não foram encontrados planos para este modelo.")
        else:
            html_card   = gerar_card_plano_html(modelo_sim, planos, imagem, segmento_sim)
            altura_card = 760 if len(planos) <= 3 else 920 if len(planos) <= 5 else 1120
            components.html(html_card, height=altura_card, scrolling=True)

            png_bytes = gerar_card_png(modelo_sim, planos, imagem, segmento_sim)
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



# =========================================================
# ABA 5 - COMPARATIVO
# =========================================================
with tab5:
    st.title("🔍 Comparativo de Planos")
    st.caption("Filtre por segmento, prazo, KM e faixa de preço. Deixe qualquer filtro vazio para buscar em todos.")

    # Segmento
    segmentos_selecionados = st.multiselect(
        "Segmento",
        options=list(BASES.keys()),
        default=[],
        placeholder="Todos os segmentos"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        prazos_selecionados = st.multiselect(
            "Prazo (meses)",
            options=[12, 18, 24, 36, 48],
            default=[],
            placeholder="Todos os prazos"
        )

    with col2:
        kms_selecionados = st.multiselect(
            "KM por mês",
            options=[500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000],
            default=[],
            placeholder="Todos os KMs"
        )

    with col3:
        preco_min = st.number_input(
            "Preço mínimo (R$)",
            min_value=0,
            max_value=99999,
            value=0,
            step=100
        )

    with col4:
        preco_max = st.number_input(
            "Preço máximo (R$)",
            min_value=0,
            max_value=99999,
            value=99999,
            step=100
        )

    st.divider()

    if st.button("🔍 Buscar ofertas", use_container_width=True):

        # Vazio = todos
        bases_busca  = {k: v for k, v in BASES.items() if k in segmentos_selecionados} if segmentos_selecionados else BASES
        prazos_busca = prazos_selecionados if prazos_selecionados else [12, 18, 24, 36, 48]
        kms_busca    = kms_selecionados    if kms_selecionados    else [500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000]

        resultados = []

        with st.spinner("Buscando..."):
            for segmento, url in bases_busca.items():
                try:
                    df_comp = carregar_base(url)

                    if "nome" not in df_comp.columns:
                        continue

                    for _, row in df_comp.iterrows():
                        nome = row.get("nome", "")
                        if pd.isna(nome) or not str(nome).strip():
                            continue

                        for prazo in prazos_busca:
                            for km in kms_busca:
                                col_preco = f"preco{km}{prazo}"

                                if col_preco not in df_comp.columns:
                                    continue

                                valor_raw = row.get(col_preco, None)

                                if pd.isna(valor_raw):
                                    continue

                                valor_str = str(valor_raw).strip()
                                if not valor_str or valor_str.lower() == "nan":
                                    continue
                                if "nao disponivel" in valor_str.lower():
                                    continue
                                if "sob consulta" in valor_str.lower():
                                    continue

                                valor_num = valor_para_float(valor_str)
                                if valor_num is None:
                                    continue

                                if preco_min <= valor_num <= preco_max:
                                    resultados.append({
                                        "Segmento":   segmento,
                                        "Modelo":     str(nome).strip(),
                                        "Prazo":      f"{prazo} meses",
                                        "KM/mês":     f"{km} km",
                                        "Valor":      valor_num,
                                        "Valor (R$)": formatar_valor_brl(valor_num)
                                    })

                except Exception as e:
                    st.warning(f"Erro ao carregar {segmento}: {e}")
                    continue

        if not resultados:
            st.info("Nenhuma oferta encontrada com os filtros selecionados.")
        else:
            df_resultado = (
                pd.DataFrame(resultados)
                .sort_values("Valor")
                .reset_index(drop=True)
            )

            df_exibir = df_resultado.drop(columns=["Valor"])

            st.success(f"{len(df_resultado)} oferta(s) encontrada(s)")

            st.dataframe(df_exibir, width="stretch", hide_index=True)