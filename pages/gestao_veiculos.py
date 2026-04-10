import streamlit as st
import pandas as pd
import requests
import json
import datetime


GV_SHEET_URL = "https://docs.google.com/spreadsheets/d/1BpAtiXz4AEuQg4kVx8OFonohPlvbScdOgWPIZRxQnxo/export?format=csv&gid=461042346"
GV_WEBHOOK   = "https://script.google.com/macros/s/AKfycbzFP-ezBsVx7W7VhYATKgaqdAg485o0AQb8s9FdGTlvmdzK1YRj7dCUVfTrXNgJOToc/exec"
GV_SENHA     = "CarreraSignature#2026"

GV_STATUS_LIST = [
    "Trânsito Disponível", "Trânsito Vendido", "Disponível",
    "Aguardando Atribuição", "Aguardando Agendamento", "Agendado",
    "Entregue", "Reagendar", "Avariado", "Distrato",
    "Remoção", "Reserva Temporária", "Evento Signature"
]

GV_FABRICANTES  = ["VOLKSWAGEN", "CHEVROLET", "NISSAN", "JEEP", "GWM",
                   "RENAULT", "HYUNDAI", "TOYOTA", "FIAT", "FORD", "OUTRO"]
GV_LOCADORAS    = ["LM FROTAS", "MOVE", "RCI", "TOOT", "OUTRO"]
GV_LOJAS        = ["LOJA ALPHAVILLE", "LOJA VILLA LOBOS", "LOJA OSASCO",
                   "LOJA BUTANTÃ", "LOJA COTIA", "OUTRO DN"]
GV_COMBUSTIVEIS = ["Flex", "Gasolina", "Elétrico", "Híbrido", "Diesel"]

GV_COLUNAS = [
    "id", "fabricante", "modelo", "chassi", "placa", "cor",
    "ano_fabricacao", "ano_modelo", "combustivel", "opcionais",
    "locadora", "consultor", "cliente", "pedido", "status",
    "local_atual", "data_chegada", "data_entrega", "hora_entrega",
    "entregador", "avaria", "obs_avaria", "loja_entrega",
    "valor_nf", "margem", "comissao",
    "criado_em", "atualizado_em", "atualizado_por"
]


# ── Helpers de data ──────────────────────────────────────────────────────────

def parse_data(valor: str) -> datetime.date | None:
    """Aceita DD/MM/YYYY e YYYY-MM-DD, retorna date ou None."""
    if not valor or str(valor).strip() in ("", "nan", "None"):
        return None
    s = str(valor).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def fmt_data(valor: str) -> str:
    """Converte qualquer formato de data para DD/MM/YYYY."""
    d = parse_data(valor)
    return d.strftime("%d/%m/%Y") if d else ""


def calcular_idade(row) -> int | None:
    """
    Retorna dias no estoque:
    - Status Entregue → data_entrega - data_chegada
    - Outros          → hoje - data_chegada
    """
    chegada = parse_data(str(row.get("data_chegada", "")))
    if not chegada:
        return None
    if str(row.get("status", "")).strip() == "Entregue":
        entrega = parse_data(str(row.get("data_entrega", "")))
        ref = entrega if entrega else datetime.date.today()
    else:
        ref = datetime.date.today()
    return (ref - chegada).days


def farol_idade(dias: int | None) -> str:
    """🟢 ≤20  🟡 ≤30  🔴 ≤45  ⚫ >45"""
    if dias is None:
        return "⚪"
    if dias <= 20:
        return "🟢"
    if dias <= 30:
        return "🟡"
    if dias <= 45:
        return "🔴"
    return "⚫"


def farol_agendamento(row) -> str:
    """
    🟡 Agendado (dentro do prazo)
    🔴 Agendado (hora passou, não entregue)
    🟢 Entregue
    """
    status = str(row.get("status", "")).strip()
    if status == "Entregue":
        return "🟢 Entregue"

    data_ent = parse_data(str(row.get("data_entrega", "")))
    if not data_ent:
        return "⚪ Sem data"

    hora_str = str(row.get("hora_entrega", "")).strip()
    agora    = datetime.datetime.now()
    try:
        h, m = map(int, hora_str.split(":"))
        dt_agendado = datetime.datetime.combine(data_ent, datetime.time(h, m))
    except Exception:
        dt_agendado = datetime.datetime.combine(data_ent, datetime.time(23, 59))

    if agora > dt_agendado:
        return "🔴 Atrasado"
    return "🟡 Agendado"


# ── Cache e envio ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def gv_carregar():
    try:
        df = pd.read_csv(GV_SHEET_URL, header=0)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        # Normaliza datas para DD/MM/YYYY
        for col in ["data_chegada", "data_entrega", "criado_em", "atualizado_em"]:
            if col in df.columns:
                df[col] = df[col].astype(str).apply(fmt_data)
        return df
    except Exception:
        return pd.DataFrame(columns=GV_COLUNAS)


def gv_enviar(payload: dict) -> bool:
    try:
        requests.post(GV_WEBHOOK, data=json.dumps(payload),
            headers={"Content-Type": "text/plain"}, timeout=30)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False


def gv_novo_id(_df) -> str:
    return "VEI" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")


# ── Render principal ──────────────────────────────────────────────────────────

