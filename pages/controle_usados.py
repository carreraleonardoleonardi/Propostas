# =========================================================
# pages/controle_usados.py
# =========================================================
import streamlit as st
import pandas as pd
import requests
import json
import datetime

CU_SHEET_URL = "https://docs.google.com/spreadsheets/d/1MlwQlLIEPfyPIgKJ-s7H5oSpBVWlf3SIRiESBxe82es/export?format=csv&gid=0"
CU_WEBHOOK   = "https://script.google.com/macros/s/AKfycbzoPBsA5OAqewzEo9GdTZSXC804jodankRokulGTb6FTqPwL1v1Hv2qA-6OdvxFGxCXVA/exec"

CU_COLUNAS = ["data_entrada","data_saida","locadora","local","marca","modelo","placa","chassi","cor","km","vex"]

CU_LOCADORAS = ["LM FROTAS","GM Fleet","RCI","TOOT","OUTRO"]
CU_LOCAIS    = ["LOJA ALPHAVILLE","LOJA VILLA LOBOS","LOJA OSASCO","LOJA BUTANTÃ","LOJA COTIA","OUTRO DN"]
CU_MARCAS    = ["Volkswagen","Chevrolet","Nissan","Jeep","GWM","GAC","Omoda", "Renault","Hyundai","Toyota","Fiat","Ford","Honda","Citroën","Peugeot","Mitsubishi","Subaru","Chery","JAC","Lexus","Kia","Dodge","BMW","Mercedes-Benz","Audi","Porsche","Volvo","Mini","Land Rover","Jaguar","Alfa Romeo","Aston Martin","Bentley","Rolls-Royce","McLaren","Pagani","Bugatti","Koenigsegg","Zeekr","BYD","Leapmotor"]


