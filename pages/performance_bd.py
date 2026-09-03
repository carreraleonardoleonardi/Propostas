"""
performance_bd.py — Carrera Signature
Área de Performance conectada ao Azure SQL Server.

Páginas: Geral · Marketing · Operação Geral · São Paulo · Santos

──────────────────────────────────────────────────────────────────────────
⚠️  CONFIGURAÇÃO NECESSÁRIA (.streamlit/secrets.toml):

    [azure_sql]
    server   = "seu-servidor.database.windows.net"
    database = "SeuBanco"
    username = "seu_usuario"      # sem "@servidor" — é adicionado automaticamente
    password = 'sua_senha_com_caracteres_especiais'   # usar aspas simples

⚠️  NOMES DE TABELA/COLUNA — confira e ajuste na seção CONFIG abaixo caso
    o nome real na Azure seja diferente. Foram usados os nomes citados
    nas especificações; alguns (marcados com TODO) são inferências que
    devem ser confirmadas.
──────────────────────────────────────────────────────────────────────────
"""

import calendar
from datetime import date, timedelta

import pandas as pd
import streamlit as st
import sqlalchemy as sa

from autenticacao import carregar_usuarios, get_col
from pages.gestao_veiculos import gv_carregar, parse_data


# ══════════════════════════════════════════════════════════════════════════
# CONFIG — TABELAS E COLUNAS (ajustar aqui se o nome real for diferente)
# ══════════════════════════════════════════════════════════════════════════
TBL_SF               = "dbo.tbConsolidaSalesforce"
COL_SF_SUBSCRIBER    = "SUBSCRIBER_KEY"
COL_SF_DATA_ASSIN    = "DATA_ASSINATURA_CONTRATO"
COL_SF_QTD_VEICULOS  = "QTD_VEICULOS"                     # confirmado
COL_SF_DATA_CRIACAO  = "DATA_CRIACAO"
COL_SF_DATA_CAPTACAO = "DATA_CAPTACAO"
COL_SF_CONSULTOR     = "CONSULTOR"
COL_SF_RESPONSAVEL   = "RESPONSAVEL"                      # confirmado — usado no ranking geral
COL_SF_MIDIA          = "MIDIA"                           # confirmado

TBL_MKT              = "mkt.ConsolidadoCampanhas"        # confirmado
COL_MKT_INVESTIMENTO = "Investimento"                     # confirmado
COL_MKT_DIA          = "Dia_Campanha"                     # confirmado
COL_MKT_PLATAFORMA   = "Plataforma"              # TODO: confirmar nome/valores (Google/Meta)
COL_MKT_IMPRESSOES   = "Impressoes"                       # confirmado
COL_MKT_CLICKS       = "Clicks"                           # confirmado

TBL_COLAB            = "dbo.tbColaboradores"
COL_COLAB_NOME       = "Colaborador"      # confirmado (planilha Controle_de_Entregas)
COL_COLAB_GESTOR     = "Gerente"          # confirmado — NÃO é "GESTOR"
COL_COLAB_FRENTE     = "Frente"           # confirmado — agrupamento usado no Controle_Frentes
COL_COLAB_RESULTADO  = "Resultado"        # confirmado — praça/unidade
COL_COLAB_AGENTE     = "Agente"           # confirmado — liga com tbUsCall (NUM_AGENTE)

TBL_CALLS            = "dbo.tbUsCall"     # confirmado
COL_CALL_AGENTE      = "NUM_AGENTE"       # TODO: confirmar nome exato nesta tabela
COL_CALL_DATAHORA    = "DATAHORA"         # TODO: confirmar nome exato nesta tabela

# "Entregues" / "Previsão de Entregar" NÃO vêm do Azure — vêm da planilha de
# Gestão de Veículos (Google Sheets, já usada em pages/gestao_veiculos.py),
# que é a fonte oficial de confirmação de entrega segundo o time.
STATUS_PENDENTE_ENTREGA = {
    "Trânsito Vendido", "Aguardando Atribuição", "Aguardando Agendamento",
    "Agendado", "Reagendar",
}

GESTOR_SANTOS   = "Andrea Bettega Pereira da Costa"
GESTOR_SAO_PAULO = "Raymond Jose Duque Bello"


# ══════════════════════════════════════════════════════════════════════════
# BRAND / VISUAL
# ══════════════════════════════════════════════════════════════════════════
AZUL     = "#1E2B3B"
AZUL2    = "#16212e"
DOURADO  = "#B5813C"
DOURADO2 = "#DCB878"
CINZA    = "#64748b"
VERDE    = "#16a34a"
VERMELHO = "#dc2626"
BRANCO   = "#ffffff"
BG       = "#f7f8fa"
BORDA    = "#e6e2da"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800;900&display=swap');
.pf-wrap * {{ font-family:'Montserrat',sans-serif !important; }}

.pf-header {{
    background:linear-gradient(135deg, {AZUL2} 0%, {AZUL} 65%, #2d4a6b 100%);
    border-radius:18px; padding:22px 26px; margin-bottom:18px;
    border:1px solid {DOURADO}; position:relative; overflow:hidden;
}}
.pf-header::after {{
    content:""; position:absolute; top:-50px; right:-50px;
    width:180px; height:180px; border-radius:50%;
    background:rgba(181,123,63,.12);
}}
.pf-titulo {{ font-size:22px; font-weight:900; color:{BRANCO}; margin:0; }}
.pf-sub    {{ font-size:12px; color:{DOURADO2}; margin-top:3px; letter-spacing:.5px; text-transform:uppercase; }}

.pf-kpi-grid {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:20px; }}
.pf-kpi {{
    background:{BRANCO}; border:1px solid {BORDA}; border-radius:14px;
    padding:16px 14px; position:relative; overflow:hidden;
    box-shadow:0 2px 10px rgba(30,43,59,.05);
}}
.pf-kpi::before {{
    content:""; position:absolute; top:0; left:0; right:0; height:3px;
    background:linear-gradient(90deg,{DOURADO},{DOURADO2});
}}
.pf-kpi-label {{ font-size:10px; font-weight:700; color:{CINZA}; text-transform:uppercase; letter-spacing:.6px; }}
.pf-kpi-val   {{ font-size:24px; font-weight:900; color:{AZUL}; line-height:1.2; margin-top:4px; }}
.pf-kpi-delta {{ font-size:11px; font-weight:700; margin-top:6px; display:inline-flex; align-items:center; gap:3px; }}
.pf-up   {{ color:{VERDE}; }}
.pf-down {{ color:{VERMELHO}; }}
.pf-flat {{ color:{CINZA}; }}

