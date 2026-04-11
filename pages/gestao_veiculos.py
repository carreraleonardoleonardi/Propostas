import streamlit as st
import pandas as pd
import requests
import json
import datetime


# ── Constantes ───────────────────────────────────────────────────────────────
GV_SHEET_URL = "https://docs.google.com/spreadsheets/d/1BpAtiXz4AEuQg4kVx8OFonohPlvbScdOgWPIZRxQnxo/export?format=csv&gid=461042346"
GV_WEBHOOK   = "https://script.google.com/macros/s/AKfycbzFP-ezBsVx7W7VhYATKgaqdAg485o0AQb8s9FdGTlvmdzK1YRj7dCUVfTrXNgJOToc/exec"
GV_SENHA     = "CarreraSignature#2026"
SENHA_FECHAMENTO = "#FECHAMENTO"

GV_STATUS_LIST = [
    "Trânsito Disponível", "Trânsito Vendido", "Disponível",
    "Aguardando Atribuição", "Aguardando Agendamento", "Agendado",
    "Entregue", "Reagendar", "Avariado", "Distrato",
    "Remoção", "Reserva Temporária", "Evento Signature"
]
GV_FABRICANTES  = ["VOLKSWAGEN","CHEVROLET","NISSAN","JEEP","GWM","RENAULT","HYUNDAI","TOYOTA","FIAT","FORD","OUTRO"]
GV_LOCADORAS    = ["LM FROTAS","MOVE","RCI","TOOT","OUTRO"]
GV_LOJAS        = ["LOJA ALPHAVILLE","LOJA VILLA LOBOS","LOJA OSASCO","LOJA BUTANTÃ","LOJA COTIA","OUTRO DN"]
GV_COMBUSTIVEIS = ["Flex","Gasolina","Elétrico","Híbrido","Diesel"]
GV_COLUNAS = [
    "id","fabricante","modelo","chassi","placa","cor",
    "ano_fabricacao","ano_modelo","combustivel","opcionais",
    "locadora","consultor","cliente","pedido","status",
    "local_atual","data_chegada","data_entrega","hora_entrega",
    "entregador","avaria","obs_avaria","loja_entrega",
    "valor_nf","margem","comissao",
    "criado_em","atualizado_em","atualizado_por"
]