def render():
    st.title("🚘 Gestão de Veículos")

    # Auth
    if "gv_autenticado" not in st.session_state:
        st.session_state["gv_autenticado"] = False
    if "ag_forcar" not in st.session_state:
        st.session_state["ag_forcar"] = False

    _, col_auth = st.columns([6, 2])
    with col_auth:
        if not st.session_state["gv_autenticado"]:
            with st.expander("🔐 Entrar como editor"):
                senha_gv = st.text_input("Senha", type="password", key="gv_senha_input")
                if st.button("Entrar", key="gv_btn_login", use_container_width=True):
                    if senha_gv == GV_SENHA:
                        st.session_state["gv_autenticado"] = True
                        st.rerun()
                    else:
                        st.error("Senha incorreta.")
        else:
            st.success("✅ Editor")
            if st.button("Sair", key="gv_btn_logout", use_container_width=True):
                st.session_state["gv_autenticado"] = False
                st.rerun()

    autenticado = st.session_state["gv_autenticado"]

    if autenticado:
        sub_tabs = st.tabs(["📋 Painel", "➕ Cadastrar", "✏️ Editar", "📅 Agendamentos", "📊 Relatórios"])
    else:
        sub_tabs = st.tabs(["📋 Painel", "📅 Agendamentos", "📊 Relatórios"])

    df_gv = gv_carregar()

    # Calcula idade e farol de idade para uso geral
    if not df_gv.empty:
        df_gv["idade_dias"] = df_gv.apply(calcular_idade, axis=1)
        df_gv["farol_idade"] = df_gv["idade_dias"].apply(
            lambda x: f"{farol_idade(x)} {x} dias" if x is not None else "⚪ —"
        )

    # ════════════════════════════════════════════════════════
    # PAINEL
    # ════════════════════════════════════════════════════════
    with sub_tabs[0]:
        col_r, _ = st.columns([1, 6])
        with col_r:
            if st.button("🔄 Atualizar", key="gv_refresh"):
                gv_carregar.clear()
                st.rerun()

        if not df_gv.empty and "status" in df_gv.columns:
            total       = len(df_gv)
            disponiveis = len(df_gv[df_gv["status"].str.contains("Disponível", na=False)])
            agendados   = len(df_gv[df_gv["status"] == "Agendado"])
            entregues   = len(df_gv[df_gv["status"] == "Entregue"])
            avariados   = len(df_gv[df_gv["status"] == "Avariado"])

            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("Total",       total)
            k2.metric("Disponíveis", disponiveis)
            k3.metric("Agendados",   agendados)
            k4.metric("Entregues",   entregues)
            k5.metric("Avariados",   avariados)

            # Legenda farol de idade
            st.caption("Farol de idade: 🟢 ≤20 dias · 🟡 ≤30 dias · 🔴 ≤45 dias · ⚫ >45 dias")
        else:
            st.info("Nenhum veículo cadastrado ainda.")

        st.divider()

        if not df_gv.empty:
            fc1, fc2, fc3, fc4 = st.columns(4)
            with fc1:
                fab_f = st.selectbox("Fabricante", ["Todos"] + sorted(df_gv["fabricante"].dropna().unique().tolist()) if "fabricante" in df_gv.columns else ["Todos"], key="gv_f_fab")
            with fc2:
                loc_f = st.selectbox("Locadora",   ["Todos"] + sorted(df_gv["locadora"].dropna().unique().tolist())   if "locadora"   in df_gv.columns else ["Todos"], key="gv_f_loc")
            with fc3:
                sta_f = st.selectbox("Status",     ["Todos"] + GV_STATUS_LIST, key="gv_f_sta")
            with fc4:
                con_f = st.selectbox("Consultor",  ["Todos"] + sorted(df_gv["consultor"].dropna().unique().tolist())  if "consultor"  in df_gv.columns else ["Todos"], key="gv_f_con")

            df_view = df_gv.copy()
            if fab_f != "Todos" and "fabricante" in df_view.columns:
                df_view = df_view[df_view["fabricante"] == fab_f]
            if loc_f != "Todos" and "locadora"   in df_view.columns:
                df_view = df_view[df_view["locadora"]   == loc_f]
            if sta_f != "Todos" and "status"     in df_view.columns:
                df_view = df_view[df_view["status"]     == sta_f]
            if con_f != "Todos" and "consultor"  in df_view.columns:
                df_view = df_view[df_view["consultor"]  == con_f]

            cols_vis = ["farol_idade", "fabricante", "modelo", "cor", "placa", "chassi",
                        "locadora", "consultor", "cliente", "status",
                        "local_atual", "data_chegada", "data_entrega", "loja_entrega"]
            if autenticado:
                cols_vis += ["valor_nf", "margem", "comissao"]

            cols_ex = [c for c in cols_vis if c in df_view.columns]
            st.markdown(f"**{len(df_view)} veículo(s)**")
            st.dataframe(df_view[cols_ex], width="stretch", hide_index=True)

            if autenticado:
                csv_exp = df_view.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Exportar CSV", data=csv_exp,
                    file_name="veiculos.csv", mime="text/csv")

    # ════════════════════════════════════════════════════════
    # CADASTRAR
    # ════════════════════════════════════════════════════════
    if autenticado:
        with sub_tabs[1]:
            st.subheader("➕ Cadastrar Veículo")
            modo = st.radio("Modo", ["Manual", "Importar Excel"], horizontal=True, key="gv_modo_cad")

            if modo == "Manual":
                with st.form("gv_form_cadastro"):
                    st.markdown("**Identificação**")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        fab  = st.selectbox("Fabricante *", GV_FABRICANTES)
                        mod  = st.text_input("Modelo *")
                        cor  = st.text_input("Cor *")
                    with c2:
                        chassi  = st.text_input("Chassi *")
                        placa   = st.text_input("Placa")
                        comb    = st.selectbox("Combustível", GV_COMBUSTIVEIS)
                    with c3:
                        ano_fab = st.text_input("Ano Fabricação")
                        ano_mod = st.text_input("Ano Modelo")
                        opc     = st.text_area("Opcionais", height=68)

                    st.markdown("**Operacional**")
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
                        avaria  = st.selectbox("Com Avaria?", ["Não", "Sim"])
                        obs_av  = st.text_area("Obs. Avaria", height=68)

                    st.markdown("**Financeiro**")
                    f1, f2, f3 = st.columns(3)
                    with f1:
                        valor_nf = st.number_input("Valor NF (R$)", min_value=0.0, step=100.0)
                    with f2:
                        margem   = st.number_input("Margem (%)",    min_value=0.0, step=0.1)
                    with f3:
                        comissao = st.number_input("Comissão (%)",  min_value=0.0, step=0.1)

                    if st.form_submit_button("💾 Cadastrar Veículo", use_container_width=True):
                        if not fab or not mod or not chassi:
                            st.error("Fabricante, Modelo e Chassi são obrigatórios.")
                        elif "chassi" in df_gv.columns and chassi.upper() in df_gv["chassi"].astype(str).str.upper().values:
                            st.error(f"⛔ Chassi `{chassi}` já existe na base! Chassi deve ser único.")
                        else:
                            agora_str  = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                            nova_linha = [
                                gv_novo_id(df_gv), fab, mod, chassi, placa, cor,
                                ano_fab, ano_mod, comb, opc,
                                loc, consultor_cad, cliente_cad, pedido, status_cad,
                                local_at,
                                data_ch.strftime("%d/%m/%Y") if data_ch else "",
                                "", "", "",
                                avaria, obs_av if avaria == "Sim" else "",
                                "", valor_nf, margem, comissao,
                                agora_str, agora_str, "Sistema"
                            ]
                            if gv_enviar({"aba": "veiculos", "acao": "inserir", "linha": nova_linha}):
                                gv_carregar.clear()
                                st.success("✅ Veículo cadastrado!")
                                st.rerun()

            else:
                st.info("Colunas reconhecidas (todas opcionais): FABRICANTE · MODELO · CHASSI · PLACA · COR · LOCADORA · STATUS · DATA CHEGADA · COM AVARIA? · LOCAL ATUAL")
                arquivo = st.file_uploader("Selecione o arquivo .xlsx", type=["xlsx"])
                if arquivo:
                    try:
                        df_imp = pd.read_excel(arquivo)
                        st.dataframe(df_imp.head(10), width="stretch")
                        st.caption(f"{len(df_imp)} linhas encontradas")

                        if st.button("📤 Importar todos", use_container_width=True, key="gv_btn_importar"):
                            agora_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                            chassis_existentes = set(df_gv["chassi"].astype(str).str.upper().tolist()) if "chassi" in df_gv.columns else set()
                            erros = 0
                            duplicados = []
                            for _, row in df_imp.iterrows():
                                def g(col):
                                    # Tenta variações do nome da coluna
                                    for tentativa in [col, col.upper(), col.lower(), col.title()]:
                                        v = row.get(tentativa, None)
                                        if v is not None and not (isinstance(v, float) and pd.isna(v)):
                                            return str(v).strip()
                                    return ""

                                dc = fmt_data(g("DATA CHEGADA")) or g("DATA CHEGADA")
                                chassi_imp = g("CHASSI").upper()

                                # Bloqueia chassi duplicado
                                if chassi_imp and chassi_imp in chassis_existentes:
                                    duplicados.append(chassi_imp)
                                    continue

                                if chassi_imp:
                                    chassis_existentes.add(chassi_imp)

                                nova_linha = [
                                    gv_novo_id(df_gv),   # id
                                    g("FABRICANTE"),      # fabricante
                                    g("MODELO"),          # modelo
                                    g("CHASSI"),          # chassi
                                    g("PLACA"),           # placa
                                    g("COR"),             # cor
                                    "",                   # ano_fabricacao
                                    "",                   # ano_modelo
                                    "",                   # combustivel
                                    "",                   # opcionais
                                    g("LOCADORA"),        # locadora
                                    "",                   # consultor
                                    "",                   # cliente
                                    "",                   # pedido
                                    g("STATUS") or "Trânsito Disponível",  # status
                                    g("LOCAL ATUAL"),     # local_atual
                                    dc,                   # data_chegada
                                    "",                   # data_entrega
                                    "",                   # hora_entrega
                                    "",                   # entregador
                                    g("COM AVARIA?") or "Não",  # avaria
                                    "",                   # obs_avaria
                                    "",                   # loja_entrega
                                    "",                   # valor_nf
                                    "",                   # margem
                                    "",                   # comissao
                                    agora_str,            # criado_em
                                    agora_str,            # atualizado_em
                                    "Importação"          # atualizado_por
                                ]
                                if not gv_enviar({"aba": "veiculos", "acao": "inserir", "linha": nova_linha}):
                                    erros += 1
                            gv_carregar.clear()
                            st.success(f"✅ {len(df_imp) - erros - len(duplicados)} importados!")
                            if duplicados:
                                st.warning(f"⛔ {len(duplicados)} chassis ignorados por já existirem na base: {', '.join(duplicados)}")
                            if erros:
                                st.error(f"{erros} erro(s) de envio.")
                    except Exception as e:
                        st.error(f"Erro ao ler arquivo: {e}")

    # ════════════════════════════════════════════════════════
    # EDITAR
    # ════════════════════════════════════════════════════════
    if autenticado:
        with sub_tabs[2]:
            st.subheader("✏️ Editar / Atualizar Veículo")

            if df_gv.empty:
                st.info("Nenhum veículo cadastrado.")
            else:
                modo_ed = st.radio("Modo", ["Individual", "Edição em Lote", "🗑️ Deletar Chassi"],
                    horizontal=True, key="gv_modo_ed")

                # ── INDIVIDUAL ───────────────────────────────────
                if modo_ed == "Individual":
                    busca = st.text_input("🔍 Buscar por Chassi, Placa, Cliente ou Modelo", key="gv_busca_edit")
                    df_busca = df_gv.copy()
                    if busca:
                        mask = pd.Series(False, index=df_busca.index)
                        for col in ["chassi", "placa", "cliente", "modelo", "fabricante", "consultor"]:
                            if col in df_busca.columns:
                                mask |= df_busca[col].astype(str).str.contains(busca, case=False, na=False)
                        df_busca = df_busca[mask]

                    if df_busca.empty:
                        st.warning("Nenhum resultado encontrado.")
                    else:
                        opcoes_edit = df_busca.apply(
                            lambda r: f"{r.get('chassi','?')} | {r.get('modelo','?')} | {r.get('status','?')}",
                            axis=1
                        ).tolist()
                        sel_idx = st.selectbox("Selecione o veículo", range(len(opcoes_edit)),
                            format_func=lambda i: opcoes_edit[i], key="gv_sel_edit")

                        vei = df_busca.iloc[sel_idx]

                        def gv_val(col, default=""):
                            v = vei.get(col, default)
                            return "" if pd.isna(v) else str(v)

                        idade_atual = calcular_idade(vei)
                        if idade_atual is not None:
                            st.info(f"{farol_idade(idade_atual)} Este veículo tem **{idade_atual} dias** no estoque.")

                        st.divider()
                        st.markdown(f"**Editando:** `{gv_val('chassi')}` — {gv_val('modelo')}")

                        with st.form("gv_form_edicao"):

                            st.markdown("**Identificação**")
                            id1, id2, id3, id4 = st.columns(4)
                            with id1:
                                e_fab = st.selectbox("Fabricante", GV_FABRICANTES,
                                    index=GV_FABRICANTES.index(gv_val("fabricante")) if gv_val("fabricante") in GV_FABRICANTES else 0)
                                e_modelo = st.text_input("Modelo", value=gv_val("modelo"))
                            with id2:
                                e_cor    = st.text_input("Cor",    value=gv_val("cor"))
                                e_placa  = st.text_input("Placa",  value=gv_val("placa"))
                            with id3:
                                e_ano_fab = st.text_input("Ano Fabricação", value=gv_val("ano_fabricacao"))
                                e_ano_mod = st.text_input("Ano Modelo",     value=gv_val("ano_modelo"))
                            with id4:
                                e_comb = st.selectbox("Combustível", GV_COMBUSTIVEIS,
                                    index=GV_COMBUSTIVEIS.index(gv_val("combustivel")) if gv_val("combustivel") in GV_COMBUSTIVEIS else 0)
                                e_opc  = st.text_area("Opcionais", value=gv_val("opcionais"), height=68)

                            st.markdown("**Operacional**")
                            e1, e2, e3 = st.columns(3)
                            with e1:
                                e_status = st.selectbox("Status", GV_STATUS_LIST,
                                    index=GV_STATUS_LIST.index(gv_val("status")) if gv_val("status") in GV_STATUS_LIST else 0)
                                e_loc = st.selectbox("Locadora", GV_LOCADORAS,
                                    index=GV_LOCADORAS.index(gv_val("locadora")) if gv_val("locadora") in GV_LOCADORAS else 0)
                                e_consultor = st.text_input("Consultor", value=gv_val("consultor"))
                            with e2:
                                e_cliente    = st.text_input("Cliente",     value=gv_val("cliente"))
                                e_pedido     = st.text_input("Nº Pedido",   value=gv_val("pedido"))
                                e_local      = st.text_input("Local Atual", value=gv_val("local_atual"))
                            with e3:
                                e_loja = st.selectbox("Loja de Entrega", [""] + GV_LOJAS,
                                    index=([""] + GV_LOJAS).index(gv_val("loja_entrega")) if gv_val("loja_entrega") in GV_LOJAS else 0)
                                e_entregador = st.text_input("Entregador", value=gv_val("entregador"))
                                e_avaria     = st.selectbox("Com Avaria?", ["Não", "Sim"],
                                    index=1 if gv_val("avaria") == "Sim" else 0)

                            e_obs_av = st.text_area("Obs. Avaria", value=gv_val("obs_avaria"), height=60)

                            st.markdown("**Datas**")
                            d1, d2, d3 = st.columns(3)
                            with d1:
                                e_data_ch  = st.date_input("Data Chegada", value=parse_data(gv_val("data_chegada")))
                            with d2:
                                e_data_ent = st.date_input("Data Entrega", value=parse_data(gv_val("data_entrega")))
                            with d3:
                                hora_str = gv_val("hora_entrega")
                                try:
                                    h, m = map(int, hora_str.split(":"))
                                    hora_val = datetime.time(h, m)
                                except Exception:
                                    hora_val = datetime.time(10, 0)
                                e_hora_ent = st.time_input("Hora Entrega", value=hora_val)

                            st.markdown("**Financeiro**")
                            fi1, fi2, fi3 = st.columns(3)
                            with fi1:
                                e_nf = st.number_input("Valor NF (R$)", value=float(gv_val("valor_nf") or 0), step=100.0)
                            with fi2:
                                e_mg = st.number_input("Margem (%)",    value=float(gv_val("margem")   or 0), step=0.1)
                            with fi3:
                                e_cm = st.number_input("Comissão (%)",  value=float(gv_val("comissao") or 0), step=0.1)

                            if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                                agora_str  = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                                linha_atual = [
                                    gv_val("id"), e_fab, e_modelo,
                                    gv_val("chassi"), e_placa, e_cor,
                                    e_ano_fab, e_ano_mod, e_comb, e_opc,
                                    e_loc, e_consultor, e_cliente, e_pedido,
                                    e_status, e_local,
                                    e_data_ch.strftime("%d/%m/%Y")  if e_data_ch  else gv_val("data_chegada"),
                                    e_data_ent.strftime("%d/%m/%Y") if e_data_ent else gv_val("data_entrega"),
                                    e_hora_ent.strftime("%H:%M"),
                                    e_entregador,
                                    e_avaria, e_obs_av if e_avaria == "Sim" else "",
                                    e_loja, e_nf, e_mg, e_cm,
                                    gv_val("criado_em"), agora_str, "Editor"
                                ]
                                linha_num = int(df_busca.index[sel_idx]) + 2
                                ok = gv_enviar({
                                    "aba": "veiculos", "acao": "atualizar_linha",
                                    "linha_num": linha_num,
                                    "valores": [{"col": i+1, "valor": v} for i, v in enumerate(linha_atual)]
                                })
                                gv_enviar({"aba": "historico", "acao": "inserir", "linha": [
                                    gv_val("id"), gv_val("chassi"), gv_val("modelo"),
                                    gv_val("status"), e_status, agora_str, "Editor"
                                ]})
                                if ok:
                                    gv_carregar.clear()
                                    if e_status in ["Agendado", "Entregue"] and e_data_ent:
                                        data_fmt = e_data_ent.strftime("%d/%m/%Y")
                                        hora_fmt = e_hora_ent.strftime("%H:%M")
                                        assunto  = f"[Carrera Signature] {e_status} — {e_modelo}"
                                        corpo    = (f"Veículo: {e_modelo}%0A"
                                                    f"Chassi: {gv_val('chassi')}%0A"
                                                    f"Cliente: {e_cliente}%0A"
                                                    f"Status: {e_status}%0A"
                                                    f"Data: {data_fmt} às {hora_fmt}%0A"
                                                    f"Local: {e_loja}")
                                        st.markdown(f"📧 [Enviar notificação por email](mailto:?subject={assunto}&body={corpo})")
                                    st.success("✅ Veículo atualizado!")
                                    st.rerun()

                # ── EDIÇÃO EM LOTE ───────────────────────────────
                elif modo_ed == "Edição em Lote":
                    st.info("Filtre os veículos e aplique uma alteração de campo para todos de uma vez.")

                    # Filtros completos
                    lf1, lf2, lf3, lf4 = st.columns(4)
                    with lf1:
                        lote_sta = st.selectbox("Status", ["Todos"] + GV_STATUS_LIST, key="lote_sta")
                    with lf2:
                        lote_fab = st.selectbox("Fabricante",
                            ["Todos"] + sorted(df_gv["fabricante"].dropna().unique().tolist()) if "fabricante" in df_gv.columns else ["Todos"],
                            key="lote_fab")
                    with lf3:
                        lote_loc = st.selectbox("Locadora",
                            ["Todos"] + sorted(df_gv["locadora"].dropna().unique().tolist()) if "locadora" in df_gv.columns else ["Todos"],
                            key="lote_loc")
                    with lf4:
                        lote_con = st.selectbox("Consultor",
                            ["Todos"] + sorted(df_gv["consultor"].dropna().unique().tolist()) if "consultor" in df_gv.columns else ["Todos"],
                            key="lote_con")

                    lf5, lf6 = st.columns(2)
                    with lf5:
                        lote_local = st.selectbox("Local Atual",
                            ["Todos"] + sorted(df_gv["local_atual"].dropna().unique().tolist()) if "local_atual" in df_gv.columns else ["Todos"],
                            key="lote_local")
                    with lf6:
                        lote_loja = st.selectbox("Loja de Entrega",
                            ["Todos"] + GV_LOJAS, key="lote_loja")

                    df_lote = df_gv.copy()
                    if lote_sta   != "Todos" and "status"       in df_lote.columns: df_lote = df_lote[df_lote["status"]       == lote_sta]
                    if lote_fab   != "Todos" and "fabricante"   in df_lote.columns: df_lote = df_lote[df_lote["fabricante"]   == lote_fab]
                    if lote_loc   != "Todos" and "locadora"     in df_lote.columns: df_lote = df_lote[df_lote["locadora"]     == lote_loc]
                    if lote_con   != "Todos" and "consultor"    in df_lote.columns: df_lote = df_lote[df_lote["consultor"]    == lote_con]
                    if lote_local != "Todos" and "local_atual"  in df_lote.columns: df_lote = df_lote[df_lote["local_atual"]  == lote_local]
                    if lote_loja  != "Todos" and "loja_entrega" in df_lote.columns: df_lote = df_lote[df_lote["loja_entrega"] == lote_loja]

                    if df_lote.empty:
                        st.warning("Nenhum veículo encontrado com esses filtros.")
                    else:
                        cols_lote = [c for c in ["chassi", "modelo", "fabricante", "cor", "status",
                                                  "consultor", "locadora", "local_atual", "loja_entrega",
                                                  "data_chegada", "data_entrega"] if c in df_lote.columns]
                        st.markdown(f"**{len(df_lote)} veículo(s) selecionado(s)**")
                        st.dataframe(df_lote[cols_lote], width="stretch", hide_index=True)

                        st.divider()
                        st.markdown("**Aplicar alteração em lote:**")

                        # Todos os campos editáveis em lote
                        CAMPOS_LOTE = {
                            "status":       ("selectbox", GV_STATUS_LIST),
                            "fabricante":   ("selectbox", GV_FABRICANTES),
                            "locadora":     ("selectbox", GV_LOCADORAS),
                            "loja_entrega": ("selectbox", GV_LOJAS),
                            "combustivel":  ("selectbox", GV_COMBUSTIVEIS),
                            "avaria":       ("selectbox", ["Não", "Sim"]),
                            "consultor":    ("text", None),
                            "cliente":      ("text", None),
                            "local_atual":  ("text", None),
                            "entregador":   ("text", None),
                            "modelo":       ("text", None),
                            "cor":          ("text", None),
                            "ano_fabricacao": ("text", None),
                            "ano_modelo":   ("text", None),
                            "data_chegada": ("date", None),
                            "data_entrega": ("date", None),
                            "hora_entrega": ("time", None),
                            "valor_nf":     ("number", None),
                            "margem":       ("number", None),
                            "comissao":     ("number", None),
                            "obs_avaria":   ("text", None),
                            "pedido":       ("text", None),
                        }

                        lt1, lt2 = st.columns(2)
                        with lt1:
                            campo_lote = st.selectbox("Campo a alterar", list(CAMPOS_LOTE.keys()), key="lote_campo")

                        tipo, opcoes = CAMPOS_LOTE[campo_lote]
                        with lt2:
                            if tipo == "selectbox":
                                valor_lote_raw = st.selectbox("Novo valor", opcoes, key="lote_val")
                                valor_lote = valor_lote_raw
                            elif tipo == "date":
                                valor_lote_raw = st.date_input("Novo valor", value=None, key="lote_val_date")
                                valor_lote = valor_lote_raw.strftime("%d/%m/%Y") if valor_lote_raw else ""
                            elif tipo == "time":
                                valor_lote_raw = st.time_input("Novo valor", value=datetime.time(10, 0), key="lote_val_time")
                                valor_lote = valor_lote_raw.strftime("%H:%M")
                            elif tipo == "number":
                                valor_lote_raw = st.number_input("Novo valor", min_value=0.0, step=0.1, key="lote_val_num")
                                valor_lote = valor_lote_raw
                            else:
                                valor_lote = st.text_input("Novo valor", key="lote_val_txt")

                        col_idx = GV_COLUNAS.index(campo_lote) + 1 if campo_lote in GV_COLUNAS else None

                        if col_idx and st.button(
                                f"✅ Aplicar em {len(df_lote)} veículo(s)",
                                use_container_width=True, key="btn_lote_aplicar"):
                            agora_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                            erros = 0
                            for idx in df_lote.index:
                                linha_num = int(idx) + 2
                                ok = gv_enviar({
                                    "aba": "veiculos", "acao": "atualizar_linha",
                                    "linha_num": linha_num,
                                    "valores": [
                                        {"col": col_idx, "valor": valor_lote},
                                        {"col": GV_COLUNAS.index("atualizado_em") + 1,  "valor": agora_str},
                                        {"col": GV_COLUNAS.index("atualizado_por") + 1, "valor": "Lote"}
                                    ]
                                })
                                if not ok:
                                    erros += 1
                            gv_carregar.clear()
                            if erros == 0:
                                st.success(f"✅ {len(df_lote)} veículos atualizados!")
                            else:
                                st.warning(f"Concluído com {erros} erros.")
                            st.rerun()

                # ── DELETAR CHASSI ───────────────────────────────
                elif modo_ed == "🗑️ Deletar Chassi":
                    st.warning("⚠️ Esta ação remove permanentemente o veículo da planilha. Use com cuidado.")

                    chassi_del = st.text_input("Digite o Chassi a deletar", key="gv_chassi_del").strip().upper()

                    if chassi_del:
                        match = df_gv[df_gv["chassi"].astype(str).str.upper() == chassi_del]

                        if match.empty:
                            st.error(f"Chassi `{chassi_del}` não encontrado.")
                        else:
                            vei_del = match.iloc[0]
                            st.info(f"**{vei_del.get('modelo','?')}** | {vei_del.get('fabricante','?')} | Status: {vei_del.get('status','?')} | Chegada: {vei_del.get('data_chegada','?')}")

                            if "gv_confirmar_delete" not in st.session_state:
                                st.session_state["gv_confirmar_delete"] = False

                            if not st.session_state["gv_confirmar_delete"]:
                                if st.button("🗑️ Confirmar exclusão", use_container_width=True, key="btn_del_confirmar", type="primary"):
                                    st.session_state["gv_confirmar_delete"] = True
                                    st.rerun()
                            else:
                                st.error("Tem certeza? Esta ação não pode ser desfeita.")
                                cd1, cd2 = st.columns(2)
                                with cd1:
                                    if st.button("✅ Sim, deletar", use_container_width=True, key="btn_del_sim"):
                                        linha_num = int(match.index[0]) + 2
                                        ok = gv_enviar({
                                            "aba": "veiculos", "acao": "deletar_linha",
                                            "linha_num": linha_num
                                        })
                                        gv_enviar({"aba": "historico", "acao": "inserir", "linha": [
                                            str(vei_del.get("id", "")),
                                            chassi_del,
                                            str(vei_del.get("modelo", "")),
                                            str(vei_del.get("status", "")),
                                            "DELETADO",
                                            datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                                            "Editor"
                                        ]})
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
    idx_ag = 3 if autenticado else 1
    with sub_tabs[idx_ag]:
        st.subheader("📅 Agendamentos")
        st.caption("Farol: 🟡 Agendado (no prazo) · 🔴 Atrasado (hora passou, não entregue) · 🟢 Entregue")

        if df_gv.empty or "status" not in df_gv.columns:
            st.info("Nenhum dado disponível.")
        else:
            ag_modo = st.radio("Visualização", ["📆 Por Dia", "📋 Todos os Agendamentos", "➕ Agendar Veículo"],
                horizontal=True, key="ag_modo")

            hoje = datetime.date.today()

            # ── POR DIA ─────────────────────────────────────
            if ag_modo == "📆 Por Dia":
                st.markdown("**Filtros**")
                fd1, fd2, fd3, fd4 = st.columns(4)
                with fd1:
                    data_filtro = st.date_input("Data", value=hoje, key="ag_data_filtro")
                with fd2:
                    loja_filtro = st.selectbox("Loja de Entrega", ["Todas"] + GV_LOJAS, key="ag_loja_filtro")
                with fd3:
                    entregador_opts = ["Todos"] + sorted(df_gv["entregador"].dropna().unique().tolist()) if "entregador" in df_gv.columns else ["Todos"]
                    entregador_filtro = st.selectbox("Entregador", entregador_opts, key="ag_entregador_filtro")
                with fd4:
                    consultor_opts = ["Todos"] + sorted(df_gv["consultor"].dropna().unique().tolist()) if "consultor" in df_gv.columns else ["Todos"]
                    consultor_filtro = st.selectbox("Consultor", consultor_opts, key="ag_consultor_filtro")

                data_str = data_filtro.strftime("%d/%m/%Y")
                df_dia = df_gv[
                    (df_gv["status"].isin(["Agendado", "Entregue", "Reagendar"])) &
                    (df_gv["data_entrega"].astype(str) == data_str)
                ].copy()

                if loja_filtro != "Todas" and "loja_entrega" in df_dia.columns:
                    df_dia = df_dia[df_dia["loja_entrega"] == loja_filtro]
                if entregador_filtro != "Todos" and "entregador" in df_dia.columns:
                    df_dia = df_dia[df_dia["entregador"] == entregador_filtro]
                if consultor_filtro != "Todos" and "consultor" in df_dia.columns:
                    df_dia = df_dia[df_dia["consultor"] == consultor_filtro]

                st.divider()

                if df_dia.empty:
                    st.info(f"Nenhum agendamento para {data_str}.")
                else:
                    df_dia["farol_ag"] = df_dia.apply(farol_agendamento, axis=1)

                    # KPIs do dia
                    kd1, kd2, kd3, kd4 = st.columns(4)
                    kd1.metric("Total do dia",   len(df_dia))
                    kd2.metric("🟡 Agendados",   len(df_dia[df_dia["farol_ag"].str.startswith("🟡")]))
                    kd3.metric("🔴 Atrasados",   len(df_dia[df_dia["farol_ag"].str.startswith("🔴")]))
                    kd4.metric("🟢 Entregues",   len(df_dia[df_dia["farol_ag"].str.startswith("🟢")]))

                    st.divider()

                    # Ordena por hora
                    df_dia = df_dia.sort_values("hora_entrega", na_position="last")

                    cols_dia = ["farol_ag", "hora_entrega", "modelo", "fabricante", "cor", "placa",
                                "cliente", "consultor", "loja_entrega", "entregador", "status", "farol_idade"]
                    cols_dia_ex = [c for c in cols_dia if c in df_dia.columns]
                    st.markdown(f"**{len(df_dia)} entrega(s) em {data_str}**")
                    st.dataframe(df_dia[cols_dia_ex], width="stretch", hide_index=True)

            # ── TODOS OS AGENDAMENTOS ────────────────────────
            elif ag_modo == "📋 Todos os Agendamentos":
                st.markdown("**Filtros**")
                ta1, ta2, ta3 = st.columns(3)
                with ta1:
                    loja_f2 = st.selectbox("Loja de Entrega", ["Todas"] + GV_LOJAS, key="ag_loja_f2")
                with ta2:
                    entregador_opts2 = ["Todos"] + sorted(df_gv["entregador"].dropna().unique().tolist()) if "entregador" in df_gv.columns else ["Todos"]
                    entregador_f2 = st.selectbox("Entregador", entregador_opts2, key="ag_ent_f2")
                with ta3:
                    farol_f2 = st.selectbox("Farol", ["Todos", "🟡 Agendado", "🔴 Atrasado", "🟢 Entregue"], key="ag_farol_f2")

                df_todos = df_gv[df_gv["status"].isin(["Agendado", "Reagendar", "Entregue"])].copy()
                df_todos["farol_ag"] = df_todos.apply(farol_agendamento, axis=1)

                if loja_f2 != "Todas" and "loja_entrega" in df_todos.columns:
                    df_todos = df_todos[df_todos["loja_entrega"] == loja_f2]
                if entregador_f2 != "Todos" and "entregador" in df_todos.columns:
                    df_todos = df_todos[df_todos["entregador"] == entregador_f2]
                if farol_f2 != "Todos":
                    df_todos = df_todos[df_todos["farol_ag"].str.startswith(farol_f2[:2])]

                st.divider()

                if df_todos.empty:
                    st.info("Nenhum agendamento encontrado.")
                else:
                    # KPIs gerais
                    kt1, kt2, kt3 = st.columns(3)
                    kt1.metric("🟡 Agendados", len(df_todos[df_todos["farol_ag"].str.startswith("🟡")]))
                    kt2.metric("🔴 Atrasados", len(df_todos[df_todos["farol_ag"].str.startswith("🔴")]))
                    kt3.metric("🟢 Entregues", len(df_todos[df_todos["farol_ag"].str.startswith("🟢")]))

                    st.divider()
                    df_todos = df_todos.sort_values(["data_entrega", "hora_entrega"], na_position="last")
                    cols_todos = ["farol_ag", "data_entrega", "hora_entrega", "modelo", "fabricante",
                                  "cor", "placa", "cliente", "consultor",
                                  "loja_entrega", "entregador", "status", "farol_idade"]
                    cols_todos_ex = [c for c in cols_todos if c in df_todos.columns]
                    st.markdown(f"**{len(df_todos)} agendamento(s)**")
                    st.dataframe(df_todos[cols_todos_ex], width="stretch", hide_index=True)

            # ── AGENDAR VEÍCULO ──────────────────────────────
            elif ag_modo == "➕ Agendar Veículo":

                # ── Regras de negócio ────────────────────────
                SENHA_FECHAMENTO = "#FECHAMENTO"

                # Rodízio SP: final da placa → dia da semana (0=seg...4=sex)
                RODIZIO_SP = {
                    "1": 0, "2": 0,  # Segunda
                    "3": 1, "4": 1,  # Terça
                    "5": 2, "6": 2,  # Quarta
                    "7": 3, "8": 3,  # Quinta
                    "9": 4, "0": 4,  # Sexta
                }
                # Rodízio bloqueia 07:00–10:00 e 17:00–20:00 (+ 1h antes = 06:00 e 16:00)
                RODIZIO_BLOQUEIO = [
                    (datetime.time(6, 0),  datetime.time(10, 0)),
                    (datetime.time(16, 0), datetime.time(20, 0)),
                ]

                def verificar_rodizio(placa: str, data: datetime.date, hora: datetime.time) -> str | None:
                    """Retorna mensagem de erro se a entrega cair no rodízio, None se ok."""
                    if not placa or len(placa) < 1:
                        return None
                    final = placa.strip()[-1].upper()
                    if final not in RODIZIO_SP:
                        return None
                    dia_rodizio = RODIZIO_SP[final]
                    if data.weekday() != dia_rodizio:
                        return None
                    dias_semana = ["segunda", "terça", "quarta", "quinta", "sexta"]
                    for inicio, fim in RODIZIO_BLOQUEIO:
                        if inicio <= hora < fim:
                            return (f"🚫 Rodízio: placa final **{final}** tem restrição na "
                                    f"**{dias_semana[dia_rodizio]}** entre "
                                    f"{inicio.strftime('%H:%M')} e {fim.strftime('%H:%M')} "
                                    f"(incluindo 1h antes). Escolha outro horário.")
                    return None

                def verificar_conflito_loja(df: pd.DataFrame, data: datetime.date,
                                            hora: datetime.time, loja: str,
                                            excluir_idx: int = -1) -> str | None:
                    """Retorna mensagem de erro se já existe agendamento na mesma loja/hora/data."""
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
                    conflitos = df[mask]
                    if not conflitos.empty:
                        vei_conf = conflitos.iloc[0]
                        return (f"🚫 Conflito: já existe agendamento em **{loja}** no dia "
                                f"**{data_str} às {hora_str}** — "
                                f"{vei_conf.get('modelo','?')} | {vei_conf.get('cliente','?')}. "
                                f"Escolha outro horário.")
                    return None

                # ── Lista de espera ──────────────────────────
                df_aguardando = df_gv[df_gv["status"].isin([
                    "Aguardando Agendamento", "Aguardando Atribuição", "Reagendar", "Disponível"
                ])].copy()

                if df_aguardando.empty:
                    st.info("Nenhum veículo aguardando agendamento.")
                else:
                    # Resumo por status
                    sa1, sa2, sa3, sa4 = st.columns(4)
                    sa1.metric("Total aguardando", len(df_aguardando))
                    sa2.metric("Ag. Agendamento",  len(df_aguardando[df_aguardando["status"] == "Aguardando Agendamento"]))
                    sa3.metric("Reagendar",         len(df_aguardando[df_aguardando["status"] == "Reagendar"]))
                    sa4.metric("Disponível",        len(df_aguardando[df_aguardando["status"] == "Disponível"]))

                    st.divider()

                    cols_aw = ["fabricante", "modelo", "cor", "placa", "chassi",
                               "cliente", "consultor", "status", "farol_idade"]
                    cols_aw_ex = [c for c in cols_aw if c in df_aguardando.columns]
                    st.dataframe(df_aguardando[cols_aw_ex], width="stretch", hide_index=True)

                    st.divider()
                    st.markdown("### 📅 Novo Agendamento")

                    # Seleção do veículo
                    opcoes_aw = df_aguardando.apply(
                        lambda r: f"{r.get('chassi','?')} | {r.get('modelo','?')} | {r.get('cliente','—')} | {r.get('status','?')}",
                        axis=1
                    ).tolist()
                    sel_aw = st.selectbox("Selecione o veículo", range(len(opcoes_aw)),
                        format_func=lambda i: opcoes_aw[i], key="ag_sel_vei")

                    vei_aw   = df_aguardando.iloc[sel_aw]
                    idx_real = df_aguardando.index[sel_aw]

                    def gv_val_aw(col, default=""):
                        v = vei_aw.get(col, default)
                        return "" if pd.isna(v) else str(v)

                    placa_vei = gv_val_aw("placa")

                    # Card resumo
                    st.info(
                        f"🚗 **{gv_val_aw('modelo')}** | {gv_val_aw('fabricante')} | "
                        f"Cor: {gv_val_aw('cor')} | Placa: **{placa_vei}** | "
                        f"Cliente: {gv_val_aw('cliente')} | Consultor: {gv_val_aw('consultor')}"
                    )

                    # Formulário de agendamento
                    with st.form("form_agendar"):
                        ag1, ag2, ag3 = st.columns(3)
                        with ag1:
                            nova_data = st.date_input("📅 Data de Entrega *", value=hoje)
                        with ag2:
                            nova_hora = st.time_input("🕐 Hora de Entrega *", value=datetime.time(10, 0))
                        with ag3:
                            nova_loja = st.selectbox("🏢 Loja de Entrega *", GV_LOJAS)

                        ag4, ag5 = st.columns(2)
                        with ag4:
                            novo_entregador = st.text_input("Entregador", value=gv_val_aw("entregador"))
                        with ag5:
                            novo_consultor = st.text_input("Consultor", value=gv_val_aw("consultor"))

                        confirmar = st.form_submit_button("📅 Confirmar Agendamento", use_container_width=True)

                    # Validações FORA do form (Streamlit não permite widgets dentro de form após submit)
                    if confirmar:
                        erros_ag = []

                        # 1. Rodízio
                        err_rod = verificar_rodizio(placa_vei, nova_data, nova_hora)
                        if err_rod:
                            erros_ag.append(err_rod)

                        # 2. Conflito de horário na loja
                        err_conf = verificar_conflito_loja(df_gv, nova_data, nova_hora, nova_loja, excluir_idx=idx_real)
                        if err_conf:
                            erros_ag.append(err_conf)

                        if erros_ag:
                            for err in erros_ag:
                                st.error(err)

                            # Permite forçar com senha #FECHAMENTO
                            st.warning("Para forçar o agendamento mesmo assim, insira a senha de fechamento:")
                            senha_forca = st.text_input("Senha de fechamento", type="password", key="ag_senha_forca")
                            if st.button("🔓 Forçar agendamento", key="btn_forcar_ag", use_container_width=True):
                                if senha_forca == SENHA_FECHAMENTO:
                                    st.session_state["ag_forcar"] = True
                                    st.rerun()
                                else:
                                    st.error("Senha incorreta.")
                        else:
                            st.session_state["ag_forcar"] = True

                    # Executa o agendamento quando aprovado
                    if st.session_state.get("ag_forcar"):
                        st.session_state["ag_forcar"] = False
                        agora_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                        linha_num = int(idx_real) + 2
                        ok = gv_enviar({
                            "aba": "veiculos", "acao": "atualizar_linha",
                            "linha_num": linha_num,
                            "valores": [
                                {"col": GV_COLUNAS.index("status")         + 1, "valor": "Agendado"},
                                {"col": GV_COLUNAS.index("data_entrega")   + 1, "valor": nova_data.strftime("%d/%m/%Y")},
                                {"col": GV_COLUNAS.index("hora_entrega")   + 1, "valor": nova_hora.strftime("%H:%M")},
                                {"col": GV_COLUNAS.index("loja_entrega")   + 1, "valor": nova_loja},
                                {"col": GV_COLUNAS.index("entregador")     + 1, "valor": novo_entregador},
                                {"col": GV_COLUNAS.index("consultor")      + 1, "valor": novo_consultor},
                                {"col": GV_COLUNAS.index("atualizado_em")  + 1, "valor": agora_str},
                                {"col": GV_COLUNAS.index("atualizado_por") + 1, "valor": "Agendamento"},
                            ]
                        })
                        gv_enviar({"aba": "historico", "acao": "inserir", "linha": [
                            gv_val_aw("id"), gv_val_aw("chassi"), gv_val_aw("modelo"),
                            gv_val_aw("status"), "Agendado", agora_str, "Agendamento"
                        ]})
                        if ok:
                            gv_carregar.clear()
                            data_fmt = nova_data.strftime("%d/%m/%Y")
                            hora_fmt = nova_hora.strftime("%H:%M")
                            assunto  = f"[Carrera Signature] Agendado — {gv_val_aw('modelo')}"
                            corpo    = (f"Veículo: {gv_val_aw('modelo')}%0A"
                                        f"Chassi: {gv_val_aw('chassi')}%0A"
                                        f"Cliente: {gv_val_aw('cliente')}%0A"
                                        f"Data: {data_fmt} às {hora_fmt}%0A"
                                        f"Local: {nova_loja}%0A"
                                        f"Entregador: {novo_entregador}")
                            st.success(f"✅ Agendado para {data_fmt} às {hora_fmt} em {nova_loja}!")
                            st.markdown(f"📧 [Enviar notificação por email](mailto:?subject={assunto}&body={corpo})")
                            st.rerun()

    # ════════════════════════════════════════════════════════
    # RELATÓRIOS
    # ════════════════════════════════════════════════════════
    idx_rel = 4 if autenticado else 2
    with sub_tabs[idx_rel]:
        st.subheader("📊 Relatórios")

        if df_gv.empty:
            st.info("Nenhum dado disponível.")
        else:
            r1, r2 = st.columns(2)
            with r1:
                st.markdown("**Veículos por Status**")
                if "status" in df_gv.columns:
                    st.bar_chart(df_gv["status"].value_counts())
            with r2:
                st.markdown("**Veículos por Fabricante**")
                if "fabricante" in df_gv.columns:
                    st.bar_chart(df_gv["fabricante"].value_counts())

            st.divider()
            st.markdown("**Veículos por Locadora**")
            if "locadora" in df_gv.columns:
                st.bar_chart(df_gv["locadora"].value_counts())

            # TME — Tempo Médio de Estoque
            if "idade_dias" in df_gv.columns:
                st.divider()
                st.markdown("**⏱ Tempo Médio de Estoque (TME)**")
                df_tme = df_gv[df_gv["idade_dias"].notna()].copy()
                if not df_tme.empty:
                    tme1, tme2, tme3 = st.columns(3)
                    tme1.metric("TME Geral",   f"{df_tme['idade_dias'].mean():.0f} dias")
                    tme2.metric("Máximo",      f"{df_tme['idade_dias'].max():.0f} dias")
                    tme3.metric("Em estoque",  len(df_tme[df_tme["status"] != "Entregue"]))

                    if "fabricante" in df_tme.columns:
                        st.markdown("TME por Fabricante")
                        tme_fab = df_tme.groupby("fabricante")["idade_dias"].mean().sort_values(ascending=False)
                        st.bar_chart(tme_fab)

            if autenticado and "valor_nf" in df_gv.columns:
                st.divider()
                st.markdown("**💰 Financeiro**")
                df_fin = df_gv.copy()
                df_fin["valor_nf"] = pd.to_numeric(df_fin["valor_nf"], errors="coerce")
                df_fin = df_fin[df_fin["valor_nf"] > 0]
                if not df_fin.empty:
                    fr1, fr2, fr3 = st.columns(3)
                    fr1.metric("Total NF",       f"R$ {df_fin['valor_nf'].sum():,.0f}".replace(",", "."))
                    fr2.metric("Média NF",       f"R$ {df_fin['valor_nf'].mean():,.0f}".replace(",", "."))
                    fr3.metric("Veículos c/ NF", len(df_fin))
