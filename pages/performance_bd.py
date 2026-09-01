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

TBL_MKT              = "mkt.ConsolidadoCampanhas"        # confirmado
COL_MKT_INVESTIMENTO = "Investimento"                     # confirmado
COL_MKT_DIA          = "Dia_Campanha"                     # confirmado
COL_MKT_PLATAFORMA   = "Plataforma"              # TODO: confirmar nome/valores (Google/Meta)

TBL_COLAB            = "dbo.tbColaboradores"      # TODO: confirmar schema (nome informado, sem schema)
COL_COLAB_NOME       = "NOME"                     # TODO: confirmar nome real
COL_COLAB_GESTOR     = "GESTOR"                   # TODO: confirmar nome real (quem ele reporta)

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
        odbc_driver = driver_cfg if "odbc driver" in driver_cfg.lower() else cfg.get(
            "odbc_driver", "ODBC Driver 18 for SQL Server"
        )
        query = {
            "driver": odbc_driver,
            "Encrypt": "yes",
            "TrustServerCertificate": "no",
            "Connection Timeout": str(timeout),
        }
        if autenticacao:
            query["Authentication"] = autenticacao

        url = sa.URL.create(
            "mssql+pyodbc",
            username=usuario,
            password=senha,
            host=servidor,
            port=porta,
            database=banco,
            query=query,
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


def _filtro_consultor(consultores: list | None, params: dict, prefixo="c") -> str:
    """Gera cláusula SQL 'AND CONSULTOR IN (...)' parametrizada."""
    if not consultores:
        return ""
    chaves = []
    for i, nome in enumerate(consultores):
        k = f"{prefixo}{i}"
        params[k] = nome
        chaves.append(f":{k}")
    return f" AND {COL_SF_CONSULTOR} IN ({','.join(chaves)})"


# ══════════════════════════════════════════════════════════════════════════
# CRUZAMENTO CONSULTOR ↔ COLABORADORES ↔ USUÁRIOS DO SISTEMA
# ══════════════════════════════════════════════════════════════════════════
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


def _variacao(atual: float, anterior: float) -> tuple[str, str]:
    """Retorna (texto, classe css) da variação percentual MoM."""
    if not anterior:
        return ("—", "pf-flat")
    pct = ((atual - anterior) / anterior) * 100
    if abs(pct) < 0.5:
        return (f"◼ {pct:+.1f}%", "pf-flat")
    seta = "▲" if pct > 0 else "▼"
    cls  = "pf-up" if pct > 0 else "pf-down"
    return (f"{seta} {pct:+.1f}%", cls)


def _kpi_html(label, valor_fmt, atual, anterior, icon="") -> str:
    txt, cls = _variacao(atual, anterior)
    return f"""<div class="pf-kpi">
        <div class="pf-kpi-label">{icon} {label}</div>
        <div class="pf-kpi-val">{valor_fmt}</div>
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

    # ── Curva acumulada + Ranking ────────────────────────────────────────────
    c1, c2 = st.columns([3, 2])
    with c1:
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

    with c2:
        st.markdown('<div class="pf-card">', unsafe_allow_html=True)
        st.markdown('<div class="pf-card-titulo">🧑‍💼 Ranking de Consultores (mês atual)</div>',
                    unsafe_allow_html=True)
        rank = _ranking_consultor(mes_ini, mes_fim, consultores)
        if rank.empty:
            st.info("Sem dados no período.")
        else:
            st.markdown(_tabela_ranking(rank.head(10)), unsafe_allow_html=True)
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

    st.markdown(f"""<div class="pf-kpi-grid" style="grid-template-columns:repeat(3,1fr)">
        {_kpi_html("Investimento Total", _fmt_brl(inv_total_atual), inv_total_atual, inv_total_ant, "💰")}
        {_kpi_html("Investimento Google", _fmt_brl(inv_google_atual), inv_google_atual, inv_google_ant, "🔍")}
        {_kpi_html("Investimento Meta", _fmt_brl(inv_meta_atual), inv_meta_atual, inv_meta_ant, "📘")}
    </div>""", unsafe_allow_html=True)

    # ── Comparativo mensal: investimento total mês atual x mês anterior ─────
    st.markdown('<div class="pf-card">', unsafe_allow_html=True)
    st.markdown('<div class="pf-card-titulo">📊 Investimento Total · Mês Atual vs. Mês Anterior</div>',
                unsafe_allow_html=True)
    curva_inv_cmp = _comparativo_mensal_investimento(mes_ini, mes_fim, mes_ant_ini, mes_ant_fim)
    st.line_chart(curva_inv_cmp, height=240)
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
# RENDER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════
def render():
    st.markdown('<div class="pf-wrap">', unsafe_allow_html=True)
    st.markdown(CSS, unsafe_allow_html=True)

    hoje = date.today()
    col_h, col_btn = st.columns([5, 1])
    with col_h:
        st.markdown(f"""<div class="pf-header">
            <div class="pf-titulo">📈 Performance · Azure SQL</div>
            <div class="pf-sub">Indicadores em tempo real · Atualizado em {hoje.strftime('%d/%m/%Y %H:%M')}</div>
        </div>""", unsafe_allow_html=True)
    with col_btn:
        st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", use_container_width=True, key="pf_refresh"):
            st.cache_data.clear()
            st.rerun()

    ok, erro = _testar_conexao()
    if not ok:
        st.error(
            "❌ Não foi possível conectar ao Azure SQL. Verifique `.streamlit/secrets.toml` "
            "(seção `[azure_sql]`) e a liberação de firewall para este IP."
        )
        with st.expander("Detalhes técnicos do erro"):
            st.code(erro)
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
        st.markdown('</div>', unsafe_allow_html=True)
        return

    pagina = st.radio(
        "Página",
        ["🏠 Geral", "📣 Marketing", "🏢 Operação Geral", "🌆 São Paulo", "⚓ Santos"],
        horizontal=True, label_visibility="collapsed", key="pf_pagina",
    )
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    if pagina == "🏠 Geral":
        _render_pagina_indicadores("Visão Geral · Todos os Consultores")

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
