# =========================================================
# auth.py — Autenticação e gerenciamento de usuários
# Estrutura da planilha:
#   Nome | E-Mail | Senha | id_user | Frente | Tipo_Acesso | senha_hash
# =========================================================
import hashlib
import datetime
import streamlit as st
import pandas as pd
import requests
import json

SESSION_DURATION_H = 1  # duração da sessão em horas


# ── Constantes ───────────────────────────────────────────
AUTH_SHEET_URL = "https://docs.google.com/spreadsheets/d/1X1EDhj6JOUoPr9zaVT5Z7MCv8b4bav0R_dLhc7KELqk/export?format=csv&gid=0"
AUTH_WEBHOOK   = "https://script.google.com/macros/s/AKfycbyp036xYAlT-osJ3ZmNz2wWS7FFcCmBeAu3uN7uKX1PXNORwrrRCX63wvK4vB0OnccRnQ/exec"

# Índices das colunas na planilha (1-based para o webhook)
# Nome=1 | E-Mail=2 | Senha=3 | id_user=4 | Frente=5 | Tipo_Acesso=6 | senha_hash=7
COL_NOME        = 1
COL_EMAIL       = 2
COL_SENHA       = 3
COL_ID_USER     = 4
COL_FRENTE      = 5
COL_TIPO_ACESSO = 6
COL_SENHA_HASH  = 7

TIPOS_ACESSO = ["Staff", "Vendas", "Parceiro"]

# Permissões por tipo de acesso
ABAS_POR_TIPO = {
    "Staff":   ["🚗 Propostas", "🎴 Card", "🔍 Comparativo",
                "📈 Performance", "🚘 Estoque", "👥 Usuários", "🛠️ Gerenciamento"],
    "Vendas":  ["🚗 Propostas", "🎴 Card",
                "🔍 Comparativo", "🚘 Estoque"],
    "Parceiro":["🚗 Propostas", "🎴 Card"],
}


# ── Hash ─────────────────────────────────────────────────
def hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.strip().encode("utf-8")).hexdigest()


# ── Carregar usuários ────────────────────────────────────
@st.cache_data(ttl=60)
def carregar_log() -> pd.DataFrame:
    try:
        url_log = AUTH_SHEET_URL.rsplit("/export", 1)[0] + "/gviz/tq?tqx=out:csv&sheet=log"
        df = pd.read_csv(url_log, header=0)
        df.columns = [c.strip().lower().replace(" ","_") for c in df.columns]
        return df.sort_values("data_hora", ascending=False) if "data_hora" in df.columns else df
    except Exception:
        return pd.DataFrame(columns=["data_hora","nome","email","tipo_acesso","acao"])


def registrar_log(nome: str, email: str, tipo: str, acao: str) -> None:
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    enviar_auth({"aba": "log", "acao": "inserir",
        "linha": [agora, nome, email, tipo, acao]})


# ── Sessão via query_params ──────────────────────────────
def _user_agent_hash() -> str:
    """Pega um identificador do navegador para vincular ao token."""
    try:
        ua = st.context.headers.get("User-Agent", "unknown")
        return hashlib.md5(ua.encode()).hexdigest()[:8]
    except Exception:
        return "00000000"


def salvar_sessao(email: str, nome: str, tipo: str, frente: str) -> None:
    """Persiste sessão nos query_params da URL (sobrevive F5)."""
    import base64
    expira = (datetime.datetime.now() + datetime.timedelta(hours=SESSION_DURATION_H)).strftime("%d/%m/%Y %H:%M")
    ua_hash = _user_agent_hash()
    token  = base64.b64encode(f"{email}||{nome}||{tipo}||{frente}||{expira}||{ua_hash}".encode()).decode()
    st.query_params["s"] = token


