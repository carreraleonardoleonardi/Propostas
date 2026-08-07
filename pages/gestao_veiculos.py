import streamlit as st
import pandas as pd
import requests
import json
import datetime
import io

# ── Constantes ───────────────────────────────────────────────────────────────

GV_SHEET_URL = "https://docs.google.com/spreadsheets/d/1BpAtiXz4AEuQg4kVx8OFonohPlvbScdOgWPIZRxQnxo/export?format=csv&gid=461042346"
GV_WEBHOOK   = "https://script.google.com/macros/s/AKfycbzFP-ezBsVx7W7VhYATKgaqdAg485o0AQb8s9FdGTlvmdzK1YRj7dCUVfTrXNgJOToc/exec"
SENHA_FECHAMENTO = "#FECHAMENTO"

GV_STATUS_LIST = [
    "Trânsito Livre", "Trânsito Vendido", "Livre",
    "Aguardando Atribuição", "Aguardando Agendamento", "Agendado",
    "Entregue", "Reagendar", "Avariado", "Distrato",
    "Remoção", "Reserva Temporária", "Evento Signature",
]
GV_FABRICANTES  =  ["Volkswagen","Chevrolet","Nissan","Jeep","GWM","GAC","Omoda", "Renault","Hyundai","Toyota","Fiat","Ford","Honda","Citroën","Peugeot","Mitsubishi","Subaru","Chery","JAC","Lexus","Kia","Dodge","BMW","Mercedes-Benz","Audi","Porsche","Volvo","Mini","Land Rover","Jaguar","Alfa Romeo","Aston Martin","Bentley","Rolls-Royce","McLaren","Pagani","Bugatti","Koenigsegg","Zeekr","BYD","Leapmotor"]
GV_LOCADORAS    = ["LM FROTAS","RCI","TOOT","GM Fleet", "Arval", "Localiza"]
GV_LOJAS        = ["LOJA ALPHAVILLE","LOJA VILLA LOBOS","LOJA OSASCO","LOJA BUTANTÃ","LOJA COTIA","OUTRO DN"]
GV_COMBUSTIVEIS = ["Flex","Gasolina","Elétrico","Híbrido","Diesel"]
GV_COLUNAS      = [
    "id","fabricante","modelo","chassi","placa","cor",
    "ano_fabricacao","ano_modelo","combustivel","opcionais",
    "locadora","consultor","cliente","pedido","status",
    "local_atual","data_chegada","data_entrega","hora_entrega",
    "entregador","avaria","obs_avaria","loja_entrega",
    "valor_nf","margem","comissao",
    "criado_em","atualizado_em","atualizado_por",
    "transporte_solicitado",
]

STATUS_CORES = {
    "Livre":                  "#22c55e",
    "Trânsito Livre":         "#3b82f6",
    "Trânsito Vendido":       "#8b5cf6",
    "Aguardando Atribuição":  "#eab308",
    "Aguardando Agendamento": "#f97316",
    "Agendado":               "#06b6d4",
    "Entregue":               "#10b981",
    "Reagendar":              "#f59e0b",
    "Avariado":               "#ef4444",
    "Distrato":               "#6b7280",
    "Remoção":                "#64748b",
    "Reserva Temporária":     "#a855f7",
    "Evento Signature":       "#ec4899",
}

# Paleta oficial Carrera
D_ESC    = "#b57b3f"
D_CLR    = "#dfc28a"
AZUL     = "#213144"

# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_data(valor):
    if not valor or str(valor).strip() in ("","nan","None","NaT"): return None
    s = str(valor).strip()
    for fmt in ("%d/%m/%Y","%Y-%m-%d","%Y/%m/%d","%d-%m-%Y"):
        try: return datetime.datetime.strptime(s, fmt).date()
        except: continue
    return None

def fmt_data(valor):
    d = parse_data(valor)
    return d.strftime("%d/%m/%Y") if d else ""

def calcular_idade(row):
    chegada = parse_data(str(row.get("data_chegada","")))
    if not chegada: return None
    if str(row.get("status","")).strip() == "Entregue":
        entrega = parse_data(str(row.get("data_entrega","")))
        ref = entrega or datetime.date.today()
    else:
        ref = datetime.date.today()
    return (ref - chegada).days

def farol_idade(dias):
    if dias is None: return "⚪"
    if dias <= 20:   return "🟢"
    if dias <= 30:   return "🟡"
    if dias <= 45:   return "🔴"

def farol_agendamento(row):
    if str(row.get("status","")).strip() == "Entregue": return "🟢"
    data_ent = parse_data(str(row.get("data_entrega","")))
    if not data_ent: return "⚪"
    hora_str = str(row.get("hora_entrega","")).strip()
    agora = datetime.datetime.now()
    try:
        h, m = map(int, hora_str.split(":"))
        dt_ag = datetime.datetime.combine(data_ent, datetime.time(h, m))
    except:
        dt_ag = datetime.datetime.combine(data_ent, datetime.time(23, 59))
    return "🔴" if agora > dt_ag else "🟡"

RODIZIO_SP       = {"1":0,"2":0,"3":1,"4":1,"5":2,"6":2,"7":3,"8":3,"9":4,"0":4}
RODIZIO_BLOQUEIO = [(datetime.time(6,0), datetime.time(10,0)), (datetime.time(16,0), datetime.time(20,0))]

def verificar_rodizio(placa, data, hora):
    if not placa: return None
    final = placa.strip()[-1].upper()
    if final not in RODIZIO_SP or data.weekday() != RODIZIO_SP[final]: return None
    dias = ["segunda","terça","quarta","quinta","sexta"]
    for ini, fim in RODIZIO_BLOQUEIO:
        if ini <= hora < fim:
            return f"🚫 Rodízio: placa **{final}** restrita na **{dias[RODIZIO_SP[final]]}** entre {ini.strftime('%H:%M')} e {fim.strftime('%H:%M')}."
    return None

def verificar_conflito_loja(df, data, hora, loja, excluir_idx=-1):
    ds, hs = data.strftime("%d/%m/%Y"), hora.strftime("%H:%M")
    mask = ((df["status"]=="Agendado") & (df["data_entrega"].astype(str)==ds) &
            (df["hora_entrega"].astype(str)==hs) & (df["loja_entrega"].astype(str)==loja))
    if excluir_idx >= 0: mask = mask & (df.index != excluir_idx)
    conf = df[mask]
    if not conf.empty:
        v = conf.iloc[0]
        return f"🚫 Conflito em **{loja}** às **{hs}** — {v.get('modelo','?')} | {v.get('cliente','?')}"
    return None

