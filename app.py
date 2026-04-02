import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import json
import datetime
import time
import os
import re
import calendar
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from pdf_generator import gerar_pdf

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="Gerador de Propostas",
    page_icon="🚗",
    layout="wide"
)

# =========================================================
# SENHAS NO CÓDIGO
# =========================================================
SENHA_DESATIVAR = "DesativaSignature#2026"
SENHA_ATIVAR = "AtivaSignature#2026"
ARQUIVO_STATUS = "status_sistema.json"

# =========================================================
# WEBHOOK / PLANILHA RELATÓRIO
# =========================================================
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxzzTh8nlzwFmAdrB7-qXrhUiEeWGGOwH7ZGAuQeaGZHcTVRa1jASmrpU-ADQcCLZgTKw/exec"
URL_RELATORIO = "https://docs.google.com/spreadsheets/d/1bxjKSfD2MpBpV4swaBCjkhi8ElHV_8M97zxI6jgtv0w/export?format=csv"

# =========================================================
# ASSETS REMOTOS
# =========================================================
URL_LOGO_CARRERA = "https://i.postimg.cc/HWrrsnvR/LOGO-SIGNATURE-AZUL-E-DOURADO.png"
URL_ICON_WPP = "https://cdn-icons-png.flaticon.com/512/3670/3670051.png"

# =========================================================
# CSS GLOBAL
# =========================================================
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.block-container {
    padding-top: 1.5rem;
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
# BASES
# =========================================================
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

# =========================================================
# SESSION STATE
# =========================================================
if "abrir_confirmacao_desativar" not in st.session_state:
    st.session_state.abrir_confirmacao_desativar = False

if "abrir_confirmacao_reativar" not in st.session_state:
    st.session_state.abrir_confirmacao_reativar = False

if "ultima_atualizacao" not in st.session_state:
    st.session_state["ultima_atualizacao"] = None

# =========================================================
# FUNÇÕES - STATUS LOCAL
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
        return {
            "modo_manutencao": False,
            "atualizado_em": "",
            "atualizado_por": ""
        }

    try:
        with open(ARQUIVO_STATUS, "r", encoding="utf-8") as f:
            dados = json.load(f)
            return {
                "modo_manutencao": bool(dados.get("modo_manutencao", False)),
                "atualizado_em": dados.get("atualizado_em", ""),
                "atualizado_por": dados.get("atualizado_por", "")
            }
    except Exception:
        return {
            "modo_manutencao": False,
            "atualizado_em": "",
            "atualizado_por": ""
        }

# =========================================================
# FUNÇÕES - DADOS
# =========================================================
@st.cache_data
def carregar_base(url):
    df = pd.read_csv(url)

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("utf-8")
        .str.replace(" ", "", regex=False)
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
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("utf-8")
        .str.replace(" ", "", regex=False)
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
            .str.strip()
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
                headers={"Content-Type": "text/plain"},
                timeout=30
            )
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

    return proposta_id

# =========================================================
# FUNÇÕES - SIMULADOR
# =========================================================
def tratar_texto_modelo(modelo: str):
    modelo = str(modelo).strip()
    partes = modelo.split(" ", 1)

    if len(partes) == 1:
        return partes[0], "", ""

    marca = partes[0]
    resto = partes[1]

    if len(resto) > 34:
        palavras = resto.split()
        linha_1 = ""
        linha_2 = ""

        for palavra in palavras:
            if len((linha_1 + " " + palavra).strip()) <= 28:
                linha_1 = (linha_1 + " " + palavra).strip()
            else:
                linha_2 = (linha_2 + " " + palavra).strip()

        return marca, linha_1, linha_2

    return marca, resto, ""


def valor_para_float(valor):
    try:
        valor_limpo = (
            str(valor)
            .replace("R$", "")
            .replace(".", "")
            .replace(",", ".")
            .strip()
        )
        return float(valor_limpo)
    except Exception:
        return None


def formatar_valor_brl(valor):
    try:
        numero = valor_para_float(valor)
        if numero is None:
            return str(valor)
        inteiro = int(round(numero))
        return f"R$ {inteiro}"
    except Exception:
        return str(valor)


def data_validade_mes_atual():
    hoje = datetime.date.today()
    ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
    data_final = datetime.date(hoje.year, hoje.month, ultimo_dia)
    return data_final.strftime("%d/%m/%Y")