def carregar_sessao() -> dict | None:
    """Lê a sessão dos query_params. Retorna None se expirada, inválida ou navegador diferente."""
    import base64
    try:
        token = st.query_params.get("s", "")
        if not token:
            return None
        valor  = base64.b64decode(token.encode()).decode()
        partes = valor.split("||")
        if len(partes) < 6:
            return None
        email, nome, tipo, frente, expira_str, ua_hash = partes
        # Verifica expiração
        expira = datetime.datetime.strptime(expira_str, "%d/%m/%Y %H:%M")
        if datetime.datetime.now() > expira:
            st.query_params.clear()
            return None
        # Verifica navegador
        if ua_hash != "00000000" and _user_agent_hash() != ua_hash:
            st.query_params.clear()
            return None
        return {"email": email, "nome": nome, "tipo": tipo, "frente": frente}
    except Exception:
        return None


def limpar_sessao() -> None:
    st.query_params.clear()


@st.cache_data(ttl=30)
def carregar_usuarios() -> pd.DataFrame:
    try:
        df = pd.read_csv(AUTH_SHEET_URL, header=0)
        # Normaliza nomes de colunas
        df.columns = [c.strip() for c in df.columns]
        return df
    except Exception as e:
        return pd.DataFrame()


def get_col(df: pd.DataFrame, nomes: list) -> str | None:
    """Retorna o nome real da coluna que bate com algum dos candidatos."""
    for n in nomes:
        if n in df.columns:
            return n
    return None


def enviar_auth(payload: dict) -> bool:
    if not AUTH_WEBHOOK:
        st.error("⚠️ Webhook de usuários não configurado em auth.py.")
        return False
    try:
        requests.post(AUTH_WEBHOOK, data=json.dumps(payload),
            headers={"Content-Type": "text/plain"}, timeout=30)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False


# ── Autenticação ─────────────────────────────────────────
def autenticar(email: str, senha: str) -> dict | None:
    """
    Tenta autenticar por senha_hash (SHA256).
    Retorna dict do usuário ou None.
    """
    df = carregar_usuarios()
    if df.empty:
        return None

    col_email = get_col(df, ["E-Mail", "email", "Email", "e-mail", "E-mail"])
    col_hash  = get_col(df, ["senha_hash", "Senha_Hash", "SenhaHash"])
    col_tipo  = get_col(df, ["Tipo_Acesso", "tipo_acesso", "Tipo", "tipo"])

    if not col_email or not col_hash:
        st.error("Colunas 'E-Mail' e 'senha_hash' não encontradas na planilha.")
        return None

    email_norm = email.strip().lower()
    hash_      = hash_senha(senha)

    match = df[
        (df[col_email].astype(str).str.strip().str.lower() == email_norm) &
        (df[col_hash].astype(str).str.strip() == hash_)
    ]

    if match.empty:
        return None

    u = match.iloc[0].to_dict()

    # Atualiza último login se houver coluna
    col_last = get_col(df, ["ultimo_login", "Ultimo_Login", "UltimoLogin"])
    if col_last and AUTH_WEBHOOK:
        linha_num = int(match.index[0]) + 2
        col_idx   = df.columns.tolist().index(col_last) + 1
        agora     = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        enviar_auth({
            "aba": "Planilha1",
            "acao": "atualizar_linha",
            "linha_num": linha_num,
            "valores": [{"col": col_idx, "valor": agora}]
        })

    return u


# ── Helpers de sessão ────────────────────────────────────
def is_logado() -> bool:
    return "auth_usuario" in st.session_state

def is_staff() -> bool:
    return st.session_state.get("auth_tipo", "") == "Staff"

def abas_permitidas() -> list:
    tipo = st.session_state.get("auth_tipo", "Vendas")
    return ABAS_POR_TIPO.get(tipo, ABAS_POR_TIPO["Vendas"])

def get_nome() -> str:
    return st.session_state.get("auth_nome", "Usuário")

def get_tipo() -> str:
    return st.session_state.get("auth_tipo", "")


# ── Senha temporária ─────────────────────────────────────
def gerar_senha_temp() -> str:
    import random, string
    chars = string.ascii_letters + string.digits + "!@#"
    return ''.join(random.choices(chars, k=10))


