# =========================================================
# pages/metas.py — Módulo de Metas (Mensais / Trimestrais)
# Segue exatamente o padrão de conexão/CRUD via Google Sheets já usado em
# pages/gestao_veiculos.py e pages/controle_usados.py (sem banco SQL).
#
# Reaproveita a MESMA planilha e webhook de autenticação (autenticacao.py) —
# os dados ficam na aba "metas" dentro da planilha de Controle de Usuários.
#
# Estrutura da aba "metas":
#   ID | Ano | Tipo_Periodo | Periodo | Responsavel | Frente | Tipo_Meta |
#   Programa | Valor | Criado_Por | Data_Criacao | Data_Atualizacao
# =========================================================
import datetime
import json

import pandas as pd
import requests
import streamlit as st

from autenticacao import carregar_usuarios, get_col, AUTH_WEBHOOK

# ── Constantes de conexão ────────────────────────────────────────────────
# Reaproveita a MESMA planilha e o MESMO webhook de autenticação
# (aba "metas" dentro da planilha de Controle de Usuários) — sem
# necessidade de criar planilha nem Apps Script novos.
METAS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1X1EDhj6JOUoPr9zaVT5Z7MCv8b4bav0R_dLhc7KELqk/export?format=csv&gid=8584723"
METAS_WEBHOOK   = AUTH_WEBHOOK

METAS_COLUNAS = [
    "ID", "Ano", "Tipo_Periodo", "Periodo", "Responsavel", "Frente",
    "Tipo_Meta", "Programa", "Valor", "Criado_Por", "Data_Criacao", "Data_Atualizacao",
]

# ── Listas fechadas (sem texto livre) ────────────────────────────────────
PROGRAMAS = [
    "Sign&Drive", "Sign&Drive Empresas", "AssineCar Mulbrand", "AssineCar One",
    "AssieCar GWM", "GAC Go and Drive", "Nissan Move", "GM Fleet",
    "AssineCar Fit", "Arval",
]
TIPOS_META    = ["Geral", "Programa"]
TIPOS_PERIODO = ["Mensal", "Trimestral"]
MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
TRIMESTRES = ["1º Trimestre", "2º Trimestre", "3º Trimestre", "4º Trimestre"]

# ── Gestores das frentes (usados como Responsavel nas regras de permissão) ──
GESTOR_ANDREA  = "Andrea Bettega Pereira da Costa"
GESTOR_RAYMOND = "Raymond Jose Duque Bello"
# Acesso total (mesmo nível de Staff), independente do Tipo_Acesso cadastrado:
NIVEL2_NOMES   = ["Wellington Cabral Alves", "Leonardo Ribeiro Leonardi"]

AZUL     = "#213144"
DOURADO  = "#b57b3f"
DOURADO2 = "#dfc28a"


# ── Infra: carregar / enviar (mesmo padrão de gv_carregar / gv_enviar) ──
@st.cache_data(ttl=60)
def metas_carregar() -> pd.DataFrame:
    try:
        df = pd.read_csv(METAS_SHEET_URL, header=0)
        df.columns = [c.strip() for c in df.columns]
        for c in METAS_COLUNAS:
            if c not in df.columns:
                df[c] = ""
        return df
    except Exception:
        return pd.DataFrame(columns=METAS_COLUNAS)


def metas_enviar(payload: dict) -> bool:
    if not METAS_WEBHOOK:
        st.error("⚠️ Webhook de autenticação não configurado em autenticacao.py.")
        return False
    try:
        requests.post(METAS_WEBHOOK, data=json.dumps(payload),
                      headers={"Content-Type": "text/plain"}, timeout=30)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False


def metas_novo_id() -> str:
    return "META" + datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]


def _normalizar_nome(nome: str) -> str:
    return " ".join(str(nome or "").strip().split()).casefold()


def _val(row, col, default="") -> str:
    v = row.get(col, default)
    s = str(v).strip()
    return "" if s in ("nan", "None", "NaT") else s