STATUS_CORES = {
    "Disponível":             "#22c55e",
    "Trânsito Disponível":    "#3b82f6",
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

CSS = """
<style>
.gv-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 12px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    transition: box-shadow 0.2s;
}
.gv-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.10); }

.gv-kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 12px;
    margin-bottom: 20px;
}
.gv-kpi {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 18px 16px;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.gv-kpi-num  { font-size: 32px; font-weight: 800; color: #213144; line-height: 1; }
.gv-kpi-lbl  { font-size: 12px; color: #64748b; margin-top: 4px; font-weight: 500; text-transform: uppercase; letter-spacing: .5px; }

.gv-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    color: #fff;
}

.gv-veiculo-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #213144;
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 16px;
}
.gv-veiculo-title { font-size: 15px; font-weight: 700; color: #1e293b; }
.gv-veiculo-sub   { font-size: 12px; color: #64748b; margin-top: 2px; }

.gv-section-title {
    font-size: 18px;
    font-weight: 700;
    color: #213144;
    margin: 24px 0 12px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid #e2e8f0;
}
.gv-form-section {
    background: #f8fafc;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
    border: 1px solid #e2e8f0;
}
.gv-ag-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 16px 20px;
    margin-bottom: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.gv-ag-hora {
    font-size: 22px;
    font-weight: 800;
    color: #213144;
}
.gv-tag {
    display: inline-block;
    background: #f1f5f9;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 11px;
    color: #475569;
    margin-right: 4px;
}
</style>
"""


# ── Helpers de data ──────────────────────────────────────────────────────────
def parse_data(valor) -> datetime.date | None:
    if not valor or str(valor).strip() in ("","nan","None","NaT"):
        return None
    s = str(valor).strip()
    for fmt in ("%d/%m/%Y","%Y-%m-%d","%Y/%m/%d","%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def fmt_data(valor) -> str:
    d = parse_data(valor)
    return d.strftime("%d/%m/%Y") if d else ""

def calcular_idade(row) -> int | None:
    chegada = parse_data(str(row.get("data_chegada","")))
    if not chegada:
        return None
    if str(row.get("status","")).strip() == "Entregue":
        entrega = parse_data(str(row.get("data_entrega","")))
        ref = entrega if entrega else datetime.date.today()
    else:
        ref = datetime.date.today()
    return (ref - chegada).days

def farol_idade(dias) -> str:
    if dias is None: return "⚪"
    if dias <= 20:   return "🟢"
    if dias <= 30:   return "🟡"
    if dias <= 45:   return "🔴"
    return "⚫"

def badge_status(status: str) -> str:
    cor = STATUS_CORES.get(status, "#94a3b8")
    return f'<span class="gv-badge" style="background:{cor}">{status}</span>'

def farol_agendamento(row) -> str:
    status = str(row.get("status","")).strip()
    if status == "Entregue": return "🟢"
    data_ent = parse_data(str(row.get("data_entrega","")))
    if not data_ent: return "⚪"
    hora_str = str(row.get("hora_entrega","")).strip()
    agora    = datetime.datetime.now()
    try:
        h, m = map(int, hora_str.split(":"))
        dt_ag = datetime.datetime.combine(data_ent, datetime.time(h, m))
    except:
        dt_ag = datetime.datetime.combine(data_ent, datetime.time(23,59))
    return "🔴" if agora > dt_ag else "🟡"

# Rodízio SP
RODIZIO_SP = {"1":0,"2":0,"3":1,"4":1,"5":2,"6":2,"7":3,"8":3,"9":4,"0":4}
RODIZIO_BLOQUEIO = [(datetime.time(6,0), datetime.time(10,0)), (datetime.time(16,0), datetime.time(20,0))]

def verificar_rodizio(placa: str, data: datetime.date, hora: datetime.time) -> str | None:
    if not placa or len(placa) < 1: return None
    final = placa.strip()[-1].upper()
    if final not in RODIZIO_SP: return None
    if data.weekday() != RODIZIO_SP[final]: return None
    dias = ["segunda","terça","quarta","quinta","sexta"]
    for ini, fim in RODIZIO_BLOQUEIO:
        if ini <= hora < fim:
            return f"🚫 Rodízio: placa final **{final}** tem restrição na **{dias[RODIZIO_SP[final]]}** entre {ini.strftime('%H:%M')} e {fim.strftime('%H:%M')}."
    return None

def verificar_conflito_loja(df, data, hora, loja, excluir_idx=-1) -> str | None:
    data_str = data.strftime("%d/%m/%Y")
    hora_str = hora.strftime("%H:%M")
    mask = (
        (df["status"] == "Agendado") &
        (df["data_entrega"].astype(str) == data_str) &
        (df["hora_entrega"].astype(str) == hora_str) &
        (df["loja_entrega"].astype(str) == loja)
    )
    if excluir_idx >= 0:
        mask = mask & (df.index != excluir_idx)
    conf = df[mask]
    if not conf.empty:
        v = conf.iloc[0]
        return f"🚫 Conflito: já existe agendamento em **{loja}** às **{hora_str}** de {data_str} — {v.get('modelo','?')} | {v.get('cliente','?')}"
    return None


# ── Cache e envio ────────────────────────────────────────────────────────────
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

def gv_enviar(payload: dict) -> bool:
    try:
        requests.post(GV_WEBHOOK, data=json.dumps(payload),
            headers={"Content-Type":"text/plain"}, timeout=30)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

def gv_novo_id(_=None) -> str:
    return "VEI" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")

def gv_val_row(row, col, default="") -> str:
    v = row.get(col, default)
    return "" if pd.isna(v) else str(v)


# ════════════════════════════════════════════════════════════════════════════
# RENDER PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════
def render():
    st.markdown(CSS, unsafe_allow_html=True)

    # ── Session state ────────────────────────────────────────
    for key, val in [
        ("gv_autenticado",        False),
        ("ag_forcar",             False),
        ("gv_confirmar_delete",   False),
        ("email11_selecionados",  []),
    ]:
        if key not in st.session_state:
            st.session_state[key] = val

    # ── Header ───────────────────────────────────────────────
    h_col1, h_col2 = st.columns([7, 3])
    with h_col1:
        st.title("🚘 Gestão de Veículos")
    with h_col2:
        if not st.session_state["gv_autenticado"]:
            with st.expander("🔐 Acesso Editor"):
                pw = st.text_input("Senha", type="password", key="gv_pw")
                if st.button("Entrar", use_container_width=True, key="gv_login"):
                    if pw == GV_SENHA:
                        st.session_state["gv_autenticado"] = True
                        st.rerun()
                    else:
                        st.error("Senha incorreta.")
        else:
            st.success("✅ Modo Editor ativo")
            if st.button("Sair", use_container_width=True, key="gv_logout"):
                st.session_state["gv_autenticado"] = False
                st.rerun()

    autenticado = st.session_state["gv_autenticado"]
    df_gv = gv_carregar()

    # Calcula idade
    if not df_gv.empty:
        df_gv["_idade"] = df_gv.apply(calcular_idade, axis=1)

    # ── Sub-abas ─────────────────────────────────────────────
    abas = ["📋 Painel", "📅 Agendamentos", "📊 Relatórios"]
    if autenticado:
        abas = ["📋 Painel", "➕ Cadastrar", "✏️ Editar", "📅 Agendamentos", "📊 Relatórios"]

    tabs = st.tabs(abas)
    idx = {a: i for i, a in enumerate(abas)}

    # ════════════════════════════════════════════════════════
    # PAINEL
    # ════════════════════════════════════════════════════════
    with tabs[idx["📋 Painel"]]:
        col_ref, _ = st.columns([1, 8])
        with col_ref:
            if st.button("🔄 Atualizar", key="gv_refresh"):
                gv_carregar.clear(); st.rerun()

        if df_gv.empty:
            st.info("Nenhum veículo cadastrado ainda.")
        else:
            # KPIs visuais
            total       = len(df_gv)
            disp        = len(df_gv[df_gv["status"].str.contains("Disponível", na=False)]) if "status" in df_gv.columns else 0
            agend       = len(df_gv[df_gv["status"] == "Agendado"]) if "status" in df_gv.columns else 0
            entregues   = len(df_gv[df_gv["status"] == "Entregue"]) if "status" in df_gv.columns else 0
            avariados   = len(df_gv[df_gv["status"] == "Avariado"]) if "status" in df_gv.columns else 0
            atrasados   = 0
            hoje = datetime.date.today()
            if "status" in df_gv.columns:
                df_ag_check = df_gv[df_gv["status"] == "Agendado"].copy()
                df_ag_check["_farol"] = df_ag_check.apply(farol_agendamento, axis=1)
                atrasados = len(df_ag_check[df_ag_check["_farol"] == "🔴"])

            st.markdown(f"""
            <div class="gv-kpi-grid">
                <div class="gv-kpi"><div class="gv-kpi-num">{total}</div><div class="gv-kpi-lbl">Total</div></div>
                <div class="gv-kpi"><div class="gv-kpi-num" style="color:#22c55e">{disp}</div><div class="gv-kpi-lbl">Disponíveis</div></div>
                <div class="gv-kpi"><div class="gv-kpi-num" style="color:#06b6d4">{agend}</div><div class="gv-kpi-lbl">Agendados</div></div>
                <div class="gv-kpi"><div class="gv-kpi-num" style="color:#10b981">{entregues}</div><div class="gv-kpi-lbl">Entregues</div></div>
                <div class="gv-kpi"><div class="gv-kpi-num" style="color:#ef4444">{avariados}</div><div class="gv-kpi-lbl">Avariados</div></div>
                <div class="gv-kpi"><div class="gv-kpi-num" style="color:#dc2626">{atrasados}</div><div class="gv-kpi-lbl">Atrasados</div></div>
            </div>
            <p style="font-size:11px;color:#94a3b8;margin-bottom:16px;">
                Farol de idade: 🟢 ≤20 dias · 🟡 ≤30 dias · 🔴 ≤45 dias · ⚫ >45 dias
            </p>
            """, unsafe_allow_html=True)

            # Filtros compactos
            with st.expander("🔍 Filtros", expanded=False):
                f1, f2, f3, f4 = st.columns(4)
                with f1:
                    flt_sta = st.selectbox("Status",     ["Todos"] + GV_STATUS_LIST, key="p_sta")
                with f2:
                    flt_fab = st.selectbox("Fabricante", ["Todos"] + sorted(df_gv["fabricante"].dropna().unique().tolist()) if "fabricante" in df_gv.columns else ["Todos"], key="p_fab")
                with f3:
                    flt_loc = st.selectbox("Locadora",   ["Todos"] + sorted(df_gv["locadora"].dropna().unique().tolist()) if "locadora" in df_gv.columns else ["Todos"], key="p_loc")
                with f4:
                    flt_con = st.selectbox("Consultor",  ["Todos"] + sorted(df_gv["consultor"].dropna().unique().tolist()) if "consultor" in df_gv.columns else ["Todos"], key="p_con")

            df_view = df_gv.copy()
            if flt_sta != "Todos": df_view = df_view[df_view["status"]     == flt_sta]
            if flt_fab != "Todos": df_view = df_view[df_view["fabricante"] == flt_fab]
            if flt_loc != "Todos": df_view = df_view[df_view["locadora"]   == flt_loc]
            if flt_con != "Todos": df_view = df_view[df_view["consultor"]  == flt_con]

            st.markdown(f"**{len(df_view)} veículo(s)** &nbsp; <span style='font-size:12px;color:#94a3b8'>— clique em um card para ver todos os detalhes</span>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            # Gera todos os cards com expansão via JS puro
            cards_html = """
<style>
.vcard {
    background:#fff;
    border:1px solid #e2e8f0;
    border-radius:14px;
    margin-bottom:10px;
    overflow:hidden;
    box-shadow:0 1px 4px rgba(0,0,0,0.05);
    transition:box-shadow .2s, transform .15s;
    cursor:pointer;
}
.vcard:hover { box-shadow:0 4px 18px rgba(0,0,0,0.10); transform:translateY(-1px); }
.vcard-header {
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:14px 20px;
    gap:12px;
    flex-wrap:wrap;
}
.vcard-left { display:flex; align-items:center; gap:14px; flex:1; min-width:0; }
.vcard-borda { width:5px; min-height:48px; border-radius:4px; flex-shrink:0; }
.vcard-modelo { font-size:15px; font-weight:700; color:#1e293b; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.vcard-sub { font-size:12px; color:#64748b; margin-top:2px; display:flex; gap:6px; flex-wrap:wrap; }
.vtag { background:#f1f5f9; border-radius:5px; padding:2px 7px; font-size:11px; color:#475569; }
.vcard-right { display:flex; flex-direction:column; align-items:flex-end; gap:4px; flex-shrink:0; }
.vbadge { padding:3px 12px; border-radius:999px; font-size:11px; font-weight:700; color:#fff; white-space:nowrap; }
.vcard-idade { font-size:11px; color:#94a3b8; }
.vcard-chevron { font-size:14px; color:#94a3b8; margin-left:8px; transition:transform .25s; }
.vcard-detail {
    display:none;
    border-top:1px solid #f1f5f9;
    background:#fafbfc;
    padding:20px 24px;
    animation: fadeIn .2s ease;
}
@keyframes fadeIn { from{opacity:0;transform:translateY(-6px)} to{opacity:1;transform:translateY(0)} }
.vcard.open .vcard-detail { display:block; }
.vcard.open .vcard-chevron { transform:rotate(180deg); }
.vcard.open { box-shadow:0 6px 24px rgba(0,0,0,0.12); }
.vdetail-grid {
    display:grid;
    grid-template-columns:repeat(auto-fill, minmax(200px, 1fr));
    gap:16px 24px;
    margin-bottom:16px;
}
.vdetail-section { margin-bottom:16px; }
.vdetail-section-title { font-size:10px; font-weight:700; color:#94a3b8; text-transform:uppercase; letter-spacing:.8px; margin-bottom:10px; padding-bottom:4px; border-bottom:1px solid #e2e8f0; }
.vfield { display:flex; flex-direction:column; gap:2px; }
.vfield-lbl { font-size:10px; color:#94a3b8; font-weight:600; text-transform:uppercase; letter-spacing:.5px; }
.vfield-val { font-size:13px; color:#1e293b; font-weight:500; }
.vfield-val.empty { color:#cbd5e1; font-style:italic; }
.vclose-btn {
    display:inline-flex; align-items:center; gap:6px;
    background:#f1f5f9; border:none; border-radius:8px;
    padding:6px 14px; font-size:12px; color:#475569;
    cursor:pointer; font-weight:600; margin-top:4px;
    transition:background .15s;
}
.vclose-btn:hover { background:#e2e8f0; }
</style>
<script>
function toggleCard(id) {
    var card = document.getElementById(id);
    card.classList.toggle('open');
}
function closeCard(id, e) {
    e.stopPropagation();
    document.getElementById(id).classList.remove('open');
}
</script>
"""

            def safe(v):
                s = str(v).strip()
                return s if s and s not in ("nan","None","NaT","") else "—"

            def vfield(label, val):
                v = safe(val)
                cls = "empty" if v == "—" else ""
                return f'<div class="vfield"><div class="vfield-lbl">{label}</div><div class="vfield-val {cls}">{v}</div></div>'

            for i, (_, row) in enumerate(df_view.iterrows()):
                idade = row.get("_idade", None)
                fi    = farol_idade(idade)
                id_txt = f"{fi} {idade}d" if idade is not None else "⚪ —"
                status = str(row.get("status",""))
                cor    = STATUS_CORES.get(status, "#94a3b8")
                card_id = f"vcard_{i}"

                cards_html += f"""
<div class="vcard" id="{card_id}" onclick="toggleCard('{card_id}')">
  <div class="vcard-header">
    <div class="vcard-left">
      <div class="vcard-borda" style="background:{cor}"></div>
      <div>
        <div class="vcard-modelo">{safe(row.get('modelo'))} &nbsp;<span style="font-weight:400;color:#94a3b8;font-size:13px">{safe(row.get('fabricante'))}</span></div>
        <div class="vcard-sub">
          <span class="vtag">🔑 {safe(row.get('chassi'))}</span>
          <span class="vtag">🪪 {safe(row.get('placa'))}</span>
          <span class="vtag">🎨 {safe(row.get('cor'))}</span>
          <span class="vtag">🏢 {safe(row.get('locadora'))}</span>
        </div>
      </div>
    </div>
    <div class="vcard-right">
      <div style="display:flex;align-items:center;gap:6px">
        <span class="vbadge" style="background:{cor}">{status}</span>
        <span class="vcard-chevron">▼</span>
      </div>
      <div class="vcard-idade">{id_txt} · {safe(row.get('local_atual'))}</div>
      {'<div style="font-size:12px;color:#475569;margin-top:2px">👤 ' + safe(row.get('cliente')) + ' · ' + safe(row.get('consultor')) + '</div>' if safe(row.get('cliente')) != '—' else ''}
    </div>
  </div>

  <div class="vcard-detail">

    <div class="vdetail-section">
      <div class="vdetail-section-title">🔍 Identificação</div>
      <div class="vdetail-grid">
        {vfield('Fabricante', row.get('fabricante'))}
        {vfield('Modelo', row.get('modelo'))}
        {vfield('Chassi', row.get('chassi'))}
        {vfield('Placa', row.get('placa'))}
        {vfield('Cor', row.get('cor'))}
        {vfield('Combustível', row.get('combustivel'))}
        {vfield('Ano Fabricação', row.get('ano_fabricacao'))}
        {vfield('Ano Modelo', row.get('ano_modelo'))}
        {vfield('Opcionais', row.get('opcionais'))}
      </div>
    </div>

    <div class="vdetail-section">
      <div class="vdetail-section-title">🏢 Operacional</div>
      <div class="vdetail-grid">
        {vfield('Status', row.get('status'))}
        {vfield('Locadora', row.get('locadora'))}
        {vfield('Consultor', row.get('consultor'))}
        {vfield('Cliente', row.get('cliente'))}
        {vfield('Nº Pedido', row.get('pedido'))}
        {vfield('Local Atual', row.get('local_atual'))}
        {vfield('Com Avaria?', row.get('avaria'))}
        {vfield('Obs. Avaria', row.get('obs_avaria'))}
      </div>
    </div>

    <div class="vdetail-section">
      <div class="vdetail-section-title">📅 Datas e Entrega</div>
      <div class="vdetail-grid">
        {vfield('Data Chegada', row.get('data_chegada'))}
        {vfield('Data Entrega', row.get('data_entrega'))}
        {vfield('Hora Entrega', row.get('hora_entrega'))}
        {vfield('Loja de Entrega', row.get('loja_entrega'))}
        {vfield('Entregador', row.get('entregador'))}
        {vfield('Idade no Estoque', f"{idade} dias" if idade is not None else "—")}
      </div>
    </div>

    <div class="vdetail-section">
      <div class="vdetail-section-title">💰 Financeiro</div>
      <div class="vdetail-grid">
        {vfield('Valor NF', row.get('valor_nf'))}
        {vfield('Margem', row.get('margem'))}
        {vfield('Comissão', row.get('comissao'))}
      </div>
    </div>

    <div class="vdetail-section">
      <div class="vdetail-section-title">🕐 Auditoria</div>
      <div class="vdetail-grid">
        {vfield('ID', row.get('id'))}
        {vfield('Criado em', row.get('criado_em'))}
        {vfield('Atualizado em', row.get('atualizado_em'))}
        {vfield('Atualizado por', row.get('atualizado_por'))}
      </div>
    </div>

    <button class="vclose-btn" onclick="closeCard('{card_id}', event)">▲ Fechar</button>
  </div>
</div>"""

            st.markdown(cards_html, unsafe_allow_html=True)

            if autenticado:
                st.markdown("<br>", unsafe_allow_html=True)
                csv_exp = df_view.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Exportar CSV", data=csv_exp, file_name="veiculos.csv", mime="text/csv")

    # ════════════════════════════════════════════════════════
    # CADASTRAR
    # ════════════════════════════════════════════════════════
    if autenticado:
        with tabs[idx["➕ Cadastrar"]]:
            st.markdown('<div class="gv-section-title">➕ Cadastrar Veículo</div>', unsafe_allow_html=True)
            modo_cad = st.radio("Modo", ["Manual", "Importar Excel"], horizontal=True, key="gv_modo_cad")

            if modo_cad == "Manual":
                with st.form("gv_form_cad"):
                    st.markdown('<div class="gv-form-section">', unsafe_allow_html=True)
                    st.markdown("**🔍 Identificação**")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        fab    = st.selectbox("Fabricante *", GV_FABRICANTES)
                        mod    = st.text_input("Modelo *")
                        cor    = st.text_input("Cor *")
                    with c2:
                        chassi = st.text_input("Chassi *")
                        placa  = st.text_input("Placa")
                        comb   = st.selectbox("Combustível", GV_COMBUSTIVEIS)
                    with c3:
                        ano_fab = st.text_input("Ano Fabricação")
                        ano_mod = st.text_input("Ano Modelo")
                        opc     = st.text_area("Opcionais", height=68)
                    st.markdown('</div>', unsafe_allow_html=True)

                    st.markdown('<div class="gv-form-section">', unsafe_allow_html=True)
                    st.markdown("**🏢 Operacional**")
                    o1, o2, o3 = st.columns(3)
                    with o1:
                        loc           = st.selectbox("Locadora", GV_LOCADORAS)
                        consultor_cad = st.text_input("Consultor")
                        pedido        = st.text_input("Nº Pedido")
                    with o2:
                        cliente_cad = st.text_input("Cliente")
                        local_at    = st.text_input("Local Atual")
                        status_cad  = st.selectbox("Status Inicial", GV_STATUS_LIST)
                    with o3:
                        data_ch = st.date_input("Data Chegada", value=None)
                        avaria  = st.selectbox("Com Avaria?", ["Não","Sim"])
                        obs_av  = st.text_area("Obs. Avaria", height=68)
                    st.markdown('</div>', unsafe_allow_html=True)

                    st.markdown('<div class="gv-form-section">', unsafe_allow_html=True)
                    st.markdown("**💰 Financeiro**")
                    f1, f2, f3 = st.columns(3)
                    with f1: valor_nf = st.number_input("Valor NF (R$)", min_value=0.0, step=100.0)
                    with f2: margem   = st.number_input("Margem (%)",    min_value=0.0, step=0.1)
                    with f3: comissao = st.number_input("Comissão (%)",  min_value=0.0, step=0.1)
                    st.markdown('</div>', unsafe_allow_html=True)

                    submitted = st.form_submit_button("💾 Cadastrar Veículo", use_container_width=True, type="primary")
                    if submitted:
                        if not fab or not mod or not chassi:
                            st.error("Fabricante, Modelo e Chassi são obrigatórios.")
                        elif "chassi" in df_gv.columns and chassi.upper() in df_gv["chassi"].astype(str).str.upper().values:
                            st.error(f"⛔ Chassi `{chassi}` já existe! Chassi deve ser único.")
                        else:
                            agora_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                            nova_linha = [
                                gv_novo_id(), fab, mod, chassi, placa, cor,
                                ano_fab, ano_mod, comb, opc,
                                loc, consultor_cad, cliente_cad, pedido, status_cad,
                                local_at, data_ch.strftime("%d/%m/%Y") if data_ch else "",
                                "","","", avaria, obs_av if avaria=="Sim" else "",
                                "", valor_nf, margem, comissao,
                                agora_str, agora_str, "Sistema"
                            ]
                            if gv_enviar({"aba":"veiculos","acao":"inserir","linha":nova_linha}):
                                gv_carregar.clear()
                                st.success("✅ Veículo cadastrado com sucesso!")
                                st.rerun()

            else:
                st.info("📎 Colunas reconhecidas (todas opcionais): **FABRICANTE · MODELO · CHASSI · PLACA · COR · LOCADORA · STATUS · DATA CHEGADA · COM AVARIA? · LOCAL ATUAL**")
                arquivo = st.file_uploader("Selecione o arquivo .xlsx", type=["xlsx"])
                if arquivo:
                    try:
                        df_imp = pd.read_excel(arquivo)
                        st.markdown(f"**{len(df_imp)} linhas encontradas — prévia:**")
                        st.dataframe(df_imp.head(5), use_container_width=True)

                        if st.button("📤 Importar todos", use_container_width=True, key="gv_btn_importar", type="primary"):
                            agora_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                            chassis_existentes = set(df_gv["chassi"].astype(str).str.upper().tolist()) if "chassi" in df_gv.columns else set()
                            erros = 0; duplicados = []

                            for _, row in df_imp.iterrows():
                                def g(col):
                                    for t in [col, col.upper(), col.lower(), col.title()]:
                                        v = row.get(t, None)
                                        if v is not None and not (isinstance(v, float) and pd.isna(v)):
                                            return str(v).strip()
                                    return ""
                                dc = fmt_data(g("DATA CHEGADA")) or g("DATA CHEGADA")
                                chassi_imp = g("CHASSI").upper()
                                if chassi_imp and chassi_imp in chassis_existentes:
                                    duplicados.append(chassi_imp); continue
                                if chassi_imp:
                                    chassis_existentes.add(chassi_imp)
                                nova_linha = [
                                    gv_novo_id(), g("FABRICANTE"), g("MODELO"),
                                    chassi_imp, g("PLACA"), g("COR"),
                                    "","","","", g("LOCADORA"),"","","",
                                    g("STATUS") or "Trânsito Disponível",
                                    g("LOCAL ATUAL"), dc,"","","",
                                    g("COM AVARIA?") or "Não","","","","","",
                                    agora_str, agora_str, "Importação"
                                ]
                                if not gv_enviar({"aba":"veiculos","acao":"inserir","linha":nova_linha}):
                                    erros += 1
                            gv_carregar.clear()
                            importados = len(df_imp) - erros - len(duplicados)
                            st.success(f"✅ {importados} veículo(s) importado(s)!")
                            if duplicados:
                                st.warning(f"⛔ {len(duplicados)} chassi(s) ignorado(s) por duplicidade: {', '.join(duplicados)}")
                            if erros:
                                st.error(f"{erros} erro(s) de envio.")
                    except Exception as e:
                        st.error(f"Erro ao ler arquivo: {e}")

    # ════════════════════════════════════════════════════════
    # EDITAR
    # ════════════════════════════════════════════════════════
    if autenticado:
        with tabs[idx["✏️ Editar"]]:
            st.markdown('<div class="gv-section-title">✏️ Editar Veículo</div>', unsafe_allow_html=True)

            if df_gv.empty:
                st.info("Nenhum veículo cadastrado.")
            else:
                modo_ed = st.radio("Modo", ["🔎 Individual", "📦 Em Lote", "🗑️ Deletar"],
                    horizontal=True, key="gv_modo_ed")

                # ── INDIVIDUAL ───────────────────────────────
                if modo_ed == "🔎 Individual":
                    busca = st.text_input("🔍 Buscar chassi, placa, cliente ou modelo", placeholder="Digite para filtrar...", key="gv_busca_edit")
                    df_busca = df_gv.copy()
                    if busca:
                        mask = pd.Series(False, index=df_busca.index)
                        for col in ["chassi","placa","cliente","modelo","fabricante","consultor"]:
                            if col in df_busca.columns:
                                mask |= df_busca[col].astype(str).str.contains(busca, case=False, na=False)
                        df_busca = df_busca[mask]

                    if df_busca.empty:
                        st.warning("Nenhum resultado.")
                    else:
                        opcoes = df_busca.apply(
                            lambda r: f"{r.get('chassi','?')} · {r.get('modelo','?')} · {r.get('status','?')}",
                            axis=1).tolist()
                        sel = st.selectbox("Selecione o veículo", range(len(opcoes)),
                            format_func=lambda i: opcoes[i], key="gv_sel_edit")

                        vei = df_busca.iloc[sel]
                        def gv_val(col, d=""):
                            v = vei.get(col, d)
                            return "" if pd.isna(v) else str(v)

                        # Card de contexto
                        idade_atual = calcular_idade(vei)
                        fi = farol_idade(idade_atual)
                        st.markdown(f"""
                        <div class="gv-card" style="border-left:4px solid {STATUS_CORES.get(gv_val('status'),'#e2e8f0')}">
                            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
                                <div>
                                    <div class="gv-veiculo-title">{gv_val('modelo')} &nbsp;<span style="font-weight:400;color:#64748b">{gv_val('fabricante')}</span></div>
                                    <div style="font-size:12px;color:#64748b;margin-top:4px">
                                        <span class="gv-tag">🔑 {gv_val('chassi')}</span>
                                        <span class="gv-tag">🪪 {gv_val('placa')}</span>
                                        <span class="gv-tag">👤 {gv_val('cliente') or '—'}</span>
                                    </div>
                                </div>
                                <div style="text-align:right">
                                    {badge_status(gv_val('status'))}
                                    <div style="font-size:12px;color:#94a3b8;margin-top:4px">{fi} {idade_atual}d no estoque</div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        with st.form("gv_form_ed"):
                            with st.expander("🔍 Identificação", expanded=False):
                                i1, i2, i3, i4 = st.columns(4)
                                with i1:
                                    e_fab   = st.selectbox("Fabricante", GV_FABRICANTES, index=GV_FABRICANTES.index(gv_val("fabricante")) if gv_val("fabricante") in GV_FABRICANTES else 0)
                                    e_modelo= st.text_input("Modelo", value=gv_val("modelo"))
                                with i2:
                                    e_cor   = st.text_input("Cor",   value=gv_val("cor"))
                                    e_placa = st.text_input("Placa", value=gv_val("placa"))
                                with i3:
                                    e_ano_fab = st.text_input("Ano Fabricação", value=gv_val("ano_fabricacao"))
                                    e_ano_mod = st.text_input("Ano Modelo",     value=gv_val("ano_modelo"))
                                with i4:
                                    e_comb = st.selectbox("Combustível", GV_COMBUSTIVEIS, index=GV_COMBUSTIVEIS.index(gv_val("combustivel")) if gv_val("combustivel") in GV_COMBUSTIVEIS else 0)
                                    e_opc  = st.text_area("Opcionais", value=gv_val("opcionais"), height=68)

                            with st.expander("🏢 Operacional", expanded=True):
                                o1, o2, o3 = st.columns(3)
                                with o1:
                                    e_status = st.selectbox("Status", GV_STATUS_LIST, index=GV_STATUS_LIST.index(gv_val("status")) if gv_val("status") in GV_STATUS_LIST else 0)
                                    e_loc    = st.selectbox("Locadora", GV_LOCADORAS, index=GV_LOCADORAS.index(gv_val("locadora")) if gv_val("locadora") in GV_LOCADORAS else 0)
                                    e_consultor = st.text_input("Consultor", value=gv_val("consultor"))
                                with o2:
                                    e_cliente    = st.text_input("Cliente",     value=gv_val("cliente"))
                                    e_pedido     = st.text_input("Nº Pedido",   value=gv_val("pedido"))
                                    e_local      = st.text_input("Local Atual", value=gv_val("local_atual"))
                                with o3:
                                    e_loja = st.selectbox("Loja de Entrega", [""]+GV_LOJAS, index=([""]+GV_LOJAS).index(gv_val("loja_entrega")) if gv_val("loja_entrega") in GV_LOJAS else 0)
                                    e_entregador = st.text_input("Entregador", value=gv_val("entregador"))
                                    e_avaria     = st.selectbox("Com Avaria?", ["Não","Sim"], index=1 if gv_val("avaria")=="Sim" else 0)
                                e_obs_av = st.text_area("Obs. Avaria", value=gv_val("obs_avaria"), height=60)

                            with st.expander("📅 Datas e Agendamento", expanded=True):
                                d1, d2, d3 = st.columns(3)
                                with d1: e_data_ch  = st.date_input("Data Chegada", value=parse_data(gv_val("data_chegada")))
                                with d2: e_data_ent = st.date_input("Data Entrega", value=parse_data(gv_val("data_entrega")))
                                with d3:
                                    hora_str = gv_val("hora_entrega")
                                    try: h,m = map(int,hora_str.split(":")); hv = datetime.time(h,m)
                                    except: hv = datetime.time(10,0)
                                    e_hora_ent = st.time_input("Hora Entrega", value=hv)

                            with st.expander("💰 Financeiro", expanded=False):
                                fi1, fi2, fi3 = st.columns(3)
                                with fi1: e_nf = st.number_input("Valor NF (R$)", value=float(gv_val("valor_nf") or 0), step=100.0)
                                with fi2: e_mg = st.number_input("Margem (%)",    value=float(gv_val("margem") or 0), step=0.1)
                                with fi3: e_cm = st.number_input("Comissão (%)",  value=float(gv_val("comissao") or 0), step=0.1)

                            if st.form_submit_button("💾 Salvar Alterações", use_container_width=True, type="primary"):
                                agora_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                                linha = [
                                    gv_val("id"), e_fab, e_modelo,
                                    gv_val("chassi"), e_placa, e_cor,
                                    e_ano_fab, e_ano_mod, e_comb, e_opc,
                                    e_loc, e_consultor, e_cliente, e_pedido,
                                    e_status, e_local,
                                    e_data_ch.strftime("%d/%m/%Y")  if e_data_ch  else gv_val("data_chegada"),
                                    e_data_ent.strftime("%d/%m/%Y") if e_data_ent else gv_val("data_entrega"),
                                    e_hora_ent.strftime("%H:%M"),
                                    e_entregador,
                                    e_avaria, e_obs_av if e_avaria=="Sim" else "",
                                    e_loja, e_nf, e_mg, e_cm,
                                    gv_val("criado_em"), agora_str, "Editor"
                                ]
                                linha_num = int(df_busca.index[sel]) + 2
                                ok = gv_enviar({"aba":"veiculos","acao":"atualizar_linha","linha_num":linha_num,
                                    "valores":[{"col":i+1,"valor":v} for i,v in enumerate(linha)]})
                                gv_enviar({"aba":"historico","acao":"inserir","linha":[
                                    gv_val("id"),gv_val("chassi"),gv_val("modelo"),
                                    gv_val("status"),e_status,agora_str,"Editor"]})
                                if ok:
                                    gv_carregar.clear()
                                    if e_status in ["Agendado","Entregue"] and e_data_ent:
                                        assunto = f"[Carrera Signature] {e_status} — {e_modelo}"
                                        corpo   = f"Veículo: {e_modelo}%0AChassi: {gv_val('chassi')}%0ACliente: {e_cliente}%0AStatus: {e_status}%0AData: {e_data_ent.strftime('%d/%m/%Y')} às {e_hora_ent.strftime('%H:%M')}%0ALocal: {e_loja}"
                                        st.markdown(f"📧 [Enviar notificação](mailto:?subject={assunto}&body={corpo})")
                                    st.success("✅ Salvo!")
                                    st.rerun()

                # ── EM LOTE ──────────────────────────────────
                elif modo_ed == "📦 Em Lote":
                    st.markdown("Filtre os veículos e aplique uma alteração de campo para todos de uma vez.")

                    with st.expander("🔍 Filtros", expanded=True):
                        lf1, lf2, lf3, lf4 = st.columns(4)
                        with lf1: lote_sta   = st.selectbox("Status",      ["Todos"]+GV_STATUS_LIST, key="lt_sta")
                        with lf2: lote_fab   = st.selectbox("Fabricante",  ["Todos"]+sorted(df_gv["fabricante"].dropna().unique().tolist()) if "fabricante" in df_gv.columns else ["Todos"], key="lt_fab")
                        with lf3: lote_loc   = st.selectbox("Locadora",    ["Todos"]+sorted(df_gv["locadora"].dropna().unique().tolist()) if "locadora" in df_gv.columns else ["Todos"], key="lt_loc")
                        with lf4: lote_con   = st.selectbox("Consultor",   ["Todos"]+sorted(df_gv["consultor"].dropna().unique().tolist()) if "consultor" in df_gv.columns else ["Todos"], key="lt_con")
                        lf5, lf6 = st.columns(2)
                        with lf5: lote_local = st.selectbox("Local Atual", ["Todos"]+sorted(df_gv["local_atual"].dropna().unique().tolist()) if "local_atual" in df_gv.columns else ["Todos"], key="lt_local")
                        with lf6: lote_loja  = st.selectbox("Loja Entrega",["Todos"]+GV_LOJAS, key="lt_loja")

                    df_lote = df_gv.copy()
                    if lote_sta   != "Todos": df_lote = df_lote[df_lote["status"]       == lote_sta]
                    if lote_fab   != "Todos": df_lote = df_lote[df_lote["fabricante"]   == lote_fab]
                    if lote_loc   != "Todos": df_lote = df_lote[df_lote["locadora"]     == lote_loc]
                    if lote_con   != "Todos": df_lote = df_lote[df_lote["consultor"]    == lote_con]
                    if lote_local != "Todos": df_lote = df_lote[df_lote["local_atual"]  == lote_local]
                    if lote_loja  != "Todos": df_lote = df_lote[df_lote["loja_entrega"] == lote_loja]

                    if df_lote.empty:
                        st.warning("Nenhum veículo com esses filtros.")
                    else:
                        st.markdown(f"**{len(df_lote)} veículo(s) selecionado(s)**")
                        cols_lt = [c for c in ["chassi","modelo","fabricante","status","consultor","locadora"] if c in df_lote.columns]
                        st.dataframe(df_lote[cols_lt], use_container_width=True, hide_index=True)

                        st.divider()
                        CAMPOS_LOTE = {
                            "status":("selectbox",GV_STATUS_LIST), "fabricante":("selectbox",GV_FABRICANTES),
                            "locadora":("selectbox",GV_LOCADORAS), "loja_entrega":("selectbox",GV_LOJAS),
                            "combustivel":("selectbox",GV_COMBUSTIVEIS), "avaria":("selectbox",["Não","Sim"]),
                            "consultor":("text",None), "cliente":("text",None), "local_atual":("text",None),
                            "entregador":("text",None), "modelo":("text",None), "cor":("text",None),
                            "ano_fabricacao":("text",None), "ano_modelo":("text",None),
                            "data_chegada":("date",None), "data_entrega":("date",None),
                            "hora_entrega":("time",None), "valor_nf":("number",None),
                            "margem":("number",None), "comissao":("number",None),
                            "obs_avaria":("text",None), "pedido":("text",None),
                        }
                        lt1, lt2 = st.columns(2)
                        with lt1: campo_lote = st.selectbox("Campo a alterar", list(CAMPOS_LOTE.keys()), key="lt_campo")
                        tipo, opts = CAMPOS_LOTE[campo_lote]
                        with lt2:
                            if tipo == "selectbox":      valor_lote = st.selectbox("Novo valor", opts, key="lt_val")
                            elif tipo == "date":
                                vr = st.date_input("Novo valor", value=None, key="lt_val_d")
                                valor_lote = vr.strftime("%d/%m/%Y") if vr else ""
                            elif tipo == "time":
                                vr = st.time_input("Novo valor", value=datetime.time(10,0), key="lt_val_t")
                                valor_lote = vr.strftime("%H:%M")
                            elif tipo == "number":       valor_lote = st.number_input("Novo valor", min_value=0.0, step=0.1, key="lt_val_n")
                            else:                        valor_lote = st.text_input("Novo valor", key="lt_val_tx")

                        col_idx = GV_COLUNAS.index(campo_lote)+1 if campo_lote in GV_COLUNAS else None
                        if col_idx and st.button(f"✅ Aplicar em {len(df_lote)} veículo(s)", use_container_width=True, key="lt_aplicar", type="primary"):
                            agora_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                            erros = 0
                            for idx2 in df_lote.index:
                                ok = gv_enviar({"aba":"veiculos","acao":"atualizar_linha","linha_num":int(idx2)+2,
                                    "valores":[{"col":col_idx,"valor":valor_lote},
                                               {"col":GV_COLUNAS.index("atualizado_em")+1,"valor":agora_str},
                                               {"col":GV_COLUNAS.index("atualizado_por")+1,"valor":"Lote"}]})
                                if not ok: erros += 1
                            gv_carregar.clear()
                            st.success(f"✅ {len(df_lote)-erros} veículo(s) atualizado(s)!")
                            if erros: st.warning(f"{erros} erro(s).")
                            st.rerun()

                # ── DELETAR ──────────────────────────────────
                elif modo_ed == "🗑️ Deletar":
                    st.warning("⚠️ Esta ação remove permanentemente o veículo da planilha.")
                    chassi_del = st.text_input("Digite o Chassi exato", placeholder="Ex: 9BWBG6DF5TT406077", key="gv_chassi_del").strip().upper()

                    if chassi_del:
                        match = df_gv[df_gv["chassi"].astype(str).str.upper() == chassi_del]
                        if match.empty:
                            st.error(f"Chassi `{chassi_del}` não encontrado.")
                        else:
                            v = match.iloc[0]
                            st.markdown(f"""
                            <div class="gv-card" style="border-left:4px solid #ef4444">
                                <div class="gv-veiculo-title">{v.get('modelo','?')}</div>
                                <div style="font-size:13px;color:#64748b;margin-top:6px">
                                    {v.get('fabricante','?')} · Status: <b>{v.get('status','?')}</b> · Chegada: {v.get('data_chegada','?')}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            if not st.session_state["gv_confirmar_delete"]:
                                if st.button("🗑️ Deletar este veículo", use_container_width=True, key="btn_del", type="primary"):
                                    st.session_state["gv_confirmar_delete"] = True
                                    st.rerun()
                            else:
                                st.error("Tem certeza? Esta ação não pode ser desfeita.")
                                cd1, cd2 = st.columns(2)
                                with cd1:
                                    if st.button("✅ Sim, deletar", use_container_width=True, key="btn_del_sim"):
                                        linha_num = int(match.index[0]) + 2
                                        gv_enviar({"aba":"veiculos","acao":"deletar_linha","linha_num":linha_num})
                                        gv_enviar({"aba":"historico","acao":"inserir","linha":[
                                            str(v.get("id","")), chassi_del, str(v.get("modelo","")),
                                            str(v.get("status","")),"DELETADO",
                                            datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),"Editor"]})
                                        st.session_state["gv_confirmar_delete"] = False
                                        gv_carregar.clear()
                                        st.success(f"Chassi `{chassi_del}` removido.")
                                        st.rerun()
                                with cd2:
                                    if st.button("❌ Cancelar", use_container_width=True, key="btn_del_nao"):
                                        st.session_state["gv_confirmar_delete"] = False
                                        st.rerun()

    # ════════════════════════════════════════════════════════
    # AGENDAMENTOS
    # ════════════════════════════════════════════════════════
    idx_ag = idx.get("📅 Agendamentos")
    with tabs[idx_ag]:
        st.markdown('<div class="gv-section-title">📅 Agendamentos</div>', unsafe_allow_html=True)
        st.caption("🟡 Agendado · 🔴 Atrasado · 🟢 Entregue")

        if df_gv.empty or "status" not in df_gv.columns:
            st.info("Nenhum dado disponível.")
        else:
            ag_modo = st.radio("", ["📆 Por Dia", "📋 Todos", "➕ Novo Agendamento", "📧 E-mail das 11"],
                horizontal=True, key="ag_modo")
            st.divider()
            hoje = datetime.date.today()

            # ── POR DIA ─────────────────────────────────────
            if ag_modo == "📆 Por Dia":
                f1, f2, f3, f4 = st.columns(4)
                with f1: data_f    = st.date_input("Data", value=hoje, key="ag_data")
                with f2: loja_f    = st.selectbox("Loja", ["Todas"]+GV_LOJAS, key="ag_loja_d")
                with f3: ent_f     = st.selectbox("Entregador", ["Todos"]+sorted(df_gv["entregador"].dropna().unique().tolist()) if "entregador" in df_gv.columns else ["Todos"], key="ag_ent_d")
                with f4: con_f     = st.selectbox("Consultor",  ["Todos"]+sorted(df_gv["consultor"].dropna().unique().tolist()) if "consultor" in df_gv.columns else ["Todos"], key="ag_con_d")

                data_str = data_f.strftime("%d/%m/%Y")
                df_dia = df_gv[(df_gv["status"].isin(["Agendado","Entregue","Reagendar"])) & (df_gv["data_entrega"].astype(str)==data_str)].copy()
                if loja_f != "Todas": df_dia = df_dia[df_dia["loja_entrega"]==loja_f]
                if ent_f  != "Todos": df_dia = df_dia[df_dia["entregador"]==ent_f]
                if con_f  != "Todos": df_dia = df_dia[df_dia["consultor"]==con_f]

                if df_dia.empty:
                    st.info(f"Nenhum agendamento para {data_str}.")
                else:
                    df_dia["_farol"] = df_dia.apply(farol_agendamento, axis=1)
                    kd1,kd2,kd3,kd4 = st.columns(4)
                    kd1.metric("Total", len(df_dia))
                    kd2.metric("🟡 Agendados", len(df_dia[df_dia["_farol"]=="🟡"]))
                    kd3.metric("🔴 Atrasados", len(df_dia[df_dia["_farol"]=="🔴"]))
                    kd4.metric("🟢 Entregues", len(df_dia[df_dia["_farol"]=="🟢"]))
                    st.divider()
                    df_dia = df_dia.sort_values("hora_entrega", na_position="last")
                    for _, row in df_dia.iterrows():
                        farol = row.get("_farol","⚪")
                        st.markdown(f"""
                        <div class="gv-ag-card">
                            <div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap">
                                <div style="min-width:60px;text-align:center">
                                    <div style="font-size:22px">{farol}</div>
                                    <div class="gv-ag-hora">{str(row.get('hora_entrega','—'))}</div>
                                </div>
                                <div style="flex:1">
                                    <div class="gv-veiculo-title">{row.get('modelo','—')} <span style="font-weight:400;font-size:13px;color:#64748b">· {row.get('fabricante','')}</span></div>
                                    <div style="font-size:12px;color:#64748b;margin-top:3px">
                                        <span class="gv-tag">👤 {row.get('cliente','—')}</span>
                                        <span class="gv-tag">🪪 {row.get('placa','—')}</span>
                                        <span class="gv-tag">🎨 {row.get('cor','—')}</span>
                                    </div>
                                </div>
                                <div style="text-align:right">
                                    <div style="font-size:12px;color:#475569;font-weight:600">{row.get('loja_entrega','—')}</div>
                                    <div style="font-size:11px;color:#94a3b8">Entregador: {row.get('entregador','—')}</div>
                                    <div style="font-size:11px;color:#94a3b8">Consultor: {row.get('consultor','—')}</div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

            # ── TODOS ────────────────────────────────────────
            elif ag_modo == "📋 Todos":
                ta1, ta2, ta3 = st.columns(3)
                with ta1: loja_f2 = st.selectbox("Loja", ["Todas"]+GV_LOJAS, key="ag_loja_t")
                with ta2: ent_f2  = st.selectbox("Entregador", ["Todos"]+sorted(df_gv["entregador"].dropna().unique().tolist()) if "entregador" in df_gv.columns else ["Todos"], key="ag_ent_t")
                with ta3: farol_f2= st.selectbox("Farol", ["Todos","🟡 Agendado","🔴 Atrasado","🟢 Entregue"], key="ag_farol_t")

                df_todos = df_gv[df_gv["status"].isin(["Agendado","Reagendar","Entregue"])].copy()
                df_todos["_farol"] = df_todos.apply(farol_agendamento, axis=1)
                if loja_f2 != "Todas": df_todos = df_todos[df_todos["loja_entrega"]==loja_f2]
                if ent_f2  != "Todos": df_todos = df_todos[df_todos["entregador"]==ent_f2]
                if farol_f2!= "Todos": df_todos = df_todos[df_todos["_farol"]==farol_f2[:2]]

                if df_todos.empty:
                    st.info("Nenhum agendamento encontrado.")
                else:
                    kt1,kt2,kt3 = st.columns(3)
                    kt1.metric("🟡 Agendados", len(df_todos[df_todos["_farol"]=="🟡"]))
                    kt2.metric("🔴 Atrasados", len(df_todos[df_todos["_farol"]=="🔴"]))
                    kt3.metric("🟢 Entregues", len(df_todos[df_todos["_farol"]=="🟢"]))
                    st.divider()
                    df_todos = df_todos.sort_values(["data_entrega","hora_entrega"], na_position="last")
                    for _, row in df_todos.iterrows():
                        farol = row.get("_farol","⚪")
                        st.markdown(f"""
                        <div class="gv-ag-card">
                            <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
                                <div style="font-size:20px">{farol}</div>
                                <div style="min-width:80px;font-size:12px;color:#475569;font-weight:600">{row.get('data_entrega','—')}<br>{row.get('hora_entrega','—')}</div>
                                <div style="flex:1">
                                    <div class="gv-veiculo-title">{row.get('modelo','—')}</div>
                                    <div style="font-size:12px;color:#64748b">
                                        <span class="gv-tag">👤 {row.get('cliente','—')}</span>
                                        <span class="gv-tag">🪪 {row.get('placa','—')}</span>
                                    </div>
                                </div>
                                <div style="text-align:right;font-size:12px;color:#475569">
                                    <b>{row.get('loja_entrega','—')}</b><br>
                                    {row.get('entregador','—')}
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

            # ── NOVO AGENDAMENTO ─────────────────────────────
            elif ag_modo == "➕ Novo Agendamento":
                df_aw = df_gv[df_gv["status"].isin([
                    "Aguardando Agendamento","Aguardando Atribuição","Reagendar","Disponível"])].copy()

                if df_aw.empty:
                    st.info("Nenhum veículo aguardando agendamento.")
                else:
                    sa1,sa2,sa3,sa4 = st.columns(4)
                    sa1.metric("Total",             len(df_aw))
                    sa2.metric("Ag. Agendamento",   len(df_aw[df_aw["status"]=="Aguardando Agendamento"]))
                    sa3.metric("Reagendar",          len(df_aw[df_aw["status"]=="Reagendar"]))
                    sa4.metric("Disponível",         len(df_aw[df_aw["status"]=="Disponível"]))
                    st.divider()

                    for _, row in df_aw.iterrows():
                        idade = row.get("_idade",None)
                        fi    = farol_idade(idade)
                        st.markdown(f"""
                        <div class="gv-card" style="border-left:4px solid {STATUS_CORES.get(str(row.get('status','')),'#e2e8f0')}">
                            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
                                <div>
                                    <div class="gv-veiculo-title">{row.get('modelo','—')} <span style="font-weight:400;color:#64748b;font-size:13px">· {row.get('fabricante','')}</span></div>
                                    <div style="font-size:12px;color:#64748b;margin-top:3px">
                                        <span class="gv-tag">👤 {row.get('cliente','—')}</span>
                                        <span class="gv-tag">🪪 {row.get('placa','—')}</span>
                                        <span class="gv-tag">🎨 {row.get('cor','—')}</span>
                                    </div>
                                </div>
                                <div style="text-align:right">
                                    {badge_status(str(row.get('status','')))}
                                    <div style="font-size:11px;color:#94a3b8;margin-top:4px">{fi} {f'{idade}d' if idade is not None else '—'}</div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    st.markdown("### Agendar")
                    opcoes_aw = df_aw.apply(
                        lambda r: f"{r.get('chassi','?')} · {r.get('modelo','?')} · {r.get('cliente','—')}",
                        axis=1).tolist()
                    sel_aw = st.selectbox("Selecione o veículo", range(len(opcoes_aw)),
                        format_func=lambda i: opcoes_aw[i], key="ag_sel")

                    vei_aw   = df_aw.iloc[sel_aw]
                    idx_real = df_aw.index[sel_aw]
                    placa_vei= gv_val_row(vei_aw, "placa")

                    with st.form("form_ag"):
                        ag1,ag2,ag3 = st.columns(3)
                        with ag1: nova_data = st.date_input("📅 Data *", value=hoje)
                        with ag2: nova_hora = st.time_input("🕐 Hora *", value=datetime.time(10,0))
                        with ag3: nova_loja = st.selectbox("🏢 Loja *", GV_LOJAS)
                        ag4,ag5 = st.columns(2)
                        with ag4: novo_ent = st.text_input("Entregador", value=gv_val_row(vei_aw,"entregador"))
                        with ag5: novo_con = st.text_input("Consultor",  value=gv_val_row(vei_aw,"consultor"))
                        confirmar = st.form_submit_button("📅 Confirmar Agendamento", use_container_width=True, type="primary")

                    if confirmar:
                        erros_ag = []
                        err_rod  = verificar_rodizio(placa_vei, nova_data, nova_hora)
                        if err_rod: erros_ag.append(err_rod)
                        err_conf = verificar_conflito_loja(df_gv, nova_data, nova_hora, nova_loja, excluir_idx=idx_real)
                        if err_conf: erros_ag.append(err_conf)

                        if erros_ag:
                            for err in erros_ag: st.error(err)
                            st.warning("Para forçar, insira a senha de fechamento:")
                            senha_forca = st.text_input("Senha", type="password", key="ag_senha_forca")
                            if st.button("🔓 Forçar agendamento", key="btn_forcar", use_container_width=True):
                                if senha_forca == SENHA_FECHAMENTO:
                                    st.session_state["ag_forcar"] = True; st.rerun()
                                else:
                                    st.error("Senha incorreta.")
                        else:
                            st.session_state["ag_forcar"] = True

                    if st.session_state.get("ag_forcar"):
                        st.session_state["ag_forcar"] = False
                        agora_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                        ok = gv_enviar({"aba":"veiculos","acao":"atualizar_linha","linha_num":int(idx_real)+2,
                            "valores":[
                                {"col":GV_COLUNAS.index("status")+1,       "valor":"Agendado"},
                                {"col":GV_COLUNAS.index("data_entrega")+1,  "valor":nova_data.strftime("%d/%m/%Y")},
                                {"col":GV_COLUNAS.index("hora_entrega")+1,  "valor":nova_hora.strftime("%H:%M")},
                                {"col":GV_COLUNAS.index("loja_entrega")+1,  "valor":nova_loja},
                                {"col":GV_COLUNAS.index("entregador")+1,    "valor":novo_ent},
                                {"col":GV_COLUNAS.index("consultor")+1,     "valor":novo_con},
                                {"col":GV_COLUNAS.index("atualizado_em")+1, "valor":agora_str},
                                {"col":GV_COLUNAS.index("atualizado_por")+1,"valor":"Agendamento"},
                            ]})
                        gv_enviar({"aba":"historico","acao":"inserir","linha":[
                            gv_val_row(vei_aw,"id"), gv_val_row(vei_aw,"chassi"), gv_val_row(vei_aw,"modelo"),
                            gv_val_row(vei_aw,"status"),"Agendado",agora_str,"Agendamento"]})
                        if ok:
                            gv_carregar.clear()
                            data_fmt = nova_data.strftime("%d/%m/%Y"); hora_fmt = nova_hora.strftime("%H:%M")
                            assunto  = f"[Carrera Signature] Agendado — {gv_val_row(vei_aw,'modelo')}"
                            corpo    = f"Veículo: {gv_val_row(vei_aw,'modelo')}%0AChassi: {gv_val_row(vei_aw,'chassi')}%0ACliente: {gv_val_row(vei_aw,'cliente')}%0AData: {data_fmt} às {hora_fmt}%0ALocal: {nova_loja}"
                            st.success(f"✅ Agendado para {data_fmt} às {hora_fmt} em {nova_loja}!")
                            st.markdown(f"📧 [Enviar notificação](mailto:?subject={assunto}&body={corpo})")
                            st.rerun()

            # ── E-MAIL DAS 11 ────────────────────────────────
            elif ag_modo == "📧 E-mail das 11":
                st.markdown("Selecione os veículos e monte a lista de liberação para o e-mail.")

                ef1,ef2,ef3 = st.columns(3)
                with ef1: e11_sta  = st.multiselect("Status", GV_STATUS_LIST, default=["Agendado","Trânsito Vendido","Remoção","Disponível"], key="e11_sta")
                with ef2: e11_fab  = st.selectbox("Fabricante", ["Todos"]+sorted(df_gv["fabricante"].dropna().unique().tolist()) if "fabricante" in df_gv.columns else ["Todos"], key="e11_fab")
                with ef3: e11_loja = st.selectbox("Loja Destino", ["Todas"]+GV_LOJAS, key="e11_loja")

                df_e11 = df_gv.copy()
                if e11_sta:  df_e11 = df_e11[df_e11["status"].isin(e11_sta)]
                if e11_fab  != "Todos": df_e11 = df_e11[df_e11["fabricante"]   == e11_fab]
                if e11_loja != "Todas": df_e11 = df_e11[df_e11["loja_entrega"] == e11_loja]

                selecionados = st.session_state["email11_selecionados"]
                st.divider()

                if df_e11.empty:
                    st.info("Nenhum veículo com esses filtros.")
                else:
                    st.markdown(f"**{len(df_e11)} veículo(s) — clique ⬜/✅ para selecionar:**")
                    hc = st.columns([0.5,2.5,2.5,2,1.5,2,2])
                    for h,t in zip(hc,["","Cliente","Modelo","Chassi","Placa","Cor","Loja"]):
                        h.markdown(f"**{t}**")

                    for i_r, (idx2, row) in enumerate(df_e11.iterrows()):
                        chassi_r = str(row.get("chassi","")).strip()
                        ja = chassi_r in selecionados
                        cols = st.columns([0.5,2.5,2.5,2,1.5,2,2])
                        with cols[0]:
                            if st.button("✅" if ja else "⬜", key=f"e11_{idx2}_{i_r}"):
                                if ja: st.session_state["email11_selecionados"].remove(chassi_r)
                                else:  st.session_state["email11_selecionados"].append(chassi_r)
                                st.rerun()
                        cols[1].write(str(row.get("cliente","—")))
                        cols[2].write(str(row.get("modelo","—")))
                        cols[3].write(f"`{chassi_r}`")
                        cols[4].write(str(row.get("placa","—")))
                        cols[5].write(str(row.get("cor","—")))
                        cols[6].write(str(row.get("loja_entrega","—")))

                st.divider()

                if not selecionados:
                    st.info("Nenhum veículo selecionado.")
                else:
                    df_sel = df_gv[df_gv["chassi"].astype(str).isin(selecionados)].copy()
                    st.markdown(f"### 📋 Lista de Liberação — {len(df_sel)} veículo(s)")

                    lojas_s = sorted(df_sel["loja_entrega"].dropna().unique().tolist()) if "loja_entrega" in df_sel.columns else [""]
                    fabs_s  = sorted(df_sel["fabricante"].dropna().unique().tolist())   if "fabricante"   in df_sel.columns else [""]
                    texto_email = ""

                    for loja in (lojas_s or ["SEM LOJA"]):
                        df_l = df_sel[df_sel["loja_entrega"].astype(str)==loja] if lojas_s else df_sel
                        for fab in (fabs_s or ["SEM FABRICANTE"]):
                            df_g = df_l[df_l["fabricante"].astype(str)==fab] if fabs_s else df_l
                            if df_g.empty: continue

                            titulo = f"TRANSPORTE {loja}"
                            st.markdown(f"#### 🚛 {titulo} — {fab}")
                            texto_email += f"{titulo}\n\n"

                            hc2 = st.columns([3,3,2.5,1.5,2.5])
                            for h,t in zip(hc2,["Cliente","Modelo","Chassi","Placa","Cor"]):
                                h.markdown(f"**{t}**")

                            for _, vrow in df_g.iterrows():
                                cl=str(vrow.get("cliente","—")); mo=str(vrow.get("modelo","—"))
                                ch=str(vrow.get("chassi","—")); pl=str(vrow.get("placa","—")); co=str(vrow.get("cor","—"))
                                rc = st.columns([3,3,2.5,1.5,2.5])
                                rc[0].write(cl); rc[1].write(mo); rc[2].write(ch); rc[3].write(pl); rc[4].write(co)
                                texto_email += f"{cl:<45} {mo:<35} {ch:<20} {pl:<10} {co}\n"
                            texto_email += "\n"
                            st.markdown("---")

                    st.markdown("**📋 Texto para copiar:**")
                    st.text_area("", value=texto_email.strip(), height=250, key="e11_txt")
                    if st.button("🗑️ Limpar seleção", key="e11_limpar"):
                        st.session_state["email11_selecionados"] = []; st.rerun()

    # ════════════════════════════════════════════════════════
    # RELATÓRIOS
    # ════════════════════════════════════════════════════════
    idx_rel = idx.get("📊 Relatórios")
    with tabs[idx_rel]:
        st.markdown('<div class="gv-section-title">📊 Relatórios</div>', unsafe_allow_html=True)

        if df_gv.empty:
            st.info("Nenhum dado disponível.")
        else:
            r1, r2 = st.columns(2)
            with r1:
                st.markdown("**Veículos por Status**")
                if "status" in df_gv.columns: st.bar_chart(df_gv["status"].value_counts())
            with r2:
                st.markdown("**Veículos por Fabricante**")
                if "fabricante" in df_gv.columns: st.bar_chart(df_gv["fabricante"].value_counts())

            st.divider()
            st.markdown("**Veículos por Locadora**")
            if "locadora" in df_gv.columns: st.bar_chart(df_gv["locadora"].value_counts())

            if "_idade" in df_gv.columns:
                st.divider()
                st.markdown("**⏱ Tempo Médio de Estoque (TME)**")
                df_tme = df_gv[df_gv["_idade"].notna()].copy()
                if not df_tme.empty:
                    t1,t2,t3 = st.columns(3)
                    t1.metric("TME Geral",  f"{df_tme['_idade'].mean():.0f} dias")
                    t2.metric("Máximo",     f"{df_tme['_idade'].max():.0f} dias")
                    t3.metric("Em estoque", len(df_tme[df_tme["status"]!="Entregue"]))
                    if "fabricante" in df_tme.columns:
                        st.markdown("TME por Fabricante")
                        st.bar_chart(df_tme.groupby("fabricante")["_idade"].mean().sort_values(ascending=False))

            if autenticado and "valor_nf" in df_gv.columns:
                st.divider()
                st.markdown("**💰 Financeiro**")
                df_fin = df_gv.copy()
                df_fin["valor_nf"] = pd.to_numeric(df_fin["valor_nf"], errors="coerce")
                df_fin = df_fin[df_fin["valor_nf"]>0]
                if not df_fin.empty:
                    fr1,fr2,fr3 = st.columns(3)
                    fr1.metric("Total NF",       f"R$ {df_fin['valor_nf'].sum():,.0f}".replace(",","."))
                    fr2.metric("Média NF",       f"R$ {df_fin['valor_nf'].mean():,.0f}".replace(",","."))
                    fr3.metric("Veículos c/ NF", len(df_fin))