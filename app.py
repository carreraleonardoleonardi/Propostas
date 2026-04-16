# =========================================================
# app.py — ponto de entrada do sistema
# =========================================================
import streamlit as st
import datetime
import json
import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import requests

from utils import formatar_valor_brl, valor_para_float, data_validade_mes_atual
from autenticacao import (
    render_login, render_sidebar_user, render_sidebar_sair, render_usuarios,
    is_logado, is_staff, abas_permitidas,
    carregar_sessao, salvar_sessao,
    render_tema_selector, aplicar_tema
)

# Páginas
from pages.propostas        import render as render_propostas
from pages.relatorio        import render as render_relatorio
from pages.gerenciamento    import render as render_gerenciamento, salvar_status_manutencao
from pages.simulador        import render as render_simulador
from pages.comparativo      import render as render_comparativo
from pages.estoque          import render as render_estoque
from pages.gestao_veiculos  import render as render_gestao_veiculos
from pages.controle_usados  import render as render_controle_usados


# =========================================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================================
st.set_page_config(page_title="Gerador de Propostas", page_icon="favicon.png", layout="wide")

SENHA_DESATIVAR  = st.secrets["SENHA_DESATIVAR"]
SENHA_ATIVAR     = st.secrets["SENHA_ATIVAR"]
ARQUIVO_STATUS   = "status_sistema.json"
URL_LOGO_CARRERA = "https://i.postimg.cc/HWrrsnvR/LOGO-SIGNATURE-AZUL-E-DOURADO.png"
URL_ICON_WPP     = "https://cdn-icons-png.flaticon.com/512/3670/3670051.png"
AZUL_CARRERA     = (33, 49, 68)
AZUL_CARRERA_HEX = "#213144"


# =========================================================
# CSS GLOBAL
# =========================================================
st.markdown("""
<style>
#MainMenu {display: none;}
footer {display: none;}
[data-testid="stDecoration"] {display: none;}
.block-container { padding-top: 2.5rem; }
.manutencao-wrapper { min-height: 72vh; display: flex; align-items: center; justify-content: center; }
.manutencao-card { background: #FFF; border: 1px solid #E5E7EB; border-radius: 22px; padding: 42px 32px; text-align: center; max-width: 760px; width: 100%; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
.manutencao-titulo { font-size: 40px; font-weight: 700; color: #213144; margin-bottom: 12px; }
.manutencao-subtitulo { font-size: 18px; color: #6B7280; line-height: 1.6; margin-bottom: 10px; }
.small-muted { color: #6B7280; font-size: 0.92rem; }
[data-testid="stSidebarNav"] {display: none !important;}
section[data-testid="stSidebarNav"] {display: none !important;}
[data-testid="stSidebar"] .stRadio label {font-size: 17px !important; padding: 10px 4px !important; font-weight: 500;}
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] {gap: 6px !important;}
</style>
""", unsafe_allow_html=True)


# =========================================================
# SESSION STATE
# =========================================================
for key, val in [
    ("abrir_confirmacao_desativar", False),
    ("abrir_confirmacao_reativar",  False),
    ("ultima_atualizacao",          None),
]:
    if key not in st.session_state:
        st.session_state[key] = val

# ── Auth: restaura sessão via query_params (persiste F5) ──
if not is_logado():
    _sessao = carregar_sessao()
    if _sessao:
        st.session_state["auth_usuario"] = _sessao
        st.session_state["auth_tipo"]    = _sessao["tipo"]
        st.session_state["auth_nome"]    = _sessao["nome"]
        st.session_state["auth_email"]   = _sessao["email"]
        st.session_state["auth_frente"]  = _sessao["frente"]

if not is_logado():
    render_login()
    st.stop()

aplicar_tema()