# ── Cruzamento com usuários cadastrados / frentes ────────────────────────
def _usuarios_da_frente(df_usuarios: pd.DataFrame, palavra_chave: str) -> list:
    """Nomes de usuários cadastrados cuja Frente contém a palavra-chave (case-insensitive)."""
    if df_usuarios.empty:
        return []
    col_nome   = get_col(df_usuarios, ["Nome", "nome"]) or "Nome"
    col_frente = get_col(df_usuarios, ["Frente", "frente"]) or "Frente"
    if col_frente not in df_usuarios.columns:
        return []
    mask = df_usuarios[col_frente].astype(str).str.casefold().str.contains(palavra_chave.casefold(), na=False)
    return sorted(df_usuarios[mask][col_nome].dropna().astype(str).str.strip().unique().tolist())


def _frente_do_usuario(df_usuarios: pd.DataFrame, nome: str) -> str:
    """Retorna a Frente cadastrada para um usuário (para preencher a coluna Frente da meta automaticamente)."""
    if df_usuarios.empty or not nome:
        return ""
    col_nome   = get_col(df_usuarios, ["Nome", "nome"]) or "Nome"
    col_frente = get_col(df_usuarios, ["Frente", "frente"]) or "Frente"
    match = df_usuarios[df_usuarios[col_nome].astype(str).str.strip() == nome.strip()]
    if match.empty or col_frente not in df_usuarios.columns:
        return ""
    return str(match.iloc[0].get(col_frente, "") or "").strip()


def metas_perfil_acesso(auth_nome: str, tipo_acesso: str, df_usuarios: pd.DataFrame) -> dict:
    """
    Regras de permissão (ver especificação do módulo):
      - Andrea Bettega Pereira da Costa:
            cria/edita metas dos consultores cadastrados na Frente Santos. Sem excluir.
            (Checada ANTES da regra de Staff — mesmo que o Tipo_Acesso dela
            no cadastro seja "Staff", a restrição por nome tem prioridade,
            igual ao padrão já usado em pages/gestao_veiculos.py.)
      - Raymond Jose Duque Bello:
            cria/edita metas dos consultores cadastrados na Frente São Paulo. Sem excluir.
      - Staff "puro" + Wellington Cabral Alves + Leonardo Ribeiro Leonardi:
            acesso total — cria, edita, exclui e vê QUALQUER meta de QUALQUER responsável.
      - Qualquer outra pessoa: sem acesso ao módulo.
    """
    nome_norm = _normalizar_nome(auth_nome)
    col_nome = get_col(df_usuarios, ["Nome", "nome"]) or "Nome"
    todos = (sorted(df_usuarios[col_nome].dropna().astype(str).str.strip().unique().tolist())
             if not df_usuarios.empty and col_nome in df_usuarios.columns else [])

    # Restrições por nome têm prioridade sobre o Tipo_Acesso genérico —
    # checadas primeiro para não serem "engolidas" pela regra de Staff.
    if nome_norm == _normalizar_nome(GESTOR_ANDREA):
        return {
            "pode_ver": True, "pode_criar": True,
            "pode_editar_qualquer": False, "pode_excluir": False,
            "responsaveis_permitidos": _usuarios_da_frente(df_usuarios, "santos"),
        }

    if nome_norm == _normalizar_nome(GESTOR_RAYMOND):
        return {
            "pode_ver": True, "pode_criar": True,
            "pode_editar_qualquer": False, "pode_excluir": False,
            "responsaveis_permitidos": _usuarios_da_frente(df_usuarios, "paulo"),
        }

    nomes_full_access = {_normalizar_nome(n) for n in NIVEL2_NOMES}
    if tipo_acesso == "Staff" or nome_norm in nomes_full_access:
        return {
            "pode_ver": True, "pode_criar": True,
            "pode_editar_qualquer": True, "pode_excluir": True,
            "responsaveis_permitidos": todos,
        }

    return {"pode_ver": False, "pode_criar": False, "pode_editar_qualquer": False,
            "pode_excluir": False, "responsaveis_permitidos": []}


