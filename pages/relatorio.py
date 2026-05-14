"""
relatorio.py — Carrera Signature
Relatório consolidado premium: LM + Estoque (Sheets) + Salesforce + Cadastro Manual
"""

import io
import os
import sys
import datetime
import subprocess
from datetime import date

import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════
DADOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Dados")
sys.path.insert(0, DADOS_DIR)

AZUL     = "#213144"
AZUL2    = "#1a2535"
DOURADO  = "#b57b3f"
DOURADO2 = "#dfc28a"
BORDA    = "#d4c4a8"
CINZA    = "#64748b"
BRANCO   = "#ffffff"
BG       = "#f8f5f0"

ARQ_BASE  = os.path.join(DADOS_DIR, "base_consolidada_completa.xlsx")
ARQ_PARQ  = os.path.join(DADOS_DIR, "base_consolidada_completa.parquet")
ARQ_MAN   = os.path.join(DADOS_DIR, "pedidos_manuais.xlsx")

SHEET_ID_SF      = "1RTm8TYpHJPGJKlh7N9AAf6iP212F7Z9u9P_-VdKfT1w"
SHEET_ID_ESTOQUE = "1BpAtiXz4AEuQg4kVx8OFonohPlvbScdOgWPIZRxQnxo"
GID_ESTOQUE      = "461042346"

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

COLUNAS_REL = [
    "Origem venda","Pedido","Segmento","Tipo","Nome","Documento",
    "Data de Inclusão","Data de Status","Mensalidade","Valor Total","Status",
    "ANO DA VENDA","MÊS DA VENDA","Venda","Data da retirada",
    "Vigência Final do contrato","Chassi","Placa","Período","Km",
    "Modelo Oficial","Cor","Opcional","Local de Venda","UF","City",
    "KickBack","Preço NF","Comissão Vendedor R$","Comissão Carrera",
    "Marca","Locadora","Empresa",
]

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800;900&display=swap');

section[data-testid="stMain"] * {{ font-family:'Montserrat',sans-serif !important; }}
section[data-testid="stMain"]  {{ background:{BG} !important; }}
div[data-testid="stAppViewContainer"] > section {{ background:{BG} !important; }}