def resetar_senha_usuario(email: str, nova_senha: str) -> bool:
    """Redefine a senha_hash de um usuário pelo e-mail."""
    df = carregar_usuarios()
    if df.empty:
        return False
    col_email = get_col(df, ["E-Mail","email","Email","e-mail","E-mail"])
    col_hash  = get_col(df, ["senha_hash","Senha_Hash"])
    if not col_email or not col_hash:
        return False
    match = df[df[col_email].astype(str).str.strip().str.lower() == email.strip().lower()]
    if match.empty:
        return False
    linha_num = int(match.index[0]) + 2
    col_hash_idx = df.columns.tolist().index(col_hash) + 1
    ok = enviar_auth({
        "aba": "Planilha1", "acao": "atualizar_linha",
        "linha_num": linha_num,
        "valores": [{"col": col_hash_idx, "valor": hash_senha(nova_senha)}]
    })
    if ok:
        carregar_usuarios.clear()
    return ok


# ── Tela de login ────────────────────────────────────────
def render_login():
    st.markdown("""
    <style>
    [data-testid="stSidebar"] {display: none;}
    .block-container {padding-top: 0 !important;}
    .login-wrap {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
    }
    .login-box {
        background: #fff;
        border-radius: 24px;
        padding: 48px 44px 40px 44px;
        max-width: 440px;
        width: 100%;
        box-shadow: 0 20px 60px rgba(33,49,68,0.12);
        text-align: center;
    }
    .login-title {
        font-size: 26px;
        font-weight: 800;
        color: #213144;
        margin: 20px 0 6px 0;
    }
    .login-sub {
        font-size: 14px;
        color: #64748b;
        margin-bottom: 32px;
    }
    .login-divider {
        height: 1px;
        background: #e2e8f0;
        margin: 24px 0;
    }
    </style>
    """, unsafe_allow_html=True)

    _, col_c, _ = st.columns([1, 2, 1])
    with col_c:
        st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)

        st.image("https://i.postimg.cc/HWrrsnvR/LOGO-SIGNATURE-AZUL-E-DOURADO.png", width=220)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown(
            "<p style='font-size:22px;font-weight:800;color:#213144;margin:0'>Bem-vindo</p>"
            "<p style='font-size:14px;color:#64748b;margin-top:4px;margin-bottom:28px'>"
            "Faça login para acessar o sistema Carrera Signature</p>",
            unsafe_allow_html=True
        )

        with st.form("form_login", clear_on_submit=False):
            email = st.text_input("E-mail", placeholder="seu@carrera.com.br",
                label_visibility="visible")
            senha = st.text_input("Senha", placeholder="••••••••",
                type="password", label_visibility="visible")
            entrar = st.form_submit_button(
                "Entrar →", use_container_width=True, type="primary")

        if entrar:
            if not email or not senha:
                st.error("Preencha e-mail e senha.")
            else:
                with st.spinner("Verificando..."):
                    usuario = autenticar(email, senha)
                if usuario:
                    df = carregar_usuarios()
                    col_tipo  = get_col(df, ["Tipo_Acesso","tipo_acesso","Tipo","tipo"]) or "Tipo_Acesso"
                    col_nome  = get_col(df, ["Nome","nome"]) or "Nome"
                    col_email = get_col(df, ["E-Mail","email","Email","e-mail","E-mail"]) or "E-Mail"
                    col_frente= get_col(df, ["Frente","frente"]) or "Frente"

                    _tipo_u   = str(usuario.get(col_tipo,  "Vendas")).strip()
                    _nome_u   = str(usuario.get(col_nome,  "")).strip()
                    _email_u  = str(usuario.get(col_email, "")).strip().lower()
                    _frente_u = str(usuario.get(col_frente,"")).strip()

                    st.session_state["auth_usuario"] = usuario
                    st.session_state["auth_tipo"]    = _tipo_u
                    st.session_state["auth_nome"]    = _nome_u
                    st.session_state["auth_email"]   = _email_u
                    st.session_state["auth_frente"]  = _frente_u

                    salvar_sessao(_email_u, _nome_u, _tipo_u, _frente_u)
                    registrar_log(_nome_u, _email_u, _tipo_u, "Login")
                    carregar_usuarios.clear()
                    st.rerun()
                else:
                    st.error("E-mail ou senha incorretos.")

        # ── Esqueci minha senha ──────────────────────────
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        with st.expander("🔑 Esqueci minha senha"):
            with st.form("form_reset_senha"):
                email_reset = st.text_input("Seu e-mail", placeholder="seu@carrera.com.br", key="reset_email")
                nova_r      = st.text_input("Nova senha *",      type="password", key="reset_nova")
                conf_r      = st.text_input("Confirmar senha *", type="password", key="reset_conf")
                submit_r    = st.form_submit_button("🔑 Redefinir senha", use_container_width=True, type="primary")

            if submit_r:
                if not email_reset or not nova_r or not conf_r:
                    st.error("Preencha todos os campos.")
                elif nova_r != conf_r:
                    st.error("As senhas não coincidem.")
                elif len(nova_r) < 6:
                    st.error("Senha mínima de 6 caracteres.")
                else:
                    df_check = carregar_usuarios()
                    col_e = get_col(df_check, ["E-Mail","email","Email","e-mail","E-mail"])
                    match_r = df_check[df_check[col_e].astype(str).str.strip().str.lower() == email_reset.strip().lower()] if col_e else pd.DataFrame()
                    if match_r.empty:
                        st.error("E-mail não encontrado.")
                    else:
                        ok = resetar_senha_usuario(email_reset, nova_r)
                        if ok:
                            st.success("✅ Senha redefinida! Faça login com a nova senha.")
                        else:
                            st.error("Erro ao redefinir senha. Tente novamente.")

        st.markdown(
            "<p style='font-size:11px;color:#cbd5e1;margin-top:16px'>"
            "Em caso de problemas, contate o administrador do sistema.</p>",
            unsafe_allow_html=True
        )