# ── Cache & envio ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def gv_carregar():
    try:
        df = pd.read_csv(GV_SHEET_URL, header=0)
        df.columns = [c.strip().lower().replace(" ","_") for c in df.columns]
        for col in ["data_chegada","data_entrega","criado_em","atualizado_em"]:
            if col in df.columns:
                df[col] = df[col].astype(str).apply(fmt_data)
        return df
    except:
        return pd.DataFrame(columns=GV_COLUNAS)

def gv_enviar(payload):
    try:
        requests.post(GV_WEBHOOK, data=json.dumps(payload),
                      headers={"Content-Type":"text/plain"}, timeout=30)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}"); return False

def gv_novo_id():
    return "VEI" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")

def gv_val_row(row, col, default=""):
    v = row.get(col, default)
    return "" if pd.isna(v) else str(v)

# ── CSS ───────────────────────────────────────────────────────────────────────

GV_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

/* Reset */
section[data-testid="stMain"] * { font-family: 'Montserrat', sans-serif !important; }

/* ── KPIs ── */
.kpi-row { display:flex; gap:10px; margin:14px 0 22px; }
.kpi-box {
    flex:1; background:#fff;
    border:1.5px solid #e8e0d0;
    border-top:4px solid #b57b3f;
    border-radius:14px;
    padding:16px 10px 12px;
    text-align:center;
    box-shadow:0 2px 10px rgba(181,123,63,.07);
    transition:transform .15s, box-shadow .15s;
}
.kpi-box:hover { transform:translateY(-2px); box-shadow:0 6px 18px rgba(181,123,63,.13); }
.kpi-n { font-size:28px; font-weight:800; line-height:1; }
.kpi-l { font-size:10px; color:#94a3b8; margin-top:5px;
          text-transform:uppercase; letter-spacing:.7px; font-weight:600; }