/* ── Header ── */
.rel-header {{
    background:linear-gradient(135deg, {AZUL2} 0%, {AZUL} 60%, #2d4a6b 100%);
    border-radius:20px;
    padding:28px 32px 24px;
    margin-bottom:24px;
    position:relative;
    overflow:hidden;
    border:1px solid {DOURADO};
}}
.rel-header::before {{
    content:"";
    position:absolute;
    top:-40px; right:-40px;
    width:200px; height:200px;
    border-radius:50%;
    background:rgba(181,123,63,.12);
}}
.rel-header::after {{
    content:"";
    position:absolute;
    bottom:-60px; right:60px;
    width:140px; height:140px;
    border-radius:50%;
    background:rgba(181,123,63,.07);
}}
.rel-titulo  {{ font-size:26px; font-weight:900; color:{BRANCO}; margin:0; letter-spacing:-.3px; }}
.rel-sub     {{ font-size:12px; color:{DOURADO2}; margin:4px 0 0; letter-spacing:.6px; text-transform:uppercase; }}
.rel-badge   {{
    display:inline-block;
    background:rgba(181,123,63,.25);
    border:1px solid {DOURADO};
    color:{DOURADO2};
    font-size:11px; font-weight:700;
    padding:3px 12px; border-radius:999px;
    margin-top:10px; letter-spacing:.5px;
}}

/* ── KPI cards ── */
.kpi-grid {{
    display:grid;
    grid-template-columns:repeat(6,1fr);
    gap:12px;
    margin-bottom:24px;
}}
.kpi-card {{
    background:{BRANCO};
    border:1px solid {BORDA};
    border-radius:16px;
    padding:20px 14px 16px;
    text-align:center;
    position:relative;
    overflow:hidden;
    box-shadow:0 2px 12px rgba(33,49,68,.06);
    transition:transform .15s, box-shadow .15s;
}}
.kpi-card:hover {{ transform:translateY(-2px); box-shadow:0 8px 24px rgba(33,49,68,.10); }}
.kpi-card::before {{
    content:"";
    position:absolute; top:0; left:0; right:0;
    height:3px;
    background:linear-gradient(90deg, {DOURADO}, {DOURADO2});
}}
.kpi-icon  {{ font-size:22px; margin-bottom:8px; }}
.kpi-val   {{ font-size:22px; font-weight:900; color:{AZUL}; line-height:1.1; }}
.kpi-val.verde  {{ color:#16a34a; }}
.kpi-val.dourado {{ color:{DOURADO}; }}
.kpi-val.roxo   {{ color:#7c3aed; }}
.kpi-label {{ font-size:10px; font-weight:700; color:{CINZA}; text-transform:uppercase; letter-spacing:.7px; margin-top:5px; }}

/* ── Seção ── */
.secao-titulo {{
    font-size:14px; font-weight:800; color:{AZUL};
    text-transform:uppercase; letter-spacing:.8px;
    border-left:4px solid {DOURADO};
    padding-left:12px;
    margin:28px 0 14px;
}}

/* ── Pódio ── */
.podium-wrap  {{ display:flex; align-items:flex-end; gap:12px; justify-content:center; padding:10px 0 4px; }}
.podium-col   {{ flex:1; display:flex; flex-direction:column; align-items:center; max-width:200px; }}
.podium-medal {{ font-size:28px; margin-bottom:6px; }}
.podium-bar   {{
    width:100%;
    border-radius:14px 14px 8px 8px;
    display:flex; flex-direction:column;
    align-items:center; justify-content:flex-end;
    padding:16px 10px 14px;
    text-align:center;
    border:1px solid {BORDA};
    position:relative; overflow:hidden;
}}
.podium-bar::before {{
    content:"";
    position:absolute; top:0; left:0; right:0;
    height:3px;
}}
.p1 .podium-bar {{ background:linear-gradient(180deg,#fff8e8,#fdf0ce); min-height:160px; }}
.p1 .podium-bar::before {{ background:linear-gradient(90deg,#f6d36b,#d89b22); }}
.p2 .podium-bar {{ background:linear-gradient(180deg,#f6f8fc,#e8edf5); min-height:120px; }}
.p2 .podium-bar::before {{ background:linear-gradient(90deg,#cfd5df,#8b95a7); }}
.p3 .podium-bar {{ background:linear-gradient(180deg,#fdf4ee,#f5e0d0); min-height:95px; }}
.p3 .podium-bar::before {{ background:linear-gradient(90deg,#efb083,#c96a27); }}
.podium-name {{ font-size:12px; font-weight:800; color:{AZUL}; line-height:1.2; margin-bottom:4px; word-break:break-word; }}
.podium-num  {{ font-size:28px; font-weight:900; color:{AZUL}; line-height:1; }}
.podium-leg  {{ font-size:9px; font-weight:700; color:{CINZA}; text-transform:uppercase; letter-spacing:.6px; margin-top:2px; }}

/* ── Tabela ranking ── */
.rank-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
.rank-table th {{
    background:{AZUL}; color:{BRANCO};
    font-size:10px; font-weight:700; text-transform:uppercase;
    letter-spacing:.6px; padding:8px 12px; text-align:left;
}}
.rank-table td {{ padding:8px 12px; border-bottom:1px solid #f0ebe2; color:{AZUL}; }}
.rank-table tr:last-child td {{ border-bottom:none; }}
.rank-table tr:hover td {{ background:#fdf8f0; }}
.rank-badge {{
    display:inline-block;
    background:linear-gradient(135deg,{DOURADO},{DOURADO2});
    color:{BRANCO}; font-size:10px; font-weight:800;
    padding:2px 8px; border-radius:999px;
}}

/* ── Card container ── */
.card {{
    background:{BRANCO};
    border:1px solid {BORDA};
    border-radius:16px;
    padding:20px;
    box-shadow:0 2px 12px rgba(33,49,68,.05);
    height:100%;
}}
.card-titulo {{
    font-size:12px; font-weight:800; color:{AZUL};
    text-transform:uppercase; letter-spacing:.7px;
    margin-bottom:14px; padding-bottom:10px;
    border-bottom:2px solid {BORDA};
}}

/* ── Filtros ── */
.filtros-wrap {{
    background:{BRANCO};
    border:1px solid {BORDA};
    border-radius:16px;
    padding:18px 20px 14px;
    margin-bottom:20px;
    box-shadow:0 2px 12px rgba(33,49,68,.04);
}}

/* ── Tabela principal ── */
div[data-testid="stDataFrame"] {{
    border:1px solid {BORDA} !important;
    border-radius:14px !important;
    overflow:hidden;
}}

@media (max-width:1100px) {{
    .kpi-grid {{ grid-template-columns:repeat(3,1fr); }}
    .podium-wrap {{ flex-wrap:wrap; }}
}}
</style>
"""


# ══════════════════════════════════════════════════════════════════════════════
# AUTH GOOGLE
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_resource
def _gc():
    info  = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


# ══════════════════════════════════════════════════════════════════════════════
# LEITURA DAS BASES
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=240, show_spinner=False)
def _ler_salesforce() -> pd.DataFrame:
    try:
        gc = _gc()
        sh = gc.open_by_key(SHEET_ID_SF)
        ws = sh.get_worksheet(0)
        return pd.DataFrame(ws.get_all_records())
    except Exception:
        arq = os.path.join(DADOS_DIR, "Base Salesforce.xlsx")
        if os.path.exists(arq):
            return pd.read_excel(arq)
        return pd.DataFrame()


@st.cache_data(ttl=120, show_spinner=False)
def _ler_estoque() -> pd.DataFrame:
    url = (f"https://docs.google.com/spreadsheets/d/{SHEET_ID_ESTOQUE}"
           f"/export?format=csv&gid={GID_ESTOQUE}")
    try:
        df = pd.read_csv(url, header=0)
        df.columns = [c.strip().lower().replace(" ","_") for c in df.columns]
        for col in ["data_chegada","data_entrega","criado_em","atualizado_em"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def _ler_base() -> pd.DataFrame:
    try:
        if os.path.exists(ARQ_PARQ): return pd.read_parquet(ARQ_PARQ)
        if os.path.exists(ARQ_BASE):  return pd.read_excel(ARQ_BASE)
    except Exception as e:
        st.error(f"Erro ao ler base: {e}")
    return pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def _ler_manuais() -> pd.DataFrame:
    if not os.path.exists(ARQ_MAN):
        return pd.DataFrame(columns=COLUNAS_REL)
    try:
        df = pd.read_excel(ARQ_MAN)
        for c in COLUNAS_REL:
            if c not in df.columns: df[c] = ""
        return df
    except Exception:
        return pd.DataFrame(columns=COLUNAS_REL)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str).str.replace(",",".").str.replace(r"[^\d.-]","",regex=True),
        errors="coerce")


def _brl(v, decimais=0) -> str:
    try:
        f = f"{{:,.{decimais}f}}"
        return "R$ " + f.format(float(v)).replace(",","X").replace(".",",").replace("X",".")
    except: return "R$ 0"


def _tipo(doc) -> str:
    d = "".join(filter(str.isdigit, str(doc)))
    if len(d)==11: return "PF"
    if len(d)==14: return "PJ"
    return ""


def _lookup_sf(df_sf, pedido) -> str:
    if df_sf.empty or "Nro do Pedido" not in df_sf.columns: return "Não encontrado"
    m = df_sf[df_sf["Nro do Pedido"].astype(str).str.strip() == str(pedido).strip()]
    if m.empty: return "Não encontrado"
    return str(m.iloc[0].get("Proprietário da oportunidade","")).strip() or "Não encontrado"


def _garantir(df, cols):
    for c in cols:
        if c not in df.columns: df[c] = ""
    return df


def _primeiro_dia_mes():
    h = date.today(); return date(h.year, h.month, 1)


def _ultimo_dia_mes():
    h = date.today()
    prox = date(h.year+1,1,1) if h.month==12 else date(h.year,h.month+1,1)
    return (pd.Timestamp(prox)-pd.Timedelta(days=1)).date()


# ══════════════════════════════════════════════════════════════════════════════
# CONSOLIDAÇÃO
# ══════════════════════════════════════════════════════════════════════════════
def _normalizar(df: pd.DataFrame, df_sf: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return pd.DataFrame(columns=COLUNAS_REL)
    b = df.copy()

    mapa = {
        "orderId":"Pedido","clientName":"Nome","cpfCnpj":"Documento",
        "orderStatus":"Status","totalOrder":"Valor Total","segment":"Segmento",
        "optional":"Opcional","chassis":"Chassi","deliveryPlate":"Placa",
        "monthlyInstallment":"Mensalidade","monthlyKmValue":"Km",
        "deadline":"Período","brand":"Marca","kickback":"KickBack",
        "vehicleValue":"Preço NF","comissao":"Comissão Carrera",
        "comissao_vendedor":"Comissão Vendedor R$",
        "dealerDelivery":"Local de Venda","estado":"UF","city":"City",
        "salesChannel":"Origem venda","clientType":"Tipo",
        "consultorNome":"Venda",
    }
    b.rename(columns={k:v for k,v in mapa.items() if k in b.columns}, inplace=True)

    if "Tipo" not in b.columns or b["Tipo"].astype(str).str.strip().eq("").all():
        if "Documento" in b.columns: b["Tipo"] = b["Documento"].apply(_tipo)

    for col in ["dateCreated","dateLastUpdated","Data Assinatura","deliveryDate"]:
        if col in b.columns:
            b[col] = pd.to_datetime(b[col], errors="coerce", dayfirst=True)

    # Renomeia datas
    b.rename(columns={"dateCreated":"Data de Inclusão","dateLastUpdated":"Data de Status",
                       "deliveryDate":"Data da retirada"}, inplace=True)

    if "Data de Inclusão" in b.columns:
        b["ANO DA VENDA"] = b["Data de Inclusão"].dt.year.astype("Int64").astype(str).replace("<NA>","")
        b["MÊS DA VENDA"] = b["Data de Inclusão"].dt.month.astype("Int64").astype(str).replace("<NA>","")

    if "Locadora" not in b.columns: b["Locadora"] = "LM FROTAS"

    # Enriquece Salesforce
    if not df_sf.empty and "Nro do Pedido" in df_sf.columns:
        sf = df_sf.drop_duplicates(subset=["Nro do Pedido"]).copy()
        sf["_k"] = sf["Nro do Pedido"].astype(str).str.strip()
        sf = sf.set_index("_k")

        def _sf_val(pedido, col):
            k = str(pedido).strip()
            if k in sf.index and col in sf.columns:
                return sf.loc[k, col]
            return ""

        if "Venda" not in b.columns or b["Venda"].astype(str).str.strip().eq("").all():
            b["Venda"] = b["Pedido"].apply(lambda p: _lookup_sf(df_sf, p))

        for col_sf, col_rel in [("Nome da conta","Empresa"),("Origem da venda","Origem venda"),
                                  ("Comissionamento","Comissão Vendedor R$")]:
            if col_sf in sf.columns:
                b[col_rel] = b["Pedido"].apply(lambda p: _sf_val(p, col_sf))

    return _garantir(b, COLUNAS_REL)


def _base_completa() -> pd.DataFrame:
    df_sf  = _ler_salesforce()
    df_lm  = _ler_base()
    df_man = _ler_manuais()
    partes = []
    if not df_lm.empty:  partes.append(_normalizar(df_lm, df_sf))
    if not df_man.empty: partes.append(_garantir(df_man, COLUNAS_REL))
    if not partes: return pd.DataFrame(columns=COLUNAS_REL)
    df = pd.concat(partes, ignore_index=True)
    return _garantir(df, COLUNAS_REL)[COLUNAS_REL]


def _concluidos(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra pedidos concluídos."""
    if df.empty or "Status" not in df.columns: return pd.DataFrame(columns=COLUNAS_REL)
    return df[df["Status"].astype(str).str.strip() == "Pedido concluído"].copy()


# ══════════════════════════════════════════════════════════════════════════════
# COMPONENTES VISUAIS
# ══════════════════════════════════════════════════════════════════════════════
def _kpi_card(icon, val, label, cls=""):
    return f"""<div class="kpi-card">
        <div class="kpi-icon">{icon}</div>
        <div class="kpi-val {cls}">{val}</div>
        <div class="kpi-label">{label}</div>
    </div>"""


def _podium_html(ranking, label_col, val_col, unidade="pedidos"):
    """Gera HTML do pódio. ranking = lista de dicts ordenada por qtd desc."""
    medalhas = {0:"🥇", 1:"🥈", 2:"🥉"}
    classes  = {0:"p1",  1:"p2",  2:"p3"}
    # ordem visual: 2º, 1º, 3º
    idx_vis  = [1,0,2] if len(ranking)>=3 else list(range(len(ranking)))
    cols_html = []
    for idx in idx_vis:
        if idx >= len(ranking): continue
        r    = ranking[idx]
        nome = str(r[label_col])[:22]
        qtd  = int(r[val_col])
        cls  = classes.get(idx,"p3")
        med  = medalhas.get(idx,"🏅")
        cols_html.append(f"""
        <div class="podium-col {cls}">
            <div class="podium-medal">{med}</div>
            <div class="podium-bar">
                <div class="podium-num">{qtd}</div>
                <div class="podium-leg">{unidade}</div>
                <div class="podium-name">{nome}</div>
            </div>
        </div>""")
    return f'<div class="podium-wrap">{"".join(cols_html)}</div>'


def _rank_table(df_rank, col_nome, col_qtd, col_val=None):
    rows = ""
    for i, (_, r) in enumerate(df_rank.iterrows()):
        badge = f'<span class="rank-badge">#{i+1}</span>'
        val_extra = f"<td>{_brl(r[col_val])}</td>" if col_val and col_val in df_rank.columns else ""
        rows += f"<tr><td>{badge}</td><td><b>{r[col_nome]}</b></td><td>{int(r[col_qtd])}</td>{val_extra}</tr>"
    headers = "<th>#</th><th>Nome</th><th>Qtd</th>"
    if col_val and col_val in df_rank.columns: headers += "<th>Valor</th>"
    return f'<table class="rank-table"><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>'


def _gravar_manual(dados: dict) -> bool:
    try:
        df = pd.read_excel(ARQ_MAN) if os.path.exists(ARQ_MAN) else pd.DataFrame(columns=COLUNAS_REL)
        df = _garantir(df, COLUNAS_REL)
        nova = {c: str(dados.get(c,"")) for c in COLUNAS_REL}
        df = pd.concat([df, pd.DataFrame([nova])], ignore_index=True)
        df.to_excel(ARQ_MAN, index=False)
        return True
    except Exception as e:
        st.error(f"Erro: {e}"); return False


# ══════════════════════════════════════════════════════════════════════════════
# RENDER
# ══════════════════════════════════════════════════════════════════════════════
def render():
    autenticado = st.session_state.get("auth_tipo","") == "Staff"
    pode_editar = autenticado and st.session_state.get("auth_nome","") not in {
        "Andrea Bettega Pereira da Costa","Raymond Jose Duque Bello"}

    st.markdown(CSS, unsafe_allow_html=True)

    hoje = date.today()

    # ── Header ────────────────────────────────────────────────────────────────
    col_h, col_btn = st.columns([5,1])
    with col_h:
        st.markdown(f"""
        <div class="rel-header">
            <div class="rel-titulo">📊 Relatório de Performance</div>
            <div class="rel-sub">Carrera Signature · Gestão Comercial</div>
            <div class="rel-badge">Atualizado em {hoje.strftime("%d/%m/%Y")}</div>
        </div>""", unsafe_allow_html=True)
    with col_btn:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", use_container_width=True, key="rel_ref"):
            st.cache_data.clear(); st.rerun()

    # ── Carrega dados ─────────────────────────────────────────────────────────
    with st.spinner("Carregando dados..."):
        df_all    = _base_completa()
        df_estoque = _ler_estoque()

    if df_all.empty:
        st.warning("⚠️ Base de dados não encontrada. Verifique `Dados/base_consolidada_completa.xlsx`.")
        return

    # ── Abas ──────────────────────────────────────────────────────────────────
    tabs = st.tabs(["📋 Dashboard","📄 Pedidos","📤 Dados","➕ Cadastro Manual"] if pode_editar
                   else ["📋 Dashboard","📄 Pedidos"])

    # ══════════════════════════════════════════════════════════════════════════
    # ABA DASHBOARD
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[0]:

        # ── Filtros ───────────────────────────────────────────────────────────
        st.markdown('<div class="filtros-wrap">', unsafe_allow_html=True)
        fa, fb, fc, fd, fe = st.columns([2,2,2,2,2])
        with fa:
            dt_ini = st.date_input("📅 De", value=_primeiro_dia_mes(), key="d_ini", format="DD/MM/YYYY")
        with fb:
            dt_fim = st.date_input("📅 Até", value=_ultimo_dia_mes(), key="d_fim", format="DD/MM/YYYY")
        with fc:
            segs   = ["Todos"] + sorted([x for x in df_all["Segmento"].dropna().astype(str).unique() if x])
            flt_seg = st.selectbox("Segmento", segs, key="d_seg")
        with fd:
            vends  = ["Todos"] + sorted([x for x in df_all["Venda"].dropna().astype(str).unique() if x])
            flt_ven = st.selectbox("Consultor", vends, key="d_ven")
        with fe:
            locs   = ["Todas"] + sorted([x for x in df_all["Locadora"].dropna().astype(str).unique() if x])
            flt_loc = st.selectbox("Locadora", locs, key="d_loc")

        bc2_col, _ = st.columns([1,7])
        with bc2_col:
            if st.button("🧹 Limpar filtros", use_container_width=True, key="d_limpar"):
                for k in ["d_ini","d_fim","d_seg","d_ven","d_loc"]:
                    if k in st.session_state: del st.session_state[k]
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # Aplica filtros sempre
        dv = df_all.copy()
        if "Data de Inclusão" in dv.columns:
            datas = pd.to_datetime(dv["Data de Inclusão"], errors="coerce", dayfirst=True).dt.date
            dv = dv[(datas >= dt_ini) & (datas <= dt_fim)]
        if flt_seg != "Todos":  dv = dv[dv["Segmento"] == flt_seg]
        if flt_ven != "Todos":  dv = dv[dv["Venda"]    == flt_ven]
        if flt_loc != "Todas":  dv = dv[dv["Locadora"] == flt_loc]

        # Base de concluídos
        dc = _concluidos(dv)

        # Estoque do mês atual
        mes_ini = _primeiro_dia_mes(); mes_fim = _ultimo_dia_mes()
        if not df_estoque.empty and "data_entrega" in df_estoque.columns:
            data_ent = df_estoque["data_entrega"].dt.date if pd.api.types.is_datetime64_any_dtype(df_estoque["data_entrega"]) else pd.to_datetime(df_estoque["data_entrega"], errors="coerce", dayfirst=True).dt.date
            est_mes  = df_estoque[(data_ent >= mes_ini) & (data_ent <= mes_fim)]
            previsao  = len(est_mes[est_mes["status"].astype(str).str.strip() == "Agendado"])
            entregues = len(est_mes[est_mes["status"].astype(str).str.strip() == "Entregue"])
        else:
            previsao = entregues = 0

        # Métricas
        n_conc      = len(dc)
        mens_media  = _num(dc["Mensalidade"]).mean() if not dc.empty else 0
        comis_total = _num(dc["Comissão Carrera"]).sum() if not dc.empty else 0
        comis_media = _num(dc["Comissão Carrera"]).mean() if not dc.empty else 0

        # ── KPI Cards ─────────────────────────────────────────────────────────
        st.markdown(f"""
        <div class="kpi-grid">
            {_kpi_card("✍️", n_conc, "Contratos Assinados", "dourado")}
            {_kpi_card("📦", previsao, "Previsão de Entrega", "")}
            {_kpi_card("✅", entregues, "Entregas Realizadas", "verde")}
            {_kpi_card("💳", _brl(mens_media), "Mensalidade Média", "")}
            {_kpi_card("💰", _brl(comis_total), "Comissão Total", "roxo")}
            {_kpi_card("📊", _brl(comis_media), "Comissão Média", "")}
        </div>""", unsafe_allow_html=True)

        # ── Pódios ────────────────────────────────────────────────────────────
        st.markdown('<div class="secao-titulo">🏆 Ranking de Performance</div>', unsafe_allow_html=True)
        pod1, pod2 = st.columns(2)

        with pod1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-titulo">🚗 Top 3 — Modelos Mais Vendidos</div>', unsafe_allow_html=True)
            if dc.empty:
                st.info("Sem dados de concluídos no período.")
            else:
                col_mod = "Modelo Oficial" if "Modelo Oficial" in dc.columns else ("Marca" if "Marca" in dc.columns else None)
                if col_mod:
                    top_mod = (dc[col_mod].dropna().astype(str)
                               .replace(["","nan","None"], pd.NA)
                               .dropna()
                               .value_counts()
                               .reset_index()
                               .rename(columns={"index":col_mod,col_mod:"qtd",0:"qtd"})
                               .head(3))
                    if "qtd" not in top_mod.columns:
                        top_mod.columns = [col_mod,"qtd"]
                    if not top_mod.empty:
                        st.markdown(_podium_html(top_mod.to_dict("records"), col_mod, "qtd"), unsafe_allow_html=True)
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.markdown(_rank_table(top_mod, col_mod, "qtd"), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with pod2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-titulo">🧑‍💼 Top 3 — Consultores</div>', unsafe_allow_html=True)
            if dc.empty:
                st.info("Sem dados de concluídos no período.")
            else:
                col_ven = "Venda"
                if col_ven in dc.columns:
                    top_ven = (dc[col_ven].dropna().astype(str)
                               .replace(["","nan","None","Não encontrado"], pd.NA)
                               .dropna()
                               .value_counts()
                               .reset_index()
                               .rename(columns={"index":col_ven,col_ven:"qtd",0:"qtd"})
                               .head(3))
                    if "qtd" not in top_ven.columns:
                        top_ven.columns = [col_ven,"qtd"]
                    if not top_ven.empty:
                        st.markdown(_podium_html(top_ven.to_dict("records"), col_ven, "qtd"), unsafe_allow_html=True)
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.markdown(_rank_table(top_ven, col_ven, "qtd"), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # ── Rankings detalhados ───────────────────────────────────────────────
        st.markdown('<div class="secao-titulo">📊 Análise por Consultor</div>', unsafe_allow_html=True)
        r1, r2 = st.columns(2)

        with r1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-titulo">✍️ Contratos Assinados por Consultor</div>', unsafe_allow_html=True)
            if dc.empty or "Venda" not in dc.columns:
                st.info("Sem dados.")
            else:
                rank_ca = (dc.groupby("Venda", as_index=False)
                           .agg(qtd=("Pedido","count"), comissao=("Comissão Carrera","sum"))
                           .sort_values("qtd", ascending=False))
                rank_ca["comissao"] = _num(rank_ca["comissao"])
                st.markdown(_rank_table(rank_ca, "Venda", "qtd", "comissao"), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with r2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-titulo">✅ Entregas por Consultor (mês atual)</div>', unsafe_allow_html=True)
            if df_estoque.empty or "status" not in df_estoque.columns:
                st.info("Base de estoque não disponível.")
            else:
                est_ent = df_estoque.copy()
                if "data_entrega" in est_ent.columns:
                    de = est_ent["data_entrega"].dt.date if pd.api.types.is_datetime64_any_dtype(est_ent["data_entrega"]) else pd.to_datetime(est_ent["data_entrega"], errors="coerce", dayfirst=True).dt.date
                    est_ent = est_ent[(de >= mes_ini) & (de <= mes_fim)]
                est_ent = est_ent[est_ent["status"].astype(str).str.strip() == "Entregue"]
                if est_ent.empty:
                    st.info("Nenhuma entrega no mês atual.")
                else:
                    col_cons_est = "consultor" if "consultor" in est_ent.columns else None
                    if col_cons_est:
                        rank_ent = (est_ent.groupby(col_cons_est, as_index=False)
                                    .agg(qtd=("chassi","count"))
                                    .sort_values("qtd", ascending=False))
                        rank_ent.columns = ["Consultor","Qtd"]
                        st.markdown(_rank_table(rank_ent, "Consultor", "Qtd"), unsafe_allow_html=True)
                    else:
                        st.info("Campo consultor não encontrado no estoque.")
            st.markdown('</div>', unsafe_allow_html=True)

        # ── Curvas de vendas e entregas ───────────────────────────────────────
        st.markdown('<div class="secao-titulo">📈 Curvas Temporais</div>', unsafe_allow_html=True)
        g1, g2 = st.columns(2)

        with g1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-titulo">📈 Curva de Vendas por Dia</div>', unsafe_allow_html=True)
            if dc.empty or "Data de Inclusão" not in dc.columns:
                st.info("Sem dados de vendas no período.")
            else:
                curva_v = dc.copy()
                curva_v["_dia"] = pd.to_datetime(curva_v["Data de Inclusão"], errors="coerce", dayfirst=True).dt.date
                curva_v = (curva_v.groupby("_dia", as_index=False)
                           .agg(vendas=("Pedido","count"))
                           .sort_values("_dia"))
                curva_v.columns = ["Data","Vendas"]
                st.line_chart(curva_v.set_index("Data"), height=220, color=DOURADO)
            st.markdown('</div>', unsafe_allow_html=True)

        with g2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-titulo">🚚 Curva de Entregas por Dia (mês atual)</div>', unsafe_allow_html=True)
            if df_estoque.empty or "data_entrega" not in df_estoque.columns:
                st.info("Base de estoque não disponível.")
            else:
                est_curva = df_estoque[df_estoque["status"].astype(str).str.strip() == "Entregue"].copy()
                if "data_entrega" in est_curva.columns:
                    est_curva["_dia"] = est_curva["data_entrega"].dt.date if pd.api.types.is_datetime64_any_dtype(est_curva["data_entrega"]) else pd.to_datetime(est_curva["data_entrega"], errors="coerce", dayfirst=True).dt.date
                    de2 = est_curva["_dia"]
                    est_curva = est_curva[(de2 >= mes_ini) & (de2 <= mes_fim)]
                    curva_e = (est_curva.groupby("_dia", as_index=False)
                               .agg(entregas=("chassi","count"))
                               .sort_values("_dia"))
                    curva_e.columns = ["Data","Entregas"]
                    st.line_chart(curva_e.set_index("Data"), height=220, color=AZUL)
                else:
                    st.info("Campo data_entrega não encontrado.")
            st.markdown('</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # ABA PEDIDOS
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[1]:
        st.markdown('<div class="secao-titulo">📄 Pedidos Consolidados</div>', unsafe_allow_html=True)

        # Filtros rápidos
        st.markdown('<div class="filtros-wrap">', unsafe_allow_html=True)
        pf1,pf2,pf3,pf4 = st.columns(4)
        with pf1: flt_sta2 = st.selectbox("Status", ["Todos"]+sorted([x for x in df_all["Status"].dropna().astype(str).unique() if x]), key="p_sta2")
        with pf2: flt_loc2 = st.selectbox("Locadora",["Todas"]+sorted([x for x in df_all["Locadora"].dropna().astype(str).unique() if x]), key="p_loc2")
        with pf3: flt_ven2 = st.selectbox("Consultor",["Todos"]+sorted([x for x in df_all["Venda"].dropna().astype(str).unique() if x]), key="p_ven2")
        with pf4: s_busca  = st.text_input("🔎 Pedido / Chassi / Cliente", key="p_busca2", placeholder="Buscar...")
        pb2_col, _ = st.columns([1,7])
        with pb2_col:
            if st.button("🧹 Limpar filtros", use_container_width=True, key="p_limpar2"):
                for k in ["p_sta2","p_loc2","p_ven2","p_busca2"]:
                    if k in st.session_state: del st.session_state[k]
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # Aplica filtros sempre
        dp = df_all.copy()
        if flt_sta2 != "Todos": dp = dp[dp["Status"]   == flt_sta2]
        if flt_loc2 != "Todas": dp = dp[dp["Locadora"] == flt_loc2]
        if flt_ven2 != "Todos": dp = dp[dp["Venda"]    == flt_ven2]
        if s_busca:
            mask = (dp["Pedido"].astype(str).str.lower().str.contains(s_busca.lower(), na=False) |
                    dp["Chassi"].astype(str).str.lower().str.contains(s_busca.lower(), na=False) |
                    dp["Nome"].astype(str).str.lower().str.contains(s_busca.lower(),   na=False))
            dp = dp[mask]

        st.markdown(f"<p style='color:{CINZA};font-size:13px;margin:6px 0 10px'>"
                    f"<b style='color:{AZUL}'>{len(dp)}</b> pedido(s)</p>", unsafe_allow_html=True)

        # Formata datas para exibição
        dp_show = dp.copy()
        for col in ["Data de Inclusão","Data de Status","Data da retirada","Vigência Final do contrato"]:
            if col in dp_show.columns:
                dp_show[col] = pd.to_datetime(dp_show[col], errors="coerce", dayfirst=True).dt.strftime("%d/%m/%Y").fillna("")
        for col in ["Mensalidade","Valor Total","Comissão Carrera","Comissão Vendedor R$","KickBack","Preço NF"]:
            if col in dp_show.columns:
                dp_show[col] = _num(dp_show[col])

        st.dataframe(dp_show, use_container_width=True, height=520, hide_index=True,
            column_config={
                "Mensalidade":          st.column_config.NumberColumn(format="R$ %.2f"),
                "Valor Total":          st.column_config.NumberColumn(format="R$ %.2f"),
                "Comissão Carrera":     st.column_config.NumberColumn(format="R$ %.2f"),
                "Comissão Vendedor R$": st.column_config.NumberColumn(format="R$ %.2f"),
                "KickBack":             st.column_config.NumberColumn(format="R$ %.2f"),
                "Preço NF":             st.column_config.NumberColumn(format="R$ %.2f"),
            })

        buf = io.BytesIO()
        dp_show.to_excel(buf, index=False, engine="openpyxl"); buf.seek(0)
        st.download_button("📥 Exportar Excel", data=buf.getvalue(),
            file_name=f"relatorio_carrera_{datetime.date.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="rel_dl")

    # ══════════════════════════════════════════════════════════════════════════
    # ABA DADOS
    # ══════════════════════════════════════════════════════════════════════════
    if pode_editar:
        with tabs[2]:
            st.markdown('<div class="secao-titulo">📤 Gestão de Dados</div>', unsafe_allow_html=True)
            st.caption("Execute os scripts em sequência. Cada etapa depende da anterior.")

            scripts = [
                ("1️⃣ Extrair Pedidos LM",    "Extracao_LM.py",      "→ Lista_LM.xlsx"),
                ("2️⃣ Detalhar Carros",        "Estrutura_Carros.py", "→ vListaCarrosDetalhes.xlsx"),
                ("3️⃣ Extrair Preços/Ofertas", "Executa_Precos.py",   "→ Ofertas_Todos_SalesChannels.xlsx"),
                ("4️⃣ Consolidar Base LM",     "Consolida_base.py",   "→ base_consolidada_completa.xlsx"),
            ]
            for label, script, desc in scripts:
                c1,c2 = st.columns([2,6])
                sp = os.path.join(DADOS_DIR, script)
                existe = os.path.exists(sp)
                with c1:
                    if st.button(label, key=f"run_{script}", use_container_width=True,
                                 disabled=not existe, type="primary"):
                        st.session_state[f"run_{script}_ok"] = True
                with c2: st.caption("⚠️ Não encontrado" if not existe else desc)
                if st.session_state.pop(f"run_{script}_ok", False):
                    with st.expander(f"📋 Log — {label}", expanded=True):
                        try:
                            proc = subprocess.Popen([sys.executable, sp],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, cwd=DADOS_DIR)
                            out=[]; ph=st.empty()
                            for line in proc.stdout:
                                out.append(line.rstrip()); ph.code("\n".join(out[-30:]))
                            proc.wait()
                            if proc.returncode==0: st.cache_data.clear(); st.success("✅ Concluído!")
                            else: st.error("❌ Erro na execução.")
                        except Exception as e: st.error(f"Erro: {e}")

            st.divider()
            st.markdown('<div class="secao-titulo">📁 Status dos Arquivos</div>', unsafe_allow_html=True)
            st.info("🌐 Salesforce e Estoque: Google Sheets (automático)")
            for nome, caminho in [("Base consolidada XLSX",ARQ_BASE),("Base consolidada Parquet",ARQ_PARQ),("Pedidos manuais",ARQ_MAN)]:
                if os.path.exists(caminho):
                    dt = datetime.datetime.fromtimestamp(os.path.getmtime(caminho)).strftime("%d/%m/%Y %H:%M")
                    st.success(f"✅ {nome} · {dt}")
                else:
                    st.warning(f"⚠️ {nome}: não encontrado")

    # ══════════════════════════════════════════════════════════════════════════
    # ABA CADASTRO MANUAL
    # ══════════════════════════════════════════════════════════════════════════
    if pode_editar:
        with tabs[3]:
            st.markdown('<div class="secao-titulo">➕ Cadastro Manual de Pedidos</div>', unsafe_allow_html=True)
            st.caption("Para pedidos que não constam na base principal.")

            df_sf2 = _ler_salesforce()
            LOCS   = ["LM FROTAS","RCI","TOOT","GM Fleet","Arval","Localiza","Outra"]
            SEGS   = ["Sign & Drive","S&D Empresas","Nissan Move","AssineCar GWM","GM Fleet","GAC Go and Drive","AssineCar Multbrand","Outro"]
            STS    = ["Em locação","Contrato assinado","Pedido concluído","Cancelado","Aguardando","Outro"]

            with st.form("form_manual"):
                st.markdown("**📋 Identificação**")
                m1,m2,m3 = st.columns(3)
                with m1: loc=st.selectbox("Locadora *",LOCS); seg=st.selectbox("Segmento *",SEGS)
                with m2: pedido=st.text_input("Nº Pedido *"); cliente=st.text_input("Cliente *")
                with m3: doc=st.text_input("CPF/CNPJ *"); status=st.selectbox("Status",STS)

                st.markdown("**🚗 Veículo**")
                v1,v2,v3 = st.columns(3)
                with v1: modelo=st.text_input("Modelo"); cor=st.text_input("Cor")
                with v2: chassi=st.text_input("Chassi"); placa=st.text_input("Placa")
                with v3: marca=st.text_input("Marca"); opcional=st.text_input("Opcional")

                st.markdown("**📅 Contrato**")
                c1,c2,c3,c4 = st.columns(4)
                with c1: data_ass=st.date_input("Data Assinatura",value=None,format="DD/MM/YYYY")
                with c2: plano=st.number_input("Plano (meses)",min_value=0,step=6,value=0)
                with c3: km=st.number_input("KM Mensal",min_value=0,step=500,value=0)
                with c4: mensalidade=st.number_input("Mensalidade (R$)",min_value=0.0,step=100.0,value=0.0)

                st.markdown("**📍 Local**")
                l1,l2,l3 = st.columns(3)
                with l1: lv=st.text_input("Local de Venda")
                with l2: uf=st.text_input("UF")
                with l3: city=st.text_input("Cidade")

                cons_prev = _lookup_sf(df_sf2, pedido) if pedido else "—"
                if pedido:
                    cor_c = "#22c55e" if cons_prev != "Não encontrado" else "#f59e0b"
                    st.markdown(f"<p style='font-size:13px;color:{cor_c}'>👤 Consultor: <b>{cons_prev}</b></p>", unsafe_allow_html=True)

                enviado = st.form_submit_button("💾 Cadastrar", use_container_width=True, type="primary")

            if enviado:
                if not pedido or not cliente or not doc:
                    st.error("Nº Pedido, Cliente e CPF/CNPJ são obrigatórios.")
                else:
                    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                    dados = {"Locadora":loc,"Segmento":seg,"Pedido":pedido,"Nome":cliente,
                             "Documento":doc,"Tipo":_tipo(doc),"Status":status,
                             "Modelo Oficial":modelo,"Cor":cor,"Chassi":chassi,"Placa":placa,
                             "Marca":marca,"Opcional":opcional,
                             "Data Assinatura":data_ass.strftime("%d/%m/%Y") if data_ass else "",
                             "Período":str(plano),"Km":str(km),"Mensalidade":str(mensalidade),
                             "Local de Venda":lv,"UF":uf,"City":city,
                             "Venda":cons_prev,"Data de Inclusão":agora,"Origem venda":"Manual"}
                    pg = st.progress(0,"Salvando..."); pg.progress(70,"Gravando...")
                    if _gravar_manual(dados):
                        pg.progress(100,"Concluído!")
                        _ler_manuais.clear(); st.cache_data.clear()
                        st.success(f"✅ Pedido **{pedido}** cadastrado!"); st.balloons()

            st.divider()
            df_man2 = _ler_manuais()
            if df_man2.empty: st.info("Nenhum pedido manual ainda.")
            else: st.dataframe(df_man2, use_container_width=True, height=300, hide_index=True)