@st.cache_data(ttl=60)
def cu_carregar() -> pd.DataFrame:
    try:
        df = pd.read_csv(CU_SHEET_URL, header=0)
        df.columns = [c.strip().lower().replace(" ","_") for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame(columns=CU_COLUNAS)


def cu_enviar(payload: dict) -> bool:
    try:
        requests.post(CU_WEBHOOK, data=json.dumps(payload),
            headers={"Content-Type":"text/plain"}, timeout=30)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False


def cu_val(row, col, default="") -> str:
    v = row.get(col, default)
    s = str(v).strip()
    if s in ("","nan","None","NaT"): return ""
    if s.endswith(".0") and s[:-2].lstrip("-").isdigit(): return s[:-2]
    return s


def render():
    st.title("🚙 Controle de Usados")

    is_staff = st.session_state.get("auth_tipo","") == "Staff"

    # Sub-abas
    if is_staff:
        sub = st.tabs(["📋 Painel", "➕ Receber Veículo", "✏️ Editar / Saída"])
    else:
        sub = st.tabs(["📋 Painel", "➕ Receber Veículo"])

    df = cu_carregar()

    # ════════════════════════════════════════════════════
    # PAINEL
    # ════════════════════════════════════════════════════
    with sub[0]:
        cr, _ = st.columns([1, 8])
        with cr:
            if st.button("🔄", key="cu_refresh"):
                cu_carregar.clear(); st.rerun()

        if df.empty:
            st.info("Nenhum veículo cadastrado ainda.")
        else:
            # KPIs
            total   = len(df)
            em_pat  = len(df[df["data_saida"].isna() | (df["data_saida"].astype(str).str.strip().isin(["","nan","None","NaT"]))])
            saidos  = total - em_pat

            k1, k2, k3 = st.columns(3)
            k1.metric("Total",        total)
            k2.metric("No Pátio",     em_pat)
            k3.metric("Retirados",       saidos)

            st.divider()

            # Filtros
            fl1, fl2, fl3 = st.columns(3)
            with fl1:
                flt_sit = st.selectbox("Situação", ["Todos","No Pátio","Retirados"], key="cu_flt_sit")
            with fl2:
                marcas_opts = ["Todas"] + sorted(df["marca"].dropna().unique().tolist()) if "marca" in df.columns else ["Todas"]
                flt_mar = st.selectbox("Marca", marcas_opts, key="cu_flt_mar")
            with fl3:
                local_opts = ["Todos"] + sorted(df["local"].dropna().unique().tolist()) if "local" in df.columns else ["Todos"]
                flt_loc = st.selectbox("Local", local_opts, key="cu_flt_loc")

            b1, b2 = st.columns(2)
            with b1: busca_placa  = st.text_input("🪪 Placa",  placeholder="Ex: Placa", key="cu_b_placa")
            with b2: busca_chassi = st.text_input("🔑 Chassi", placeholder="Ex: Chassi",  key="cu_b_chassi")

            df_view = df.copy()

            if flt_sit == "No Pátio":
                df_view = df_view[df_view["data_saida"].isna() | (df_view["data_saida"].astype(str).str.strip().isin(["","nan","None","NaT"]))]
            elif flt_sit == "Retirados":
                df_view = df_view[~(df_view["data_saida"].isna() | (df_view["data_saida"].astype(str).str.strip().isin(["","nan","None","NaT"])))]

            if flt_mar != "Todas" and "marca" in df_view.columns:
                df_view = df_view[df_view["marca"] == flt_mar]
            if flt_loc != "Todos" and "local" in df_view.columns:
                df_view = df_view[df_view["local"] == flt_loc]
            if busca_placa and "placa" in df_view.columns:
                df_view = df_view[df_view["placa"].astype(str).str.lower().str.contains(busca_placa.strip().lower(), na=False)]
            if busca_chassi and "chassi" in df_view.columns:
                df_view = df_view[df_view["chassi"].astype(str).str.lower().str.contains(busca_chassi.strip().lower(), na=False)]

            st.markdown(f"**{len(df_view)} veículo(s)**")

            for i, (idx, row) in enumerate(df_view.iterrows()):
                tem_saida = cu_val(row, "data_saida") != ""
                cor_borda = "#10b981" if tem_saida else "#f97316"
                status_txt = "Retirado" if tem_saida else "No Pátio"
                cor_badge  = "#10b981" if tem_saida else "#f97316"

                with st.container(border=False):
                    saida_txt = f" &nbsp;·&nbsp; Saída: {cu_val(row, 'data_saida')}" if tem_saida else ""
                    st.markdown(
                        f"<div style='border-left:5px solid {cor_borda};padding:12px 16px;"
                        f"background:#fff;border-radius:0 12px 12px 0;margin-bottom:8px;"
                        f"border:1px solid #e2e8f0;border-left:5px solid {cor_borda}'>"
                        f"<div style='display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px'>"
                        f"<div>"
                        f"<div style='font-size:15px;font-weight:700;color:#1e293b'>{cu_val(row,'modelo')} "
                        f"<span style='font-weight:400;color:#94a3b8;font-size:13px'>{cu_val(row,'marca')}</span></div>"
                        f"<div style='font-size:12px;color:#64748b;margin-top:3px'>"
                        f"🔑 {cu_val(row,'chassi')} &nbsp;·&nbsp; 🪪 {cu_val(row,'placa')} &nbsp;·&nbsp; 🎨 {cu_val(row,'cor')}"
                        f"</div>"
                        f"<div style='font-size:11px;color:#94a3b8;margin-top:3px'>"
                        f"📍 {cu_val(row,'local')} &nbsp;·&nbsp; 🏢 {cu_val(row,'locadora')} &nbsp;·&nbsp; "
                        f"KM: {cu_val(row,'km')} &nbsp;·&nbsp; VEX: {cu_val(row,'vex')}"
                        f"</div>"
                        f"<div style='font-size:11px;color:#64748b;margin-top:3px'>"
                        f"📅 Entrada: {cu_val(row,'data_entrada')}{saida_txt}"
                        f"</div>"
                        f"</div>"
                        f"<span style='background:{cor_badge};color:#fff;padding:3px 12px;"
                        f"border-radius:999px;font-size:11px;font-weight:700'>{status_txt}</span>"
                        f"</div></div>",
                        unsafe_allow_html=True
                    )

    # ════════════════════════════════════════════════════
    # RECEBER VEÍCULO
    # ════════════════════════════════════════════════════
    with sub[1]:
        st.markdown("### ➕ Registrar Recebimento")
        with st.form("form_cu_receber"):
            r1, r2, r3 = st.columns(3)
            with r1:
                data_entrada = st.date_input("📅 Data Entrada *", value=datetime.date.today())
                locadora     = st.selectbox("Locadora *", CU_LOCADORAS)
                local        = st.selectbox("Local *", CU_LOCAIS)
            with r2:
                marca  = st.selectbox("Marca *", CU_MARCAS)
                modelo = st.text_input("Modelo *")
                placa  = st.text_input("Placa *")
            with r3:
                chassi = st.text_input("Chassi")
                cor    = st.text_input("Cor")
                km     = st.text_input("KM")
                vex    = st.text_input("VEX")

            if st.form_submit_button("✅ Registrar Entrada", use_container_width=True, type="primary"):
                if not modelo or not placa or not locadora:
                    st.error("Preencha os campos obrigatórios: Modelo, Placa e Locadora.")
                else:
                    prog = st.progress(0, text="Salvando...")
                    prog.progress(50, text="Enviando para planilha...")
                    nova_linha = [
                        data_entrada.strftime("%d/%m/%Y"),  # data_entrada
                        "",                                  # data_saida
                        locadora,                            # locadora
                        local,                               # local
                        marca,                               # marca
                        modelo.strip(),                      # modelo
                        placa.strip().upper(),               # placa
                        chassi.strip().upper(),              # chassi
                        cor.strip(),                         # cor
                        km.strip(),                          # km
                        vex.strip(),                         # vex
                    ]
                    ok = cu_enviar({"aba":"Planilha1","acao":"inserir","linha":nova_linha})
                    prog.progress(100, text="Concluído!")
                    if ok:
                        cu_carregar.clear()
                        st.success(f"✅ {modelo} — {placa} registrado com entrada em {data_entrada.strftime('%d/%m/%Y')}!")
                        st.rerun()

    # ════════════════════════════════════════════════════
    # EDITAR / SAÍDA (só Staff)
    # ════════════════════════════════════════════════════
    if is_staff:
        with sub[2]:
            st.markdown("### ✏️ Editar / Registrar Saída")

            if df.empty:
                st.info("Nenhum veículo cadastrado.")
            else:
                # Busca o veículo
                busca_ed = st.text_input("🔍 Buscar por placa ou chassi", key="cu_busca_ed")
                df_ed = df.copy()
                if busca_ed:
                    mask = pd.Series(False, index=df_ed.index)
                    for col in ["placa","chassi","modelo"]:
                        if col in df_ed.columns:
                            mask |= df_ed[col].astype(str).str.lower().str.contains(busca_ed.strip().lower(), na=False)
                    df_ed = df_ed[mask]

                if df_ed.empty:
                    st.warning("Nenhum veículo encontrado.")
                else:
                    opcoes_ed = df_ed.apply(
                        lambda r: f"{cu_val(r,'modelo')} | {cu_val(r,'placa')} | {cu_val(r,'chassi')} | Entrada: {cu_val(r,'data_entrada')}",
                        axis=1).tolist()
                    sel_ed = st.selectbox("Selecione o veículo", range(len(opcoes_ed)),
                        format_func=lambda i: opcoes_ed[i], key="cu_sel_ed")

                    row_ed    = df_ed.iloc[sel_ed]
                    idx_ed    = df_ed.index[sel_ed]
                    linha_ed  = int(idx_ed) + 2

                    # Card resumo
                    tem_saida_ed = cu_val(row_ed, "data_saida") != ""
                    cor_b = "#10b981" if tem_saida_ed else "#f97316"
                    st.markdown(
                        f"<div style='border-left:5px solid {cor_b};padding:12px 16px;"
                        f"background:#f8fafc;border-radius:0 12px 12px 0;margin:8px 0;"
                        f"border:1px solid #e2e8f0;border-left:5px solid {cor_b}'>"
                        f"<b>{cu_val(row_ed,'modelo')}</b> · {cu_val(row_ed,'marca')} · "
                        f"🪪 {cu_val(row_ed,'placa')} · 🔑 {cu_val(row_ed,'chassi')}<br>"
                        f"<span style='font-size:12px;color:#64748b'>"
                        f"Entrada: {cu_val(row_ed,'data_entrada')} · "
                        f"{'Saída: ' + cu_val(row_ed,'data_saida') if tem_saida_ed else 'No Pátio'}"
                        f"</span></div>",
                        unsafe_allow_html=True
                    )

                    with st.form("form_cu_editar"):
                        e1, e2, e3 = st.columns(3)
                        with e1:
                            # Parse data_entrada
                            de_str = cu_val(row_ed,"data_entrada")
                            try: de_val = datetime.datetime.strptime(de_str, "%d/%m/%Y").date()
                            except: de_val = datetime.date.today()
                            e_data_entrada = st.date_input("Data Entrada", value=de_val)

                            # Parse data_saida
                            ds_str = cu_val(row_ed,"data_saida")
                            try: ds_val = datetime.datetime.strptime(ds_str, "%d/%m/%Y").date()
                            except: ds_val = None
                            e_data_saida = st.date_input("Data Saída", value=ds_val)

                        with e2:
                            e_locadora = st.selectbox("Locadora", CU_LOCADORAS,
                                index=CU_LOCADORAS.index(cu_val(row_ed,"locadora")) if cu_val(row_ed,"locadora") in CU_LOCADORAS else 0)
                            e_local    = st.selectbox("Local", CU_LOCAIS,
                                index=CU_LOCAIS.index(cu_val(row_ed,"local")) if cu_val(row_ed,"local") in CU_LOCAIS else 0)
                            e_marca    = st.selectbox("Marca", CU_MARCAS,
                                index=CU_MARCAS.index(cu_val(row_ed,"marca")) if cu_val(row_ed,"marca") in CU_MARCAS else 0)

                        with e3:
                            e_modelo = st.text_input("Modelo", value=cu_val(row_ed,"modelo"))
                            e_placa  = st.text_input("Placa",  value=cu_val(row_ed,"placa"))
                            e_chassi = st.text_input("Chassi", value=cu_val(row_ed,"chassi"))
                            e_cor    = st.text_input("Cor",    value=cu_val(row_ed,"cor"))
                            e_km     = st.text_input("KM",     value=cu_val(row_ed,"km"))
                            e_vex    = st.text_input("VEX",    value=cu_val(row_ed,"vex"))

                        if st.form_submit_button("💾 Salvar Alterações", use_container_width=True, type="primary"):
                            prog2 = st.progress(0, text="Salvando...")
                            prog2.progress(50, text="Atualizando planilha...")
                            valores = []
                            campos = [
                                ("data_entrada", e_data_entrada.strftime("%d/%m/%Y")),
                                ("data_saida",   e_data_saida.strftime("%d/%m/%Y") if e_data_saida else ""),
                                ("locadora",     e_locadora),
                                ("local",        e_local),
                                ("marca",        e_marca),
                                ("modelo",       e_modelo.strip()),
                                ("placa",        e_placa.strip().upper()),
                                ("chassi",       e_chassi.strip().upper()),
                                ("cor",          e_cor.strip()),
                                ("km",           e_km.strip()),
                                ("vex",          e_vex.strip()),
                            ]
                            for col, val in campos:
                                if col in CU_COLUNAS:
                                    valores.append({"col": CU_COLUNAS.index(col)+1, "valor": val})

                            ok = cu_enviar({"aba":"Planilha1","acao":"atualizar_linha",
                                "linha_num": linha_ed, "valores": valores})
                            prog2.progress(100, text="Concluído!")
                            if ok:
                                cu_carregar.clear()
                                st.success("✅ Dados atualizados!")
                                st.rerun()