def metas_tem_acesso() -> bool:
    """Usado por app.py para decidir se mostra a aba Metas no menu."""
    auth_nome   = st.session_state.get("auth_nome", "")
    tipo_acesso = st.session_state.get("auth_tipo", "")
    if not auth_nome:
        return False
    nome_norm = _normalizar_nome(auth_nome)
    nomes_especiais = {_normalizar_nome(n) for n in
                        (NIVEL2_NOMES + [GESTOR_ANDREA, GESTOR_RAYMOND])}
    return tipo_acesso == "Staff" or nome_norm in nomes_especiais


def _pode_editar_meta(perfil: dict, responsavel_meta: str) -> bool:
    if perfil["pode_editar_qualquer"]:
        return True
    return responsavel_meta in perfil["responsaveis_permitidos"]


# ── Validação de duplicidade ──────────────────────────────────────────────
def _ja_existe(df: pd.DataFrame, ano, tipo_periodo, periodo, responsavel, tipo_meta, programa,
               ignorar_id=None) -> bool:
    if df.empty:
        return False
    programa_cmp = programa if tipo_meta == "Programa" else ""
    mask = (
        (df["Ano"].astype(str) == str(ano))
        & (df["Tipo_Periodo"].astype(str) == str(tipo_periodo))
        & (df["Periodo"].astype(str) == str(periodo))
        & (df["Responsavel"].astype(str).str.strip() == str(responsavel).strip())
        & (df["Tipo_Meta"].astype(str) == str(tipo_meta))
        & (df["Programa"].astype(str).str.strip() == str(programa_cmp).strip())
    )
    if ignorar_id:
        mask &= (df["ID"].astype(str) != str(ignorar_id))
    return bool(mask.any())


# ── Formatação ────────────────────────────────────────────────────────────
def _fmt_num(v) -> str:
    """Valor da meta é uma quantidade (número), não dinheiro."""
    try:
        return f"{int(round(float(v))):,}".replace(",", ".")
    except Exception:
        return "0"


# ── CSS (mesma paleta/estilo do restante do app) ─────────────────────────
METAS_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');
section[data-testid="stMain"] * {{ font-family: 'Montserrat', sans-serif !important; }}