# ── Sidebar do usuário logado ────────────────────────────
def render_sidebar_user():
    nome   = st.session_state.get("auth_nome",   "Usuário")
    tipo   = st.session_state.get("auth_tipo",   "")
    email  = st.session_state.get("auth_email",  "")
    frente = st.session_state.get("auth_frente", "")

    CORES = {"Staff": "#213144", "Vendas": "#0284c7", "Parceiro": "#7c3aed"}
    cor   = CORES.get(tipo, "#64748b")

    st.sidebar.markdown(f"""
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;
        padding:14px 16px;margin-bottom:16px">
        <div style="font-size:15px;font-weight:700;color:#1e293b;
            white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{nome}</div>
        <div style="font-size:11px;color:#64748b;margin-top:2px">{email}</div>
        {f'<div style="font-size:11px;color:#94a3b8;margin-top:1px">{frente}</div>' if frente else ''}
        <div style="margin-top:8px">
            <span style="background:{cor};color:#fff;padding:2px 10px;
                border-radius:999px;font-size:11px;font-weight:700">{tipo}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar_sair():
    """Botão Sair — chamar no app.py após as abas."""
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Sair", use_container_width=True, key="auth_sair"):
        registrar_log(
            st.session_state.get("auth_nome",""),
            st.session_state.get("auth_email",""),
            st.session_state.get("auth_tipo",""),
            "Logout"
        )
        limpar_sessao()
        for k in ["auth_usuario","auth_tipo","auth_nome","auth_email","auth_frente"]:
            st.session_state.pop(k, None)
        st.rerun()


# ════════════════════════════════════════════════════════
# GERENCIAMENTO DE USUÁRIOS (Staff)
# ════════════════════════════════════════════════════════
def render_usuarios():
    st.title("👥 Usuários")

    if not is_staff():
        st.error("Acesso restrito a Staff.")
        return

    df = carregar_usuarios()

    col_nome   = get_col(df, ["Nome","nome"]) or "Nome"
    col_email  = get_col(df, ["E-Mail","email","Email","e-mail","E-mail"]) or "E-Mail"
    col_tipo   = get_col(df, ["Tipo_Acesso","tipo_acesso","Tipo","tipo"]) or "Tipo_Acesso"
    col_frente = get_col(df, ["Frente","frente"]) or "Frente"
    col_hash   = get_col(df, ["senha_hash","Senha_Hash"]) or "senha_hash"
    col_last   = get_col(df, ["ultimo_login","Ultimo_Login"])

    sub = st.tabs(["👥 Lista", "➕ Novo Usuário", "✏️ Editar", "🗑️ Deletar", "🔑 Alterar Senha", "📋 Histórico de Log"])

    # ── LISTA ────────────────────────────────────────────
    with sub[0]:
        col_r, _ = st.columns([1,7])
        with col_r:
            if st.button("🔄", key="usr_refresh"):
                carregar_usuarios.clear(); st.rerun()

        if df.empty:
            st.info("Nenhum usuário cadastrado.")
            return

        CORES = {"Staff":"#213144","Vendas":"#0284c7","Parceiro":"#7c3aed"}

        for i, (_, row) in enumerate(df.iterrows()):
            tipo_u  = str(row.get(col_tipo, "")).strip()
            cor_u   = CORES.get(tipo_u, "#94a3b8")
            nome_u  = str(row.get(col_nome, "—"))
            email_u = str(row.get(col_email, "—"))
            frente_u= str(row.get(col_frente,"—"))
            last_u  = str(row.get(col_last,"—")) if col_last else "—"
            tem_hash= bool(str(row.get(col_hash,"")).strip()) if col_hash in df.columns else False

            st.markdown(f"""
            <div style="background:#fff;border:1px solid #e2e8f0;border-left:4px solid {cor_u};
                border-radius:12px;padding:14px 20px;margin-bottom:8px;
                display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
                <div>
                    <div style="font-size:14px;font-weight:700;color:#1e293b">{nome_u}</div>
                    <div style="font-size:12px;color:#64748b;margin-top:1px">{email_u}</div>
                    <div style="font-size:11px;color:#94a3b8;margin-top:2px">
                        Frente: {frente_u} &nbsp;·&nbsp; Último login: {last_u}
                        &nbsp;·&nbsp; {'🔐 Hash OK' if tem_hash else '⚠️ Sem hash'}
                    </div>
                </div>
                <span style="background:{cor_u};color:#fff;padding:3px 12px;
                    border-radius:999px;font-size:11px;font-weight:700">{tipo_u}</span>
            </div>
            """, unsafe_allow_html=True)


    # ── EDITAR ────────────────────────────────────────────
    with sub[2]:
        if df.empty:
            st.info("Nenhum usuário cadastrado.")
        else:
            opcoes_ed = df.apply(
                lambda r: f"{r.get(col_nome,'?')} — {r.get(col_email,'?')} ({r.get(col_tipo,'?')})",
                axis=1).tolist()
            sel_ed = st.selectbox("Selecione o usuário", range(len(opcoes_ed)),
                format_func=lambda i: opcoes_ed[i], key="usr_sel_ed")
            u_ed = df.iloc[sel_ed]

            with st.form("form_edit_usr"):
                eu1, eu2, eu3 = st.columns(3)
                with eu1:
                    e_nome   = st.text_input("Nome",   value=str(u_ed.get(col_nome,"")))
                    e_email  = st.text_input("E-mail", value=str(u_ed.get(col_email,"")))
                with eu2:
                    e_tipo   = st.selectbox("Tipo", TIPOS_ACESSO,
                        index=TIPOS_ACESSO.index(u_ed.get(col_tipo,"Vendas")) if u_ed.get(col_tipo) in TIPOS_ACESSO else 1)
                    e_frente = st.text_input("Frente", value=str(u_ed.get(col_frente,"")))
                with eu3:
                    col_id = get_col(df, ["id_user","ID_User","id"])
                    e_id   = st.text_input("id_user", value=str(u_ed.get(col_id,"")) if col_id else "")

                if st.form_submit_button("💾 Salvar", use_container_width=True, type="primary"):
                    linha_num = int(df.index[sel_ed]) + 2
                    ok = enviar_auth({
                        "aba": "Planilha1", "acao": "atualizar_linha",
                        "linha_num": linha_num,
                        "valores": [
                            {"col": COL_NOME,        "valor": e_nome.strip()},
                            {"col": COL_EMAIL,        "valor": e_email.strip().lower()},
                            {"col": COL_TIPO_ACESSO,  "valor": e_tipo},
                            {"col": COL_FRENTE,       "valor": e_frente.strip()},
                        ]
                    })
                    if ok:
                        carregar_usuarios.clear()
                        st.success("✅ Usuário atualizado!")
                        st.rerun()

    # ── DELETAR ───────────────────────────────────────────
    with sub[3]:
        if df.empty:
            st.info("Nenhum usuário cadastrado.")
        else:
            email_logado_del = st.session_state.get("auth_email", "")
            opcoes_del = df.apply(
                lambda r: f"{r.get(col_nome,'?')} — {r.get(col_email,'?')} ({r.get(col_tipo,'?')})",
                axis=1).tolist()
            sel_del = st.selectbox("Selecione o usuário para deletar", range(len(opcoes_del)),
                format_func=lambda i: opcoes_del[i], key="usr_sel_del")

            u_del     = df.iloc[sel_del]
            email_del = str(u_del.get(col_email, "")).strip().lower()
            nome_del  = str(u_del.get(col_nome,  ""))
            tipo_del  = str(u_del.get(col_tipo,  ""))
            cor_del   = {"Staff":"#213144","Vendas":"#0284c7","Parceiro":"#7c3aed"}.get(tipo_del, "#94a3b8")

            st.markdown(f"""
            <div style="background:#fff;border:1px solid #e2e8f0;border-left:4px solid {cor_del};
                border-radius:12px;padding:16px 20px;margin:12px 0">
                <div style="font-size:15px;font-weight:700;color:#1e293b">{nome_del}</div>
                <div style="font-size:12px;color:#64748b;margin-top:2px">{email_del}</div>
                <div style="margin-top:8px">
                    <span style="background:{cor_del};color:#fff;padding:2px 10px;
                        border-radius:999px;font-size:11px;font-weight:700">{tipo_del}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if email_del == email_logado_del:
                st.warning("⚠️ Você não pode deletar sua própria conta.")
            else:
                if "usr_confirmar_del" not in st.session_state:
                    st.session_state["usr_confirmar_del"] = False
                if not st.session_state["usr_confirmar_del"]:
                    if st.button(f"🗑️ Deletar {nome_del}", key="btn_del_usr", use_container_width=True):
                        st.session_state["usr_confirmar_del"] = True
                        st.rerun()
                else:
                    st.error("Tem certeza? Esta ação não pode ser desfeita.")
                    cd1, cd2 = st.columns(2)
                    with cd1:
                        if st.button("✅ Sim, deletar", key="btn_del_usr_sim", use_container_width=True):
                            ok = enviar_auth({
                                "aba": "Planilha1", "acao": "deletar_linha",
                                "linha_num": int(df.index[sel_del]) + 2
                            })
                            if ok:
                                st.session_state["usr_confirmar_del"] = False
                                carregar_usuarios.clear()
                                st.success(f"✅ {nome_del} deletado.")
                                st.rerun()
                    with cd2:
                        if st.button("❌ Cancelar", key="btn_del_usr_nao", use_container_width=True):
                            st.session_state["usr_confirmar_del"] = False
                            st.rerun()

        # ── NOVO USUÁRIO ─────────────────────────────────────
    with sub[1]:
        with st.form("form_novo_usr"):
            n1, n2 = st.columns(2)
            with n1:
                n_nome   = st.text_input("Nome completo *")
                n_email  = st.text_input("E-mail *")
                n_frente = st.text_input("Frente")
            with n2:
                n_tipo   = st.selectbox("Tipo de acesso *", TIPOS_ACESSO, index=1)
                n_senha  = st.text_input("Senha inicial *", type="password")
                n_conf   = st.text_input("Confirmar senha *", type="password")

            if st.form_submit_button("➕ Criar Usuário", use_container_width=True, type="primary"):
                if not n_nome or not n_email or not n_senha:
                    st.error("Preencha todos os campos obrigatórios.")
                elif n_senha != n_conf:
                    st.error("As senhas não coincidem.")
                elif len(n_senha) < 6:
                    st.error("Senha mínima de 6 caracteres.")
                else:
                    emails_ex = df[col_email].astype(str).str.strip().str.lower().tolist() if not df.empty else []
                    if n_email.strip().lower() in emails_ex:
                        st.error(f"E-mail `{n_email}` já cadastrado.")
                    else:
                        # id_user automático
                        import random, string
                        sufixo = ''.join(random.choices(string.digits, k=4))
                        tipo_abrev = "Staff" if n_tipo=="Staff" else "Vendas" if n_tipo=="Vendas" else "Parceiro"
                        novo_id = f"{n_nome.split()[0]}_{tipo_abrev}#{sufixo}"

                        nova_linha = [
                            n_nome.strip(),
                            n_email.strip().lower(),
                            "",                   # Senha (texto simples — mantém vazio)
                            novo_id,
                            n_frente.strip(),
                            n_tipo,
                            hash_senha(n_senha),  # senha_hash
                        ]
                        ok = enviar_auth({"aba":"Planilha1","acao":"inserir","linha":nova_linha})
                        if ok:
                            carregar_usuarios.clear()
                            st.success(f"✅ Usuário **{n_nome}** criado!")
                            st.rerun()

    # ── ALTERAR SENHA ────────────────────────────────────
    with sub[4]:
        email_logado = st.session_state.get("auth_email","")

        if is_staff():
            st.markdown("**Redefinir senha de qualquer usuário:**")
            opcoes_p = df.apply(
                lambda r: f"{r.get(col_nome,'?')} — {r.get(col_email,'?')} ({r.get(col_tipo,'?')})",
                axis=1).tolist()
            sel_p = st.selectbox("Usuário", range(len(opcoes_p)),
                format_func=lambda i: opcoes_p[i], key="usr_pwd_sel")
            u_p   = df.iloc[sel_p]
            idx_p = df.index[sel_p]

            # Opção: gerar senha temporária (Staff → envia email)
            st.divider()
            st.markdown("**Opção 1 — Gerar senha temporária e enviar por e-mail:**")
            if st.button("🎲 Gerar senha temporária", key="btn_gen_tmp", use_container_width=True):
                senha_tmp = gerar_senha_temp()
                ok = enviar_auth({
                    "aba": "Planilha1", "acao": "atualizar_linha",
                    "linha_num": int(idx_p) + 2,
                    "valores": [{"col": df.columns.tolist().index(col_hash)+1 if col_hash in df.columns else COL_SENHA_HASH,
                                 "valor": hash_senha(senha_tmp)}]
                })
                if ok:
                    carregar_usuarios.clear()
                    nome_dest  = str(u_p.get(col_nome,""))
                    email_dest = str(u_p.get(col_email,""))
                    assunto = "[Carrera Signature] Redefinição de senha"
                    corpo   = (
                        f"Olá {nome_dest},%0A%0A"
                        f"Sua senha foi redefinida por um administrador.%0A%0A"
                        f"Nova senha temporária: {senha_tmp}%0A%0A"
                        f"Acesse o sistema e altere sua senha em 👥 Usuários → Alterar Senha.%0A%0A"
                        f"Att,%0ACarrera Signature"
                    )
                    mailto = f"mailto:{email_dest}?subject={assunto}&body={corpo}"
                    st.success(f"✅ Senha temporária gerada: **`{senha_tmp}`**")
                    st.markdown(f"📧 [Enviar e-mail para {nome_dest}]({mailto})")

            st.divider()
            st.markdown("**Opção 2 — Definir nova senha manualmente:**")
        else:
            match_p = df[df[col_email].astype(str).str.strip().str.lower()==email_logado]
            if match_p.empty:
                st.warning("Usuário não encontrado."); return
            u_p   = match_p.iloc[0]
            idx_p = match_p.index[0]
            st.info(f"Alterando senha de: **{u_p.get(col_nome,'')}**")

        with st.form("form_pwd"):
            p1, p2 = st.columns(2)
            with p1: nova_pwd = st.text_input("Nova senha *",      type="password")
            with p2: conf_pwd = st.text_input("Confirmar senha *", type="password")

            if st.form_submit_button("🔑 Alterar Senha", use_container_width=True, type="primary"):
                if not nova_pwd or not conf_pwd:
                    st.error("Preencha os dois campos.")
                elif nova_pwd != conf_pwd:
                    st.error("As senhas não coincidem.")
                elif len(nova_pwd) < 6:
                    st.error("Senha mínima de 6 caracteres.")
                else:
                    col_hash_idx = df.columns.tolist().index(col_hash) + 1 if col_hash in df.columns else COL_SENHA_HASH
                    ok = enviar_auth({
                        "aba": "Planilha1", "acao": "atualizar_linha",
                        "linha_num": int(idx_p) + 2,
                        "valores": [{"col": col_hash_idx, "valor": hash_senha(nova_pwd)}]
                    })
                    if ok:
                        carregar_usuarios.clear()
                        st.success("✅ Senha alterada com sucesso!")

    # ── HISTÓRICO DE LOG ─────────────────────────────────
    with sub[5]:
        col_rl, _ = st.columns([1, 7])
        with col_rl:
            if st.button("🔄", key="log_refresh"):
                carregar_log.clear(); st.rerun()

        df_log = carregar_log()

        if df_log.empty:
            st.info("Nenhum registro de log ainda.")
        else:
            lf1, lf2, lf3 = st.columns(3)
            with lf1:
                opts_usr = ["Todos"] + sorted(df_log["email"].dropna().unique().tolist()) if "email" in df_log.columns else ["Todos"]
                filtro_usr = st.selectbox("Usuário", opts_usr, key="log_usr")
            with lf2:
                filtro_acao = st.selectbox("Ação", ["Todos","Login","Logout"], key="log_acao")
            with lf3:
                filtro_data = st.date_input("A partir de", value=None, key="log_data")

            df_lv = df_log.copy()
            if filtro_usr  != "Todos" and "email" in df_lv.columns:
                df_lv = df_lv[df_lv["email"] == filtro_usr]
            if filtro_acao != "Todos" and "acao" in df_lv.columns:
                df_lv = df_lv[df_lv["acao"] == filtro_acao]
            if filtro_data and "data_hora" in df_lv.columns:
                df_lv = df_lv[
                    pd.to_datetime(df_lv["data_hora"], dayfirst=True, errors="coerce")
                    >= pd.to_datetime(filtro_data)
                ]

            k1, k2, k3 = st.columns(3)
            k1.metric("Total",   len(df_lv))
            k2.metric("Logins",  len(df_lv[df_lv["acao"]=="Login"])  if "acao" in df_lv.columns else 0)
            k3.metric("Logouts", len(df_lv[df_lv["acao"]=="Logout"]) if "acao" in df_lv.columns else 0)
            st.divider()

            for _, row in df_lv.iterrows():
                acao_r  = str(row.get("acao",""))
                cor_r   = "#22c55e" if acao_r == "Login" else "#64748b"
                icone_r = "→" if acao_r == "Login" else "←"
                st.markdown(f"""
<div style="display:flex;align-items:center;gap:16px;padding:10px 16px;
    background:#fff;border:1px solid #e2e8f0;border-radius:10px;
    margin-bottom:6px;border-left:3px solid {cor_r}">
    <div style="font-size:16px">{icone_r}</div>
    <div style="flex:1">
        <div style="font-size:13px;font-weight:600;color:#1e293b">{row.get('nome','—')}</div>
        <div style="font-size:11px;color:#64748b">{row.get('email','—')} &nbsp;·&nbsp;
            <span style="color:{cor_r};font-weight:600">{acao_r}</span>
        </div>
    </div>
    <div style="font-size:11px;color:#94a3b8;text-align:right">
        {row.get('data_hora','—')}<br>
        <span style="font-size:10px">{row.get('tipo_acesso','')}</span>
    </div>
</div>
                """, unsafe_allow_html=True)