def extrair_planos_modelo(df, modelo):
    dados_filtrados = df[df["nome"] == modelo]

    if dados_filtrados.empty:
        return {}, ""

    row = dados_filtrados.iloc[0]
    imagem = row.get("imagem", "")

    planos = {}
    padrao = re.compile(r"^preco(\d+)(\d{2})$")

    for col in df.columns:
        match = padrao.match(str(col))
        if not match:
            continue

        km = int(match.group(1))
        prazo = int(match.group(2))

        valor = row.get(col, None)

        if pd.isna(valor):
            continue

        valor_str = str(valor).strip()
        if not valor_str or valor_str.lower() == "nan":
            continue

        if "nao disponivel" in valor_str.lower():
            continue

        if prazo not in planos:
            planos[prazo] = []

        planos[prazo].append({
            "km": km,
            "valor": formatar_valor_brl(valor)
        })

    planos_ordenados = {}
    for prazo in sorted(planos.keys()):
        planos_ordenados[prazo] = sorted(planos[prazo], key=lambda x: x["km"])

    return planos_ordenados, imagem


def gerar_card_plano_html(modelo, planos, imagem_url):
    marca, linha_1, linha_2 = tratar_texto_modelo(modelo)
    validade = data_validade_mes_atual()
    qtd_colunas = max(1, len(planos))

    if qtd_colunas <= 3:
        prazo_font = 26
        km_font = 14
        valor_font = 18
        bloco_padding = "18px 14px"
        bloco_min_height = "220px"
        gap_grid = "18px"
    elif qtd_colunas <= 5:
        prazo_font = 22
        km_font = 13
        valor_font = 16
        bloco_padding = "16px 12px"
        bloco_min_height = "220px"
        gap_grid = "14px"
    else:
        prazo_font = 18
        km_font = 11
        valor_font = 14
        bloco_padding = "14px 10px"
        bloco_min_height = "220px"
        gap_grid = "10px"

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
                <div class="plano-bloco">
                    {linhas}
                </div>
            </div>
        """

    imagem_html = ""
    if isinstance(imagem_url, str) and imagem_url.strip().startswith("http"):
        imagem_html = f'<img src="{imagem_url}" alt="Imagem do veículo">'
    else:
        imagem_html = ""

    return f"""
    <html>
    <head>
        <style>
            body {{
                margin: 0;
                padding: 14px;
                background: #f3f3f3;
                font-family: Arial, sans-serif;
            }}

            .plano-card {{
                background: #ffffff;
                border: 1px solid #d9d9d9;
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 8px 24px rgba(0,0,0,0.08);
            }}

            .plano-header {{
                background: linear-gradient(135deg, #173B85 0%, #3A62C7 100%);
                color: #ffffff;
                padding: 24px 28px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 20px;
            }}

            .plano-header-left {{
                flex: 1;
            }}

            .plano-marca {{
                font-size: 15px;
                font-weight: 700;
                margin-bottom: 6px;
                text-transform: uppercase;
            }}

            .plano-modelo {{
                font-size: 34px;
                font-weight: 800;
                line-height: 1.05;
                margin-bottom: 6px;
            }}

            .plano-submodelo {{
                font-size: 18px;
                font-weight: 600;
                line-height: 1.2;
            }}

            .plano-header img {{
                max-width: 320px;
                max-height: 170px;
                object-fit: contain;
            }}

            .plano-body {{
                background: #f7f7f7;
                padding: 18px 18px 8px 18px;
            }}

            .plano-caption {{
                color: #4d4d4d;
                font-size: 20px;
                font-weight: 700;
                margin-bottom: 16px;
            }}

            .plano-grid {{
                display: grid;
                grid-template-columns: repeat({qtd_colunas}, minmax(140px, 1fr));
                gap: {gap_grid};
                align-items: start;
            }}

            .plano-coluna {{
                text-align: center;
            }}

            .plano-prazo {{
                font-size: {prazo_font}px;
                font-weight: 800;
                color: #244760;
                margin-bottom: 10px;
            }}

            .plano-bloco {{
                background: rgba(35, 35, 35, 0.88);
                color: white;
                border-radius: 20px;
                padding: {bloco_padding};
                min-height: {bloco_min_height};
                box-shadow: 0 8px 18px rgba(0,0,0,0.16);
            }}

            .plano-linha {{
                margin-bottom: 12px;
            }}

            .plano-km {{
                font-size: {km_font}px;
                opacity: 0.95;
                line-height: 1.2;
            }}

            .plano-valor {{
                font-size: {valor_font}px;
                font-weight: 800;
                line-height: 1.2;
            }}

            .plano-footer {{
                padding: 18px 18px 22px 18px;
                background: #f7f7f7;
            }}

            .plano-aviso {{
                font-size: 14px;
                color: #4d4d4d;
                margin-bottom: 10px;
            }}

            .plano-validade {{
                font-size: 14px;
                color: #4d4d4d;
                margin-bottom: 16px;
                font-weight: 700;
            }}

            .plano-contato {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 16px;
                flex-wrap: wrap;
            }}

            .plano-telefone-wrap {{
                display: flex;
                align-items: center;
                gap: 10px;
            }}

            .plano-wpp {{
                width: 28px;
                height: 28px;
                object-fit: contain;
            }}

            .plano-telefone {{
                font-size: 24px;
                font-weight: 800;
                color: #143B57;
            }}

            .plano-texto-final {{
                display: flex;
                align-items: center;
                gap: 10px;
            }}

            .plano-logo-final-img {{
                height: 36px;
                object-fit: contain;
            }}

            @media (max-width: 1200px) {{
                .plano-grid {{
                    grid-template-columns: repeat(2, 1fr);
                }}
            }}

            @media (max-width: 768px) {{
                .plano-header {{
                    flex-direction: column;
                    align-items: flex-start;
                }}

                .plano-grid {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="plano-card">
            <div class="plano-header">
                <div class="plano-header-left">
                    <div class="plano-marca">{marca}</div>
                    <div class="plano-modelo">{linha_1}</div>
                    <div class="plano-submodelo">{linha_2}</div>
                </div>
                {imagem_html}
            </div>

            <div class="plano-body">
                <div class="plano-caption">PLANOS DISPONÍVEIS:</div>
                <div class="plano-grid">
                    {html_planos}
                </div>
            </div>

            <div class="plano-footer">
                <div class="plano-aviso">
                    A cor escolhida pode alterar o preço. Consulte disponibilidade e condições vigentes.
                </div>
                <div class="plano-validade">
                    Planos válidos até {validade}
                </div>
                <div class="plano-contato">
                    <div class="plano-telefone-wrap">
                        <img class="plano-wpp" src="{URL_ICON_WPP}" alt="WhatsApp">
                        <div class="plano-telefone">4003.7214</div>
                    </div>
                    <div class="plano-texto-final">
                        <img class="plano-logo-final-img" src="{URL_LOGO_CARRERA}" alt="Carrera Signature">
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


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


def gerar_card_png(modelo, planos, imagem_url):
    largura = 1800
    margem = 18
    card_x1, card_x2 = margem, largura - margem
    qtd_colunas = max(1, len(planos))

    if qtd_colunas <= 3:
        prazo_font_sz = 28
        km_font_sz = 18
        valor_font_sz = 24
        linha_gap = 72
        gap = 18
        bloco_padding_top = 24
        bloco_padding_bottom = 24
    elif qtd_colunas <= 5:
        prazo_font_sz = 24
        km_font_sz = 16
        valor_font_sz = 21
        linha_gap = 66
        gap = 14
        bloco_padding_top = 22
        bloco_padding_bottom = 22
    else:
        prazo_font_sz = 20
        km_font_sz = 14
        valor_font_sz = 18
        linha_gap = 58
        gap = 10
        bloco_padding_top = 18
        bloco_padding_bottom = 18

    header_h = 260
    body_caption_h = 70
    prazo_area_h = 52

    maior_qtd_linhas = max(len(itens) for itens in planos.values()) if planos else 1
    bloco_h = bloco_padding_top + bloco_padding_bottom + (maior_qtd_linhas * linha_gap)

    footer_top_gap = 34
    aviso_h = 28
    validade_h = 28
    contato_h = 62
    footer_bottom_pad = 26

    footer_h = footer_top_gap + aviso_h + validade_h + contato_h + footer_bottom_pad

    altura = (
        margem * 2
        + header_h
        + body_caption_h
        + prazo_area_h
        + bloco_h
        + footer_h
    )

    bg = Image.new("RGBA", (largura, altura), (243, 243, 243, 255))
    draw = ImageDraw.Draw(bg)

    card_y1, card_y2 = margem, altura - margem

    draw.rounded_rectangle(
        [card_x1, card_y1, card_x2, card_y2],
        radius=22,
        fill=(255, 255, 255, 255),
        outline=(217, 217, 217, 255),
        width=2
    )

    draw.rounded_rectangle(
        [card_x1, card_y1, card_x2, card_y1 + header_h],
        radius=22,
        fill=(46, 86, 191, 255)
    )
    draw.rectangle(
        [card_x1, card_y1 + 30, card_x2, card_y1 + header_h],
        fill=(46, 86, 191, 255)
    )

    marca, linha_1, linha_2 = tratar_texto_modelo(modelo)

    font_marca = get_font(24, bold=True)
    font_modelo = get_font(58, bold=True)
    font_sub = get_font(34, bold=True)

    draw.text((card_x1 + 28, card_y1 + 48), marca.upper(), font=font_marca, fill=(255, 255, 255, 255))
    draw.text((card_x1 + 28, card_y1 + 90), linha_1, font=font_modelo, fill=(255, 255, 255, 255))
    if linha_2:
        draw.text((card_x1 + 28, card_y1 + 160), linha_2, font=font_sub, fill=(255, 255, 255, 255))

    foto = baixar_imagem_pil(imagem_url)
    if foto:
        max_w, max_h = 360, 190
        foto.thumbnail((max_w, max_h))
        fx = card_x2 - foto.width - 28
        fy = card_y1 + 30
        bg.paste(foto, (fx, fy), foto)

    body_top = card_y1 + header_h + 24
    font_caption = get_font(34, bold=True)
    draw.text((card_x1 + 22, body_top), "PLANOS DISPONÍVEIS:", font=font_caption, fill=(66, 66, 66, 255))

    grid_top = body_top + 62
    grid_left = card_x1 + 22
    grid_right = card_x2 - 22
    col_w = int((grid_right - grid_left - gap * (qtd_colunas - 1)) / qtd_colunas)

    font_prazo = get_font(prazo_font_sz, bold=True)
    font_km = get_font(km_font_sz, bold=False)
    font_valor = get_font(valor_font_sz, bold=True)

    for i, (prazo, itens) in enumerate(planos.items()):
        x = grid_left + i * (col_w + gap)

        prazo_text = f"{prazo} meses"
        draw_text_center(draw, x, x + col_w, grid_top, prazo_text, font_prazo, (34, 73, 104, 255))

        bloco_y = grid_top + prazo_area_h
        draw.rounded_rectangle(
            [x, bloco_y, x + col_w, bloco_y + bloco_h],
            radius=22,
            fill=(56, 56, 56, 235)
        )

        cursor_y = bloco_y + bloco_padding_top

        for item in itens:
            km_text = f"{item['km']} km/mês"
            valor_text = f"{item['valor']} /mês"

            draw_text_center(draw, x, x + col_w, cursor_y, km_text, font_km, (240, 240, 240, 255))
            draw_text_center(draw, x, x + col_w, cursor_y + 24, valor_text, font_valor, (255, 255, 255, 255))

            cursor_y += linha_gap

    footer_y = grid_top + prazo_area_h + bloco_h + footer_top_gap

    font_footer = get_font(22, bold=False)
    font_validade = get_font(22, bold=True)
    font_tel = get_font(34, bold=True)

    aviso = "A cor escolhida pode alterar o preço. Consulte disponibilidade e condições vigentes."
    validade = f"Planos válidos até {data_validade_mes_atual()}"

    draw.text((card_x1 + 22, footer_y), aviso, font=font_footer, fill=(66, 66, 66, 255))
    draw.text((card_x1 + 22, footer_y + 34), validade, font=font_validade, fill=(66, 66, 66, 255))

    icon = baixar_imagem_pil(URL_ICON_WPP)
    y_tel = footer_y + 84
    x_tel = card_x1 + 22

    if icon:
        icon.thumbnail((34, 34))
        bg.paste(icon, (x_tel, y_tel - 2), icon)
        x_tel += 44

    draw.text((x_tel, y_tel), "4003.7214", font=font_tel, fill=(20, 59, 87, 255))

    logo = baixar_imagem_pil(URL_LOGO_CARRERA)
    if logo:
        logo.thumbnail((220, 70))
        lx = card_x2 - logo.width - 22
        ly = footer_y + 68
        bg.paste(logo, (lx, ly), logo)
    else:
        font_logo = get_font(28, bold=True)
        texto = "Carrera Signature"
        tw, _ = medir_texto(draw, texto, font_logo)
        draw.text((card_x2 - tw - 22, footer_y + 92), texto, font=font_logo, fill=(140, 107, 47, 255))

    out = BytesIO()
    bg.convert("RGB").save(out, format="PNG")
    out.seek(0)
    return out.getvalue()

# =========================================================
# STATUS ATUAL
# =========================================================
status_sistema = carregar_status_manutencao()
modo_manutencao = status_sistema.get("modo_manutencao", False)

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.image(URL_LOGO_CARRERA, width=180)

    if not modo_manutencao:
        st.markdown("### 👤 Dados da Proposta")
        vendedor = st.text_input("Consultor *")
        cliente = st.text_input("Cliente *")
        qtd = st.selectbox("Qtd ofertas", [1, 2, 3], index=2)
        progress_container = st.empty()
    else:
        vendedor = ""
        cliente = ""
        qtd = 3
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

    responsavel_reativar = st.text_input(
        "Nome do responsável",
        value=status_sistema.get("atualizado_por", "") or "Administrador",
        key="responsavel_reativar"
    )

    if st.button("🟢 Reativar sistema", use_container_width=True):
        st.session_state.abrir_confirmacao_reativar = True

    if st.session_state.abrir_confirmacao_reativar:
        senha_ativar = st.text_input(
            "Senha de reativação",
            type="password",
            key="senha_ativar_input"
        )

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
# ABAS
# =========================================================
tab1, tab2, tab3, tab4 = st.tabs(["🚗 Propostas", "📊 Relatório", "🛠️ Gerenciamento", "🧮 Simulador"])

# =========================================================
# PROPOSTAS
# =========================================================
with tab1:
    st.title("🚗 Gerador de Propostas da Carrera Signature")

    cotacoes = []
    cols = st.columns(3)

    for i in range(3):
        with cols[i]:
            if i < qtd:
                st.subheader(f"Oferta {i + 1}:")

                segmento = st.selectbox("Segmento", list(BASES.keys()), key=f"seg_{i}")
                df = carregar_base(BASES[segmento])

                if "nome" not in df.columns:
                    st.error(f"A base do segmento '{segmento}' não possui a coluna 'nome'.")
                    continue

                veiculos_disponiveis = df["nome"].dropna().unique()

                if len(veiculos_disponiveis) == 0:
                    st.warning(f"Sem veículos disponíveis para {segmento}.")
                    continue

                veiculo = st.selectbox("Veículo", veiculos_disponiveis, key=f"vei_{i}")
                dados_filtrados = df[df["nome"] == veiculo]

                if dados_filtrados.empty:
                    st.warning("Veículo não encontrado.")
                    continue

                dados = dados_filtrados.iloc[0]

                if "imagem" in dados.index and pd.notna(dados["imagem"]):
                    st.image(dados["imagem"], use_container_width=True)

                prazo = st.selectbox("Prazo", [12, 18, 24, 36, 48], key=f"prazo_{i}")
                km = st.selectbox(
                    "KM",
                    [500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000],
                    key=f"km_{i}"
                )

                col_preco = f"preco{km}{prazo}"
                valor = dados[col_preco] if col_preco in df.columns else "Sob consulta"

                st.success(str(valor))

                cotacoes.append({
                    "segmento": segmento,
                    "modelo": veiculo,
                    "prazo": prazo,
                    "km": km,
                    "valor": str(valor),
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
# RELATÓRIO
# =========================================================
with tab2:
    col_title, col_btn = st.columns([6, 1])

    with col_title:
        st.title("📊 Dashboard")

        if st.session_state["ultima_atualizacao"] is not None:
            st.caption(
                f"Última atualização: {st.session_state['ultima_atualizacao'].strftime('%H:%M:%S')}"
            )

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
        data_min = df["data"].min() if "data" in df.columns and not df["data"].dropna().empty else datetime.datetime.now().date()
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

    propostas = df_filtro["proposta_id"].nunique() if "proposta_id" in df_filtro.columns else 0
    veiculos = len(df_filtro)
    top_consultor = df_filtro["consultor"].mode()[0] if ("consultor" in df_filtro.columns and not df_filtro.empty and not df_filtro["consultor"].dropna().empty) else "-"
    top_modelo = df_filtro["modelo"].mode()[0] if ("modelo" in df_filtro.columns and not df_filtro.empty and not df_filtro["modelo"].dropna().empty) else "-"

    col1.metric("Propostas", propostas)
    col2.metric("Veículos", veiculos)
    col3.metric("Top Consultor", top_consultor)
    col4.metric("Top Modelo", top_modelo)

    st.divider()

    if not df_filtro.empty and "data" in df_filtro.columns and "proposta_id" in df_filtro.columns:
        st.subheader("📈 Propostas por dia")
        df_dia = df_filtro.groupby(df_filtro["data"].dt.date)["proposta_id"].nunique()
        st.bar_chart(df_dia)

    if not df_filtro.empty and "consultor" in df_filtro.columns:
        st.subheader("🏆 Ranking Consultores")
        st.bar_chart(df_filtro["consultor"].value_counts())

    if not df_filtro.empty and "segmento" in df_filtro.columns:
        st.subheader("🚗 Segmentos")
        st.bar_chart(df_filtro["segmento"].value_counts())

    if not df_filtro.empty and "modelo" in df_filtro.columns and "proposta_id" in df_filtro.columns:
        st.subheader("🔥 Modelos mais ofertados")
        df_carro = df_filtro.groupby("modelo")["proposta_id"].nunique().sort_values(ascending=False)
        st.bar_chart(df_carro)

# =========================================================
# GERENCIAMENTO
# =========================================================
with tab3:
    st.title("🛠️ Gerenciamento")
    st.caption("Área administrativa para controle do sistema.")

    st.markdown('<div class="status-card">', unsafe_allow_html=True)

    col_status_1, col_status_2 = st.columns([1, 4])

    with col_status_1:
        if modo_manutencao:
            st.error("🔴 Offline")
        else:
            st.success("🟢 Online")

    with col_status_2:
        atualizado_por = status_sistema.get("atualizado_por", "-") or "-"
        atualizado_em = status_sistema.get("atualizado_em", "-") or "-"

        if modo_manutencao:
            st.write("O sistema está em modo manutenção e indisponível para os usuários.")
        else:
            st.write("O sistema está ativo e disponível normalmente.")

        st.markdown(
            f"<div class='small-muted'><b>Última alteração:</b> {atualizado_em} | <b>Por:</b> {atualizado_por}</div>",
            unsafe_allow_html=True
        )

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card-gerenciamento">', unsafe_allow_html=True)
    st.subheader("Controle do sistema")

    responsavel_admin = st.text_input(
        "Nome do responsável",
        value=status_sistema.get("atualizado_por", "") or "Administrador",
        key="responsavel_admin"
    )

    if not modo_manutencao:
        st.warning("Ao desativar o sistema, todos os usuários verão a tela de manutenção.")

        if st.button("🔴 Tirar sistema do ar", use_container_width=True):
            st.session_state.abrir_confirmacao_desativar = True

        if st.session_state.abrir_confirmacao_desativar:
            senha_desativar = st.text_input(
                "Senha de desativação",
                type="password",
                key="senha_desativacao_gerenciamento"
            )

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
        st.info("O sistema já está em manutenção. A reativação deve ser feita pela tela principal de manutenção.")

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# SIMULADOR
# =========================================================
with tab4:
    st.title("🧮 Simulador de Plano")
    st.caption("Selecione o segmento e o modelo para montar o card comercial do plano.")

    col1, col2 = st.columns(2)

    with col1:
        segmento_sim = st.selectbox(
            "Segmento",
            list(BASES.keys()),
            key="sim_segmento"
        )

    df_sim = carregar_base(BASES[segmento_sim])

    modelos_disponiveis = []
    if "nome" in df_sim.columns:
        modelos_disponiveis = sorted(df_sim["nome"].dropna().unique())

    with col2:
        modelo_sim = st.selectbox(
            "Modelo",
            modelos_disponiveis,
            key="sim_modelo"
        )

    if st.button("✨ Montar card do plano", use_container_width=True):
        planos, imagem = extrair_planos_modelo(df_sim, modelo_sim)

        if not planos:
            st.warning("Não foram encontrados planos para este modelo.")
        else:
            html_card = gerar_card_plano_html(modelo_sim, planos, imagem)
            altura_card = 760 if len(planos) <= 3 else 920 if len(planos) <= 5 else 1120
            components.html(html_card, height=altura_card, scrolling=True)

            png_bytes = gerar_card_png(modelo_sim, planos, imagem)

            st.download_button(
                "📥 Baixar card em PNG",
                data=png_bytes,
                file_name=f"Card Plano - {modelo_sim}.png",
                mime="image/png",
                use_container_width=True
            )

            st.divider()

            with st.expander("Ver estrutura dos planos encontrados"):
                linhas = []
                for prazo, itens in planos.items():
                    for item in itens:
                        linhas.append({
                            "Prazo": prazo,
                            "KM por mês": item["km"],
                            "Valor": f"{item['valor']}"
                        })

                if linhas:
                    st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)