# =========================================================
# FUNÇÕES DO CARD PNG
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
    for c in [
        "assets/Montserrat-Bold.ttf"    if bold else "assets/Montserrat-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf"  if bold else "C:/Windows/Fonts/arial.ttf",
    ]:
        try:
            return ImageFont.truetype(c, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def medir_texto(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_text_center(draw, box_x1, box_x2, y, text, font, fill):
    w, _ = medir_texto(draw, text, font)
    draw.text((box_x1 + ((box_x2 - box_x1) - w) / 2, y), text, font=font, fill=fill)


def gerar_card_plano_html(modelo, planos, imagem_url, segmento="", versao=""):
    validade    = data_validade_mes_atual()
    qtd_colunas = max(1, len(planos))
    titulo      = str(modelo).strip().title()
    subtitulo   = str(versao).strip()
    seg_label   = "GM Fleet" if str(segmento).strip().startswith("GM Fleet") else str(segmento).strip()

    if qtd_colunas <= 3:
        pf, kf, vf = 26, 14, 18; bp = "18px 14px"; gg = "18px"
    elif qtd_colunas <= 5:
        pf, kf, vf = 22, 13, 16; bp = "16px 12px"; gg = "14px"
    else:
        pf, kf, vf = 18, 11, 14; bp = "14px 10px"; gg = "10px"

    html_planos = ""
    for prazo, itens in planos.items():
        linhas = "".join(f'<div class="plano-linha"><div class="plano-km">{i["km"]} km/mês</div><div class="plano-valor">{i["valor"]}</div></div>' for i in itens)
        html_planos += f'<div class="plano-coluna"><div class="plano-prazo">{prazo} meses</div><div class="plano-bloco">{linhas}</div></div>'

    img_html  = f'<img src="{imagem_url}" alt="Veículo">' if isinstance(imagem_url, str) and imagem_url.strip().startswith("http") else ""
    sub_html  = f'<div class="plano-versao">{subtitulo}</div>' if subtitulo else ""
    seg_html  = f'<div class="plano-segmento">{seg_label}</div>' if seg_label else ""

    return f"""<html><head>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body{{margin:0;padding:14px;background:#f3f3f3;font-family:'Montserrat',Arial,sans-serif;}}
        .plano-card{{background:#fff;border:1px solid #d9d9d9;border-radius:16px;overflow:hidden;box-shadow:0 8px 24px rgba(0,0,0,.08);}}
        .plano-header{{background:{AZUL_CARRERA_HEX};color:#fff;padding:28px 32px;display:flex;justify-content:space-between;align-items:center;gap:20px;min-height:180px;}}
        .plano-header-left{{flex:1;display:flex;flex-direction:column;justify-content:center;gap:4px;}}
        .plano-titulo{{font-size:42px;font-weight:800;line-height:1.1;margin:0;}}
        .plano-versao{{font-size:20px;font-weight:600;opacity:.9;margin:4px 0 0 0;}}
        .plano-segmento{{font-size:13px;font-weight:500;letter-spacing:1px;opacity:.65;margin-top:8px;}}
        .plano-header img{{max-width:380px;max-height:200px;object-fit:contain;}}
        .plano-body{{background:#fff;padding:24px 24px 8px 24px;}}
        .plano-caption{{color:#3f3f3f;font-size:13px;font-weight:700;margin-bottom:18px;text-transform:uppercase;letter-spacing:1px;text-align:center;}}
        .plano-grid{{display:grid;grid-template-columns:repeat({qtd_colunas},minmax(140px,220px));gap:{gg};align-items:start;justify-content:center;}}
        .plano-coluna{{text-align:center;}}
        .plano-prazo{{font-size:{pf}px;font-weight:800;color:{AZUL_CARRERA_HEX};margin-bottom:10px;}}
        .plano-bloco{{background:rgba(33,49,68,.9);color:#fff;border-radius:20px;padding:{bp};box-shadow:0 8px 18px rgba(0,0,0,.16);}}
        .plano-linha{{margin-bottom:12px;}}
        .plano-km{{font-size:{kf}px;opacity:.85;font-weight:500;}}
        .plano-valor{{font-size:{vf}px;font-weight:800;}}
        .plano-footer{{padding:18px 24px 22px 24px;background:#fff;}}
        .plano-aviso{{font-size:13px;color:#6b7280;margin-bottom:16px;text-align:center;}}
        .plano-contato{{display:flex;align-items:center;justify-content:space-between;gap:16px;}}
        .plano-telefone-wrap{{display:flex;align-items:center;gap:10px;}}
        .plano-wpp{{width:28px;height:28px;object-fit:contain;}}
        .plano-telefone{{font-size:26px;font-weight:800;color:{AZUL_CARRERA_HEX};}}
        .plano-linha-sep{{flex:1;height:1px;background:{AZUL_CARRERA_HEX};opacity:.2;margin:0 16px;}}
        .plano-logo-final-img{{height:40px;object-fit:contain;}}
    </style></head><body>
    <div class="plano-card">
        <div class="plano-header">
            <div class="plano-header-left"><div class="plano-titulo">{titulo}</div>{sub_html}{seg_html}</div>
            {img_html}
        </div>
        <div class="plano-body">
            <div class="plano-caption">Planos Disponíveis</div>
            <div class="plano-grid">{html_planos}</div>
        </div>
        <div class="plano-footer">
            <div class="plano-aviso">A cor escolhida pode alterar o preço. Ofertas válidas até {validade}</div>
            <div class="plano-contato">
                <div class="plano-telefone-wrap">
                    <img class="plano-wpp" src="{URL_ICON_WPP}" alt="WhatsApp">
                    <div class="plano-telefone">4003.7214</div>
                </div>
                <div class="plano-linha-sep"></div>
                <div><img class="plano-logo-final-img" src="{URL_LOGO_CARRERA}" alt="Carrera Signature"></div>
            </div>
        </div>
    </div></body></html>"""


def gerar_card_png(modelo, planos, imagem_url, segmento="", versao=""):
    S = 1.636
    largura = 1800; margem = int(18 * S)
    card_x1, card_x2 = margem, largura - margem
    qtd_colunas = max(1, len(planos))

    pf, kf, vf, gap = int(26*S), int(14*S), int(18*S), int(18*S)
    if qtd_colunas > 3 and qtd_colunas <= 5:
        pf, kf, vf, gap = int(22*S), int(13*S), int(16*S), int(14*S)
    elif qtd_colunas > 5:
        pf, kf, vf, gap = int(18*S), int(11*S), int(14*S), int(10*S)

    bp  = int(18 * S)
    lgp = int(kf + vf + 18)
    hh  = int(180 * S)
    pah = int(52 * S)
    mql = max(len(v) for v in planos.values()) if planos else 1
    bh  = bp * 2 + mql * lgp
    alt = margem * 2 + hh + int(60*S) + pah + bh + int(160*S)

    bg   = Image.new("RGBA", (largura, alt), (243, 243, 243, 255))
    draw = ImageDraw.Draw(bg)
    cy1  = margem

    draw.rounded_rectangle([card_x1, cy1, card_x2, alt - margem], radius=int(16*S), fill=(255,255,255,255), outline=(217,217,217,255), width=2)
    draw.rounded_rectangle([card_x1, cy1, card_x2, cy1 + hh], radius=int(16*S), fill=(*AZUL_CARRERA, 255))
    draw.rectangle([card_x1, cy1 + int(30*S), card_x2, cy1 + hh], fill=(*AZUL_CARRERA, 255))

    titulo    = str(modelo).strip().title()
    subtitulo = str(versao).strip()
    seg_label = "GM Fleet" if str(segmento).strip().startswith("GM Fleet") else str(segmento).strip()
    ph = int(28 * S)

    draw.text((card_x1 + ph, cy1 + ph), titulo, font=get_font(int(42*S), bold=True), fill=(255,255,255,255))
    yc = cy1 + ph + int(52*S)
    if subtitulo:
        draw.text((card_x1 + ph, yc), subtitulo, font=get_font(int(20*S)), fill=(255,255,255,230)); yc += int(28*S)
    if seg_label:
        draw.text((card_x1 + ph, yc), seg_label, font=get_font(int(13*S)), fill=(255,255,255,140))

    foto = baixar_imagem_pil(imagem_url)
    if foto:
        foto.thumbnail((int(380*S), int(200*S)))
        bg.paste(foto, (card_x2 - foto.width - ph, cy1 + int(10*S)), foto)

    bt       = cy1 + hh + int(24*S)
    fc       = get_font(int(13*S), bold=True)
    wc, _    = medir_texto(draw, "PLANOS DISPONÍVEIS", fc)
    draw.text(((largura - wc) // 2, bt), "PLANOS DISPONÍVEIS", font=fc, fill=(66,66,66,255))

    gt   = bt + int(42*S)
    cw   = min(int(220*S), int((card_x2 - card_x1 - gap * (qtd_colunas - 1)) / qtd_colunas))
    gtot = qtd_colunas * cw + gap * (qtd_colunas - 1)
    gl   = (largura - gtot) // 2

    for i, (prazo, itens) in enumerate(planos.items()):
        x = gl + i * (cw + gap)
        draw_text_center(draw, x, x + cw, gt, f"{prazo} meses", get_font(pf, bold=True), AZUL_CARRERA + (255,))
        by  = gt + pah
        bhc = bp * 2 + len(itens) * lgp
        draw.rounded_rectangle([x, by, x + cw, by + bhc], radius=int(20*S), fill=(33,49,68,230))
        cy = by + bp
        for item in itens:
            draw_text_center(draw, x, x + cw, cy,       f"{item['km']} km/mês", get_font(kf),            (200,210,220,255))
            draw_text_center(draw, x, x + cw, cy+kf+4,  f"{item['valor']}",     get_font(vf, bold=True), (255,255,255,255))
            cy += lgp

    fy       = gt + pah + bh + int(34*S)
    validade = data_validade_mes_atual()
    geracao  = datetime.datetime.now().strftime("Gerado em: %d/%m/%Y %H:%M")
    fav      = get_font(int(13*S))
    wav, _   = medir_texto(draw, f"A cor escolhida pode alterar o preço. Ofertas válidas até {validade}", fav)
    draw.text(((largura - wav) // 2, fy), f"A cor escolhida pode alterar o preço. Ofertas válidas até {validade}", font=fav, fill=(120,130,140,255))
    wg, _    = medir_texto(draw, geracao, fav)
    draw.text(((largura - wg) // 2, fy + int(20*S)), geracao, font=fav, fill=(160,170,180,255))

    ly = fy + int(36*S)
    draw.line([(card_x1 + int(22*S), ly), (card_x2 - int(22*S), ly)], fill=(*AZUL_CARRERA, 60), width=2)

    ftl      = get_font(int(26*S), bold=True)
    btl      = draw.textbbox((0,0), "4003.7214", font=ftl)
    htl      = btl[3] - btl[1]; aof = btl[1]
    yt       = ly + int(18*S); xt = card_x1 + int(24*S)
    icon     = baixar_imagem_pil(URL_ICON_WPP)
    if icon:
        isz = htl + int(4*S); icon.thumbnail((isz, isz))
        bg.paste(icon, (xt, yt + aof + (htl - icon.height) // 2), icon)
        xt += icon.width + int(10*S)
    draw.text((xt, yt), "4003.7214", font=ftl, fill=AZUL_CARRERA + (255,))

    logo = baixar_imagem_pil(URL_LOGO_CARRERA)
    if logo:
        logo.thumbnail((int(90*S), int(50*S)))
        bg.paste(logo, (card_x2 - logo.width - int(24*S), ly + int(22*S)), logo)

    out = BytesIO(); bg.convert("RGB").save(out, format="PNG"); out.seek(0)
    return out.getvalue()


# =========================================================
# STATUS DO SISTEMA
# =========================================================
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


status_sistema  = carregar_status_manutencao()
modo_manutencao = status_sistema.get("modo_manutencao", False)


# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.image(URL_LOGO_CARRERA, width=180)
    render_sidebar_user()

vendedor           = ""
cliente            = ""
qtd                = 3
progress_container = st.empty()


# =========================================================
# TELA DE MANUTENÇÃO
# =========================================================
if modo_manutencao and not is_staff():
    st.markdown("""
    <div class="manutencao-wrapper"><div class="manutencao-card">
        <div class="manutencao-titulo">🚧 Sistema em manutenção</div>
        <div class="manutencao-subtitulo">Estamos atualizando a base de dados.<br>O sistema será reativado em breve.</div>
    </div></div>""", unsafe_allow_html=True)

    st.subheader("🔓 Reativar sistema")
    responsavel_reativar = st.text_input("Nome do responsável",
        value=status_sistema.get("atualizado_por", "") or "Administrador", key="responsavel_reativar")

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
                    st.success("Sistema reativado!")
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
# ── Navegação pelo sidebar ─────────────────────────────
_TODAS_ABAS = [
    "🚗 Propostas", "🎴 Card", "🔍 Comparativo",
    "📈 Performance", "🚘 Estoque", "🚙 Controle Usados",
    "📅 Agenda de Entregas", "👥 Usuários", "🛠️ Gerenciamento"
]
_abas_render = [a for a in _TODAS_ABAS if a in abas_permitidas()]

with st.sidebar:
    st.markdown("<hr style='margin:8px 0;border-color:#e2e8f0'>", unsafe_allow_html=True)
    _aba_ativa = st.radio("Navegação", _abas_render, label_visibility="collapsed")
    render_sidebar_sair()

# ── Renderiza a aba selecionada ─────────────────────────
if _aba_ativa == "🚗 Propostas":
    render_propostas()

elif _aba_ativa == "🎴 Card":
    render_simulador(gerar_card_plano_html, gerar_card_png)

elif _aba_ativa == "🔍 Comparativo":
    render_comparativo()

elif _aba_ativa == "📈 Performance":
    render_relatorio()

elif _aba_ativa == "🚘 Estoque":
    render_gestao_veiculos()

elif _aba_ativa == "🚙 Controle Usados":
    render_controle_usados()

elif _aba_ativa == "📅 Agenda de Entregas":
    # Entregador vê só a agenda do dia da gestão de veículos
    render_gestao_veiculos()

elif _aba_ativa == "👥 Usuários":
    render_usuarios()

elif _aba_ativa == "🛠️ Gerenciamento":
    render_gerenciamento(status_sistema, modo_manutencao, SENHA_DESATIVAR)