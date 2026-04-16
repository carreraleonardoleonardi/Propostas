import streamlit as st
import pandas as pd
import requests
import json
import datetime


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

# Paleta oficial Carrera
DOURADO_ESC = "#b57b3f"
DOURADO_CLR = "#dfc28a"
AMARELO_CLR = "#f9f4c2"
AZUL_ESC    = "#213144"
AZUL_CLR    = "#73a3db"
VERDE_ESC   = "#13422a"
CINZA_BG    = "#eaeaea"


def parse_data(valor):
    if not valor or str(valor).strip() in ("","nan","None","NaT"): return None
    s = str(valor).strip()
    for fmt in ("%d/%m/%Y","%Y-%m-%d","%Y/%m/%d","%d-%m-%Y"):
        try: return datetime.datetime.strptime(s, fmt).date()
        except: continue
    return None

def fmt_data(valor) -> str:
    d = parse_data(valor)
    return d.strftime("%d/%m/%Y") if d else ""

def calcular_idade(row):
    chegada = parse_data(str(row.get("data_chegada","")))
    if not chegada: return None
    if str(row.get("status","")).strip() == "Entregue":
        entrega = parse_data(str(row.get("data_entrega","")))
        ref = entrega if entrega else datetime.date.today()
    else: ref = datetime.date.today()
    return (ref - chegada).days

def farol_idade(dias) -> str:
    if dias is None: return "⚪"
    if dias <= 20:   return "🟢"
    if dias <= 30:   return "🟡"
    if dias <= 45:   return "🔴"
    return "⚫"

def badge_status(status: str) -> str:
    cor = STATUS_CORES.get(status, "#94a3b8")
    return f'<span style="background:{cor};color:#fff;padding:3px 12px;border-radius:999px;font-size:11px;font-weight:700">{status}</span>'

def farol_agendamento(row) -> str:
    status = str(row.get("status","")).strip()
    if status == "Entregue": return "🟢"
    data_ent = parse_data(str(row.get("data_entrega","")))
    if not data_ent: return "⚪"
    hora_str = str(row.get("hora_entrega","")).strip()
    agora = datetime.datetime.now()
    try:
        h, m = map(int, hora_str.split(":"))
        dt_ag = datetime.datetime.combine(data_ent, datetime.time(h, m))
    except: dt_ag = datetime.datetime.combine(data_ent, datetime.time(23,59))
    return "🔴" if agora > dt_ag else "🟡"

RODIZIO_SP = {"1":0,"2":0,"3":1,"4":1,"5":2,"6":2,"7":3,"8":3,"9":4,"0":4}
RODIZIO_BLOQUEIO = [(datetime.time(6,0), datetime.time(10,0)), (datetime.time(16,0), datetime.time(20,0))]

def verificar_rodizio(placa, data, hora):
    if not placa or len(placa) < 1: return None
    final = placa.strip()[-1].upper()
    if final not in RODIZIO_SP: return None
    if data.weekday() != RODIZIO_SP[final]: return None
    dias = ["segunda","terça","quarta","quinta","sexta"]
    for ini, fim in RODIZIO_BLOQUEIO:
        if ini <= hora < fim:
            return f"🚫 Rodízio: placa final **{final}** na **{dias[RODIZIO_SP[final]]}** entre {ini.strftime('%H:%M')} e {fim.strftime('%H:%M')}."
    return None

def verificar_conflito_loja(df, data, hora, loja, excluir_idx=-1):
    data_str = data.strftime("%d/%m/%Y"); hora_str = hora.strftime("%H:%M")
    mask = ((df["status"]=="Agendado") & (df["data_entrega"].astype(str)==data_str) &
            (df["hora_entrega"].astype(str)==hora_str) & (df["loja_entrega"].astype(str)==loja))
    if excluir_idx >= 0: mask = mask & (df.index != excluir_idx)
    conf = df[mask]
    if not conf.empty:
        v = conf.iloc[0]
        return f"🚫 Conflito em **{loja}** às **{hora_str}** — {v.get('modelo','?')} | {v.get('cliente','?')}"
    return None

@st.cache_data(ttl=60)
def gv_carregar():
    try:
        df = pd.read_csv(GV_SHEET_URL, header=0)
        df.columns = [c.strip().lower().replace(" ","_") for c in df.columns]
        for col in ["data_chegada","data_entrega","criado_em","atualizado_em"]:
            if col in df.columns: df[col] = df[col].astype(str).apply(fmt_data)
        return df
    except: return pd.DataFrame(columns=GV_COLUNAS)