/* ── Card veículo ── */
.vcard {
    background:#fff;
    border:1.5px solid #e8e0d0;
    border-left:5px solid #b57b3f;
    border-radius:13px;
    padding:13px 18px;
    margin-bottom:6px;
    box-shadow:0 1px 5px rgba(0,0,0,.04);
    transition:box-shadow .18s, transform .14s, border-color .18s, background .18s;
}
.vcard:hover {
    border-color:#b57b3f;
    box-shadow:0 5px 18px rgba(181,123,63,.13);
    transform:translateY(-1px);
    background:#fdfbf7;
}
.vcard.ativo {
    background:#fdf8f0;
    border-color:#b57b3f;
    box-shadow:0 5px 22px rgba(181,123,63,.18);
}
.vcard-row   { display:flex; align-items:center; gap:14px; }
.vcard-left  { flex:1; min-width:0; }
.vcard-modelo { font-size:15px; font-weight:700; color:#213144; }
.vcard-fab    { font-size:12px; font-weight:400; color:#94a3b8; margin-left:6px; }
.vcard-tags   { display:flex; flex-wrap:wrap; gap:5px; margin-top:5px; }
.vtag {
    background:#f4f0e8; border:1px solid #e5ddd0;
    border-radius:6px; padding:2px 8px;
    font-size:11px; color:#6b5c45;
}
.vcard-cli  { font-size:11px; color:#475569; margin-top:4px; }
.vcard-right { text-align:right; flex-shrink:0; }
.vbadge { display:inline-block; padding:4px 13px; border-radius:999px;
           font-size:11px; font-weight:700; color:#fff; white-space:nowrap; }
.vidade { font-size:11px; color:#94a3b8; margin-top:5px; }
.vag    { font-size:11px; color:#0891b2; margin-top:2px; }

/* ── Painel de ações (inline) ── */
.painel-wrap {
    background:#fff;
    border:2px solid #b57b3f;
    border-radius:14px;
    padding:22px 26px 18px;
    margin:-2px 0 10px;
    box-shadow:0 8px 28px rgba(181,123,63,.14);
    animation:slideDown .2s ease;
}
@keyframes slideDown {
    from { opacity:0; transform:translateY(-8px); }
    to   { opacity:1; transform:translateY(0); }
}
.p-title { font-size:18px; font-weight:800; color:#213144; }
.p-fab   { font-size:13px; font-weight:400; color:#94a3b8; margin-left:7px; }
.p-sub   { font-size:12px; color:#64748b; margin-top:5px; line-height:1.6; }
.p-badge { display:inline-block; padding:4px 14px; border-radius:999px;
           font-size:11px; font-weight:700; color:#fff; margin-top:8px; }

/* ── Detalhe grid ── */
.det-sec  { margin-bottom:18px; }
.det-head { font-size:10px; font-weight:700; color:#b57b3f;
            text-transform:uppercase; letter-spacing:.8px;
            border-bottom:1px solid #f0e8d8;
            padding-bottom:4px; margin-bottom:10px; }
.det-grid { display:grid;
            grid-template-columns:repeat(auto-fill,minmax(160px,1fr));
            gap:10px 20px; }
.det-l { font-size:10px; color:#94a3b8; font-weight:600; text-transform:uppercase; }
.det-v { font-size:13px; color:#213144; font-weight:500; margin-top:2px; }
.det-v.em { color:#cbd5e1; font-style:italic; }
</style>
"""

# ── Gerador de PDF ───────────────────────────────────────────────────────────
CARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1RbDl9eD5MafLLQ0QisBy3KQzJOJSGqELyuyGEvZUfm8/export?format=csv&gid=0"

_MONTSERRAT_REGISTERED = False

def _registrar_montserrat():
    global _MONTSERRAT_REGISTERED
    if _MONTSERRAT_REGISTERED:
        return True
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import urllib.request, zipfile, tempfile, os as _os

        url = "https://fonts.google.com/download?family=Montserrat"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read()

        needed = {
            "Montserrat-Regular":    "Montserrat/static/Montserrat-Regular.ttf",
            "Montserrat-Bold":       "Montserrat/static/Montserrat-Bold.ttf",
            "Montserrat-SemiBold":   "Montserrat/static/Montserrat-SemiBold.ttf",
            "Montserrat-ExtraBold":  "Montserrat/static/Montserrat-ExtraBold.ttf",
        }
        tmpdir = tempfile.mkdtemp()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for font_name, zip_path in needed.items():
                fname = _os.path.join(tmpdir, f"{font_name}.ttf")
                with open(fname, "wb") as f:
                    f.write(z.read(zip_path))
                pdfmetrics.registerFont(TTFont(font_name, fname))

        _MONTSERRAT_REGISTERED = True
        return True
    except Exception:
        return False

@st.cache_data(ttl=600, show_spinner="Carregando dados dos segmentos...")
def _load_card_data() -> list:
    df = pd.read_csv(CARD_SHEET_URL, header=0)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df.fillna("").to_dict(orient="records")

def card_segmentos_disponiveis() -> list:
    try:
        data = _load_card_data()
        return sorted({d.get("segmento","") for d in data if d.get("segmento","")})
    except Exception:
        return ["Sign & Drive", "S&D Empresas", "Nissan Move",
                "AssineCar GWM", "GM Fleet", "GAC Go and Drive", "AssineCar Multbrand"]

def card_lookup(segmento: str, loja: str) -> dict:
    try:
        data = _load_card_data()
    except Exception:
        return {}

    seg_n = segmento.strip().lower()
    loj_n = loja.strip().lower()

    for d in data:
        if d.get("segmento","").strip().lower() == seg_n and \
           d.get("loja","").strip().lower() == loj_n:
            return d

    loj_base = loj_n.replace("loja ","").strip()
    for d in data:
        if d.get("segmento","").strip().lower() != seg_n:
            continue
        loja_d_base = d.get("loja","").strip().lower().replace("loja ","").strip()
        if loj_base and loja_d_base and (loj_base in loja_d_base or loja_d_base in loj_base):
            return d

    for d in data:
        if d.get("segmento","").strip().lower() == seg_n:
            return d

    return data[0] if data else {}

def gerar_pdf_agendamento(row, sv_fn, segmento: str = "") -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Spacer
        import os
    except ImportError:
        return (f"CARRERA SIGNATURE\nCliente: {sv_fn(row,'cliente')}\n"
                f"Placa: {sv_fn(row,'placa')}\nData: {sv_fn(row,'data_entrega')} "
                f"{sv_fn(row,'hora_entrega')}\nLoja: {sv_fn(row,'loja_entrega')}\n").encode("utf-8")

    def sv(c): return sv_fn(row, c)

    seg  = segmento if segmento else sv("locadora")
    info = card_lookup(seg, sv("loja_entrega"))
    def inf(k, fb=""): return info.get(k, fb) or fb

    c24_v  = inf("contato_central_24h", "0800 770 4220")
    csig_v = inf("contato_carrera_signature", "0800 591 1400")
    csem_v = inf("contato_sem_parar", "0800 723 2244")

    _mont = _registrar_montserrat()
    R  = "Montserrat"         if _mont else "Helvetica"
    B  = "Montserrat-Bold"    if _mont else "Helvetica-Bold"
    XB = "Montserrat-ExtraBold"if _mont else "Helvetica-Bold"

    AZUL     = colors.HexColor("#213144")
    DOURADO  = colors.HexColor("#b57b3f")
    DOURADO2 = colors.HexColor("#dfc28a")
    BRANCO   = colors.white
    CINZA_BD = colors.HexColor("#ddd8d0")

    W, H   = A4
    MG     = 1.5*cm

    FOOTER_H  = 1.3*cm
    REDES_H   = 0.9*cm
    AVISO_H   = 0.7*cm
    BOTTOM_H  = FOOTER_H + REDES_H + AVISO_H + 0.5*cm

    HEADER_H = H * 0.24
    CARD_H   = 6.0*cm
    CARD_Y   = H - HEADER_H - 0.5*cm
    CW_BODY  = W - 2*MG

    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "LOGO_SIGNATURE.png")

    def draw_page(c, doc):
        c.saveState()
        c.setFillColor(AZUL)
        c.rect(0, H-HEADER_H, W, HEADER_H, fill=1, stroke=0)
        c.setFillColor(BRANCO)
        c.rect(0, BOTTOM_H, W, H-HEADER_H-BOTTOM_H, fill=1, stroke=0)
        c.setFillColor(DOURADO)
        c.rect(0, H-HEADER_H-3, W, 5, fill=1, stroke=0)

        for r in range(6):
            for col in range(6):
                c.circle(W-1.0*cm-col*0.27*cm, H-0.7*cm-r*0.27*cm, 0.038*cm, fill=1, stroke=0)

        if os.path.exists(logo_path):
            c.drawImage(logo_path, MG, H-3.0*cm, width=4.5*cm, height=2.2*cm, preserveAspectRatio=True, mask=[0,30,0,30,0,30])
        else:
            c.setFont(B,16); c.setFillColor(BRANCO)
            c.drawString(MG, H-2.5*cm, "Carrera Signature")

        c.setFont(XB, 20); c.setFillColor(BRANCO)
        c.drawString(MG, H-3.8*cm, "Chegou a hora de pegar seu carro!")
        c.setFont(R, 8.5); c.setFillColor(DOURADO2)
        c.drawString(MG, H-4.3*cm, "Aqui estão as informações para a retirada do seu veículo.")

        CX = MG; CY = CARD_Y
        c.setFillColor(colors.HexColor("#bdb5a5"))
        c.roundRect(CX+3, CY-CARD_H-3, CW_BODY, CARD_H, 8, fill=1, stroke=0)
        c.setFillColor(BRANCO)
        c.roundRect(CX, CY-CARD_H, CW_BODY, CARD_H, 8, fill=1, stroke=0)
        c.setFillColor(DOURADO)
        c.roundRect(CX, CY-CARD_H, 6, CARD_H, 3, fill=1, stroke=0)

        LX  = CX + 0.9*cm
        C2  = CX + CW_BODY*0.52
        TY  = CY - 0.65*cm
        RH  = 1.08*cm
        SZ  = 10

        def lbl(t, x, y):
            c.setFont(B, 7); c.setFillColor(DOURADO); c.drawString(x, y, t.upper())
        def val(t, x, y):
            c.setFont(B, SZ); c.setFillColor(AZUL); c.drawString(x, y, str(t))
        def hsep(y):
            c.setStrokeColor(CINZA_BD); c.setLineWidth(0.4); c.line(LX-0.1*cm, y, CX+CW_BODY-0.5*cm, y)

        MAX_L = CW_BODY * 0.48

        def truncate(txt, max_pts):
            from reportlab.pdfbase.pdfmetrics import stringWidth
            while len(txt) > 1 and stringWidth(txt, B, SZ) > max_pts: txt = txt[:-1]
            return txt

        cliente_val = sv("cliente")
        if cliente_val in ("—","Estoque","","nan"): cliente_val = "—"
        lbl("Cliente", LX, TY); val(truncate(cliente_val, MAX_L), LX, TY-0.37*cm)
        lbl("Placa",   C2, TY); val(sv("placa"), C2, TY-0.37*cm)
        hsep(TY - RH*0.82)

        lbl("Veículo", LX, TY-RH); val(truncate(f"{sv('modelo')} · {sv('fabricante')}", MAX_L), LX, TY-RH-0.37*cm)
        lbl("Data · Hora", C2, TY-RH); val(f"{sv('data_entrega')}   {sv('hora_entrega')}", C2, TY-RH-0.37*cm)
        hsep(TY - RH*1.82)

        lbl("Chassi", LX, TY-2*RH); val(sv("chassi"), LX, TY-2*RH-0.37*cm)
        lbl("Entregador", C2, TY-2*RH); val(sv("entregador"), C2, TY-2*RH-0.37*cm)
        hsep(TY - RH*2.82)

        lbl("Cor", LX, TY-3*RH); val(sv("cor"), LX, TY-3*RH-0.37*cm)
        lbl("Consultor", C2, TY-3*RH); val(sv("consultor"), C2, TY-3*RH-0.37*cm)
        hsep(TY - RH*3.82)

        lbl("Local de Entrega", LX, TY-4*RH)
        val(truncate(f"{sv('loja_entrega')} · {inf('endereco_entrega')}", CW_BODY-1.5*cm), LX, TY-4*RH-0.37*cm)

        c.setFillColor(AZUL); c.rect(0, 0, W, FOOTER_H, fill=1, stroke=0)
        pares = [("Central 24h:", c24_v), ("Carrera Signature:", csig_v), ("Sem Parar:", csem_v)]
        col_w = W / 3
        for i, (l, v) in enumerate(pares):
            cx = col_w * i + col_w / 2
            c.setFont(R, 7); c.setFillColor(BRANCO); c.drawCentredString(cx, FOOTER_H*0.6, l)
            c.setFont(B, 9.5); c.setFillColor(DOURADO2); c.drawCentredString(cx, FOOTER_H*0.18, v)

        c.setFillColor(colors.HexColor("#1a2a3a")); c.rect(0, FOOTER_H, W, REDES_H, fill=1, stroke=0)
        c.setFont(B, 8); c.setFillColor(BRANCO); c.drawCentredString(W/2, FOOTER_H+REDES_H*0.35, "Acompanhe-nos: @carrerasignature  ·  carrerasignature.com.br")

        c.setFillColor(CINZA_BD); c.rect(0, FOOTER_H+REDES_H, W, AVISO_H, fill=1, stroke=0)
        c.setFont(B, 7.5); c.setFillColor(AZUL); c.drawCentredString(W/2, FOOTER_H+REDES_H+AVISO_H*0.3, "⚠️ Para eventuais alterações ou reagendamentos, comunique com antecedência mínima de 24 horas.")
        c.restoreState()

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=MG, rightMargin=MG, topMargin=1*cm, bottomMargin=BOTTOM_H)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
    template = PageTemplate(id='agendamento_card', frames=frame, onPage=draw_page)
    doc.addPageTemplates([template])
    doc.build([Spacer(1, 1)])
    return buf.getvalue()

# ── Render principal ──────────────────────────────────────────────────────────

def render():
    st.markdown(GV_CSS, unsafe_allow_html=True)

    autenticado = st.session_state.get("auth_tipo", "") == "Staff"
    auth_nome   = st.session_state.get("auth_nome", "")
    usuario     = auth_nome if auth_nome else "Desconhecido"

    STAFF_READONLY = {"Andrea Bettega Pereira da Costa", "Raymond Jose Duque Bello"}
    pode_editar = autenticado and (auth_nome not in STAFF_READONLY)

    hoje = datetime.date.today()

    if "gv_sel" not in st.session_state:
        st.session_state["gv_sel"] = None
    if "ag_forcar" not in st.session_state:
        st.session_state["ag_forcar"] = False
    if "gv_cad_open" not in st.session_state:
        st.session_state["gv_cad_open"] = False

    df_gv = gv_carregar()

    if not df_gv.empty:
        df_gv["_idade"] = df_gv.apply(calcular_idade, axis=1)

    def sv(r, c):
        v = r.get(c, "")
        s = str(v).strip()
        if s in ("","nan","None","NaT"): return "—"
        if s.endswith(".0") and s[:-2].lstrip("-").isdigit(): return s[:-2]
        return s

    # ── Topo e Botões Superiores ─────────────────────────────────────────────
    h1, h2, h3 = st.columns([5, 1.5, 1.5])
    with h1:
        st.markdown(f"<h2 style='color:{AZUL};margin:0;'>🚘 Estoque de Veículos</h2>", unsafe_allow_html=True)
    with h2:
        if st.button("🔄 Atualizar", use_container_width=True):
            gv_carregar.clear()
            st.rerun()
    with h3:
        if pode_editar:
            lbl_btn = "🔼 Fechar" if st.session_state["gv_cad_open"] else "➕ Cadastrar"
            if st.button(lbl_btn, use_container_width=True):
                st.session_state["gv_cad_open"] = not st.session_state["gv_cad_open"]
                st.rerun()

    # Form de Cadastro
    if pode_editar and st.session_state["gv_cad_open"]:
        st.markdown("<div class='painel-wrap'><span class='p-title'>✨ Cadastrar Novo Veículo</span>", unsafe_allow_html=True)
        with st.form("form_gv_novo", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                n_fab   = st.selectbox("Fabricante *", [""] + GV_FABRICANTES)
                n_mod   = st.text_input("Modelo *")
                n_cha   = st.text_input("Chassi *", max_chars=17)
                n_pla   = st.text_input("Placa", max_chars=7)
                n_cor   = st.text_input("Cor")
            with c2:
                n_anof  = st.text_input("Ano Fabricação", max_chars=4)
                n_anom  = st.text_input("Ano Modelo", max_chars=4)
                n_comb  = st.selectbox("Combustível", [""] + GV_COMBUSTIVEIS)
                n_opc   = st.text_area("Opcionais", height=68) # Modificado rows=2 para height=68
                n_loc   = st.selectbox("Locadora/Parceiro", [""] + GV_LOCADORAS)
            with c3:
                n_cli   = st.text_input("Cliente (Estoque se vazio)")
                n_ped   = st.text_input("Pedido/Contrato")
                n_sta   = st.selectbox("Status *", GV_STATUS_LIST, index=GV_STATUS_LIST.index("Livre"))
                n_loca  = st.text_input("Local Atual")
                n_cheg  = st.date_input("Data de Chegada", value=hoje)

            st.write("🔧 *Dados Financeiros (Opcionais)*")
            f1, f2, f3 = st.columns(3)
            with f1: n_vnf = st.number_input("Valor NF", min_value=0.0, step=1000.0)
            with f2: n_marg = st.number_input("Margem", min_value=0.0, step=100.0)
            with f3: n_comi = st.number_input("Comissão", min_value=0.0, step=100.0)

            if st.form_submit_button("💾 Salvar Registro", use_container_width=True):
                if not n_fab or not n_mod or not n_cha or not n_sta:
                    st.error("Preencha Fabricante, Modelo, Chassi e Status!")
                elif not df_gv.empty and (n_cha.strip() in df_gv["chassi"].astype(str).str.strip().values):
                    st.error("Erro: Já existe um veículo cadastrado com este Chassi!")
                else:
                    agora_s = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    payload = {
                        "action": "insert", "id": gv_novo_id(), "fabricante": n_fab, "modelo": n_mod.strip().upper(),
                        "chassi": n_cha.strip().upper(), "placa": n_pla.strip().upper(), "cor": n_cor.strip().upper(),
                        "ano_fabricacao": n_anof, "ano_modelo": n_anom, "combustivel": n_comb, "opcionais": n_opc.strip(),
                        "locadora": n_loc, "consultor": "—", "cliente": n_cli.strip() if n_cli.strip() else "Estoque",
                        "pedido": n_ped.strip(), "status": n_sta, "local_atual": n_loca.strip(),
                        "data_chegada": n_cheg.strftime("%d/%m/%Y") if n_cheg else "", "data_entrega": "", "hora_entrega": "",
                        "entregador": "—", "avaria": "Não", "obs_avaria": "", "loja_entrega": "—",
                        "valor_nf": n_vnf, "margem": n_marg, "comissao": n_comi, "criado_em": agora_s,
                        "atualizado_em": agora_s, "atualizado_por": usuario, "transporte_solicitado": "Não"
                    }
                    if gv_enviar(payload):
                        st.success("Veículo incluído com sucesso!")
                        st.session_state["gv_cad_open"] = False
                        gv_carregar.clear()
                        st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Seção de Filtros Laterais ─────────────────────────────────────────────
    st.sidebar.markdown("### 🔍 Filtros")
    f_status = st.sidebar.selectbox("Status", ["Todos"] + GV_STATUS_LIST)
    f_fab    = st.sidebar.selectbox("Fabricante", ["Todos"] + GV_FABRICANTES)
    f_modelo = st.sidebar.text_input("Modelo").strip().lower()
    f_cor    = st.sidebar.text_input("Cor").strip().lower()
    f_final_placa = st.sidebar.text_input("Final de Placa", max_chars=1).strip()

    df_filtrado = df_gv.copy()
    if not df_filtrado.empty:
        if f_status != "Todos":
            df_filtrado = df_filtrado[df_filtrado["status"] == f_status]
        if f_fab != "Todos":
            df_filtrado = df_filtrado[df_filtrado["fabricante"] == f_fab]
        if f_modelo:
            df_filtrado = df_filtrado[df_filtrado["modelo"].astype(str).str.lower().str.contains(f_modelo)]
        if f_cor:
            df_filtrado = df_filtrado[df_filtrado["cor"].astype(str).str.lower().str.contains(f_cor)]
        if f_final_placa:
            df_filtrado = df_filtrado[df_filtrado["placa"].astype(str).str.strip().str.endswith(f_final_placa)]

    # ── Dashboard / KPIs Superiores ──────────────────────────────────────────
    if not df_gv.empty:
        total_geral = len(df_gv)
        total_livre = len(df_gv[df_gv["status"] == "Livre"])
        total_agendado = len(df_gv[df_gv["status"] == "Agendado"])
        total_transito = len(df_gv[df_gv["status"].astype(str).str.contains("Trânsito")])
        total_entregue = len(df_gv[df_gv["status"] == "Entregue"])
    else:
        total_geral = total_livre = total_agendado = total_transito = total_entregue = 0

    st.markdown(f"""
    <div class="kpi-row">
        <div class="kpi-box"><div class="kpi-n" style="color:{AZUL};">{total_geral}</div><div class="kpi-l">Total Geral</div></div>
        <div class="kpi-box"><div class="kpi-n" style="color:#22c55e;">{total_livre}</div><div class="kpi-l">Disponíveis</div></div>
        <div class="kpi-box"><div class="kpi-n" style="color:#3b82f6;">{total_transito}</div><div class="kpi-l">Em Trânsito</div></div>
        <div class="kpi-box"><div class="kpi-n" style="color:#06b6d4;">{total_agendado}</div><div class="kpi-l">Agendados</div></div>
        <div class="kpi-box"><div class="kpi-n" style="color:#10b981;">{total_entregue}</div><div class="kpi-l">Entregues</div></div>
    </div>
    """, unsafe_allow_html=True)

    if df_gv.empty:
        st.info("Nenhum veículo encontrado na planilha.")
        return

    # ── Layout principal em duas colunas (Listagem vs Painel de Ações) ─────────
    col_lista, col_painel = st.columns([1.1, 1.4])

    with col_lista:
        st.markdown(f"<p style='font-size:12px;color:#64748b;margin-bottom:8px;'>Exibindo {len(df_filtrado)} resultado(s)</p>", unsafe_allow_html=True)
        
        for idx, row in df_filtrado.iterrows():
            ch = sv(row, "chassi")
            status_atual = sv(row, "status")
            cor_badge = STATUS_CORES.get(status_atual, "#b57b3f")
            is_selected = (st.session_state["gv_sel"] == idx)
            classe_ativo = " ativo" if is_selected else ""
            
            idade = row.get("_idade", None)
            txt_idade = f"{idade} dias em pátio" if idade is not None else ""
            txt_farol = farol_idade(idade) if status_atual != "Entregue" else "🟢"
            
            txt_ag = f"<div class='vag'>📅 {sv(row,'data_entrega')} às {sv(row,'hora_entrega')}</div>" if status_atual == "Agendado" else ""
            
            card_html = f"""
            <div class="vcard{classe_ativo}">
                <div class="vcard-row">
                    <div class="vcard-left">
                        <span class="vcard-modelo">{sv(row, 'modelo')}</span>
                        <span class="vcard-fab">{sv(row, 'fabricante')}</span>
                        <div class="vcard-cli"><b>Cli:</b> {sv(row, 'cliente')} | <b>Chassi:</b> ...{ch[-6:]}</div>
                        <div class="vcard-tags">
                            <span class="vtag">📍 {sv(row, 'local_atual')}</span>
                            <span class="vtag">🎨 {sv(row, 'cor')}</span>
                        </div>
                        {txt_ag}
                    </div>
                    <div class="vcard-right">
                        <span class="vbadge" style="background:{cor_badge};">{status_atual}</span>
                        <div class="vidade">{txt_farol} {txt_idade}</div>
                    </div>
                </div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)
            
            if st.button(f"🔍 Tratar: {ch[-6:]}", key=f"btn_sel_{idx}", use_container_width=True):
                st.session_state["gv_sel"] = idx
                st.session_state["ag_forcar"] = False
                st.rerun()

    with col_painel:
        idx_sel = st.session_state["gv_sel"]
        if idx_sel is not None and idx_sel in df_gv.index:
            row = df_gv.loc[idx_sel]
            chassi_sel = sv(row, "chassi")
            status_atual = sv(row, "status")
            cor_badge = STATUS_CORES.get(status_atual, "#b57b3f")

            st.markdown(f"""
            <div class="painel-wrap">
                <span class="p-title">{sv(row, 'modelo')}</span>
                <span class="p-fab">{sv(row, 'fabricante')}</span><br>
                <span class="p-badge" style="background:{cor_badge};">{status_atual}</span>
                <p class="p-sub"><b>ID Único:</b> {sv(row,'id')} | <b>Chassi:</b> {chassi_sel}<br>
                <b>Última atualização:</b> {sv(row,'atualizado_em')} por {sv(row,'atualizado_por')}</p>
            </div>
            """, unsafe_allow_html=True)

            # ── Abas Laterais de Ação Reestabelecidas Completamente ───────────
            t1, t2, t3 = st.tabs(["📝 Detalhes Completos", "⚙️ Atualizar Status / Dados", "🖨️ Documentação / Agendamento"])

            with t1:
                st.markdown("<div class='det-sec'><div class='det-head'>Dados do Veículo</div><div class='det-grid'>", unsafe_allow_html=True)
                st.markdown(f"<div><div class='det-l'>Placa</div><div class='det-v'>{sv(row,'placa')}</div></div>", unsafe_allow_html=True)
                st.markdown(f"<div><div class='det-l'>Cor</div><div class='det-v'>{sv(row,'cor')}</div></div>", unsafe_allow_html=True)
                st.markdown(f"<div><div class='det-l'>Ano Fab / Mod</div><div class='det-v'>{sv(row,'ano_fabricacao')} / {sv(row,'ano_modelo')}</div></div>", unsafe_allow_html=True)
                st.markdown(f"<div><div class='det-l'>Combustível</div><div class='det-v'>{sv(row,'combustivel')}</div></div>", unsafe_allow_html=True)
                st.markdown("</div></div>", unsafe_allow_html=True)

                st.markdown("<div class='det-sec'><div class='det-head'>Vínculo Comercial</div><div class='det-grid'>", unsafe_allow_html=True)
                st.markdown(f"<div><div class='det-l'>Cliente</div><div class='det-v'>{sv(row,'cliente')}</div></div>", unsafe_allow_html=True)
                st.markdown(f"<div><div class='det-l'>Locadora / Parceiro</div><div class='det-v'>{sv(row,'locadora')}</div></div>", unsafe_allow_html=True)
                st.markdown(f"<div><div class='det-l'>Pedido / Contrato</div><div class='det-v'>{sv(row,'pedido')}</div></div>", unsafe_allow_html=True)
                st.markdown(f"<div><div class='det-l'>Consultor Prospecção</div><div class='det-v'>{sv(row,'consultor')}</div></div>", unsafe_allow_html=True)
                st.markdown("</div></div>", unsafe_allow_html=True)

                st.markdown("<div class='det-sec'><div class='det-head'>Logística & Pátio</div><div class='det-grid'>", unsafe_allow_html=True)
                st.markdown(f"<div><div class='det-l'>Localização Atual</div><div class='det-v'>{sv(row,'local_atual')}</div></div>", unsafe_allow_html=True)
                st.markdown(f"<div><div class='det-l'>Data Chegada Pátio</div><div class='det-v'>{sv(row,'data_chegada')}</div></div>", unsafe_allow_html=True)
                st.markdown(f"<div><div class='det-l'>Transporte Solicitado?</div><div class='det-v'>{sv(row,'transporte_solicitado')}</div></div>", unsafe_allow_html=True)
                st.markdown("</div></div>", unsafe_allow_html=True)

                if status_atual in ("Agendado", "Entregue"):
                    st.markdown("<div class='det-sec'><div class='det-head'>Dados de Agendamento / Entrega</div><div class='det-grid'>", unsafe_allow_html=True)
                    st.markdown(f"<div><div class='det-l'>Data Agendada</div><div class='det-v'>{sv(row,'data_entrega')}</div></div>", unsafe_allow_html=True)
                    st.markdown(f"<div><div class='det-l'>Horário</div><div class='det-v'>{sv(row,'hora_entrega')}</div></div>", unsafe_allow_html=True)
                    st.markdown(f"<div><div class='det-l'>Loja de Entrega</div><div class='det-v'>{sv(row,'loja_entrega')}</div></div>", unsafe_allow_html=True)
                    st.markdown(f"<div><div class='det-l'>Entregador</div><div class='det-v'>{sv(row,'entregador')}</div></div>", unsafe_allow_html=True)
                    st.markdown("</div></div>", unsafe_allow_html=True)

                if pode_editar:
                    st.markdown("<div class='det-sec'><div class='det-head'>Resultados Financeiros</div><div class='det-grid'>", unsafe_allow_html=True)
                    st.markdown(f"<div><div class='det-l'>Valor NF</div><div class='det-v'>R$ {sv(row,'valor_nf')}</div></div>", unsafe_allow_html=True)
                    st.markdown(f"<div><div class='det-l'>Margem</div><div class='det-v'>R$ {sv(row,'margem')}</div></div>", unsafe_allow_html=True)
                    st.markdown(f"<div><div class='det-l'>Comissão</div><div class='det-v'>R$ {sv(row,'comissao')}</div></div>", unsafe_allow_html=True)
                    st.markdown("</div></div>", unsafe_allow_html=True)

            with t2:
                if not pode_editar:
                    st.warning("Seu usuário não possui permissão para editar registros.")
                else:
                    with st.form(f"form_edicao_{idx_sel}"):
                        ed_sta = st.selectbox("Novo Status", GV_STATUS_LIST, index=GV_STATUS_LIST.index(status_atual))
                        ed_loca = st.text_input("Localização Atual", value=sv(row,"local_atual"))
                        ed_cli = st.text_input("Cliente", value=sv(row,"cliente"))
                        ed_ped = st.text_input("Pedido/Contrato", value=sv(row,"pedido"))
                        ed_cons = st.text_input("Consultor", value=sv(row,"consultor"))
                        ed_trans = st.selectbox("Transporte Solicitado?", ["Não", "Sim"], index=0 if sv(row,"transporte_solicitado")=="Não" else 1)
                        ed_ava = st.selectbox("Possui Avaria?", ["Não", "Sim"], index=0 if sv(row,"avaria")=="Não" else 1)
                        ed_obs_ava = st.text_area("Descrição da Avaria", value=sv(row,"obs_avaria"), height=68) # Modificado rows=2 para height=68
                        
                        ed_vnf = st.number_input("Valor NF", value=float(row.get("valor_nf", 0) if pd.notna(row.get("valor_nf")) else 0.0))
                        ed_marg = st.number_input("Margem", value=float(row.get("margem", 0) if pd.notna(row.get("margem")) else 0.0))
                        ed_comi = st.number_input("Comissão", value=float(row.get("comissao", 0) if pd.notna(row.get("comissao")) else 0.0))

                        if st.form_submit_button("💾 Confirmar Alterações", use_container_width=True):
                            agora_s = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                            payload = {
                                "action": "update", "id": sv(row,"id"), "status": ed_sta, "local_atual": ed_loca.strip(),
                                "cliente": ed_cli.strip() if ed_cli.strip() else "Estoque", "pedido": ed_ped.strip(),
                                "consultor": ed_cons.strip(), "transporte_solicitado": ed_trans, "avaria": ed_ava,
                                "obs_avaria": ed_obs_ava.strip(), "valor_nf": ed_vnf, "margem": ed_marg, "comissao": ed_comi,
                                "atualizado_em": agora_s, "atualizado_por": usuario
                            }
                            if gv_enviar(payload):
                                st.success("Veículo updated!")
                                gv_carregar.clear(); st.rerun()

            with t3:
                st.markdown("#### 📅 Agendamento de Entrega ao Cliente")
                com_data = parse_data(row.get("data_entrega", "")) or hoje
                com_hora = row.get("hora_entrega", "10:00")
                if not com_hora or str(com_hora).strip() == "—": com_hora = "10:00"
                com_loja = row.get("loja_entrega", "")
                if not com_loja or str(com_loja).strip() == "—": com_loja = GV_LOJAS[0]
                com_entregador = row.get("entregador", "")
                if not com_entregador or str(com_entregador).strip() == "—": com_entregador = ""

                with st.form(f"form_agendamento_{idx_sel}"):
                    c_ag1, c_ag2 = st.columns(2)
                    with c_ag1:
                        ag_data = st.date_input("Data da Entrega", value=com_data)
                        horas_lista = [f"{h:02d}:{m:02d}" for h in range(8, 19) for m in (0, 30)]
                        if com_hora not in horas_lista: horas_lista.insert(0, com_hora)
                        ag_hora = st.selectbox("Horário", horas_lista, index=horas_lista.index(com_hora))
                    with c_ag2:
                        ag_loja = st.selectbox("Loja de Retirada", GV_LOJAS, index=GV_LOJAS.index(com_loja) if com_loja in GV_LOJAS else 0)
                        ag_entr = st.text_input("Nome do Entregador", value=com_entregador)
                    
                    alertas_ops = []
                    try:
                        h_t, m_t = map(int, ag_hora.split(":"))
                        h_obj = datetime.time(h_t, m_t)
                    except:
                        h_obj = datetime.time(12, 0)
                    
                    msg_rodizio = verificar_rodizio(sv(row,"placa"), ag_data, h_obj)
                    if msg_rodizio: alertas_ops.append(msg_rodizio)
                    msg_conflito = verificar_conflito_loja(df_gv, ag_data, h_obj, ag_loja, excluir_idx=idx_sel)
                    if msg_conflito: alertas_ops.append(msg_conflito)
                    
                    if alertas_ops:
                        for al in alertas_ops: st.error(al)
                        st.session_state["ag_forcar"] = st.checkbox("Sim, assumo o risco operacional e quero forçar", value=st.session_state["ag_forcar"])
                    else:
                        st.session_state["ag_forcar"] = True

                    btn_texto = "📅 Agendar & Mudar Status para 'Agendado'" if status_atual != "Agendado" else "🔄 Atualizar Dados do Agendamento"
                    
                    if st.form_submit_button(btn_texto, use_container_width=True, disabled=not pode_editar):
                        if st.session_state["ag_forcar"]:
                            agora_s = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                            payload = {
                                "action": "update", "id": sv(row, "id"), "status": "Agendado",
                                "data_entrega": ag_data.strftime("%d/%m/%Y"), "hora_entrega": ag_hora,
                                "loja_entrega": ag_loja, "entregador": ag_entr.strip() if ag_entr.strip() else "—",
                                "atualizado_em": agora_s, "atualizado_por": usuario
                            }
                            if gv_enviar(payload):
                                st.success("Agendamento salvo!"); gv_carregar.clear(); st.rerun()

                st.markdown("---")
                st.markdown("#### 🖨️ Documentos Oficiais Carrera Signature")
                seg_lista = card_segmentos_disponiveis()
                loc_veic = sv(row, "locadora")
                idx_default_seg = seg_lista.index(loc_veic) if loc_veic in seg_lista else 0
                sel_seg_card = st.selectbox("Selecione o Segmento para o Layout:", seg_lista, index=idx_default_seg)
                
                if sv(row, "data_entrega") == "—" or sv(row, "loja_entrega") == "—":
                    st.info("Preencha o agendamento acima para poder gerar o Card Oficial em PDF.")
                else:
                    pdf_bytes = gerar_pdf_agendamento(row, sv, segmento=sel_seg_card)
                    st.download_button("📥 Baixar Card de Agendamento Premium (PDF)", data=pdf_bytes,
                                       file_name=f"Agendamento_{sv(row,'placa') or sv(row,'chassi')[-6:]}.pdf",
                                       mime="application/pdf", use_container_width=True)

                if status_atual == "Agendado" and pode_editar:
                    st.markdown("---")
                    st.markdown("#### 🏁 Finalizar Processo (Entrega Realizada)")
                    with st.form(f"form_entrega_{idx_sel}"):
                        senha = st.text_input("Senha de Fechamento Interno", type="password")
                        if st.form_submit_button("✅ Confirmar como Veículo ENTREGUE", use_container_width=True):
                            if senha == SENHA_FECHAMENTO:
                                agora_s = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                                payload = { "action": "update", "id": sv(row, "id"), "status": "Entregue", "atualizado_em": agora_s, "atualizado_por": usuario }
                                if gv_enviar(payload):
                                    st.success("Veículo finalizado no sistema!"); gv_carregar.clear(); st.rerun()
                            else:
                                st.error("Senha incorreta!")
        else:
            st.markdown("""
            <div style="border:2px dashed #ddd8d0;border-radius:14px;padding:40px;text-align:center;color:#94a3b8;margin-top:22px;">
                <span style="font-size:40px;">🚘</span><br>
                <p style="font-size:14px;font-weight:600;margin-top:10px;">Selecione um veículo da lista à esquerda para tratar ou realizar agendamentos.</p>
            </div>
            """, unsafe_allow_html=True)

    # ── Solicitação de Transporte Coletivo / Roteirização ────────────────────
    st.markdown("---")
    st.markdown(f"<h3 style='color:{AZUL};'>🚛 Solicitação de Transporte / Logística Integrada</h3>", unsafe_allow_html=True)
    c_p1, c_p2 = st.columns(2)
    with c_p1:
        p_filtro = st.selectbox("Período de Agendamentos", ["Hoje", "Amanhã", "Próximos 3 Dias", "Próximos 7 Dias", "Todos os Agendados"])
    with c_p2:
        p_loja = st.selectbox("Filtrar por Loja de Destino", ["Todas"] + GV_LOJAS)

    if not df_gv.empty:
        df_ag = df_gv[df_gv["status"] == "Agendado"].copy()
        datas_alvo = []
        if p_filtro == "Hoje": datas_alvo.append(hoje.strftime("%d/%m/%Y"))
        elif p_filtro == "Amanhã": datas_alvo.append((hoje + datetime.timedelta(days=1)).strftime("%d/%m/%Y"))
        elif p_filtro == "Próximos 3 Dias":
            for d in range(3): datas_alvo.append((hoje + datetime.timedelta(days=d)).strftime("%d/%m/%Y"))
        elif p_filtro == "Próximos 7 Dias":
            for d in range(7): datas_alvo.append((hoje + datetime.timedelta(days=d)).strftime("%d/%m/%Y"))

        if p_filtro != "Todos os Agendados" and datas_alvo:
            df_ag = df_ag[df_ag["data_entrega"].astype(str).str.strip().isin(datas_alvo)]
        if p_loja != "Todas":
            df_ag = df_ag[df_ag["loja_entrega"] == p_loja]

        if not df_ag.empty:
            chassis_marcados = []
            linhas_todas = []
            for idx, r_ag in df_ag.iterrows():
                lbl_c = f"📌 {sv(r_ag,'data_entrega')} {sv(r_ag,'hora_entrega')} — {sv(r_ag,'modelo')} ({sv(r_ag,'cor')}) | Destino: {sv(r_ag,'loja_entrega')}"
                if st.checkbox(lbl_c, value=True, key=f"chk_transp_{idx}"):
                    chassis_marcados.append(sv(r_ag, "chassi"))
                linhas_todas.append({
                    "id": sv(r_ag, "id"), "data": sv(r_ag, "data_entrega"), "hora": sv(r_ag, "hora_entrega"),
                    "cliente": sv(r_ag, "cliente"), "modelo": sv(r_ag, "modelo"), "chassi": sv(r_ag, "chassi"),
                    "placa": sv(r_ag, "placa"), "cor": sv(r_ag, "cor"), "loja": sv(r_ag, "loja_entrega"),
                    "extra": (sv(r_ag, "transporte_solicitado") == "Sim")
                })

            if chassis_marcados:
                if pode_editar and st.button("🚀 Sinalizar no Banco: 'Transporte Solicitado'", use_container_width=True):
                    for _, n_r in df_ag[df_ag["chassi"].isin(chassis_marcados)].iterrows():
                        gv_enviar({"action": "update", "id": n_r["id"], "transporte_solicitado": "Sim", "atualizado_em": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "atualizado_por": usuario})
                    st.success("Status de transporte atualizado!"); gv_carregar.clear(); st.rerun()

                SEP = "-"*62; SEP2 = "="*62
                linhas_txt = [f"SOLICITAÇÃO DE TRANSPORTE — {p_filtro.upper()}", SEP2, f"Total: {len(chassis_marcados)} veículo(s)", ""]
                lojas_todas = sorted(list(set([l["loja"] for l in linhas_todas if l["chassi"] in chassis_marcados])))
                for loja in lojas_todas:
                    grupo = sorted([l for l in linhas_todas if l["loja"] == loja and l["chassi"] in chassis_marcados], key=lambda x: (x["data"], x["hora"]))
                    linhas_txt.append(f"📍 {loja.upper()} ({len(grupo)} veículo(s))")
                    linhas_txt.append(SEP)
                    for l in grupo:
                        linhas_txt.append(f"[✓] {l['data']} {l['hora']:<6} {l['cliente'][:20]:<21} {l['modelo'][:20]:<21} {l['chassi']} {l['placa']}")
                    linhas_txt.append("")
                linhas_txt += [SEP2, "Carrera Signature"]
                st.text_area("Texto Formatado para WhatsApp/E-mail", value="\n".join(linhas_txt), height=200)

if __name__ == "__main__":
    render()