.mt-kpi-row {{ display:flex; gap:10px; margin:10px 0 20px; flex-wrap:wrap; }}
.mt-kpi-box {{
    flex:1; min-width:150px; background:#fff; border:1.5px solid #e8e0d0;
    border-top:4px solid {DOURADO}; border-radius:14px; padding:14px 10px;
    text-align:center; box-shadow:0 2px 10px rgba(181,123,63,.07);
}}
.mt-kpi-n {{ font-size:22px; font-weight:800; color:{AZUL}; }}
.mt-kpi-l {{ font-size:10px; color:#94a3b8; margin-top:4px; text-transform:uppercase; letter-spacing:.6px; font-weight:600; }}

.mt-tabela {{ width:100%; border-collapse:collapse; font-size:13px; }}
.mt-tabela th {{
    background:{AZUL}; color:#fff; font-size:10px; font-weight:700;
    text-transform:uppercase; letter-spacing:.5px; padding:8px 10px; text-align:left;
}}
.mt-tabela td {{ padding:7px 10px; border-bottom:1px solid #f0ebe2; color:{AZUL}; }}
.mt-badge {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:10px; font-weight:700; color:#fff; }}
</style>
"""


# ══════════════════════════════════════════════════════════════════════════
# RENDER
# ══════════════════════════════════════════════════════════════════════════
def render():
    st.markdown(METAS_CSS, unsafe_allow_html=True)
    st.markdown(f"<h2 style='color:{AZUL};margin:0'>🎯 Metas</h2>", unsafe_allow_html=True)

    auth_nome   = st.session_state.get("auth_nome", "")
    tipo_acesso = st.session_state.get("auth_tipo", "")

    df_usuarios = carregar_usuarios()
    perfil = metas_perfil_acesso(auth_nome, tipo_acesso, df_usuarios)

    if not perfil["pode_ver"]:
        st.warning("Você não tem permissão para acessar o módulo de Metas.")
        return

    col_h1, col_h2 = st.columns([5, 1])
    with col_h2:
        if st.button("🔄 Atualizar", use_container_width=True, key="mt_refresh"):
            metas_carregar.clear()
            st.rerun()

    df_metas = metas_carregar()
    hoje = datetime.date.today()

    # ══════════════════════════════════════════════════════
    # CRIAR / EDITAR
    # ══════════════════════════════════════════════════════
    editando_id = st.session_state.get("mt_editando")
    meta_edicao = None
    if editando_id and not df_metas.empty:
        match = df_metas[df_metas["ID"].astype(str) == str(editando_id)]
        if not match.empty:
            meta_edicao = match.iloc[0]

    if perfil["pode_criar"] or meta_edicao is not None:
        titulo_form = "✏️ Editar Meta" if meta_edicao is not None else "➕ Nova Meta"
        with st.expander(titulo_form, expanded=(meta_edicao is not None)):
            with st.form("mt_form", clear_on_submit=(meta_edicao is None)):
                c1, c2, c3 = st.columns(3)
                with c1:
                    anos_disp = list(range(hoje.year - 1, hoje.year + 3))
                    ano_default = int(_val(meta_edicao, "Ano", hoje.year)) if meta_edicao is not None else hoje.year
                    ano = st.selectbox("Ano", anos_disp,
                                        index=anos_disp.index(ano_default) if ano_default in anos_disp else 1)
                with c2:
                    tp_default = _val(meta_edicao, "Tipo_Periodo", "Mensal") if meta_edicao is not None else "Mensal"
                    tipo_periodo = st.selectbox("Mensal / Trimestral", TIPOS_PERIODO,
                                                 index=TIPOS_PERIODO.index(tp_default) if tp_default in TIPOS_PERIODO else 0)
                with c3:
                    opcoes_periodo = MESES if tipo_periodo == "Mensal" else TRIMESTRES
                    per_default = _val(meta_edicao, "Periodo", opcoes_periodo[0]) if meta_edicao is not None else opcoes_periodo[0]
                    periodo = st.selectbox("Período", opcoes_periodo,
                                            index=opcoes_periodo.index(per_default) if per_default in opcoes_periodo else 0)

                c4, c5, c6 = st.columns(3)
                with c4:
                    resp_opcoes = perfil["responsaveis_permitidos"]
                    if not resp_opcoes:
                        st.selectbox("Responsável", ["(nenhum consultor disponível)"], disabled=True)
                        responsavel = None
                    else:
                        resp_default = _val(meta_edicao, "Responsavel") if meta_edicao is not None else resp_opcoes[0]
                        responsavel = st.selectbox("Responsável", resp_opcoes,
                                                    index=resp_opcoes.index(resp_default) if resp_default in resp_opcoes else 0)
                with c5:
                    tm_default = _val(meta_edicao, "Tipo_Meta", "Geral") if meta_edicao is not None else "Geral"
                    tipo_meta = st.selectbox("Tipo de Meta", TIPOS_META,
                                              index=TIPOS_META.index(tm_default) if tm_default in TIPOS_META else 0)
                with c6:
                    if tipo_meta == "Programa":
                        prog_default = _val(meta_edicao, "Programa", PROGRAMAS[0]) if meta_edicao is not None else PROGRAMAS[0]
                        programa = st.selectbox("Programa", PROGRAMAS,
                                                 index=PROGRAMAS.index(prog_default) if prog_default in PROGRAMAS else 0)
                    else:
                        st.selectbox("Programa", ["— Meta Geral (sem programa) —"], disabled=True)
                        programa = ""

                try:
                    valor_default = float(_val(meta_edicao, "Valor", 0) or 0) if meta_edicao is not None else 0.0
                except ValueError:
                    valor_default = 0.0
                valor = st.number_input("Valor da Meta (quantidade)", min_value=0, step=1, value=int(valor_default))

                col_salvar, col_cancelar = st.columns([3, 1])
                with col_salvar:
                    salvar = st.form_submit_button(
                        "💾 Salvar Alterações" if meta_edicao is not None else "💾 Criar Meta",
                        use_container_width=True, type="primary",
                    )
                with col_cancelar:
                    cancelar = st.form_submit_button("✕ Cancelar", use_container_width=True) if meta_edicao is not None else False

                if cancelar:
                    st.session_state["mt_editando"] = None
                    st.rerun()

                if salvar:
                    if not responsavel:
                        st.error("Nenhum responsável disponível para o seu perfil de acesso.")
                    elif not _pode_editar_meta(perfil, responsavel):
                        st.error("Você não tem permissão para definir metas para este responsável.")
                    elif valor <= 0:
                        st.error("Informe um valor de meta maior que zero.")
                    else:
                        duplicado = _ja_existe(
                            df_metas, ano, tipo_periodo, periodo, responsavel, tipo_meta, programa,
                            ignorar_id=editando_id if meta_edicao is not None else None,
                        )
                        if duplicado:
                            st.error(
                                "Já existe uma meta cadastrada para este Responsável + Período + "
                                "Tipo de Meta + Programa. Edite a meta existente em vez de duplicar."
                            )
                        else:
                            agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                            frente = _frente_do_usuario(df_usuarios, responsavel)
                            if meta_edicao is not None:
                                idx = df_metas[df_metas["ID"].astype(str) == str(editando_id)].index[0]
                                linha_num = int(idx) + 2
                                valores = [
                                    {"col": METAS_COLUNAS.index("Ano") + 1, "valor": ano},
                                    {"col": METAS_COLUNAS.index("Tipo_Periodo") + 1, "valor": tipo_periodo},
                                    {"col": METAS_COLUNAS.index("Periodo") + 1, "valor": periodo},
                                    {"col": METAS_COLUNAS.index("Responsavel") + 1, "valor": responsavel},
                                    {"col": METAS_COLUNAS.index("Frente") + 1, "valor": frente},
                                    {"col": METAS_COLUNAS.index("Tipo_Meta") + 1, "valor": tipo_meta},
                                    {"col": METAS_COLUNAS.index("Programa") + 1, "valor": programa},
                                    {"col": METAS_COLUNAS.index("Valor") + 1, "valor": valor},
                                    {"col": METAS_COLUNAS.index("Data_Atualizacao") + 1, "valor": agora},
                                ]
                                ok = metas_enviar({"aba": "metas", "acao": "atualizar_linha",
                                                    "linha_num": linha_num, "valores": valores})
                                if ok:
                                    metas_carregar.clear()
                                    st.session_state["mt_editando"] = None
                                    st.success("✅ Meta atualizada!")
                                    st.rerun()
                            else:
                                linha = [
                                    metas_novo_id(), ano, tipo_periodo, periodo, responsavel, frente,
                                    tipo_meta, programa, valor, auth_nome, agora, agora,
                                ]
                                ok = metas_enviar({"aba": "metas", "acao": "inserir", "linha": linha})
                                if ok:
                                    metas_carregar.clear()
                                    st.success("✅ Meta criada!")
                                    st.rerun()

    st.divider()

    # ══════════════════════════════════════════════════════
    # FILTROS
    # ══════════════════════════════════════════════════════
    df_metas = metas_carregar()

    # Restringe a listagem ao que o perfil pode ver? Regra: Staff vê tudo;
    # os demais perfis também só ENXERGAM as metas dos seus responsáveis
    # permitidos (mesma lista usada para editar).
    if not perfil["pode_editar_qualquer"]:
        df_metas = df_metas[df_metas["Responsavel"].astype(str).str.strip().isin(perfil["responsaveis_permitidos"])]

    if df_metas.empty:
        st.info("Nenhuma meta cadastrada ainda.")
        return

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        anos_existentes = sorted(df_metas["Ano"].dropna().astype(str).unique().tolist(), reverse=True)
        flt_ano = st.selectbox("Ano", ["Todos"] + anos_existentes, key="mt_flt_ano")
    with f2:
        flt_tp = st.selectbox("Mensal/Trimestral", ["Todos"] + TIPOS_PERIODO, key="mt_flt_tp")
    with f3:
        resp_existentes = sorted(df_metas["Responsavel"].dropna().astype(str).unique().tolist())
        flt_resp = st.selectbox("Responsável", ["Todos"] + resp_existentes, key="mt_flt_resp")
    with f4:
        flt_tm = st.selectbox("Tipo de Meta", ["Todos"] + TIPOS_META, key="mt_flt_tm")

    dv = df_metas.copy()
    if flt_ano != "Todos": dv = dv[dv["Ano"].astype(str) == flt_ano]
    if flt_tp  != "Todos": dv = dv[dv["Tipo_Periodo"] == flt_tp]
    if flt_resp != "Todos": dv = dv[dv["Responsavel"] == flt_resp]
    if flt_tm  != "Todos": dv = dv[dv["Tipo_Meta"] == flt_tm]

    # ══════════════════════════════════════════════════════
    # RESUMO
    # ══════════════════════════════════════════════════════
    dv["_valor_num"] = pd.to_numeric(dv["Valor"], errors="coerce").fillna(0)
    total_geral = dv[dv["Tipo_Meta"] == "Geral"]["_valor_num"].sum()
    total_programa = dv[dv["Tipo_Meta"] == "Programa"]["_valor_num"].sum()
    qtd_metas = len(dv)
    qtd_responsaveis = dv["Responsavel"].nunique()

    st.markdown(f"""
    <div class="mt-kpi-row">
      <div class="mt-kpi-box"><div class="mt-kpi-n">{qtd_metas}</div><div class="mt-kpi-l">Metas no filtro</div></div>
      <div class="mt-kpi-box"><div class="mt-kpi-n">{qtd_responsaveis}</div><div class="mt-kpi-l">Responsáveis</div></div>
      <div class="mt-kpi-box"><div class="mt-kpi-n">{_fmt_num(total_geral)}</div><div class="mt-kpi-l">Soma Metas Gerais</div></div>
      <div class="mt-kpi-box"><div class="mt-kpi-n">{_fmt_num(total_programa)}</div><div class="mt-kpi-l">Soma Metas por Programa</div></div>
    </div>
    """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════
    # LISTAGEM
    # ══════════════════════════════════════════════════════
    st.markdown(f"<p style='color:#94a3b8;font-size:13px'><b style='color:{AZUL}'>{len(dv)}</b> meta(s)</p>",
                unsafe_allow_html=True)

    for _, row in dv.sort_values(["Ano", "Responsavel"], ascending=[False, True]).iterrows():
        pode_editar_esta = _pode_editar_meta(perfil, str(row["Responsavel"]).strip())
        cor_badge = DOURADO if row["Tipo_Meta"] == "Geral" else "#0891b2"

        col_info, col_acoes = st.columns([6, 1])
        with col_info:
            programa_txt = f" · 📦 {row['Programa']}" if row["Tipo_Meta"] == "Programa" and row.get("Programa") else ""
            st.markdown(f"""
                <div style='background:#fff;border:1px solid #e8e0d0;border-left:4px solid {DOURADO};
                     border-radius:10px;padding:10px 16px;margin-bottom:6px'>
                    <span class='mt-badge' style='background:{cor_badge}'>{row['Tipo_Meta']}</span>
                    &nbsp;<b style='color:{AZUL}'>{row['Responsavel']}</b>
                    &nbsp;·&nbsp;{row['Tipo_Periodo']} {row['Periodo']}/{row['Ano']}{programa_txt}
                    <div style='font-size:18px;font-weight:800;color:{AZUL};margin-top:4px'>{_fmt_num(row['Valor'])}</div>
                    <div style='font-size:10px;color:#94a3b8;margin-top:2px'>
                        Frente: {row.get('Frente','—') or '—'} · Criado por {row.get('Criado_Por','—')} em {row.get('Data_Criacao','—')}
                    </div>
                </div>
            """, unsafe_allow_html=True)
        with col_acoes:
            if pode_editar_esta:
                if st.button("✏️", key=f"mt_edit_{row['ID']}", help="Editar", use_container_width=True):
                    st.session_state["mt_editando"] = row["ID"]
                    st.rerun()
                if perfil["pode_excluir"]:
                    if st.button("🗑️", key=f"mt_del_{row['ID']}", help="Excluir", use_container_width=True):
                        idx = df_metas[df_metas["ID"].astype(str) == str(row["ID"])].index[0]
                        linha_num = int(idx) + 2
                        if metas_enviar({"aba": "metas", "acao": "deletar_linha", "linha_num": linha_num}):
                            metas_carregar.clear()
                            st.success("Meta excluída.")
                            st.rerun()