def gv_enviar(payload: dict) -> bool:
    try:
        requests.post(GV_WEBHOOK, data=json.dumps(payload),
            headers={"Content-Type":"text/plain"}, timeout=30)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}"); return False

def gv_novo_id(_=None) -> str:
    return "VEI" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")

def gv_val_row(row, col, default="") -> str:
    v = row.get(col, default)
    return "" if pd.isna(v) else str(v)


GV_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── KPI strip ── */
.kpi-strip { display:flex; gap:10px; margin:16px 0 20px; }
.kpi-box {
    flex:1; background:#fff;
    border:1px solid #dfc28a;
    border-top:4px solid #b57b3f;
    border-radius:14px;
    padding:16px 12px 12px;
    text-align:center;
    box-shadow:0 2px 8px rgba(181,123,63,.08);
    font-family:'Inter',sans-serif;
}
.kpi-num { font-size:28px; font-weight:800; line-height:1; }
.kpi-lbl { font-size:10px; color:#94a3b8; margin-top:5px;
           text-transform:uppercase; letter-spacing:.7px; font-weight:600; }

/* ── Card veículo ── */
.veh-card {
    display:flex; align-items:stretch;
    background:#fff;
    border:1.5px solid #e8e0d0;
    border-radius:14px;
    margin-bottom:8px;
    overflow:hidden;
    box-shadow:0 1px 4px rgba(181,123,63,.06);
    transition:box-shadow .18s, transform .14s, border-color .18s;
    font-family:'Inter',sans-serif;
}
.veh-card:hover {
    box-shadow:0 6px 20px rgba(181,123,63,.14);
    transform:translateY(-2px);
    border-color:#dfc28a;
}
.veh-card.open {
    border-color:#b57b3f;
    box-shadow:0 6px 24px rgba(181,123,63,.22);
    background:#fdfaf5;
}

.veh-stripe { width:5px; min-height:68px; flex-shrink:0; }