.pf-card {{
    background:{BRANCO}; border:1px solid {BORDA}; border-radius:14px;
    padding:18px; box-shadow:0 2px 10px rgba(30,43,59,.04); height:100%;
}}
.pf-card-titulo {{
    font-size:12px; font-weight:800; color:{AZUL}; text-transform:uppercase;
    letter-spacing:.6px; margin-bottom:12px; padding-bottom:8px; border-bottom:2px solid {BORDA};
}}
.pf-tabela {{ width:100%; border-collapse:collapse; font-size:13px; }}
.pf-tabela th {{
    background:{AZUL}; color:{BRANCO}; font-size:10px; font-weight:700;
    text-transform:uppercase; letter-spacing:.5px; padding:8px 10px; text-align:left;
}}
.pf-tabela td {{ padding:7px 10px; border-bottom:1px solid #f0ebe2; color:{AZUL}; }}
.pf-badge-ok  {{ background:#dcfce7; color:{VERDE};  padding:1px 8px; border-radius:999px; font-size:10px; font-weight:700; }}
.pf-badge-off {{ background:#fef3c7; color:#b45309; padding:1px 8px; border-radius:999px; font-size:10px; font-weight:700; }}

@media (max-width:1100px) {{ .pf-kpi-grid {{ grid-template-columns:repeat(2,1fr); }} }}
</style>
"""


# ══════════════════════════════════════════════════════════════════════════
# CONEXÃO AZURE SQL
# ══════════════════════════════════════════════════════════════════════════
def _melhor_driver_odbc(preferido: str) -> str:
    """
    Retorna o driver ODBC "SQL Server" realmente instalado neste ambiente.
    Local (Windows) costuma ter o Driver 18; o Streamlit Community Cloud
    normalmente só tem o Driver 17 pré-instalado — em vez de travar exigindo
    um específico, detecta o que está disponível e usa a versão mais nova.
    Se não conseguir sondar (pyodbc ausente), mantém o valor configurado.
    """
    try:
        import pyodbc
        instalados = [d for d in pyodbc.drivers() if "ODBC Driver" in d and "SQL Server" in d]
    except Exception:
        instalados = []

    if not instalados:
        return preferido
    if preferido in instalados:
        return preferido

    import re
    def _versao(nome):
        m = re.search(r"(\d+)", nome)
        return int(m.group(1)) if m else 0

    return sorted(instalados, key=_versao, reverse=True)[0]


@st.cache_resource(show_spinner=False)
def _engine():
    """
    Cria a engine SQLAlchemy para o Azure SQL.

    Driver: st.secrets['azure_sql']['driver'] — aceita "pymssql", "pyodbc"
    ou o nome literal do driver ODBC (ex.: "ODBC Driver 18 for SQL Server"),
    que já implica pyodbc.

    Autenticação Azure AD: detectada automaticamente quando o `username` é
    um e-mail corporativo (ex.: leonardo.leonardi@carrera.com.br) em vez de
    um login SQL tradicional — nesse caso usa Authentication=
    ActiveDirectoryPassword via pyodbc (pymssql NÃO suporta Azure AD; se o
    driver ainda estiver como "pymssql" nesse cenário, um erro claro é
    levantado orientando a trocar para pyodbc).

    Pode-se forçar o modo de autenticação com
    st.secrets['azure_sql']['authentication'] (ex.: "SqlPassword").
    """
    cfg = st.secrets["azure_sql"]
    servidor = cfg["server"]
    banco    = cfg["database"]
    usuario  = cfg["username"]
    senha    = cfg["password"]
    porta    = int(cfg.get("port", 1433))
    timeout  = int(cfg.get("timeout", 30))

    short_name = servidor.split(".")[0]
    driver_cfg = str(cfg.get("driver", "pymssql")).strip()
    usa_pyodbc = "odbc" in driver_cfg.lower()

    # Azure AD: usuário no formato e-mail e que NÃO é o padrão de login SQL
    # "usuario@nome-curto-do-servidor".
    eh_azure_ad = (
        "@" in usuario
        and not usuario.lower().endswith(f"@{short_name.lower()}")
    )
    autenticacao = cfg.get(
        "authentication", "ActiveDirectoryPassword" if eh_azure_ad else None
    )

    if usa_pyodbc:
        odbc_driver_desejado = driver_cfg if "odbc driver" in driver_cfg.lower() else cfg.get(
            "odbc_driver", "ODBC Driver 18 for SQL Server"
        )
        odbc_driver = _melhor_driver_odbc(odbc_driver_desejado)

        # Alguns modos de autenticação Azure AD são interativos ou não usam
        # usuário/senha da forma tradicional — não incluir UID/PWD nesses
        # casos (incluí-los pode até quebrar o handshake dependendo da
        # versão do driver).
        auth_lower = (autenticacao or "").lower()
        SEM_SENHA = {"activedirectoryinteractive", "activedirectoryintegrated",
                     "activedirectorydevicecodeflow", "activedirectorymsi"}
        incluir_uid = auth_lower != "activedirectoryintegrated"
        incluir_pwd = auth_lower not in SEM_SENHA

        # Monta a connection string ODBC manualmente (em vez de deixar o
        # SQLAlchemy montar a partir de um dict de query params) — chaves
        # com espaço como "Connection Timeout" podem ser mal codificadas na
        # URL e corromper a autenticação, resultando em erro de login
        # genérico ("<token-identified principal>") mesmo com credenciais
        # corretas.
        partes = [
            f"DRIVER={{{odbc_driver}}}",
            f"SERVER=tcp:{servidor},{porta}",
            f"DATABASE={banco}",
        ]
        if incluir_uid: partes.append(f"UID={usuario}")
        if incluir_pwd: partes.append(f"PWD={senha}")
        partes += [
            "Encrypt=yes",
            "TrustServerCertificate=no",
            f"Connection Timeout={timeout}",
        ]
        if autenticacao:
            partes.append(f"Authentication={autenticacao}")
        conn_str = ";".join(partes) + ";"

        url = sa.URL.create(
            "mssql+pyodbc",
            query={"odbc_connect": conn_str},
        )
        return sa.create_engine(url, pool_pre_ping=True, fast_executemany=True)

    # ── pymssql (login SQL tradicional apenas) ──────────────────────────
    if eh_azure_ad:
        raise RuntimeError(
            f"O usuário '{usuario}' parece ser uma conta Azure AD (e-mail "
            "corporativo), mas o driver está configurado como 'pymssql', que "
            "NÃO suporta autenticação Azure AD. Defina no secrets.toml:\n"
            '  driver = "ODBC Driver 18 for SQL Server"\n'
            "(requer o driver ODBC instalado no sistema)."
        )

    usuario_sql = usuario if "@" in usuario else f"{usuario}@{short_name}"
    url = sa.URL.create(
        "mssql+pymssql",
        username=usuario_sql,
        password=senha,
        host=servidor,
        port=porta,
        database=banco,
    )
    return sa.create_engine(
        url, connect_args={"tds_version": "7.4", "login_timeout": timeout},
        pool_pre_ping=True,
    )


def _debug_info() -> dict:
    """
    Recalcula os parâmetros de conexão (sem cache, sem tocar no banco) só
    para exibir em modo debug — senha sempre mascarada. Usado para comparar
    lado a lado com o testar_conexao_azure.py quando o login falha mesmo
    com credenciais corretas.
    """
    cfg = st.secrets.get("azure_sql", {})
    servidor = cfg.get("server", "")
    banco    = cfg.get("database", "")
    usuario  = cfg.get("username", "")
    senha    = cfg.get("password", "")
    porta    = int(cfg.get("port", 1433))
    timeout  = int(cfg.get("timeout", 30))
    short_name = servidor.split(".")[0] if servidor else ""
    driver_cfg = str(cfg.get("driver", "pymssql")).strip()
    usa_pyodbc = "odbc" in driver_cfg.lower()
    eh_azure_ad = bool(usuario) and "@" in usuario and not usuario.lower().endswith(f"@{short_name.lower()}")
    autenticacao = cfg.get("authentication", "ActiveDirectoryPassword" if eh_azure_ad else None)

    senha_masc = (senha[:2] + "•" * max(len(senha) - 2, 0)) if senha else "(VAZIA — verifique o secrets.toml!)"

    if usa_pyodbc:
        odbc_driver_desejado = driver_cfg if "odbc driver" in driver_cfg.lower() else cfg.get(
            "odbc_driver", "ODBC Driver 18 for SQL Server"
        )
        odbc_driver = _melhor_driver_odbc(odbc_driver_desejado)
        auth_lower = (autenticacao or "").lower()
        SEM_SENHA = {"activedirectoryinteractive", "activedirectoryintegrated",
                     "activedirectorydevicecodeflow", "activedirectorymsi"}
        incluir_uid = auth_lower != "activedirectoryintegrated"
        incluir_pwd = auth_lower not in SEM_SENHA
        partes = [f"DRIVER={{{odbc_driver}}}", f"SERVER=tcp:{servidor},{porta}", f"DATABASE={banco}"]
        if incluir_uid: partes.append(f"UID={usuario}")
        if incluir_pwd: partes.append(f"PWD={senha_masc}")
        partes += ["Encrypt=yes", "TrustServerCertificate=no", f"Connection Timeout={timeout}"]
        if autenticacao: partes.append(f"Authentication={autenticacao}")
        conn_str_masc = ";".join(partes) + ";"
    else:
        conn_str_masc = (
            f"mssql+pymssql — usuário={usuario if '@' in usuario else f'{usuario}@{short_name}'}, "
            f"senha={senha_masc}, host={servidor}:{porta}, banco={banco}, tds_version=7.4"
        )

    drivers_instalados = None
    pyodbc_versao = None
    try:
        import pyodbc
        pyodbc_versao = pyodbc.version
        drivers_instalados = [d for d in pyodbc.drivers() if "SQL Server" in d]
    except Exception:
        pass

    return {
        "driver_cfg": driver_cfg,
        "odbc_driver_usado": odbc_driver if usa_pyodbc else None,
        "usa_pyodbc": usa_pyodbc, "eh_azure_ad": eh_azure_ad,
        "autenticacao": autenticacao, "conn_str_masc": conn_str_masc,
        "pyodbc_versao": pyodbc_versao, "drivers_instalados": drivers_instalados,
    }


def _testar_conexao() -> tuple[bool, str]:
    try:
        with _engine().connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        return True, ""
    except Exception as e:
        return False, str(e)


@st.cache_data(ttl=180, show_spinner=False)
def _scalar(sql: str, params: dict) -> float:
    with _engine().connect() as conn:
        v = conn.execute(sa.text(sql), params).scalar()
    return float(v) if v is not None else 0.0


@st.cache_data(ttl=180, show_spinner=False)
def _df(sql: str, params: dict) -> pd.DataFrame:
    with _engine().connect() as conn:
        return pd.read_sql(sa.text(sql), conn, params=params)


def _filtro_consultor(consultores: list | None, params: dict, prefixo="c", coluna: str = None) -> str:
    """Gera cláusula SQL 'AND <coluna> IN (...)' parametrizada (default: CONSULTOR)."""
    if not consultores:
        return ""
    coluna = coluna or COL_SF_CONSULTOR
    chaves = []
    for i, nome in enumerate(consultores):
        k = f"{prefixo}{i}"
        params[k] = nome
        chaves.append(f":{k}")
    return f" AND {coluna} IN ({','.join(chaves)})"


# ══════════════════════════════════════════════════════════════════════════
# CRUZAMENTO CONSULTOR ↔ COLABORADORES ↔ USUÁRIOS DO SISTEMA
# ══════════════════════════════════════════════════════════════════════════
def _normalizar_nome(nome: str) -> str:
    """Normaliza nome para comparação robusta (case/espaços não derrubam o match)."""
    return " ".join(str(nome).strip().split()).casefold()


@st.cache_data(ttl=600, show_spinner=False)
def _usuarios_sistema() -> set:
    try:
        df_u = carregar_usuarios()
        col_nome = get_col(df_u, ["Nome", "nome"]) or "Nome"
        return set(df_u[col_nome].dropna().astype(str).str.strip()) if not df_u.empty else set()
    except Exception:
        return set()


@st.cache_data(ttl=600, show_spinner=False)
def _consultores_por_gestor(gestor_nome: str) -> list:
    """
    Retorna os consultores (incluindo o próprio gestor) que reportam a um
    gestor, cruzando tbColaboradores com os usuários cadastrados no sistema.
    """
    try:
        sql = f"SELECT {COL_COLAB_NOME} AS nome, {COL_COLAB_GESTOR} AS gestor FROM {TBL_COLAB}"
        df_colab = _df(sql, {})
    except Exception:
        return [gestor_nome]

    if df_colab.empty:
        return [gestor_nome]

    df_colab["nome"]   = df_colab["nome"].astype(str).str.strip()
    df_colab["gestor"] = df_colab["gestor"].astype(str).str.strip()

    equipe = set(
        df_colab[df_colab["gestor"].str.lower() == gestor_nome.strip().lower()]["nome"].tolist()
    )
    equipe.add(gestor_nome.strip())

    nomes_sistema = _usuarios_sistema()
    if nomes_sistema:
        equipe_valida = {n for n in equipe if n in nomes_sistema}
        if equipe_valida:
            return sorted(equipe_valida)
    return sorted(equipe)


@st.cache_data(ttl=600, show_spinner=False)
def _tabela_colaboradores() -> pd.DataFrame:
    """Colunas: nome, frente, resultado, gerente, agente."""
    sql = f"""
        SELECT {COL_COLAB_NOME} AS nome, {COL_COLAB_FRENTE} AS frente,
               {COL_COLAB_RESULTADO} AS resultado, {COL_COLAB_GESTOR} AS gerente,
               {COL_COLAB_AGENTE} AS agente
        FROM {TBL_COLAB}
    """
    try:
        df = _df(sql, {})
    except Exception:
        return pd.DataFrame(columns=["nome", "frente", "resultado", "gerente", "agente"])
    for c in ["nome", "frente", "resultado", "gerente"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    return df


@st.cache_data(ttl=180, show_spinner=False)
def _ligacoes_por_consultor(ini: date, fim: date) -> pd.DataFrame:
    """
    Conta ligações em tbUsCall por consultor, cruzando NUM_AGENTE com o
    campo Agente de tbColaboradores. Retorna colunas: consultor, ligacoes.
    """
    df_colab = _tabela_colaboradores()
    if df_colab.empty or "agente" not in df_colab.columns:
        return pd.DataFrame(columns=["consultor", "ligacoes"])

    sql = f"""
        SELECT {COL_CALL_AGENTE} AS agente, COUNT(*) AS ligacoes
        FROM {TBL_CALLS}
        WHERE {COL_CALL_DATAHORA} BETWEEN :ini AND :fim
        GROUP BY {COL_CALL_AGENTE}
    """
    try:
        df_calls = _df(sql, {"ini": ini, "fim": fim})
    except Exception:
        return pd.DataFrame(columns=["consultor", "ligacoes"])

    if df_calls.empty:
        return pd.DataFrame(columns=["consultor", "ligacoes"])

    merged = df_calls.merge(
        df_colab[["nome", "agente"]], on="agente", how="left"
    )
    merged["consultor"] = merged["nome"].fillna("(agente não mapeado)")
    return merged.groupby("consultor", as_index=False)["ligacoes"].sum()


@st.cache_data(ttl=180, show_spinner=False)
def _entregas_e_previsao_por_consultor(ini: date, fim: date) -> pd.DataFrame:
    """
    "Entregues" e "Previsão de Entregar" vêm da planilha de Gestão de
    Veículos (Google Sheets, fonte oficial de confirmação de entrega),
    não do Azure SQL. Retorna colunas: consultor, entregues, previsao.
    """
    try:
        df_gv = gv_carregar()
    except Exception:
        return pd.DataFrame(columns=["consultor", "entregues", "previsao"])

    if df_gv.empty or "consultor" not in df_gv.columns:
        return pd.DataFrame(columns=["consultor", "entregues", "previsao"])

    df_gv = df_gv.copy()
    df_gv["_data_entrega_dt"] = df_gv.get("data_entrega", "").apply(parse_data)

    entregues = df_gv[
        (df_gv["status"] == "Entregue")
        & df_gv["_data_entrega_dt"].apply(lambda d: d is not None and ini <= d <= fim)
    ]
    tab_entregues = (
        entregues.groupby("consultor").size().reset_index(name="entregues")
        if not entregues.empty else pd.DataFrame(columns=["consultor", "entregues"])
    )

    # Previsão de Entregar: backlog ATUAL (vendido, ainda não entregue) —
    # não é filtrado por período, é uma foto do momento.
    pendentes = df_gv[df_gv["status"].isin(STATUS_PENDENTE_ENTREGA)]
    tab_previsao = (
        pendentes.groupby("consultor").size().reset_index(name="previsao")
        if not pendentes.empty else pd.DataFrame(columns=["consultor", "previsao"])
    )

    return tab_entregues.merge(tab_previsao, on="consultor", how="outer").fillna(0)


# ══════════════════════════════════════════════════════════════════════════
# HELPERS DE PERÍODO
# ══════════════════════════════════════════════════════════════════════════
def _periodo_mes(ref: date) -> tuple[date, date]:
    ultimo = calendar.monthrange(ref.year, ref.month)[1]
    return date(ref.year, ref.month, 1), date(ref.year, ref.month, ultimo)


def _mes_anterior_ref(ref: date) -> date:
    primeiro_dia = date(ref.year, ref.month, 1)
    return primeiro_dia - timedelta(days=1)


# ══════════════════════════════════════════════════════════════════════════
# QUERIES — GERAL
# ══════════════════════════════════════════════════════════════════════════
def _contratos_assinados(ini: date, fim: date, consultores=None) -> int:
    params = {"ini": ini, "fim": fim}
    sql = (f"SELECT COUNT(DISTINCT {COL_SF_SUBSCRIBER}) FROM {TBL_SF} "
           f"WHERE {COL_SF_DATA_ASSIN} BETWEEN :ini AND :fim")
    sql += _filtro_consultor(consultores, params)
    return int(_scalar(sql, params))


def _veiculos_assinados(ini: date, fim: date, consultores=None) -> int:
    params = {"ini": ini, "fim": fim}
    sql = (f"SELECT SUM({COL_SF_QTD_VEICULOS}) FROM {TBL_SF} "
           f"WHERE {COL_SF_DATA_ASSIN} BETWEEN :ini AND :fim")
    sql += _filtro_consultor(consultores, params)
    return int(_scalar(sql, params))


def _leads_gerados(ini: date, fim: date, consultores=None) -> int:
    params = {"ini": ini, "fim": fim}
    sql = (f"SELECT COUNT({COL_SF_SUBSCRIBER}) FROM {TBL_SF} "
           f"WHERE {COL_SF_DATA_CRIACAO} BETWEEN :ini AND :fim")
    sql += _filtro_consultor(consultores, params)
    return int(_scalar(sql, params))


def _leads_pescados(ini: date, fim: date, consultores=None) -> int:
    params = {"ini": ini, "fim": fim}
    sql = (f"SELECT COUNT({COL_SF_SUBSCRIBER}) FROM {TBL_SF} "
           f"WHERE {COL_SF_DATA_CAPTACAO} BETWEEN :ini AND :fim")
    sql += _filtro_consultor(consultores, params)
    return int(_scalar(sql, params))


@st.cache_data(ttl=180, show_spinner=False)
def _ranking_consultor(ini: date, fim: date, consultores=None) -> pd.DataFrame:
    """Leads gerados, pescados e contratos assinados por consultor no período."""
    params = {"ini": ini, "fim": fim}
    filtro = _filtro_consultor(consultores, params)
    sql = f"""
        SELECT {COL_SF_CONSULTOR} AS consultor,
               COUNT(DISTINCT CASE WHEN {COL_SF_DATA_ASSIN} BETWEEN :ini AND :fim
                     THEN {COL_SF_SUBSCRIBER} END) AS contratos,
               COUNT(CASE WHEN {COL_SF_DATA_CRIACAO} BETWEEN :ini AND :fim
                     THEN {COL_SF_SUBSCRIBER} END) AS leads_gerados,
               COUNT(CASE WHEN {COL_SF_DATA_CAPTACAO} BETWEEN :ini AND :fim
                     THEN {COL_SF_SUBSCRIBER} END) AS leads_pescados
        FROM {TBL_SF}
        WHERE 1=1 {filtro}
        GROUP BY {COL_SF_CONSULTOR}
        ORDER BY contratos DESC
    """
    return _df(sql, params)


@st.cache_data(ttl=180, show_spinner=False)
def _ranking_geral_consultor(ini: date, fim: date, consultores=None) -> pd.DataFrame:
    """
    Ranking completo de consultores do mês — usa RESPONSAVEL (não CONSULTOR)
    como nome, conforme especificado. Colunas: consultor, leads_pescados,
    assinados (soma de veículos, não contagem de contratos), ligacoes
    (tbUsCall via tbColaboradores.Agente), entregues (Gestão de Veículos) e
    conversao = leads_pescados / assinados.
    """
    params = {"ini": ini, "fim": fim}
    filtro = _filtro_consultor(consultores, params, coluna=COL_SF_RESPONSAVEL)
    sql = f"""
        SELECT {COL_SF_RESPONSAVEL} AS consultor,
               COUNT(CASE WHEN {COL_SF_DATA_CAPTACAO} BETWEEN :ini AND :fim
                     THEN {COL_SF_SUBSCRIBER} END) AS leads_pescados,
               SUM(CASE WHEN {COL_SF_DATA_ASSIN} BETWEEN :ini AND :fim
                     THEN {COL_SF_QTD_VEICULOS} ELSE 0 END) AS assinados
        FROM {TBL_SF}
        WHERE 1=1 {filtro}
        GROUP BY {COL_SF_RESPONSAVEL}
    """
    df = _df(sql, params)
    if not df.empty:
        df["consultor"] = df["consultor"].astype(str).str.strip()

    ligacoes = _ligacoes_por_consultor(ini, fim)
    entregas = _entregas_e_previsao_por_consultor(ini, fim)

    df = df.merge(ligacoes, on="consultor", how="outer")
    if not entregas.empty:
        df = df.merge(entregas[["consultor", "entregues"]], on="consultor", how="outer")

    for c in ["leads_pescados", "assinados", "ligacoes", "entregues"]:
        if c not in df.columns:
            df[c] = 0
        df[c] = df[c].fillna(0)

    df["conversao"] = df.apply(
        lambda r: (r["leads_pescados"] / r["assinados"] * 100) if r["assinados"] else 0.0, axis=1
    )
    df["meta"] = "—"  # Meta do mês — a configurar futuramente

    return df.sort_values("assinados", ascending=False)


@st.cache_data(ttl=180, show_spinner=False)
def _curva_contratos(ini: date, fim: date, consultores=None) -> pd.DataFrame:
    params = {"ini": ini, "fim": fim}
    filtro = _filtro_consultor(consultores, params)
    sql = f"""
        SELECT CAST({COL_SF_DATA_ASSIN} AS DATE) AS dia,
               COUNT(DISTINCT {COL_SF_SUBSCRIBER}) AS contratos
        FROM {TBL_SF}
        WHERE {COL_SF_DATA_ASSIN} BETWEEN :ini AND :fim {filtro}
        GROUP BY CAST({COL_SF_DATA_ASSIN} AS DATE)
        ORDER BY dia
    """
    return _df(sql, params)


MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
    7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


@st.cache_data(ttl=180, show_spinner=False)
def _curva_generica_sf(coluna_data: str, expressao_valor: str, ini: date, fim: date,
                        consultores=None) -> pd.DataFrame:
    """Curva diária genérica sobre tbConsolidaSalesforce (retorna colunas: dia, valor)."""
    params = {"ini": ini, "fim": fim}
    filtro = _filtro_consultor(consultores, params)
    sql = f"""
        SELECT CAST({coluna_data} AS DATE) AS dia, {expressao_valor} AS valor
        FROM {TBL_SF}
        WHERE {coluna_data} BETWEEN :ini AND :fim {filtro}
        GROUP BY CAST({coluna_data} AS DATE)
        ORDER BY dia
    """
    return _df(sql, params)


def _comparativo_mensal_sf(coluna_data: str, expressao_valor: str,
                            mes_ini: date, mes_fim: date,
                            mes_ant_ini: date, mes_ant_fim: date,
                            consultores=None) -> pd.DataFrame:
    """
    Monta DataFrame indexado por dia-do-mês (1..31) com duas colunas
    (mês atual x mês anterior) para sobrepor num único gráfico de linha.
    """
    atual = _curva_generica_sf(coluna_data, expressao_valor, mes_ini, mes_fim, consultores)
    anterior = _curva_generica_sf(coluna_data, expressao_valor, mes_ant_ini, mes_ant_fim, consultores)

    label_atual = f"{MESES_PT[mes_fim.month]}/{mes_fim.year}"
    label_ant   = f"{MESES_PT[mes_ant_fim.month]}/{mes_ant_fim.year}"

    ultimo_dia = max(mes_fim.day, mes_ant_fim.day)
    base = pd.DataFrame({"dia_mes": range(1, ultimo_dia + 1)}).set_index("dia_mes")

    if not atual.empty:
        atual = atual.copy()
        atual["dia_mes"] = pd.to_datetime(atual["dia"]).dt.day
        base[label_atual] = atual.set_index("dia_mes")["valor"]
    else:
        base[label_atual] = 0

    if not anterior.empty:
        anterior = anterior.copy()
        anterior["dia_mes"] = pd.to_datetime(anterior["dia"]).dt.day
        base[label_ant] = anterior.set_index("dia_mes")["valor"]
    else:
        base[label_ant] = 0

    return base.fillna(0)


# ══════════════════════════════════════════════════════════════════════════
# QUERIES — MARKETING
# ══════════════════════════════════════════════════════════════════════════
def _investimento(ini: date, fim: date, plataforma: str = None) -> float:
    params = {"ini": ini, "fim": fim}
    sql = (f"SELECT SUM({COL_MKT_INVESTIMENTO}) FROM {TBL_MKT} "
           f"WHERE {COL_MKT_DIA} BETWEEN :ini AND :fim")
    if plataforma:
        sql += f" AND {COL_MKT_PLATAFORMA} = :plat"
        params["plat"] = plataforma
    return _scalar(sql, params)


@st.cache_data(ttl=180, show_spinner=False)
def _mkt_totais(ini: date, fim: date) -> dict:
    """Investimento + Clicks + Impressões somados no período, numa só query."""
    sql = f"""
        SELECT SUM({COL_MKT_INVESTIMENTO}) AS investimento,
               SUM({COL_MKT_CLICKS}) AS clicks,
               SUM({COL_MKT_IMPRESSOES}) AS impressoes
        FROM {TBL_MKT}
        WHERE {COL_MKT_DIA} BETWEEN :ini AND :fim
    """
    df = _df(sql, {"ini": ini, "fim": fim})
    if df.empty:
        return {"investimento": 0.0, "clicks": 0.0, "impressoes": 0.0}
    r = df.iloc[0]
    return {
        "investimento": float(r["investimento"] or 0),
        "clicks": float(r["clicks"] or 0),
        "impressoes": float(r["impressoes"] or 0),
    }


@st.cache_data(ttl=180, show_spinner=False)
def _leads_por_midia_dia(ini: date, fim: date) -> pd.DataFrame:
    """Volume de leads por dia, pivotado por Mídia (tbConsolidaSalesforce)."""
    sql = f"""
        SELECT CAST({COL_SF_DATA_CRIACAO} AS DATE) AS dia,
               {COL_SF_MIDIA} AS midia, COUNT(*) AS volume
        FROM {TBL_SF}
        WHERE {COL_SF_DATA_CRIACAO} BETWEEN :ini AND :fim
        GROUP BY CAST({COL_SF_DATA_CRIACAO} AS DATE), {COL_SF_MIDIA}
        ORDER BY dia
    """
    df = _df(sql, {"ini": ini, "fim": fim})
    if df.empty:
        return df
    df["midia"] = df["midia"].fillna("(sem mídia)")
    return df.pivot_table(index="dia", columns="midia", values="volume", aggfunc="sum").fillna(0)


@st.cache_data(ttl=180, show_spinner=False)
def _conversoes_por_canal_dia(ini: date, fim: date) -> pd.DataFrame:
    """
    Volume de "conversões" por dia, pivotado por Plataforma (canal), a
    partir de mkt.ConsolidadoCampanhas — contagem de registros por
    Plataforma × Dia_Campanha (sem coluna dedicada de conversões na
    origem, conforme orientado).
    """
    sql = f"""
        SELECT CAST({COL_MKT_DIA} AS DATE) AS dia,
               {COL_MKT_PLATAFORMA} AS canal, COUNT(*) AS volume
        FROM {TBL_MKT}
        WHERE {COL_MKT_DIA} BETWEEN :ini AND :fim
        GROUP BY CAST({COL_MKT_DIA} AS DATE), {COL_MKT_PLATAFORMA}
        ORDER BY dia
    """
    df = _df(sql, {"ini": ini, "fim": fim})
    if df.empty:
        return df
    df["canal"] = df["canal"].fillna("(sem canal)")
    return df.pivot_table(index="dia", columns="canal", values="volume", aggfunc="sum").fillna(0)


@st.cache_data(ttl=180, show_spinner=False)
def _curva_investimento(ini: date, fim: date) -> pd.DataFrame:
    sql = f"""
        SELECT CAST({COL_MKT_DIA} AS DATE) AS dia, {COL_MKT_PLATAFORMA} AS plataforma,
               SUM({COL_MKT_INVESTIMENTO}) AS investimento
        FROM {TBL_MKT}
        WHERE {COL_MKT_DIA} BETWEEN :ini AND :fim
        GROUP BY CAST({COL_MKT_DIA} AS DATE), {COL_MKT_PLATAFORMA}
        ORDER BY dia
    """
    return _df(sql, {"ini": ini, "fim": fim})


@st.cache_data(ttl=180, show_spinner=False)
def _comparativo_mensal_investimento(mes_ini: date, mes_fim: date,
                                      mes_ant_ini: date, mes_ant_fim: date) -> pd.DataFrame:
    """Investimento total por dia-do-mês, mês atual x mês anterior."""
    sql = f"""
        SELECT CAST({COL_MKT_DIA} AS DATE) AS dia, SUM({COL_MKT_INVESTIMENTO}) AS valor
        FROM {TBL_MKT}
        WHERE {COL_MKT_DIA} BETWEEN :ini AND :fim
        GROUP BY CAST({COL_MKT_DIA} AS DATE)
        ORDER BY dia
    """
    atual = _df(sql, {"ini": mes_ini, "fim": mes_fim})
    anterior = _df(sql, {"ini": mes_ant_ini, "fim": mes_ant_fim})

    label_atual = f"{MESES_PT[mes_fim.month]}/{mes_fim.year}"
    label_ant   = f"{MESES_PT[mes_ant_fim.month]}/{mes_ant_fim.year}"

    ultimo_dia = max(mes_fim.day, mes_ant_fim.day)
    base = pd.DataFrame({"dia_mes": range(1, ultimo_dia + 1)}).set_index("dia_mes")

    if not atual.empty:
        atual = atual.copy()
        atual["dia_mes"] = pd.to_datetime(atual["dia"]).dt.day
        base[label_atual] = atual.set_index("dia_mes")["valor"]
    else:
        base[label_atual] = 0

    if not anterior.empty:
        anterior = anterior.copy()
        anterior["dia_mes"] = pd.to_datetime(anterior["dia"]).dt.day
        base[label_ant] = anterior.set_index("dia_mes")["valor"]
    else:
        base[label_ant] = 0

    return base.fillna(0)


# ══════════════════════════════════════════════════════════════════════════
# COMPONENTES VISUAIS
# ══════════════════════════════════════════════════════════════════════════
def _fmt_num(v) -> str:
    try:
        return f"{int(v):,}".replace(",", ".")
    except Exception:
        return "0"


def _fmt_brl(v) -> str:
    try:
        s = f"{float(v):,.2f}"
        return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def _fmt_pct(v) -> str:
    try:
        return f"{float(v):.2f}%".replace(".", ",")
    except Exception:
        return "0,00%"


def _safe_div(a, b):
    return (a / b) if b else 0.0


def _variacao(atual: float, anterior: float, inverter: bool = False) -> tuple[str, str]:
    """
    Retorna (texto, classe css) da variação percentual MoM.
    `inverter=True` para métricas de custo, onde SUBIR é ruim (vermelho) e
    DESCER é bom (verde) — ex.: CAC, CPL, CPC, CPM.
    """
    if not anterior:
        return ("—", "pf-flat")
    pct = ((atual / anterior) - 1) * 100
    if abs(pct) < 0.5:
        return (f"◼ {pct:+.1f}%", "pf-flat")
    seta = "▲" if pct > 0 else "▼"
    bom  = (pct < 0) if inverter else (pct > 0)
    cls  = "pf-up" if bom else "pf-down"
    return (f"{seta} {pct:+.1f}%", cls)


def _variacao_pp(atual: float, anterior: float) -> tuple[str, str]:
    """Variação em pontos percentuais (p.p.) — para métricas que já são %."""
    diff = atual - anterior
    if abs(diff) < 0.05:
        return (f"◼ {diff:+.2f} p.p.", "pf-flat")
    seta = "▲" if diff > 0 else "▼"
    cls  = "pf-up" if diff > 0 else "pf-down"
    return (f"{seta} {diff:+.2f} p.p.", cls)


def _kpi_html(label, valor_fmt, atual, anterior, icon="", inverter=False) -> str:
    txt, cls = _variacao(atual, anterior, inverter=inverter)
    return f"""<div class="pf-kpi">
        <div class="pf-kpi-label">{icon} {label}</div>
        <div class="pf-kpi-val">{valor_fmt}</div>
        <div class="pf-kpi-delta {cls}">{txt} vs mês anterior</div>
    </div>"""


def _kpi_html_pct(label, atual_pct, anterior_pct, icon="") -> str:
    """KPI cujo valor já é percentual (CTR/CLR/CVR) — compara em p.p."""
    txt, cls = _variacao_pp(atual_pct, anterior_pct)
    return f"""<div class="pf-kpi">
        <div class="pf-kpi-label">{icon} {label}</div>
        <div class="pf-kpi-val">{_fmt_pct(atual_pct)}</div>
        <div class="pf-kpi-delta {cls}">{txt} vs mês anterior</div>
    </div>"""


def _tabela_ranking(df: pd.DataFrame) -> str:
    usuarios = _usuarios_sistema()
    rows = ""
    for _, r in df.iterrows():
        nome = str(r["consultor"])
        badge = ('<span class="pf-badge-ok">No sistema</span>' if nome in usuarios
                 else '<span class="pf-badge-off">Não cadastrado</span>')
        rows += (f"<tr><td><b>{nome}</b></td><td>{badge}</td>"
                 f"<td>{_fmt_num(r.get('leads_gerados',0))}</td>"
                 f"<td>{_fmt_num(r.get('leads_pescados',0))}</td>"
                 f"<td>{_fmt_num(r.get('contratos',0))}</td></tr>")
    return f"""<table class="pf-tabela">
        <thead><tr><th>Consultor</th><th>Sistema</th><th>Leads Gerados</th>
        <th>Leads Pescados</th><th>Contratos</th></tr></thead>
        <tbody>{rows}</tbody></table>"""


def _tabela_ranking_geral_html(df: pd.DataFrame) -> str:
    """Ranking completo: Consultor, Meta, Ligações, Leads Pescados, Assinados (veículos), Entregues, Conversão."""
    rows = ""
    for _, r in df.iterrows():
        nome = str(r["consultor"])
        if not nome or nome.lower() in ("nan", "none"):
            continue
        rows += (
            f"<tr><td><b>{nome}</b></td>"
            f"<td>{r.get('meta', '—')}</td>"
            f"<td>{_fmt_num(r.get('ligacoes', 0))}</td>"
            f"<td>{_fmt_num(r.get('leads_pescados', 0))}</td>"
            f"<td>{_fmt_num(r.get('assinados', 0))}</td>"
            f"<td>{_fmt_num(r.get('entregues', 0))}</td>"
            f"<td><b>{r.get('conversao', 0):.1f}%</b></td></tr>"
        )
    return f"""<table class="pf-tabela">
        <thead><tr><th>Consultor</th><th>Meta do Mês</th><th>Ligações</th>
        <th>Leads Pescados</th><th>Assinados</th><th>Entregues</th><th>Conversão</th></tr></thead>
        <tbody>{rows}</tbody></table>"""


# ══════════════════════════════════════════════════════════════════════════
# RENDER — PÁGINA "GERAL" (reaproveitada por Operação Geral / SP / Santos)
# ══════════════════════════════════════════════════════════════════════════
def _render_pagina_indicadores(titulo: str, consultores=None):
    hoje = date.today()
    ontem = hoje - timedelta(days=1)
    mes_ini, mes_fim = _periodo_mes(hoje)
    ref_ant = _mes_anterior_ref(hoje)
    mes_ant_ini, mes_ant_fim = _periodo_mes(ref_ant)

    with st.spinner("Consultando Azure SQL..."):
        contratos_atual = _contratos_assinados(mes_ini, mes_fim, consultores)
        contratos_ant   = _contratos_assinados(mes_ant_ini, mes_ant_fim, consultores)

        veic_atual = _veiculos_assinados(mes_ini, mes_fim, consultores)
        veic_ant   = _veiculos_assinados(mes_ant_ini, mes_ant_fim, consultores)

        leads_ger_atual = _leads_gerados(mes_ini, mes_fim, consultores)
        leads_ger_ant   = _leads_gerados(mes_ant_ini, mes_ant_fim, consultores)

        leads_dia_atual = _leads_pescados(hoje, hoje, consultores)
        leads_dia_ant   = _leads_pescados(ontem, ontem, consultores)

        leads_mes_atual = _leads_pescados(mes_ini, mes_fim, consultores)
        leads_mes_ant   = _leads_pescados(mes_ant_ini, mes_ant_fim, consultores)

    st.markdown(f'<div class="pf-card-titulo" style="border:none;font-size:14px">{titulo}</div>',
                unsafe_allow_html=True)

    st.markdown(f"""<div class="pf-kpi-grid">
        {_kpi_html("Contratos Assinados", _fmt_num(contratos_atual), contratos_atual, contratos_ant, "✍️")}
        {_kpi_html("Veículos Assinados", _fmt_num(veic_atual), veic_atual, veic_ant, "🚗")}
        {_kpi_html("Leads Gerados (mês)", _fmt_num(leads_ger_atual), leads_ger_atual, leads_ger_ant, "📥")}
        {_kpi_html("Leads Pescados (dia)", _fmt_num(leads_dia_atual), leads_dia_atual, leads_dia_ant, "🎣")}
        {_kpi_html("Leads Pescados (mês)", _fmt_num(leads_mes_atual), leads_mes_atual, leads_mes_ant, "🎯")}
    </div>""", unsafe_allow_html=True)

    # ── Comparativo mensal: mês atual x mês anterior (grid 2x2) ─────────────
    st.markdown('<div class="pf-card-titulo" style="border:none;font-size:14px;margin-top:6px">'
                '📊 Comparativo · Mês Atual vs. Mês Anterior</div>', unsafe_allow_html=True)

    with st.spinner("Montando curvas comparativas..."):
        curva_contratos_cmp = _comparativo_mensal_sf(
            COL_SF_DATA_ASSIN, f"COUNT(DISTINCT {COL_SF_SUBSCRIBER})",
            mes_ini, mes_fim, mes_ant_ini, mes_ant_fim, consultores)
        curva_veic_cmp = _comparativo_mensal_sf(
            COL_SF_DATA_ASSIN, f"SUM({COL_SF_QTD_VEICULOS})",
            mes_ini, mes_fim, mes_ant_ini, mes_ant_fim, consultores)
        curva_leads_ger_cmp = _comparativo_mensal_sf(
            COL_SF_DATA_CRIACAO, f"COUNT({COL_SF_SUBSCRIBER})",
            mes_ini, mes_fim, mes_ant_ini, mes_ant_fim, consultores)
        curva_leads_pesc_cmp = _comparativo_mensal_sf(
            COL_SF_DATA_CAPTACAO, f"COUNT({COL_SF_SUBSCRIBER})",
            mes_ini, mes_fim, mes_ant_ini, mes_ant_fim, consultores)

    cc1, cc2 = st.columns(2)
    with cc1:
        st.markdown('<div class="pf-card">', unsafe_allow_html=True)
        st.markdown('<div class="pf-card-titulo">✍️ Contratos Assinados por dia do mês</div>',
                    unsafe_allow_html=True)
        st.line_chart(curva_contratos_cmp, height=220)
        st.markdown('</div>', unsafe_allow_html=True)
    with cc2:
        st.markdown('<div class="pf-card">', unsafe_allow_html=True)
        st.markdown('<div class="pf-card-titulo">🚗 Veículos Assinados por dia do mês</div>',
                    unsafe_allow_html=True)
        st.line_chart(curva_veic_cmp, height=220)
        st.markdown('</div>', unsafe_allow_html=True)

    cc3, cc4 = st.columns(2)
    with cc3:
        st.markdown('<div class="pf-card">', unsafe_allow_html=True)
        st.markdown('<div class="pf-card-titulo">📥 Leads Gerados por dia do mês</div>',
                    unsafe_allow_html=True)
        st.line_chart(curva_leads_ger_cmp, height=220)
        st.markdown('</div>', unsafe_allow_html=True)
    with cc4:
        st.markdown('<div class="pf-card">', unsafe_allow_html=True)
        st.markdown('<div class="pf-card-titulo">🎣 Leads Pescados por dia do mês</div>',
                    unsafe_allow_html=True)
        st.line_chart(curva_leads_pesc_cmp, height=220)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Curva acumulada de contratos ─────────────────────────────────────
    st.markdown('<div class="pf-card">', unsafe_allow_html=True)
    st.markdown('<div class="pf-card-titulo">📈 Curva Acumulada de Contratos (mês atual)</div>',
                unsafe_allow_html=True)
    curva = _curva_contratos(mes_ini, mes_fim, consultores)
    if curva.empty:
        st.info("Sem contratos assinados no período.")
    else:
        curva = curva.set_index("dia")
        curva["acumulado"] = curva["contratos"].cumsum()
        st.line_chart(curva[["acumulado"]], height=240, color=DOURADO)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── Ranking de Consultores (mês atual) — largura total ───────────────
    st.markdown('<div class="pf-card">', unsafe_allow_html=True)
    st.markdown('<div class="pf-card-titulo">🧑‍💼 Ranking de Consultores (mês atual)</div>',
                unsafe_allow_html=True)
    with st.spinner("Cruzando Azure SQL + tbUsCall + Gestão de Veículos..."):
        rank_geral = _ranking_geral_consultor(mes_ini, mes_fim, consultores)

    if not rank_geral.empty:
        usuarios_sistema = _usuarios_sistema()
        usuarios_norm = {_normalizar_nome(u) for u in usuarios_sistema}
        rank_geral = rank_geral[
            rank_geral["consultor"].apply(lambda n: _normalizar_nome(n) in usuarios_norm)
        ]
        rank_geral = rank_geral.sort_values("assinados", ascending=False)

    if rank_geral.empty:
        st.info("Sem dados no período.")
    else:
        st.markdown(_tabela_ranking_geral_html(rank_geral), unsafe_allow_html=True)
        st.caption(
            "Somente consultores cadastrados no sistema · ordenado por Assinados (maior → menor) · "
            "Assinados = quantidade de veículos (não de contratos) · "
            "Entregues vem da Gestão de Veículos · "
            "Conversão = Leads Pescados ÷ Assinados · "
            "Meta do Mês ainda não configurada."
        )
    st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# RENDER — PÁGINA "MARKETING"
# ══════════════════════════════════════════════════════════════════════════
def _render_pagina_marketing():
    hoje = date.today()
    mes_ini, mes_fim = _periodo_mes(hoje)
    ref_ant = _mes_anterior_ref(hoje)
    mes_ant_ini, mes_ant_fim = _periodo_mes(ref_ant)

    with st.spinner("Consultando Azure SQL..."):
        inv_total_atual = _investimento(mes_ini, mes_fim)
        inv_total_ant   = _investimento(mes_ant_ini, mes_ant_fim)

        inv_google_atual = _investimento(mes_ini, mes_fim, "Google")
        inv_google_ant   = _investimento(mes_ant_ini, mes_ant_fim, "Google")

        inv_meta_atual = _investimento(mes_ini, mes_fim, "Meta")
        inv_meta_ant   = _investimento(mes_ant_ini, mes_ant_fim, "Meta")

        curva = _curva_investimento(mes_ini, mes_fim)

        # ── Dados-base para os KPIs de eficiência ────────────────────────
        mkt_atual = _mkt_totais(mes_ini, mes_fim)
        mkt_ant   = _mkt_totais(mes_ant_ini, mes_ant_fim)

        contratos_atual = _contratos_assinados(mes_ini, mes_fim)
        contratos_ant   = _contratos_assinados(mes_ant_ini, mes_ant_fim)

        veic_atual = _veiculos_assinados(mes_ini, mes_fim)
        veic_ant   = _veiculos_assinados(mes_ant_ini, mes_ant_fim)

        leads_atual = _leads_gerados(mes_ini, mes_fim)
        leads_ant   = _leads_gerados(mes_ant_ini, mes_ant_fim)

        leads_midia_curva = _leads_por_midia_dia(mes_ini, mes_fim)
        conversoes_canal_curva = _conversoes_por_canal_dia(mes_ini, mes_fim)

    # ── KPI principal: volume de vendas ──────────────────────────────────
    st.markdown(f"""<div class="pf-kpi-grid" style="grid-template-columns:repeat(2,1fr)">
        {_kpi_html("Contratos Assinados", _fmt_num(contratos_atual), contratos_atual, contratos_ant, "✍️")}
        {_kpi_html("Veículos Assinados", _fmt_num(veic_atual), veic_atual, veic_ant, "🚗")}
    </div>""", unsafe_allow_html=True)

    st.markdown(f"""<div class="pf-kpi-grid" style="grid-template-columns:repeat(3,1fr)">
        {_kpi_html("Investimento Total", _fmt_brl(inv_total_atual), inv_total_atual, inv_total_ant, "💰")}
        {_kpi_html("Investimento Google", _fmt_brl(inv_google_atual), inv_google_atual, inv_google_ant, "🔍")}
        {_kpi_html("Investimento Meta", _fmt_brl(inv_meta_atual), inv_meta_atual, inv_meta_ant, "📘")}
    </div>""", unsafe_allow_html=True)

    # ── KPIs de eficiência (custo por resultado) ─────────────────────────
    cac_atual = _safe_div(mkt_atual["investimento"], contratos_atual)
    cac_ant   = _safe_div(mkt_ant["investimento"], contratos_ant)

    cpl_atual = _safe_div(mkt_atual["investimento"], leads_atual)
    cpl_ant   = _safe_div(mkt_ant["investimento"], leads_ant)

    cpc_atual = _safe_div(mkt_atual["investimento"], mkt_atual["clicks"])
    cpc_ant   = _safe_div(mkt_ant["investimento"], mkt_ant["clicks"])

    cpm_atual = _safe_div(mkt_atual["investimento"], mkt_atual["impressoes"]) * 1000
    cpm_ant   = _safe_div(mkt_ant["investimento"], mkt_ant["impressoes"]) * 1000

    st.markdown('<div class="pf-card-titulo" style="border:none;font-size:14px;margin-top:6px">'
                '💸 Custo por Resultado</div>', unsafe_allow_html=True)
    st.markdown(f"""<div class="pf-kpi-grid" style="grid-template-columns:repeat(4,1fr)">
        {_kpi_html("CAC · Custo por Venda", _fmt_brl(cac_atual), cac_atual, cac_ant, "🎯", inverter=True)}
        {_kpi_html("CPL · Custo por Lead", _fmt_brl(cpl_atual), cpl_atual, cpl_ant, "📥", inverter=True)}
        {_kpi_html("CPC · Custo por Clique", _fmt_brl(cpc_atual), cpc_atual, cpc_ant, "🖱️", inverter=True)}
        {_kpi_html("CPM · Custo/mil Impressões", _fmt_brl(cpm_atual), cpm_atual, cpm_ant, "👁️", inverter=True)}
    </div>""", unsafe_allow_html=True)

    # ── KPIs de taxa/eficiência do funil (%) ─────────────────────────────
    ctr_atual = _safe_div(mkt_atual["clicks"], mkt_atual["impressoes"]) * 100
    ctr_ant   = _safe_div(mkt_ant["clicks"], mkt_ant["impressoes"]) * 100

    clr_atual = _safe_div(leads_atual, mkt_atual["impressoes"]) * 100
    clr_ant   = _safe_div(leads_ant, mkt_ant["impressoes"]) * 100

    cvr_atual = _safe_div(contratos_atual, leads_atual) * 100
    cvr_ant   = _safe_div(contratos_ant, leads_ant) * 100

    st.markdown('<div class="pf-card-titulo" style="border:none;font-size:14px;margin-top:6px">'
                '🔻 Funil de Conversão (%)</div>', unsafe_allow_html=True)
    st.markdown(f"""<div class="pf-kpi-grid" style="grid-template-columns:repeat(3,1fr)">
        {_kpi_html_pct("CTR · Clique/Impressão", ctr_atual, ctr_ant, "👆")}
        {_kpi_html_pct("CLR · Lead/Impressão", clr_atual, clr_ant, "🧲")}
        {_kpi_html_pct("CVR · Venda/Lead", cvr_atual, cvr_ant, "✅")}
    </div>""", unsafe_allow_html=True)

    # ── Comparativo mensal: investimento total mês atual x mês anterior ─────
    st.markdown('<div class="pf-card">', unsafe_allow_html=True)
    st.markdown('<div class="pf-card-titulo">📊 Investimento Total · Mês Atual vs. Mês Anterior</div>',
                unsafe_allow_html=True)
    curva_inv_cmp = _comparativo_mensal_investimento(mes_ini, mes_fim, mes_ant_ini, mes_ant_fim)
    st.line_chart(curva_inv_cmp, height=240)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── Volume de leads por Mídia / Conversões por Canal (dia a dia) ────────
    cm1, cm2 = st.columns(2)
    with cm1:
        st.markdown('<div class="pf-card">', unsafe_allow_html=True)
        st.markdown('<div class="pf-card-titulo">📥 Volume de Leads por Mídia (dia a dia)</div>',
                    unsafe_allow_html=True)
        if leads_midia_curva.empty:
            st.info("Sem leads no período.")
        else:
            st.line_chart(leads_midia_curva, height=260)
        st.markdown('</div>', unsafe_allow_html=True)
    with cm2:
        st.markdown('<div class="pf-card">', unsafe_allow_html=True)
        st.markdown('<div class="pf-card-titulo">🔁 Volume de Conversões por Canal (dia a dia)</div>',
                    unsafe_allow_html=True)
        if conversoes_canal_curva.empty:
            st.info("Sem dados de campanha no período.")
        else:
            st.line_chart(conversoes_canal_curva, height=260)
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="pf-card">', unsafe_allow_html=True)
        st.markdown('<div class="pf-card-titulo">📈 Investimento Diário por Plataforma</div>',
                    unsafe_allow_html=True)
        if curva.empty:
            st.info("Sem dados de investimento no período.")
        else:
            piv = curva.pivot_table(index="dia", columns="plataforma", values="investimento", aggfunc="sum").fillna(0)
            st.line_chart(piv, height=260)
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="pf-card">', unsafe_allow_html=True)
        st.markdown('<div class="pf-card-titulo">📊 Participação por Plataforma (mês atual)</div>',
                    unsafe_allow_html=True)
        if curva.empty:
            st.info("Sem dados de investimento no período.")
        else:
            resumo = curva.groupby("plataforma")["investimento"].sum().sort_values(ascending=False)
            st.bar_chart(resumo, height=260, color=AZUL)
        st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# RENDER — PÁGINA "FRENTES" (padrão do Controle_Frentes)
# ══════════════════════════════════════════════════════════════════════════
def _tabela_frente_html(df: pd.DataFrame) -> str:
    usuarios = _usuarios_sistema()
    rows = ""
    for _, r in df.iterrows():
        nome = str(r["consultor"])
        badge = ('<span class="pf-badge-ok">No sistema</span>' if nome in usuarios
                 else '<span class="pf-badge-off">Não cadastrado</span>')
        conv = r.get("conversao", 0)
        conv_txt = f"{conv:.1f}%" if pd.notna(conv) else "—"
        rows += (
            f"<tr><td><b>{nome}</b></td><td>{badge}</td>"
            f"<td>{_fmt_num(r.get('ligacoes', 0))}</td>"
            f"<td>{_fmt_num(r.get('leads_pescados', 0))}</td>"
            f"<td>{_fmt_num(r.get('assinados', 0))}</td>"
            f"<td>{_fmt_num(r.get('previsao', 0))}</td>"
            f"<td>{_fmt_num(r.get('entregues', 0))}</td>"
            f"<td><b>{conv_txt}</b></td></tr>"
        )
    return f"""<table class="pf-tabela">
        <thead><tr><th>Consultor</th><th>Sistema</th><th>Ligações</th>
        <th>Leads Pescados</th><th>Assinados</th><th>Previsão Entregar</th>
        <th>Entregues</th><th>Conversão</th></tr></thead>
        <tbody>{rows}</tbody></table>"""


def _montar_tabela_frente(ini: date, fim: date, consultores_frente: list) -> pd.DataFrame:
    """
    Monta a tabela por consultor no padrão Controle_Frentes, cruzando:
    Azure (leads pescados, assinados) + tbUsCall (ligações) + Gestão de
    Veículos / Google Sheets (entregues, previsão de entregar).
    """
    rank_sf = _ranking_consultor(ini, fim, consultores_frente)  # contratos, leads_gerados, leads_pescados
    ligacoes = _ligacoes_por_consultor(ini, fim)
    entregas = _entregas_e_previsao_por_consultor(ini, fim)

    base = rank_sf.rename(columns={"contratos": "assinados"})[["consultor", "leads_pescados", "assinados"]]
    if consultores_frente:
        extras = pd.DataFrame({"consultor": [c for c in consultores_frente if c not in base["consultor"].values]})
        base = pd.concat([base, extras], ignore_index=True)
        base[["leads_pescados", "assinados"]] = base[["leads_pescados", "assinados"]].fillna(0)

    df = base.merge(ligacoes, on="consultor", how="left")
    df = df.merge(entregas, on="consultor", how="left")
    for c in ["ligacoes", "leads_pescados", "assinados", "previsao", "entregues"]:
        if c not in df.columns:
            df[c] = 0
        df[c] = df[c].fillna(0)

    df["conversao"] = df.apply(
        lambda r: (r["assinados"] / r["leads_pescados"] * 100) if r["leads_pescados"] else 0.0, axis=1
    )
    return df.sort_values("assinados", ascending=False)


def _render_pagina_frentes():
    hoje = date.today()
    mes_ini, mes_fim = _periodo_mes(hoje)

    df_colab = _tabela_colaboradores()
    frentes_disp = ["Todas"] + (sorted(df_colab["frente"].dropna().unique().tolist())
                                 if not df_colab.empty and "frente" in df_colab.columns else [])

    c1, c2 = st.columns([2, 3])
    with c1:
        frente_sel = st.selectbox("Frente", frentes_disp, key="pf_frente_sel")
    with c2:
        st.caption(
            "Ligações vem de `tbUsCall` · Leads Pescados/Assinados vêm de "
            "`tbConsolidaSalesforce` · Entregues/Previsão vêm da Gestão de "
            "Veículos (planilha) — igual ao Controle_Frentes original."
        )

    if frente_sel == "Todas":
        grupos = frentes_disp[1:]
    else:
        grupos = [frente_sel]

    if not grupos:
        st.warning("Não consegui carregar as Frentes de `tbColaboradores`. Mostrando visão sem agrupamento.")
        grupos = [None]

    with st.spinner("Consultando Azure SQL + tbUsCall + Gestão de Veículos..."):
        for frente in grupos:
            if frente:
                consultores_frente = sorted(
                    df_colab[df_colab["frente"] == frente]["nome"].dropna().unique().tolist()
                )
                titulo = f"{MESES_PT[hoje.month]} · {frente}"
            else:
                consultores_frente = None
                titulo = f"{MESES_PT[hoje.month]} · Todos os Consultores"

            tabela = _montar_tabela_frente(mes_ini, mes_fim, consultores_frente)

            st.markdown('<div class="pf-card">', unsafe_allow_html=True)
            st.markdown(f'<div class="pf-card-titulo">{titulo}</div>', unsafe_allow_html=True)
            if tabela.empty:
                st.info("Sem dados para esta frente no período.")
            else:
                st.markdown(_tabela_frente_html(tabela), unsafe_allow_html=True)
                tot = tabela[["ligacoes", "leads_pescados", "assinados", "previsao", "entregues"]].sum()
                tot_conv = (tot["assinados"] / tot["leads_pescados"] * 100) if tot["leads_pescados"] else 0
                st.markdown(
                    f"<div style='margin-top:8px;font-size:12px;color:{CINZA};font-weight:700'>"
                    f"Total Geral — Ligações: {_fmt_num(tot['ligacoes'])} · "
                    f"Leads Pescados: {_fmt_num(tot['leads_pescados'])} · "
                    f"Assinados: {_fmt_num(tot['assinados'])} · "
                    f"Previsão Entregar: {_fmt_num(tot['previsao'])} · "
                    f"Entregues: {_fmt_num(tot['entregues'])} · "
                    f"Conversão: {tot_conv:.1f}%</div>",
                    unsafe_allow_html=True,
                )
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# EXPORTAÇÃO — PDF CONSOLIDADO
# ══════════════════════════════════════════════════════════════════════════
def _gerar_pdf_relatorio() -> bytes:
    """
    Gera um PDF consolidado com todas as páginas do Performance:
    Geral, Marketing, Frentes e Ranking geral de consultores.
    Reaproveita as mesmas queries cacheadas já usadas nas páginas da tela.
    """
    import io
    import os
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.platypus import (
        BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table,
        TableStyle, NextPageTemplate, PageBreak, HRFlowable, KeepTogether,
    )
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.linecharts import HorizontalLineChart
    from reportlab.graphics.charts.legends import Legend

    C_AZUL     = colors.HexColor(AZUL)
    C_AZUL2    = colors.HexColor(AZUL2)
    C_DOURADO  = colors.HexColor(DOURADO)
    C_DOURADO2 = colors.HexColor(DOURADO2)
    C_BRANCO   = colors.white
    C_CINZA    = colors.HexColor(CINZA)
    C_CINZA_BG = colors.HexColor("#f4f2ef")
    C_CINZA_BD = colors.HexColor("#ddd8d0")
    C_VERDE    = colors.HexColor(VERDE)
    C_VERMELHO = colors.HexColor(VERMELHO)

    hoje = date.today()
    mes_ini, mes_fim = _periodo_mes(hoje)
    ref_ant = _mes_anterior_ref(hoje)
    mes_ant_ini, mes_ant_fim = _periodo_mes(ref_ant)
    ontem = hoje - timedelta(days=1)

    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "LOGO_SIGNATURE.png")

    # ── Coleta de dados (reaproveitando as queries já cacheadas) ─────────
    contratos_atual = _contratos_assinados(mes_ini, mes_fim)
    contratos_ant    = _contratos_assinados(mes_ant_ini, mes_ant_fim)
    veic_atual       = _veiculos_assinados(mes_ini, mes_fim)
    veic_ant         = _veiculos_assinados(mes_ant_ini, mes_ant_fim)
    leads_ger_atual  = _leads_gerados(mes_ini, mes_fim)
    leads_ger_ant    = _leads_gerados(mes_ant_ini, mes_ant_fim)
    leads_dia_atual  = _leads_pescados(hoje, hoje)
    leads_dia_ant    = _leads_pescados(ontem, ontem)
    leads_mes_atual  = _leads_pescados(mes_ini, mes_fim)
    leads_mes_ant    = _leads_pescados(mes_ant_ini, mes_ant_fim)

    inv_total_atual  = _investimento(mes_ini, mes_fim)
    inv_total_ant    = _investimento(mes_ant_ini, mes_ant_fim)
    inv_google_atual = _investimento(mes_ini, mes_fim, "Google")
    inv_google_ant   = _investimento(mes_ant_ini, mes_ant_fim, "Google")
    inv_meta_atual   = _investimento(mes_ini, mes_fim, "Meta")
    inv_meta_ant     = _investimento(mes_ant_ini, mes_ant_fim, "Meta")
    mkt_atual        = _mkt_totais(mes_ini, mes_fim)
    mkt_ant          = _mkt_totais(mes_ant_ini, mes_ant_fim)

    cac_atual = _safe_div(mkt_atual["investimento"], contratos_atual)
    cpl_atual = _safe_div(mkt_atual["investimento"], leads_ger_atual)
    cpc_atual = _safe_div(mkt_atual["investimento"], mkt_atual["clicks"])
    cpm_atual = _safe_div(mkt_atual["investimento"], mkt_atual["impressoes"]) * 1000
    ctr_atual = _safe_div(mkt_atual["clicks"], mkt_atual["impressoes"]) * 100
    clr_atual = _safe_div(leads_ger_atual, mkt_atual["impressoes"]) * 100
    cvr_atual = _safe_div(contratos_atual, leads_ger_atual) * 100

    curva_contratos = _curva_contratos(mes_ini, mes_fim)
    rank_geral = _ranking_consultor(mes_ini, mes_fim)

    df_colab = _tabela_colaboradores()
    frentes = sorted(df_colab["frente"].dropna().unique().tolist()) if not df_colab.empty else []
    tabelas_frente = {}
    for frente in frentes[:8]:  # limite razoável de páginas
        consultores_frente = sorted(df_colab[df_colab["frente"] == frente]["nome"].dropna().unique().tolist())
        tabelas_frente[frente] = _montar_tabela_frente(mes_ini, mes_fim, consultores_frente)

    # ── Estilos ────────────────────────────────────────────────────────
    st_titulo_secao = ParagraphStyle(
        "secao", fontName="Helvetica-Bold", fontSize=14, textColor=C_AZUL,
        spaceBefore=4, spaceAfter=10,
    )
    st_sub_secao = ParagraphStyle(
        "subsecao", fontName="Helvetica-Bold", fontSize=10.5, textColor=C_DOURADO,
        spaceBefore=10, spaceAfter=6,
    )
    st_corpo = ParagraphStyle("corpo", fontName="Helvetica", fontSize=8.5, textColor=C_AZUL, leading=12)
    st_rodape = ParagraphStyle("rodape", fontName="Helvetica", fontSize=7.5, textColor=C_CINZA, alignment=TA_CENTER)

    def _fmt_var(atual, anterior) -> str:
        if not anterior:
            return "—"
        pct = ((atual / anterior) - 1) * 100
        sinal = "+" if pct >= 0 else ""
        return f"{sinal}{pct:.1f}%"

    def tabela_kpis(linhas: list, larguras=None) -> Table:
        """linhas: [(rótulo, atual_fmt, anterior_fmt, variação_fmt), ...] com cabeçalho já incluso."""
        larguras = larguras or [7.5*cm, 3.3*cm, 3.3*cm, 3.3*cm]
        t = Table(linhas, colWidths=larguras, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_AZUL),
            ("TEXTCOLOR", (0, 0), (-1, 0), C_BRANCO),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8.5),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8.5),
            ("TEXTCOLOR", (0, 1), (-1, -1), C_AZUL),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_BRANCO, C_CINZA_BG]),
            ("GRID", (0, 0), (-1, -1), 0.4, C_CINZA_BD),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ]))
        return t

    def grafico_linha(df: pd.DataFrame, titulo: str, largura=17*cm, altura=6*cm) -> Drawing:
        """Gráfico de linha simples a partir de um DataFrame indexado por data/rótulo."""
        drawing = Drawing(largura, altura + 1.2*cm)
        if df is None or df.empty:
            return drawing
        chart = HorizontalLineChart()
        chart.x = 45
        chart.y = 20
        chart.width = largura - 90
        chart.height = altura - 20
        cols = list(df.columns)[:6]  # limite de séries pra não poluir
        chart.data = [df[c].tolist() for c in cols]
        n = len(df.index)
        passo = max(1, n // 8)
        chart.categoryAxis.categoryNames = [
            (str(v)[5:10] if i % passo == 0 else "") for i, v in enumerate(df.index)
        ]
        chart.categoryAxis.labels.fontSize = 6
        chart.categoryAxis.labels.angle = 0
        chart.valueAxis.labels.fontSize = 6
        paleta = [C_DOURADO, C_AZUL2, C_VERDE, C_VERMELHO, colors.HexColor("#8b5cf6"), colors.HexColor("#06b6d4")]
        for i, cor in enumerate(paleta[:len(cols)]):
            chart.lines[i].strokeColor = cor
            chart.lines[i].strokeWidth = 1.4
        drawing.add(chart)
        legend = Legend()
        legend.x = 45
        legend.y = altura + 0.9*cm
        legend.dx = 8
        legend.dy = 8
        legend.fontSize = 6.5
        legend.columnMaximum = 1
        legend.colorNamePairs = list(zip(paleta[:len(cols)], cols))
        drawing.add(legend)
        return drawing

    def tabela_frente(nome_frente: str, df: pd.DataFrame) -> list:
        elementos = [Paragraph(nome_frente, st_sub_secao)]
        if df.empty:
            elementos.append(Paragraph("Sem dados no período.", st_corpo))
            return elementos
        cab = ["Consultor", "Ligações", "Leads Pesc.", "Assinados", "Previsão", "Entregues", "Conv."]
        linhas = [cab]
        for _, r in df.iterrows():
            linhas.append([
                str(r["consultor"])[:28], f"{int(r['ligacoes'])}", f"{int(r['leads_pescados'])}",
                f"{int(r['assinados'])}", f"{int(r['previsao'])}", f"{int(r['entregues'])}",
                f"{r['conversao']:.1f}%",
            ])
        tot = df[["ligacoes", "leads_pescados", "assinados", "previsao", "entregues"]].sum()
        tot_conv = (tot["assinados"] / tot["leads_pescados"] * 100) if tot["leads_pescados"] else 0
        linhas.append([
            "TOTAL GERAL", f"{int(tot['ligacoes'])}", f"{int(tot['leads_pescados'])}",
            f"{int(tot['assinados'])}", f"{int(tot['previsao'])}", f"{int(tot['entregues'])}",
            f"{tot_conv:.1f}%",
        ])
        t = Table(linhas, colWidths=[4.3*cm, 2.1*cm, 2.3*cm, 2.1*cm, 2.1*cm, 2.1*cm, 1.6*cm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_AZUL),
            ("TEXTCOLOR", (0, 0), (-1, 0), C_BRANCO),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), C_DOURADO2),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("TEXTCOLOR", (0, 1), (-1, -2), C_AZUL),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [C_BRANCO, C_CINZA_BG]),
            ("GRID", (0, 0), (-1, -1), 0.4, C_CINZA_BD),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elementos.append(t)
        return elementos

    # ── Canvas: cabeçalho/rodapé de todas as páginas ─────────────────────
    def draw_page(c, doc):
        c.saveState()
        W, H = A4
        c.setFillColor(C_AZUL)
        c.rect(0, H - 2.1*cm, W, 2.1*cm, fill=1, stroke=0)
        c.setFillColor(C_DOURADO)
        c.rect(0, H - 2.1*cm - 3, W, 4, fill=1, stroke=0)
        if os.path.exists(logo_path):
            c.drawImage(logo_path, 1.3*cm, H - 1.85*cm, width=3.2*cm, height=1.55*cm,
                        preserveAspectRatio=True, mask=[0, 30, 0, 30, 0, 30])
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(C_BRANCO)
        c.drawRightString(W - 1.3*cm, H - 1.15*cm, "Relatório de Performance")
        c.setFont("Helvetica", 8.5)
        c.setFillColor(C_DOURADO2)
        c.drawRightString(W - 1.3*cm, H - 1.55*cm,
                          f"{MESES_PT[hoje.month]}/{hoje.year} · Gerado em {hoje.strftime('%d/%m/%Y %H:%M')}")
        c.setFont("Helvetica", 7.5)
        c.setFillColor(C_CINZA)
        c.drawCentredString(W/2, 1*cm, f"Carrera Signature · página {doc.page}")
        c.setStrokeColor(C_CINZA_BD)
        c.line(1.3*cm, 1.35*cm, W - 1.3*cm, 1.35*cm)
        c.restoreState()

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4,
                          leftMargin=1.3*cm, rightMargin=1.3*cm,
                          topMargin=2.6*cm, bottomMargin=1.7*cm)
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="corpo")
    doc.addPageTemplates([PageTemplate(id="padrao", frames=[frame], onPage=draw_page)])

    story = []

    # ── Seção Geral ────────────────────────────────────────────────────
    story.append(Paragraph("Visão Geral · Todos os Consultores", st_titulo_secao))
    story.append(tabela_kpis([
        ["Indicador", f"{MESES_PT[hoje.month]}/{hoje.year}", f"{MESES_PT[mes_ant_fim.month]}/{mes_ant_fim.year}", "Variação"],
        ["Contratos Assinados", _fmt_num(contratos_atual), _fmt_num(contratos_ant), _fmt_var(contratos_atual, contratos_ant)],
        ["Veículos Assinados", _fmt_num(veic_atual), _fmt_num(veic_ant), _fmt_var(veic_atual, veic_ant)],
        ["Leads Gerados (mês)", _fmt_num(leads_ger_atual), _fmt_num(leads_ger_ant), _fmt_var(leads_ger_atual, leads_ger_ant)],
        ["Leads Pescados (dia)", _fmt_num(leads_dia_atual), _fmt_num(leads_dia_ant), _fmt_var(leads_dia_atual, leads_dia_ant)],
        ["Leads Pescados (mês)", _fmt_num(leads_mes_atual), _fmt_num(leads_mes_ant), _fmt_var(leads_mes_atual, leads_mes_ant)],
    ]))
    story.append(Spacer(1, 0.5*cm))

    if not curva_contratos.empty:
        story.append(Paragraph("Curva de Contratos Assinados no Mês", st_sub_secao))
        df_curva = curva_contratos.set_index("dia")[["contratos"]].rename(columns={"contratos": "Contratos"})
        story.append(grafico_linha(df_curva, "Contratos"))
        story.append(Spacer(1, 0.3*cm))

    if not rank_geral.empty:
        story.append(Paragraph("Ranking de Consultores (Top 10 — mês atual)", st_sub_secao))
        cab = ["Consultor", "Leads Gerados", "Leads Pescados", "Contratos"]
        linhas = [cab] + [
            [str(r["consultor"])[:34], _fmt_num(r["leads_gerados"]), _fmt_num(r["leads_pescados"]), _fmt_num(r["contratos"])]
            for _, r in rank_geral.head(10).iterrows()
        ]
        story.append(tabela_kpis(linhas, larguras=[7.5*cm, 3.3*cm, 3.3*cm, 3.3*cm]))

    story.append(PageBreak())

    # ── Seção Marketing ────────────────────────────────────────────────
    story.append(Paragraph("Marketing", st_titulo_secao))
    story.append(tabela_kpis([
        ["Indicador", f"{MESES_PT[hoje.month]}/{hoje.year}", f"{MESES_PT[mes_ant_fim.month]}/{mes_ant_fim.year}", "Variação"],
        ["Investimento Total", _fmt_brl(inv_total_atual), _fmt_brl(inv_total_ant), _fmt_var(inv_total_atual, inv_total_ant)],
        ["Investimento Google", _fmt_brl(inv_google_atual), _fmt_brl(inv_google_ant), _fmt_var(inv_google_atual, inv_google_ant)],
        ["Investimento Meta", _fmt_brl(inv_meta_atual), _fmt_brl(inv_meta_ant), _fmt_var(inv_meta_atual, inv_meta_ant)],
    ]))
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("Custo por Resultado", st_sub_secao))
    cab_custo = ["CAC (venda)", "CPL (lead)", "CPC (clique)", "CPM (1000 impr.)"]
    story.append(tabela_kpis([
        cab_custo,
        [_fmt_brl(cac_atual), _fmt_brl(cpl_atual), _fmt_brl(cpc_atual), _fmt_brl(cpm_atual)],
    ], larguras=[4.25*cm]*4))
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("Funil de Conversão", st_sub_secao))
    story.append(tabela_kpis([
        ["CTR (clique/impr.)", "CLR (lead/impr.)", "CVR (venda/lead)"],
        [f"{ctr_atual:.2f}%", f"{clr_atual:.2f}%", f"{cvr_atual:.2f}%"],
    ], larguras=[5.67*cm]*3))
    story.append(PageBreak())

    # ── Seção Frentes ──────────────────────────────────────────────────
    if tabelas_frente:
        story.append(Paragraph("Frentes", st_titulo_secao))
        for nome_frente, df_frente in tabelas_frente.items():
            story.append(KeepTogether(tabela_frente(nome_frente, df_frente)))
            story.append(Spacer(1, 0.45*cm))

    story.append(Spacer(1, 0.6*cm))
    story.append(HRFlowable(width="100%", color=C_CINZA_BD, thickness=0.6))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "Relatório gerado automaticamente a partir do Azure SQL e da Gestão de Veículos. "
        "Alguns valores (Entregues, Previsão de Entregar) refletem a base de estoque no "
        "momento da geração.", st_rodape,
    ))

    doc.build(story)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════
# RENDER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════
def render():
    st.markdown('<div class="pf-wrap">', unsafe_allow_html=True)
    st.markdown(CSS, unsafe_allow_html=True)

    hoje = date.today()
    col_h, col_btn, col_pdf = st.columns([4.4, 1, 1.4])
    with col_h:
        st.markdown(f"""<div class="pf-header">
            <div class="pf-titulo">📈 Performance · Azure SQL</div>
            <div class="pf-sub">Indicadores em tempo real · Atualizado em {hoje.strftime('%d/%m/%Y %H:%M')}</div>
        </div>""", unsafe_allow_html=True)
    with col_btn:
        st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", use_container_width=True, key="pf_refresh"):
            st.cache_data.clear()
            _engine.clear()  # descarta também a engine de conexão em cache
            st.rerun()
    with col_pdf:
        st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
        if st.button("📄 Gerar PDF", use_container_width=True, key="pf_pdf_gerar"):
            with st.spinner("Montando o relatório em PDF..."):
                try:
                    st.session_state["pf_pdf_bytes"] = _gerar_pdf_relatorio()
                    st.session_state["pf_pdf_erro"] = None
                except Exception as e:
                    st.session_state["pf_pdf_bytes"] = None
                    st.session_state["pf_pdf_erro"] = str(e)

    if st.session_state.get("pf_pdf_erro"):
        st.error(f"❌ Não foi possível gerar o PDF: {st.session_state['pf_pdf_erro']}")
    if st.session_state.get("pf_pdf_bytes"):
        st.download_button(
            "⬇️ Baixar Relatório PDF",
            data=st.session_state["pf_pdf_bytes"],
            file_name=f"performance_carrera_{hoje.strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="pf_pdf_download",
        )

    ok, erro = _testar_conexao()
    if not ok:
        st.error(
            "❌ Não foi possível conectar ao Azure SQL. Verifique `.streamlit/secrets.toml` "
            "(seção `[azure_sql]`) e a liberação de firewall para este IP."
        )
        with st.expander("Detalhes técnicos do erro"):
            st.code(erro)
        with st.expander("🔍 Debug — string de conexão que o app está usando (senha mascarada)"):
            info_dbg = _debug_info()
            st.write(f"**Driver configurado no secrets.toml:** `{info_dbg['driver_cfg']}`")
            if info_dbg.get("odbc_driver_usado"):
                st.write(f"**Driver ODBC realmente usado (auto-detectado):** `{info_dbg['odbc_driver_usado']}`")
            st.write(f"**Detectado como Azure AD:** {info_dbg['eh_azure_ad']}")
            st.write(f"**Authentication usado:** `{info_dbg['autenticacao']}`")
            if info_dbg["pyodbc_versao"]:
                st.write(f"**pyodbc versão:** `{info_dbg['pyodbc_versao']}`")
                st.write(f"**Drivers ODBC instalados:** {info_dbg['drivers_instalados']}")
            else:
                st.write("**pyodbc:** não encontrado neste ambiente Python.")
            st.write("**Connection string montada:**")
            st.code(info_dbg["conn_str_masc"])
            st.caption(
                "Compare esta string com a que funcionou no `testar_conexao_azure.py` "
                "(mesmo servidor, banco, usuário, driver e Authentication). Se algo aqui "
                "estiver diferente do que você digitou no secrets.toml, o app está lendo "
                "outro arquivo de secrets."
            )
        if "20002" in erro or "20018" in erro or "Adaptive Server" in erro:
            st.info(
                "💡 Esse erro específico costuma ser falha de handshake TLS/FreeTDS "
                "(comum no Windows) — ou, se o usuário for um e-mail corporativo, "
                "o `pymssql` simplesmente não suporta login Azure AD. Rode no terminal:\n\n"
                "`python Dados/testar_conexao_azure.py`\n\n"
                "para isolar a causa. Se o diagnóstico indicar sucesso com pyodbc, "
                "confirme no secrets.toml: `driver = \"ODBC Driver 18 for SQL Server\"`."
            )
        elif "Azure AD" in erro or "ActiveDirectoryPassword" in erro:
            st.info(
                "💡 O usuário configurado é uma conta Azure AD — ajuste o driver "
                "para `\"ODBC Driver 18 for SQL Server\"` no secrets.toml."
            )
        elif "18456" in erro or "token-identified principal" in erro:
            st.info(
                "💡 Login rejeitado. Confira no secrets.toml se `username`/`password` "
                "estão exatamente certos (sem espaços extras) e se `driver` está como "
                '`"ODBC Driver 18 for SQL Server"`. Se acabou de trocar o código ou as '
                "credenciais, clique em **🔄 Atualizar** acima — ele agora também limpa "
                "a conexão em cache."
            )
        st.markdown('</div>', unsafe_allow_html=True)
        return

    pagina = st.radio(
        "Página",
        ["🏠 Geral", "🧭 Frentes", "📣 Marketing", "🏢 Operação Geral", "🌆 São Paulo", "⚓ Santos"],
        horizontal=True, label_visibility="collapsed", key="pf_pagina",
    )
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    if pagina == "🏠 Geral":
        _render_pagina_indicadores("Visão Geral · Todos os Consultores")

    elif pagina == "🧭 Frentes":
        _render_pagina_frentes()

    elif pagina == "📣 Marketing":
        _render_pagina_marketing()

    elif pagina == "🏢 Operação Geral":
        santos = _consultores_por_gestor(GESTOR_SANTOS)
        sp     = _consultores_por_gestor(GESTOR_SAO_PAULO)
        equipe_operacao = sorted(set(santos) | set(sp))
        _render_pagina_indicadores(
            "Operação Geral · Consultores Santos + São Paulo", equipe_operacao
        )

    elif pagina == "🌆 São Paulo":
        equipe_sp = _consultores_por_gestor(GESTOR_SAO_PAULO)
        _render_pagina_indicadores(
            f"São Paulo · Consultores reportando a {GESTOR_SAO_PAULO.split()[0]}", equipe_sp
        )

    elif pagina == "⚓ Santos":
        equipe_santos = _consultores_por_gestor(GESTOR_SANTOS)
        _render_pagina_indicadores(
            f"Santos · Consultores reportando a {GESTOR_SANTOS.split()[0]}", equipe_santos
        )

    st.markdown('</div>', unsafe_allow_html=True)