.veh-body { flex:1; padding:13px 16px; min-width:0; }
.veh-title { font-size:15px; font-weight:700; color:#213144;
             white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.veh-fab { font-size:12px; font-weight:400; color:#94a3b8; margin-left:6px; }
.veh-meta { font-size:12px; color:#64748b; margin-top:5px;
            display:flex; flex-wrap:wrap; gap:5px; }
.veh-tag { background:#f4f0e8; border-radius:6px; padding:2px 8px;
           font-size:11px; color:#6b5c45; border:1px solid #e8dfd0; }
.veh-cli { font-size:11px; color:#475569; margin-top:5px; }
.veh-ag  { font-size:11px; color:#0891b2; margin-top:3px; }

.veh-mid { padding:13px 16px 13px 0; text-align:right;
           flex-shrink:0; min-width:130px; display:flex;
           flex-direction:column; justify-content:center; }
.veh-badge { display:inline-block; padding:4px 12px; border-radius:999px;
             font-size:11px; font-weight:700; color:#fff; white-space:nowrap; }
.veh-idade { font-size:11px; color:#94a3b8; margin-top:5px; }

/* ── Botão CTA ── */
.veh-cta-col button {
    border-radius:10px !important;
    border:2px solid #b57b3f !important;
    background:#fff !important;
    color:#b57b3f !important;
    font-size:18px !important;
    font-weight:600 !important;
    transition:all .18s !important;
    box-shadow:0 2px 6px rgba(181,123,63,.12) !important;
}
.veh-cta-col button:hover {
    background:#b57b3f !important;
    color:#fff !important;
    box-shadow:0 4px 14px rgba(181,123,63,.30) !important;
}

/* ── Pop-up ── */
.popup-title { font-size:20px; font-weight:800; color:#213144; font-family:'Inter',sans-serif; }
.popup-sub   { font-size:12px; color:#64748b; margin-top:5px; }
.popup-badge { display:inline-block; padding:4px 14px; border-radius:999px;
               font-size:11px; font-weight:700; color:#fff; margin-top:8px; }

/* ── Detalhes grid ── */
.det-sec  { margin-bottom:18px; }
.det-head { font-size:10px; font-weight:700; color:#b57b3f; text-transform:uppercase;
            letter-spacing:.8px; border-bottom:1px solid #f0e8d8;
            padding-bottom:4px; margin-bottom:10px; }
.det-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(170px,1fr));
            gap:10px 20px; }
.det-lbl  { font-size:10px; color:#94a3b8; font-weight:600; text-transform:uppercase; }
.det-val  { font-size:13px; color:#213144; font-weight:500; margin-top:2px; }
.det-val.em { color:#cbd5e1; font-style:italic; }

/* ── Agendamento cards ── */
.ag-card {
    background:#fff; border:1px solid #e8e0d0;
    border-radius:12px; padding:16px 20px; margin-bottom:10px;
    box-shadow:0 1px 4px rgba(0,0,0,.04);
}
.ag-hora { font-size:22px; font-weight:800; color:#213144; }
</style>
"""


def render():
    st.markdown(GV_CSS, unsafe_allow_html=True)

    autenticado = st.session_state.get("auth_tipo","") == "Staff"
    hoje = datetime.date.today()

    for k,v in [("gv_popup_chassi",None),("ag_forcar",False),("email11_selecionados",[])]:
        if k not in st.session_state: st.session_state[k] = v

    df_gv = gv_carregar()
    if not df_gv.empty:
        df_gv["_idade"] = df_gv.apply(calcular_idade, axis=1)

    # ── Header ──────────────────────────────────────────
    h1,h2,h3,h4 = st.columns([5,1,1,1])
    with h1:
        st.markdown(f"<h2 style='color:{AZUL_ESC};margin:0;font-family:Inter,sans-serif'>🚘 Estoque de Veículos</h2>",unsafe_allow_html=True)
    with h2:
        if st.button("🔄 Atualizar",use_container_width=True,key="gv_ref"):
            gv_carregar.clear(); st.rerun()
    with h3:
        if autenticado and st.button("➕ Cadastrar",use_container_width=True,key="gv_cad",type="primary"):
            st.session_state["gv_popup_chassi"]="__NOVO__"; st.rerun()
    with h4:
        if autenticado and not df_gv.empty:
            try:
                import io; buf=io.BytesIO()
                df_gv.to_excel(buf,index=False,engine="openpyxl"); buf.seek(0)
                st.download_button("📥 Excel",data=buf.getvalue(),file_name="veiculos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,key="gv_xl")
            except:
                st.download_button("📥 CSV",data=df_gv.to_csv(index=False).encode(),
                    file_name="veiculos.csv",mime="text/csv",use_container_width=True,key="gv_csv")

    if df_gv.empty:
        st.info("Nenhum veículo cadastrado ainda."); return

    # ── KPIs ────────────────────────────────────────────
    total=len(df_gv)
    disp=len(df_gv[df_gv["status"].str.contains("Disponível",na=False)])
    agend=len(df_gv[df_gv["status"]=="Agendado"])
    entr=len(df_gv[df_gv["status"]=="Entregue"])
    avar=len(df_gv[df_gv["status"]=="Avariado"])
    ach=df_gv[df_gv["status"]=="Agendado"].copy()
    if not ach.empty:
        ach["_f"]=ach.apply(farol_agendamento,axis=1); atras=len(ach[ach["_f"]=="🔴"])
    else: atras=0

    st.markdown(f"""
    <div class="kpi-strip">
      <div class="kpi-box"><div class="kpi-num" style="color:{AZUL_ESC}">{total}</div><div class="kpi-lbl">Total</div></div>
      <div class="kpi-box"><div class="kpi-num" style="color:#22c55e">{disp}</div><div class="kpi-lbl">Disponíveis</div></div>
      <div class="kpi-box"><div class="kpi-num" style="color:#06b6d4">{agend}</div><div class="kpi-lbl">Agendados</div></div>
      <div class="kpi-box"><div class="kpi-num" style="color:#10b981">{entr}</div><div class="kpi-lbl">Entregues</div></div>
      <div class="kpi-box"><div class="kpi-num" style="color:#ef4444">{avar}</div><div class="kpi-lbl">Avariados</div></div>
      <div class="kpi-box"><div class="kpi-num" style="color:#dc2626">{atras}</div><div class="kpi-lbl">Atrasados</div></div>
    </div>""",unsafe_allow_html=True)

    # ── Filtros ─────────────────────────────────────────
    f1,f2,f3,f4=st.columns(4)
    with f1: flt_sta=st.selectbox("Status",["Todos"]+GV_STATUS_LIST,key="p_sta")
    with f2:
        fabs=["Todos"]+sorted(df_gv["fabricante"].dropna().unique()) if "fabricante" in df_gv.columns else ["Todos"]
        flt_fab=st.selectbox("Fabricante",fabs,key="p_fab")
    with f3:
        locs=["Todos"]+sorted(df_gv["locadora"].dropna().unique()) if "locadora" in df_gv.columns else ["Todos"]
        flt_loc=st.selectbox("Locadora",locs,key="p_loc")
    with f4:
        cons=["Todos"]+sorted(df_gv["consultor"].dropna().unique()) if "consultor" in df_gv.columns else ["Todos"]
        flt_con=st.selectbox("Consultor",cons,key="p_con")

    b1,b2,b3=st.columns(3)
    with b1: s_ch=st.text_input("🔑 Chassi",placeholder="9BWBG...",key="b_ch")
    with b2: s_pl=st.text_input("🪪 Placa",placeholder="QSO8D24",key="b_pl")
    with b3: s_pe=st.text_input("📄 Nº Pedido",placeholder="12345",key="b_pe")

    dv=df_gv.copy()
    if flt_sta!="Todos": dv=dv[dv["status"]==flt_sta]
    if flt_fab!="Todos": dv=dv[dv["fabricante"]==flt_fab]
    if flt_loc!="Todos": dv=dv[dv["locadora"]==flt_loc]
    if flt_con!="Todos": dv=dv[dv["consultor"]==flt_con]
    if s_ch: dv=dv[dv["chassi"].astype(str).str.lower().str.contains(s_ch.lower(),na=False)]
    if s_pl: dv=dv[dv["placa"].astype(str).str.lower().str.contains(s_pl.lower(),na=False)]
    if s_pe: dv=dv[dv["pedido"].astype(str).str.lower().str.contains(s_pe.lower(),na=False)]

    st.markdown(f"<p style='color:#94a3b8;font-size:13px;margin:8px 0 4px'><b style='color:{AZUL_ESC}'>{len(dv)}</b> veículo(s)</p>",unsafe_allow_html=True)
    st.divider()

    def sv(r,c):
        v=r.get(c,""); s=str(v).strip()
        if s in ("","nan","None","NaT"): return "—"
        if s.endswith(".0") and s[:-2].lstrip("-").isdigit(): return s[:-2]
        return s

    # ══ POP-UP CADASTRAR ══════════════════════════════════
    chassi_pop=st.session_state.get("gv_popup_chassi")

    if chassi_pop=="__NOVO__" and autenticado:
        with st.container(border=True):
            p1,p2=st.columns([6,1])
            with p1: st.markdown(f"<div style='font-size:18px;font-weight:800;color:{AZUL_ESC};font-family:Inter,sans-serif'>➕ Cadastrar Veículo</div>",unsafe_allow_html=True)
            with p2:
                if st.button("✕ Fechar",key="cad_x"): st.session_state["gv_popup_chassi"]=None; st.rerun()
            modo=st.radio("",["Manual","Importar Excel"],horizontal=True,key="cad_modo")
            if modo=="Manual":
                with st.form("f_cad"):
                    c1,c2,c3=st.columns(3)
                    with c1: fab=st.selectbox("Fabricante *",GV_FABRICANTES); mod=st.text_input("Modelo *"); cor=st.text_input("Cor *")
                    with c2: chassi=st.text_input("Chassi *"); placa=st.text_input("Placa"); comb=st.selectbox("Combustível",GV_COMBUSTIVEIS)
                    with c3: anof=st.text_input("Ano Fab."); anom=st.text_input("Ano Mod."); stc=st.selectbox("Status Inicial",GV_STATUS_LIST)
                    o1,o2,o3=st.columns(3)
                    with o1: loc=st.selectbox("Locadora",GV_LOCADORAS); consc=st.text_input("Consultor")
                    with o2: clic=st.text_input("Cliente"); localc=st.text_input("Local Atual")
                    with o3: dch=st.date_input("Data Chegada",value=None); av=st.selectbox("Avaria?",["Não","Sim"])
                    obs=st.text_area("Obs. Avaria",height=60)
                    if st.form_submit_button("💾 Cadastrar",use_container_width=True,type="primary"):
                        if not fab or not mod or not chassi: st.error("Fabricante, Modelo e Chassi são obrigatórios.")
                        elif "chassi" in df_gv.columns and chassi.upper() in df_gv["chassi"].astype(str).str.upper().values: st.error("Chassi já existe!")
                        else:
                            agr=datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                            nl=[gv_novo_id(),fab,mod,chassi,placa,cor,anof,anom,comb,"",loc,consc,clic,"",stc,localc,
                                dch.strftime("%d/%m/%Y") if dch else "","","","",av,obs if av=="Sim" else "","","","","",agr,agr,"Sistema"]
                            pg=st.progress(0,"Salvando..."); pg.progress(70,"Enviando...")
                            if gv_enviar({"aba":"veiculos","acao":"inserir","linha":nl}):
                                pg.progress(100,"Concluído!"); gv_carregar.clear()
                                st.success("✅ Cadastrado!"); st.session_state["gv_popup_chassi"]=None; st.rerun()
            else:
                st.info("Colunas: FABRICANTE · MODELO · CHASSI · PLACA · COR · LOCADORA · STATUS · DATA CHEGADA · COM AVARIA? · LOCAL ATUAL")
                arq=st.file_uploader(".xlsx",type=["xlsx"],key="gv_up")
                if arq:
                    try:
                        di=pd.read_excel(arq); st.dataframe(di.head(5),use_container_width=True)
                        if st.button("📤 Importar",use_container_width=True,key="gv_imp",type="primary"):
                            agr=datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                            cex=set(df_gv["chassi"].astype(str).str.upper()) if "chassi" in df_gv.columns else set()
                            errs=0; dps=[]
                            pg2=st.progress(0,"Importando...")
                            for ri,(_,row) in enumerate(di.iterrows()):
                                pg2.progress(int(ri/len(di)*90)+5,f"Linha {ri+1}/{len(di)}...")
                                def g(c):
                                    for t in [c,c.upper(),c.lower(),c.title()]:
                                        vv=row.get(t,None)
                                        if vv is not None and not(isinstance(vv,float) and pd.isna(vv)): return str(vv).strip()
                                    return ""
                                ci=g("CHASSI").upper()
                                if ci and ci in cex: dps.append(ci); continue
                                if ci: cex.add(ci)
                                nl=[gv_novo_id(),g("FABRICANTE"),g("MODELO"),ci,g("PLACA"),g("COR"),"","","","",
                                    g("LOCADORA"),"","","",g("STATUS") or "Trânsito Disponível",g("LOCAL ATUAL"),
                                    g("DATA CHEGADA"),"","","",g("COM AVARIA?") or "Não","","","","","",agr,agr,"Importação"]
                                if not gv_enviar({"aba":"veiculos","acao":"inserir","linha":nl}): errs+=1
                            pg2.progress(100,"Concluído!")
                            gv_carregar.clear()
                            st.success(f"✅ {len(di)-errs-len(dps)} importado(s)!")
                            if dps: st.warning(f"Duplicados: {', '.join(dps)}")
                            st.session_state["gv_popup_chassi"]=None; st.rerun()
                    except Exception as e: st.error(f"Erro: {e}")
        st.divider()

    # ══ POP-UP VEÍCULO ════════════════════════════════════
    elif chassi_pop and chassi_pop!="__NOVO__":
        mx=df_gv[df_gv["chassi"].astype(str)==chassi_pop]
        if not mx.empty:
            vm=mx.iloc[0]; idx_vm=mx.index[0]; lvm=int(idx_vm)+2
            cor_p=STATUS_CORES.get(sv(vm,"status"),"#94a3b8")
            id_p=vm.get("_idade",None); fi_p=farol_idade(id_p)

            with st.container(border=True):
                pa,pb=st.columns([6,1])
                with pa:
                    st.markdown(
                        f"<div class='popup-title'>{sv(vm,'modelo')}"
                        f"<span style='font-size:14px;font-weight:400;color:#94a3b8;margin-left:8px'>{sv(vm,'fabricante')}</span></div>"
                        f"<div class='popup-sub'>🔑 {sv(vm,'chassi')} &nbsp;·&nbsp; 🪪 {sv(vm,'placa')} &nbsp;·&nbsp; 🎨 {sv(vm,'cor')} &nbsp;·&nbsp; 🏢 {sv(vm,'locadora')}</div>"
                        f"<span class='popup-badge' style='background:{cor_p}'>{sv(vm,'status')}</span>"
                        f"&nbsp;<span style='font-size:12px;color:#94a3b8'>{fi_p} {f'{id_p}d' if id_p else '—'}</span>",
                        unsafe_allow_html=True)
                with pb:
                    if st.button("✕ Fechar",key="px",use_container_width=True):
                        st.session_state["gv_popup_chassi"]=None; st.rerun()

                abas_p=["🔄 Status","📅 Agendar","✏️ Editar","📋 Detalhes"]
                if autenticado: abas_p.append("🗑️ Deletar")
                tp=st.tabs(abas_p)

                with tp[0]:
                    with st.form("fp_s"):
                        is_=GV_STATUS_LIST.index(sv(vm,"status")) if sv(vm,"status") in GV_STATUS_LIST else 0
                        ns=st.selectbox("Novo status",GV_STATUS_LIST,index=is_)
                        if st.form_submit_button("✅ Salvar",use_container_width=True,type="primary"):
                            agr=datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                            pg=st.progress(0,"..."); pg.progress(50,"Salvando...")
                            gv_enviar({"aba":"veiculos","acao":"atualizar_linha","linha_num":lvm,"valores":[
                                {"col":GV_COLUNAS.index("status")+1,"valor":ns},
                                {"col":GV_COLUNAS.index("atualizado_em")+1,"valor":agr},
                                {"col":GV_COLUNAS.index("atualizado_por")+1,"valor":st.session_state.get("auth_nome","Sistema")}]})
                            gv_enviar({"aba":"historico","acao":"inserir","linha":[sv(vm,"id"),sv(vm,"chassi"),sv(vm,"modelo"),sv(vm,"status"),ns,agr,st.session_state.get("auth_nome","Sistema")]})
                            pg.progress(100,"✓"); gv_carregar.clear(); st.success(f"✅ → {ns}"); st.rerun()

                with tp[1]:
                    with st.form("fp_a"):
                        a1,a2,a3=st.columns(3)
                        with a1: nd=st.date_input("Data *",value=hoje)
                        with a2: nh=st.time_input("Hora *",value=datetime.time(10,0))
                        with a3: nl_=st.selectbox("Loja *",GV_LOJAS)
                        a4,a5=st.columns(2)
                        with a4: ne=st.text_input("Entregador",value=sv(vm,"entregador") if sv(vm,"entregador")!="—" else "")
                        with a5: nc=st.text_input("Consultor",value=sv(vm,"consultor") if sv(vm,"consultor")!="—" else "")
                        conf=st.form_submit_button("📅 Confirmar",use_container_width=True,type="primary")
                    if conf:
                        errs=[e for e in [verificar_rodizio(sv(vm,"placa"),nd,nh),verificar_conflito_loja(df_gv,nd,nh,nl_,excluir_idx=idx_vm)] if e]
                        if errs:
                            for e in errs: st.error(e)
                            sf=st.text_input("Senha para forçar",type="password",key="ag_sf")
                            if st.button("🔓 Forçar",key="ag_frc"):
                                if sf==SENHA_FECHAMENTO: st.session_state["ag_forcar"]=True; st.rerun()
                                else: st.error("Incorreta.")
                        else: st.session_state["ag_forcar"]=True
                    if st.session_state.get("ag_forcar"):
                        st.session_state["ag_forcar"]=False
                        agr=datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                        pg2=st.progress(0,"..."); pg2.progress(50,"Agendando...")
                        gv_enviar({"aba":"veiculos","acao":"atualizar_linha","linha_num":lvm,"valores":[
                            {"col":GV_COLUNAS.index("status")+1,"valor":"Agendado"},
                            {"col":GV_COLUNAS.index("data_entrega")+1,"valor":nd.strftime("%d/%m/%Y")},
                            {"col":GV_COLUNAS.index("hora_entrega")+1,"valor":nh.strftime("%H:%M")},
                            {"col":GV_COLUNAS.index("loja_entrega")+1,"valor":nl_},
                            {"col":GV_COLUNAS.index("entregador")+1,"valor":ne},
                            {"col":GV_COLUNAS.index("consultor")+1,"valor":nc},
                            {"col":GV_COLUNAS.index("atualizado_em")+1,"valor":agr},
                            {"col":GV_COLUNAS.index("atualizado_por")+1,"valor":st.session_state.get("auth_nome","Sistema")}]})
                        gv_enviar({"aba":"historico","acao":"inserir","linha":[sv(vm,"id"),sv(vm,"chassi"),sv(vm,"modelo"),sv(vm,"status"),"Agendado",agr,st.session_state.get("auth_nome","Sistema")]})
                        pg2.progress(100,"✓"); gv_carregar.clear(); st.success("✅ Agendado!"); st.rerun()

                with tp[2]:
                    with st.form("fp_e"):
                        e1,e2=st.columns(2)
                        with e1:
                            ep=st.text_input("Placa",value=sv(vm,"placa") if sv(vm,"placa")!="—" else "")
                            ec=st.text_input("Cor",value=sv(vm,"cor") if sv(vm,"cor")!="—" else "")
                            ecl=st.text_input("Cliente",value=sv(vm,"cliente") if sv(vm,"cliente")!="—" else "")
                            eco=st.text_input("Consultor",value=sv(vm,"consultor") if sv(vm,"consultor")!="—" else "")
                            elo=st.text_input("Local Atual",value=sv(vm,"local_atual") if sv(vm,"local_atual")!="—" else "")
                        with e2:
                            epe=st.text_input("Nº Pedido",value=sv(vm,"pedido") if sv(vm,"pedido")!="—" else "")
                            elj=st.selectbox("Loja Entrega",[""]+GV_LOJAS,index=([""]+GV_LOJAS).index(sv(vm,"loja_entrega")) if sv(vm,"loja_entrega") in GV_LOJAS else 0)
                            eav=st.selectbox("Avaria?",["Não","Sim"],index=1 if sv(vm,"avaria")=="Sim" else 0)
                            eob=st.text_area("Obs. Avaria",value=sv(vm,"obs_avaria") if sv(vm,"obs_avaria")!="—" else "",height=72)
                            een=st.text_input("Entregador",value=sv(vm,"entregador") if sv(vm,"entregador")!="—" else "")
                        if st.form_submit_button("💾 Salvar",use_container_width=True,type="primary"):
                            agr=datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                            pg3=st.progress(0,"..."); pg3.progress(50,"Salvando...")
                            campos=[("placa",ep),("cor",ec),("cliente",ecl),("consultor",eco),("local_atual",elo),
                                    ("pedido",epe),("loja_entrega",elj),("avaria",eav),
                                    ("obs_avaria",eob if eav=="Sim" else ""),("entregador",een),
                                    ("atualizado_em",agr),("atualizado_por",st.session_state.get("auth_nome","Sistema"))]
                            vals=[{"col":GV_COLUNAS.index(c)+1,"valor":v} for c,v in campos if c in GV_COLUNAS]
                            ok=gv_enviar({"aba":"veiculos","acao":"atualizar_linha","linha_num":lvm,"valores":vals})
                            pg3.progress(100,"✓")
                            if ok: gv_carregar.clear(); st.success("✅ Salvo!"); st.rerun()

                with tp[3]:
                    def vf(l,v):
                        cl="em" if v=="—" else ""
                        return f"<div><div class='det-lbl'>{l}</div><div class='det-val {cl}'>{v}</div></div>"
                    secs=[
                        ("🔍 Identificação",[("Fabricante",sv(vm,"fabricante")),("Modelo",sv(vm,"modelo")),("Chassi",sv(vm,"chassi")),("Placa",sv(vm,"placa")),("Cor",sv(vm,"cor")),("Combustível",sv(vm,"combustivel")),("Ano Fab.",sv(vm,"ano_fabricacao")),("Ano Mod.",sv(vm,"ano_modelo")),("Opcionais",sv(vm,"opcionais"))]),
                        ("🏢 Operacional",[("Status",sv(vm,"status")),("Locadora",sv(vm,"locadora")),("Consultor",sv(vm,"consultor")),("Cliente",sv(vm,"cliente")),("Pedido",sv(vm,"pedido")),("Local Atual",sv(vm,"local_atual")),("Avaria",sv(vm,"avaria")),("Obs. Avaria",sv(vm,"obs_avaria"))]),
                        ("📅 Datas",[("Data Chegada",sv(vm,"data_chegada")),("Data Entrega",sv(vm,"data_entrega")),("Hora Entrega",sv(vm,"hora_entrega")),("Loja Entrega",sv(vm,"loja_entrega")),("Entregador",sv(vm,"entregador")),("Idade",f"{id_p}d" if id_p else "—")]),
                        ("💰 Financeiro",[("Valor NF",sv(vm,"valor_nf")),("Margem",sv(vm,"margem")),("Comissão",sv(vm,"comissao"))]),
                        ("🕐 Auditoria",[("ID",sv(vm,"id")),("Criado em",sv(vm,"criado_em")),("Atualizado em",sv(vm,"atualizado_em")),("Por",sv(vm,"atualizado_por"))]),
                    ]
                    for tt,cc in secs:
                        st.markdown(f"<div class='det-sec'><div class='det-head'>{tt}</div><div class='det-grid'>{''.join(vf(l,v) for l,v in cc)}</div></div>",unsafe_allow_html=True)

                if autenticado:
                    with tp[4]:
                        st.error(f"⚠️ Deletar **{sv(vm,'modelo')}** ({sv(vm,'chassi')}) permanentemente?")
                        d1,d2=st.columns(2)
                        with d1:
                            if st.button("✅ Sim, deletar",key="dp",use_container_width=True,type="primary"):
                                pg4=st.progress(0,"..."); pg4.progress(60,"Removendo...")
                                gv_enviar({"aba":"veiculos","acao":"deletar_linha","linha_num":lvm})
                                gv_enviar({"aba":"historico","acao":"inserir","linha":[sv(vm,"id"),sv(vm,"chassi"),sv(vm,"modelo"),sv(vm,"status"),"DELETADO",datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),st.session_state.get("auth_nome","Sistema")]})
                                pg4.progress(100,"✓"); gv_carregar.clear()
                                st.session_state["gv_popup_chassi"]=None; st.rerun()
                        with d2:
                            if st.button("❌ Cancelar",key="dc",use_container_width=True):
                                st.session_state["gv_popup_chassi"]=None; st.rerun()
        st.divider()

    # ══ CARDS ═════════════════════════════════════════════
    for i,(_,row) in enumerate(dv.iterrows()):
        ch_r=sv(row,"chassi"); st_r=str(row.get("status",""))
        cor_r=STATUS_CORES.get(st_r,"#94a3b8")
        id_r=row.get("_idade",None); fi_r=farol_idade(id_r)
        id_txt=f"{fi_r} {id_r}d" if id_r is not None else "⚪ —"
        ab=st.session_state.get("gv_popup_chassi")==ch_r
        cli_h=f"<div class='veh-cli'>👤 <b>{sv(row,'cliente')}</b> · {sv(row,'consultor')}</div>" if sv(row,"cliente")!="—" else ""
        ag_h=f"<div class='veh-ag'>📅 {sv(row,'data_entrega')} {sv(row,'hora_entrega')} · {sv(row,'loja_entrega')}</div>" if st_r=="Agendado" and sv(row,"data_entrega")!="—" else ""
        open_cls="open" if ab else ""

        col_card,col_cta=st.columns([11,1])
        with col_card:
            st.markdown(
                f"<div class='veh-card {open_cls}'>"
                f"<div class='veh-stripe' style='background:{cor_r}'></div>"
                f"<div class='veh-body'>"
                f"<div class='veh-title'>{sv(row,'modelo')}<span class='veh-fab'>{sv(row,'fabricante')}</span></div>"
                f"<div class='veh-meta'>"
                f"<span class='veh-tag'>🔑 {sv(row,'chassi')}</span>"
                f"<span class='veh-tag'>🪪 {sv(row,'placa')}</span>"
                f"<span class='veh-tag'>🎨 {sv(row,'cor')}</span>"
                f"<span class='veh-tag'>🏢 {sv(row,'locadora')}</span>"
                f"</div>{cli_h}</div>"
                f"<div class='veh-mid'>"
                f"<span class='veh-badge' style='background:{cor_r}'>{st_r}</span>"
                f"<div class='veh-idade'>{id_txt}</div>{ag_h}"
                f"</div></div>",
                unsafe_allow_html=True)
        with col_cta:
            st.markdown("<div class='veh-cta-col'>",unsafe_allow_html=True)
            cta_ico="✕" if ab else "➕"
            if st.button(cta_ico,key=f"cta_{i}_{ch_r}",use_container_width=True,
                         type="primary" if ab else "secondary"):
                st.session_state["gv_popup_chassi"]=None if ab else ch_r
                st.rerun()
            st.markdown("</div>",unsafe_allow_html=True)
