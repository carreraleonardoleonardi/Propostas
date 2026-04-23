"""
relatorio.py — Carrera Signature
Relatório consolidado local: LM + Salesforce + Cadastro Manual
"""

import io
import os
import sys
import datetime
import subprocess
from datetime import date

import pandas as pd
import streamlit as st


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════
DADOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Dados")
sys.path.insert(0, DADOS_DIR)

AZUL = "#213144"
DOURADO = "#b57b3f"
VERDE = "#16a34a"
ROXO = "#7c3aed"
LARANJA = "#ea580c"
CINZA_TEXTO = "#64748b"
BORDA = "#e8dccb"
FUNDO_CARD = "#ffffff"

ARQ_BASE_PRINCIPAL_XLSX = os.path.join(DADOS_DIR, "base_consolidada_completa.xlsx")
ARQ_BASE_PRINCIPAL_PARQUET = os.path.join(DADOS_DIR, "base_consolidada_completa.parquet")
ARQ_SALESFORCE = os.path.join(DADOS_DIR, "Base Salesforce.xlsx")
ARQ_MANUAIS = os.path.join(DADOS_DIR, "pedidos_manuais.xlsx")
ARQ_COCKPIT = os.path.join(DADOS_DIR, "Cockpit_Carrera.xlsx")

COLUNAS_RELATORIO = [
    "Origem venda", "Pedido", "Segmento", "Tipo", "Nome", "Documento",
    "Data de Inclusão", "Data de Status", "dateLastUpdated", "Mensalidade",
    "Valor Total", "Status", "ANO DA VENDA", "MÊS DA VENDA", "Prospecção",
    "Venda", "Previsão", "Data da retirada", "Vigência Final do contrato",
    "Chassi", "Placa", "Período", "Km", "Modelo Oficial", "Cor", "Opcional",
    "Local de Venda", "UF", "City", "KickBack", "Preço NF",
    "Comissão Vendedor R$", "Comissão Carrera", "Marca", "Locadora",
    "Empresa", "Data Assinatura"
]


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _tipo_cliente(doc: str) -> str:
    digits = "".join(filter(str.isdigit, str(doc)))
    if len(digits) == 11:
        return "PF"
    if len(digits) == 14:
        return "PJ"
    return ""


def _to_num_serie(series: pd.Series) -> pd.Series:
    if series is None or len(series) == 0:
        return pd.Series(dtype="float64")
    return pd.to_numeric(
        series.astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace(r"[^\d\.-]", "", regex=True),
        errors="coerce"
    )


def _to_num_col(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series([None] * len(df), index=df.index, dtype="float64")
    return _to_num_serie(df[col])


def _garantir_colunas(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in colunas:
        if col not in out.columns:
            out[col] = ""
    return out


def _formatar_datas_para_exibicao(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    dv = df.copy()
    for col in colunas:
        if col in dv.columns:
            dv[col] = pd.to_datetime(dv[col], errors="coerce", dayfirst=True).dt.strftime("%d/%m/%Y").fillna("")
    return dv


def _lookup_consultor(df_sf: pd.DataFrame, numero_pedido) -> str:
    if df_sf.empty:
        return "Não encontrado"

    col_pedido = "Nro do Pedido"
    col_consul = "Proprietário da oportunidade"

    if col_pedido not in df_sf.columns or col_consul not in df_sf.columns:
        return "Não encontrado"

    match = df_sf[df_sf[col_pedido].astype(str).str.strip() == str(numero_pedido).strip()]
    if match.empty:
        return "Não encontrado"

    return str(match.iloc[0][col_consul]).strip() or "Não encontrado"


def _fmt_brl(valor) -> str:
    if pd.isna(valor):
        valor = 0
    try:
        return f"R$ {float(valor):,.0f}"
    except Exception:
        return "R$ 0"


def _primeiro_dia_mes_atual() -> date:
    hoje = date.today()
    return date(hoje.year, hoje.month, 1)


def _ultimo_dia_mes_atual() -> date:
    hoje = date.today()
    if hoje.month == 12:
        prox = date(hoje.year + 1, 1, 1)
    else:
        prox = date(hoje.year, hoje.month + 1, 1)
    return (pd.Timestamp(prox) - pd.Timedelta(days=1)).date()


def _coluna_data_filtro(df: pd.DataFrame) -> str | None:
    if "dateLastUpdated" in df.columns:
        return "dateLastUpdated"
    if "Data de Status" in df.columns:
        return "Data de Status"
    return None


def _preparar_exibicao(df: pd.DataFrame) -> pd.DataFrame:
    dv = df.copy()

    col_moeda = [
        "Mensalidade",
        "Valor Total",
        "Comissão Carrera",
        "Comissão Vendedor R$",
        "KickBack",
        "Preço NF",
    ]
    for col in col_moeda:
        if col in dv.columns:
            dv[col] = _to_num_col(dv, col)

    col_num = ["Km", "Período", "ANO DA VENDA", "MÊS DA VENDA"]
    for col in col_num:
        if col in dv.columns:
            dv[col] = _to_num_col(dv, col)

    dv = _formatar_datas_para_exibicao(
        dv,
        [
            "Data de Inclusão",
            "Data de Status",
            "dateLastUpdated",
            "Data da retirada",
            "Vigência Final do contrato",
            "Data Assinatura",
        ]
    )

    ordem = [
        "Pedido", "Locadora", "Segmento", "Status", "Venda", "Nome", "Documento",
        "Tipo", "Marca", "Modelo Oficial", "Cor", "Placa", "Chassi",
        "Mensalidade", "Valor Total", "Preço NF", "Comissão Carrera",
        "Comissão Vendedor R$", "Período", "Km",
        "dateLastUpdated", "Data de Inclusão", "Data Assinatura", "Data de Status",
        "Data da retirada", "Vigência Final do contrato",
        "Local de Venda", "UF", "City", "Origem venda", "Empresa", "Opcional"
    ]

    ordem_final = [c for c in ordem if c in dv.columns] + [c for c in dv.columns if c not in ordem]
    return dv[ordem_final]


def _top_3_carros_podium(df: pd.DataFrame) -> pd.DataFrame:
    """
    Top 3 carros mais vendidos:
    - considera apenas Status = Pedido concluído
    - prioriza Modelo Oficial
    - usa Marca como fallback
    """
    if df.empty:
        return pd.DataFrame(columns=["modelo", "qtd"])

    base = df.copy()

    if "Status" in base.columns:
        base = base[
            base["Status"].astype(str).str.strip().str.lower() == "pedido concluído"
        ]

    if base.empty:
        return pd.DataFrame(columns=["modelo", "qtd"])

    if "Modelo Oficial" in base.columns:
        base["modelo"] = base["Modelo Oficial"].astype(str).str.strip()
    else:
        base["modelo"] = ""

    if "Marca" in base.columns:
        base["modelo"] = base.apply(
            lambda row: row["modelo"]
            if str(row["modelo"]).strip() not in ["", "nan", "None"]
            else str(row.get("Marca", "")).strip(),
            axis=1,
        )

    base["modelo"] = base["modelo"].replace(["", "nan", "None"], pd.NA)
    base = base.dropna(subset=["modelo"])

    if base.empty:
        return pd.DataFrame(columns=["modelo", "qtd"])

    top3 = (
        base.groupby("modelo", as_index=False)
        .size()
        .rename(columns={"size": "qtd"})
        .sort_values(["qtd", "modelo"], ascending=[False, True])
        .head(3)
        .reset_index(drop=True)
    )

    return top3


def _render_podium_card(posicao: int, modelo: str, qtd: int) -> str:
    medalha = {1: "👑", 2: "🥈", 3: "🥉"}[posicao]
    classe = f"podium-{posicao}"
    return f"""
        <div class="podium-col {classe}">
            <div class="podium-badge">{posicao}</div>
            <div class="podium-box">
                <div class="podium-model">{medalha}</div>
                <div class="podium-name">{modelo}</div>
                <div class="podium-qtd">{qtd}</div>
                <div class="podium-leg">Pedidos</div>
            </div>
        </div>
    """


# ══════════════════════════════════════════════════════════════════════════════
# LEITURA LOCAL
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=120, show_spinner=False)
def _ler_salesforce_local() -> pd.DataFrame:
    if not os.path.exists(ARQ_SALESFORCE):
        return pd.DataFrame()

    try:
        return pd.read_excel(ARQ_SALESFORCE)
    except Exception as e:
        st.warning(f"⚠️ Não foi possível ler o Salesforce local: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def _ler_base_local() -> pd.DataFrame:
    try:
        if os.path.exists(ARQ_BASE_PRINCIPAL_PARQUET):
            return pd.read_parquet(ARQ_BASE_PRINCIPAL_PARQUET)

        if os.path.exists(ARQ_BASE_PRINCIPAL_XLSX):
            return pd.read_excel(ARQ_BASE_PRINCIPAL_XLSX)

        return pd.DataFrame()

    except Exception as e:
        st.error(f"Erro ao ler a base consolidada local: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def _ler_manuais_local() -> pd.DataFrame:
    if not os.path.exists(ARQ_MANUAIS):
        return pd.DataFrame(columns=COLUNAS_RELATORIO)

    try:
        df = pd.read_excel(ARQ_MANUAIS)
        return _garantir_colunas(df, COLUNAS_RELATORIO)
    except Exception as e:
        st.warning(f"⚠️ Não foi possível ler os pedidos manuais: {e}")
        return pd.DataFrame(columns=COLUNAS_RELATORIO)


# ══════════════════════════════════════════════════════════════════════════════
# CONSOLIDAÇÃO
# ══════════════════════════════════════════════════════════════════════════════
def _normalizar_base_principal(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=COLUNAS_RELATORIO)

    base = df.copy()

    mapa = {
        "orderId": "Pedido",
        "clientName": "Nome",
        "cpfCnpj": "Documento",
        "orderStatus": "Status",
        "createdAt": "Data de Inclusão",
        "updatedAt": "Data de Status",
        "dateLastUpdated": "dateLastUpdated",
        "totalOrder": "Valor Total",
        "segment": "Segmento",
        "optional": "Opcional",
        "chassis": "Chassi",
        "deliveryPlate": "Placa",
        "monthlyInstallment": "Mensalidade",
        "monthlyKmValue": "Km",
        "deadline": "Período",
        "brand": "Marca",
        "kickback": "KickBack",
        "vehicleValue": "Preço NF",
        "comissao": "Comissão Carrera",
        "comissao_vendedor": "Comissão Vendedor R$",
        "dealerDelivery": "Local de Venda",
        "estado": "UF",
        "city": "City",
        "orderDate": "Data Assinatura",
        "deliveryDate": "Data da retirada",
        "salesChannel": "Origem venda",
        "clientType": "Tipo",
        "consultorNome": "Venda",
    }

    base.rename(columns={k: v for k, v in mapa.items() if k in base.columns}, inplace=True)

    if "Tipo" not in base.columns or base["Tipo"].astype(str).str.strip().eq("").all():
        if "Documento" in base.columns:
            base["Tipo"] = base["Documento"].apply(_tipo_cliente)

    for col in ["Data de Inclusão", "Data de Status", "dateLastUpdated", "Data Assinatura", "Data da retirada"]:
        if col in base.columns:
            base[col] = pd.to_datetime(base[col], errors="coerce", dayfirst=True)

    if "Data de Inclusão" in base.columns:
        if "ANO DA VENDA" not in base.columns:
            base["ANO DA VENDA"] = base["Data de Inclusão"].dt.year.astype("Int64").astype(str).replace("<NA>", "")
        if "MÊS DA VENDA" not in base.columns:
            base["MÊS DA VENDA"] = base["Data de Inclusão"].dt.month.astype("Int64").astype(str).replace("<NA>", "")

    if "Vigência Final do contrato" not in base.columns:
        if "Data Assinatura" in base.columns and "Período" in base.columns:
            periodo_num = _to_num_col(base, "Período")
            base["Vigência Final do contrato"] = base.apply(
                lambda r: (
                    r["Data Assinatura"] + pd.DateOffset(months=int(periodo_num.loc[r.name]))
                ) if pd.notnull(r.get("Data Assinatura")) and pd.notnull(periodo_num.loc[r.name]) else None,
                axis=1,
            )

    if "Locadora" not in base.columns:
        base["Locadora"] = "LM FROTAS"

    return _garantir_colunas(base, COLUNAS_RELATORIO)


def _enriquecer_com_salesforce(df: pd.DataFrame, df_sf: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    if df_sf.empty or "Nro do Pedido" not in df_sf.columns:
        if "Venda" not in out.columns:
            out["Venda"] = ""
        return out

    sf_idx = df_sf.copy()
    sf_idx["_pedido_idx"] = df_sf["Nro do Pedido"].astype(str).str.strip()
    sf_idx = sf_idx.drop_duplicates(subset=["_pedido_idx"]).set_index("_pedido_idx")

    if "Venda" not in out.columns:
        out["Venda"] = out["Pedido"].apply(lambda p: _lookup_consultor(df_sf, p))
    else:
        out["Venda"] = out.apply(
            lambda row: row["Venda"] if str(row.get("Venda", "")).strip()
            else _lookup_consultor(df_sf, row.get("Pedido", "")),
            axis=1,
        )

    sf_map = {
        "Nome da conta": "Empresa",
        "Origem da venda": "Origem venda",
        "Comissionamento": "Comissão Vendedor R$",
    }

    for col_sf, col_rel in sf_map.items():
        if col_sf in sf_idx.columns:
            out[col_rel] = out.apply(
                lambda row: (
                    sf_idx.loc[str(row["Pedido"]).strip(), col_sf]
                    if str(row["Pedido"]).strip() in sf_idx.index
                    else row.get(col_rel, "")
                ),
                axis=1,
            )

    return out


def _base_completa_local() -> pd.DataFrame:
    df_base = _ler_base_local()
    df_sf = _ler_salesforce_local()
    df_manual = _ler_manuais_local()

    partes = []

    if not df_base.empty:
        partes.append(_normalizar_base_principal(df_base))

    if not df_manual.empty:
        partes.append(_garantir_colunas(df_manual, COLUNAS_RELATORIO))

    if not partes:
        return pd.DataFrame(columns=COLUNAS_RELATORIO)

    df = pd.concat(partes, ignore_index=True)
    df = _garantir_colunas(df, COLUNAS_RELATORIO)
    df = _enriquecer_com_salesforce(df, df_sf)

    return df[COLUNAS_RELATORIO]


# ══════════════════════════════════════════════════════════════════════════════
# MANUAIS
# ══════════════════════════════════════════════════════════════════════════════
def _gravar_manual_local(dados: dict) -> bool:
    try:
        if os.path.exists(ARQ_MANUAIS):
            df = pd.read_excel(ARQ_MANUAIS)
        else:
            df = pd.DataFrame(columns=COLUNAS_RELATORIO)

        df = _garantir_colunas(df, COLUNAS_RELATORIO)

        nova_linha = {c: str(dados.get(c, "")) for c in COLUNAS_RELATORIO}
        df = pd.concat([df, pd.DataFrame([nova_linha])], ignore_index=True)
        df.to_excel(ARQ_MANUAIS, index=False)
        return True
    except Exception as e:
        st.error(f"Erro ao gravar pedido manual: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════
def render():
    autenticado = st.session_state.get("auth_tipo", "") == "Staff"
    pode_editar = autenticado and st.session_state.get("auth_nome", "") not in {
        "Andrea Bettega Pereira da Costa",
        "Raymond Jose Duque Bello",
    }

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Montserrat', sans-serif !important;
        }}

        section[data-testid="stMain"] * {{
            font-family: 'Montserrat', sans-serif !important;
        }}

        .page-title {{
            font-size: 28px;
            font-weight: 800;
            color: {AZUL};
            margin: 0;
            padding: 0;
        }}

        .section-title {{
            font-size: 16px;
            font-weight: 800;
            color: {AZUL};
            margin: 0 0 12px 0;
        }}

        .soft-card {{
            background: {FUNDO_CARD};
            border: 1px solid {BORDA};
            border-radius: 18px;
            padding: 18px 16px 12px 16px;
            box-shadow: 0 4px 18px rgba(33,49,68,.05);
            margin-bottom: 18px;
        }}

        .kpi-wrap {{
            display: grid;
            grid-template-columns: repeat(6, minmax(120px, 1fr));
            gap: 12px;
            margin: 18px 0 12px 0;
        }}

        .kpi-box {{
            background: #fff;
            border: 1px solid {BORDA};
            border-top: 4px solid {DOURADO};
            border-radius: 18px;
            padding: 18px 12px 14px 12px;
            text-align: center;
            box-shadow: 0 4px 18px rgba(181,123,63,.06);
        }}

        .kpi-n {{
            font-size: 24px;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 6px;
            word-break: break-word;
        }}

        .kpi-l {{
            font-size: 11px;
            font-weight: 700;
            letter-spacing: .7px;
            color: #94a3b8;
            text-transform: uppercase;
        }}

        .mini-note {{
            color: {CINZA_TEXTO};
            font-size: 13px;
            margin: 6px 0 16px 0;
        }}

        .podium-card {{
            background: #fff;
            border: 1px solid {BORDA};
            border-radius: 18px;
            padding: 18px;
            box-shadow: 0 4px 18px rgba(33,49,68,.05);
            height: 100%;
            margin-bottom: 18px;
        }}

        .podium-wrap {{
            display: flex;
            align-items: end;
            justify-content: center;
            gap: 16px;
            margin-top: 18px;
            min-height: 320px;
        }}

        .podium-col {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: end;
            flex-direction: column;
            max-width: 320px;
        }}

        .podium-badge {{
            width: 44px;
            height: 44px;
            border-radius: 999px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 22px;
            margin-bottom: 10px;
            border: 3px solid #fff;
            box-shadow: 0 4px 12px rgba(0,0,0,.08);
        }}

        .podium-box {{
            width: 100%;
            border-radius: 18px 18px 10px 10px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 18px 12px;
            text-align: center;
            border: 1px solid {BORDA};
        }}

        .podium-model {{
            font-size: 26px;
            margin-bottom: 8px;
        }}

        .podium-name {{
            font-size: 24px;
            font-weight: 800;
            color: {AZUL};
            line-height: 1.1;
            margin-bottom: 10px;
            text-transform: uppercase;
            word-break: break-word;
        }}

        .podium-qtd {{
            font-size: 42px;
            font-weight: 800;
            color: {AZUL};
            line-height: 1;
        }}

        .podium-leg {{
            font-size: 12px;
            font-weight: 700;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: .6px;
            margin-top: 6px;
        }}

        .podium-1 .podium-badge {{
            background: linear-gradient(180deg, #f6d36b, #d89b22);
            color: white;
        }}

        .podium-2 .podium-badge {{
            background: linear-gradient(180deg, #cfd5df, #8b95a7);
            color: white;
        }}

        .podium-3 .podium-badge {{
            background: linear-gradient(180deg, #efb083, #c96a27);
            color: white;
        }}

        .podium-1 .podium-box {{
            background: linear-gradient(180deg, #fff8ea, #f5e3b6);
            min-height: 230px;
        }}

        .podium-2 .podium-box {{
            background: linear-gradient(180deg, #f5f7fb, #dfe5ef);
            min-height: 180px;
        }}

        .podium-3 .podium-box {{
            background: linear-gradient(180deg, #fbf2eb, #efd7c8);
            min-height: 150px;
        }}

        .podium-note {{
            font-size: 13px;
            color: {CINZA_TEXTO};
            margin-top: 14px;
        }}

        div[data-testid="stSelectbox"] label,
        div[data-testid="stTextInput"] label,
        div[data-testid="stDateInput"] label,
        div[data-testid="stNumberInput"] label {{
            color: {AZUL} !important;
            font-weight: 700 !important;
            font-size: 13px !important;
        }}

        div[data-testid="stSelectbox"] > div,
        div[data-testid="stTextInput"] > div,
        div[data-testid="stDateInput"] > div,
        div[data-testid="stNumberInput"] > div {{
            border-radius: 14px !important;
        }}

        div[data-testid="stButton"] button {{
            border-radius: 14px !important;
            height: 44px !important;
            font-weight: 700 !important;
        }}

        div[data-testid="stDataFrame"] {{
            border: 1px solid {BORDA};
            border-radius: 16px;
            overflow: hidden;
        }}

        @media (max-width: 1100px) {{
            .kpi-wrap {{
                grid-template-columns: repeat(2, minmax(120px, 1fr));
            }}
        }}

        @media (max-width: 900px) {{
            .podium-wrap {{
                flex-direction: column;
                align-items: center;
                min-height: auto;
            }}

            .podium-box {{
                min-height: 140px !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    abas = st.tabs(["📋 Relatório", "📤 Dados", "➕ Cadastro Manual"] if pode_editar else ["📋 Relatório"])

    # ──────────────────────────────────────────────────────────────────────
    # ABA RELATÓRIO
    # ──────────────────────────────────────────────────────────────────────
    with abas[0]:
        h1, h2 = st.columns([6, 1.2])
        with h1:
            st.markdown(f'<p class="page-title">📊 Relatório Consolidado</p>', unsafe_allow_html=True)
        with h2:
            if st.button("🔄 Atualizar", use_container_width=True, key="rel_refresh"):
                st.cache_data.clear()
                st.rerun()

        with st.spinner("Carregando base local..."):
            df = _base_completa_local()

        if df.empty:
            st.info("Nenhum dado disponível. Verifique se a base consolidada existe na pasta Dados.")
            st.code(
                "Arquivos esperados:\n"
                "- Dados/base_consolidada_completa.xlsx ou .parquet\n"
                "- Dados/Base Salesforce.xlsx (opcional)\n"
                "- Dados/pedidos_manuais.xlsx (opcional)"
            )
            return

        col_data_filtro = _coluna_data_filtro(df)
        data_inicio_default = _primeiro_dia_mes_atual()
        data_fim_default = _ultimo_dia_mes_atual()

        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        st.markdown('<p class="section-title">🔎 Filtros</p>', unsafe_allow_html=True)

        f1, f2, f3, f4 = st.columns(4)
        with f1:
            flt_loc = st.selectbox(
                "Locadora",
                ["Todas"] + sorted([x for x in df["Locadora"].dropna().astype(str).unique().tolist() if x]),
                key="rel_loc",
            )
        with f2:
            flt_seg = st.selectbox(
                "Segmento",
                ["Todos"] + sorted([x for x in df["Segmento"].dropna().astype(str).unique().tolist() if x]),
                key="rel_seg",
            )
        with f3:
            flt_sta = st.selectbox(
                "Status",
                ["Todos"] + sorted([x for x in df["Status"].dropna().astype(str).unique().tolist() if x]),
                key="rel_sta",
            )
        with f4:
            flt_ven = st.selectbox(
                "Consultor",
                ["Todos"] + sorted([x for x in df["Venda"].dropna().astype(str).unique().tolist() if x]),
                key="rel_ven",
            )

        f5, f6, f7, f8 = st.columns(4)
        with f5:
            dt_inicio = st.date_input(
                "Data início",
                value=st.session_state.get("rel_dt_inicio", data_inicio_default),
                key="rel_dt_inicio",
            )
        with f6:
            dt_fim = st.date_input(
                "Data fim",
                value=st.session_state.get("rel_dt_fim", data_fim_default),
                key="rel_dt_fim",
            )
        with f7:
            flt_tipo = st.selectbox("Tipo", ["Todos", "PF", "PJ"], key="rel_tipo")
        with f8:
            s_ped = st.text_input(
                "Pedido / Chassi / Cliente",
                key="rel_busca",
                placeholder="Digite para buscar",
            )

        cb1, cb2, _ = st.columns([1.1, 1.1, 5.8])
        with cb1:
            if st.button("🔎 Pesquisar", type="primary", use_container_width=True, key="rel_pesq"):
                st.session_state["rel_flt_ok"] = True
        with cb2:
            if st.button("🧹 Limpar", use_container_width=True, key="rel_limpar"):
                for k in [
                    "rel_loc", "rel_seg", "rel_sta", "rel_ven",
                    "rel_tipo", "rel_busca", "rel_flt_ok",
                    "rel_cols", "rel_ordem_col", "rel_ordem_desc", "rel_det_pedido",
                    "rel_dt_inicio", "rel_dt_fim",
                ]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        dv = df.copy()

        if flt_loc != "Todas":
            dv = dv[dv["Locadora"] == flt_loc]
        if flt_seg != "Todos":
            dv = dv[dv["Segmento"] == flt_seg]
        if flt_sta != "Todos":
            dv = dv[dv["Status"] == flt_sta]
        if flt_ven != "Todos":
            dv = dv[dv["Venda"] == flt_ven]
        if flt_tipo != "Todos":
            dv = dv[dv["Tipo"] == flt_tipo]

        if col_data_filtro:
            serie_data = pd.to_datetime(dv[col_data_filtro], errors="coerce", dayfirst=True).dt.date
            if dt_inicio:
                dv = dv[serie_data >= dt_inicio]
            if dt_fim:
                dv = dv[serie_data <= dt_fim]

        if s_ped:
            mask = (
                dv["Pedido"].astype(str).str.lower().str.contains(s_ped.lower(), na=False)
                | dv["Chassi"].astype(str).str.lower().str.contains(s_ped.lower(), na=False)
                | dv["Nome"].astype(str).str.lower().str.contains(s_ped.lower(), na=False)
            )
            dv = dv[mask]

        total_ped = len(dv)
        val_total = _to_num_col(dv, "Valor Total").sum()
        mens_media = _to_num_col(dv, "Mensalidade").mean()
        comis_total = _to_num_col(dv, "Comissão Carrera").sum()
        n_lm = len(dv[dv["Locadora"] == "LM FROTAS"]) if not dv.empty else 0
        n_rci = len(dv[dv["Locadora"].astype(str).isin(["RCI", "TOOT", "RCI/TOOT"])]) if not dv.empty else 0

        st.markdown(
            f"""
            <div class="kpi-wrap">
              <div class="kpi-box"><div class="kpi-n" style="color:{AZUL}">{total_ped}</div><div class="kpi-l">Pedidos</div></div>
              <div class="kpi-box"><div class="kpi-n" style="color:{VERDE}">{_fmt_brl(val_total)}</div><div class="kpi-l">Valor Total</div></div>
              <div class="kpi-box"><div class="kpi-n" style="color:{DOURADO}">{_fmt_brl(0 if pd.isna(mens_media) else mens_media)}</div><div class="kpi-l">Mensalidade Média</div></div>
              <div class="kpi-box"><div class="kpi-n" style="color:{ROXO}">{_fmt_brl(comis_total)}</div><div class="kpi-l">Comissão Carrera</div></div>
              <div class="kpi-box"><div class="kpi-n" style="color:#2563eb">{n_lm}</div><div class="kpi-l">LM Frotas</div></div>
              <div class="kpi-box"><div class="kpi-n" style="color:{LARANJA}">{n_rci}</div><div class="kpi-l">RCI / TOOT</div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"<p class='mini-note'><b style='color:{AZUL}'>{len(dv)}</b> pedido(s) no resultado atual</p>",
            unsafe_allow_html=True,
        )

        st.markdown("### 🏆 Top 3 Carros Mais Vendidos")
        top3 = _top_3_carros_podium(dv)

        if top3.empty:
            st.info("Não há pedidos concluídos no período/filtro selecionado para montar o pódio.")
        else:
            ranking = top3.to_dict("records")
            cards = []

            if len(ranking) >= 2:
                cards.append(_render_podium_card(2, ranking[1]["modelo"], int(ranking[1]["qtd"])))
            if len(ranking) >= 1:
                cards.append(_render_podium_card(1, ranking[0]["modelo"], int(ranking[0]["qtd"])))
            if len(ranking) >= 3:
                cards.append(_render_podium_card(3, ranking[2]["modelo"], int(ranking[2]["qtd"])))

            st.markdown(
                f"""
                <div class="podium-card">
                    <div style="font-size:13px; color:{CINZA_TEXTO}; margin-bottom:8px;">
                        Considerando apenas status: <b>Pedido concluído</b>
                    </div>

                    <div class="podium-wrap">
                        {''.join(cards)}
                    </div>

                    <div class="podium-note">
                        Ranking baseado na quantidade de pedidos com status <b>Pedido concluído</b>
                        dentro do resultado filtrado atual.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("### 📈 Resumos")
        r1, r2, r3 = st.columns(3)

        with r1:
            resumo_status = dv["Status"].fillna("Sem status").astype(str).value_counts().reset_index()
            resumo_status.columns = ["Status", "Qtd"]
            st.markdown("**Pedidos por Status**")
            st.dataframe(resumo_status, use_container_width=True, hide_index=True, height=260)

        with r2:
            resumo_vendedor = dv["Venda"].fillna("Sem vendedor").astype(str).value_counts().reset_index()
            resumo_vendedor.columns = ["Consultor", "Qtd"]
            st.markdown("**Pedidos por Consultor**")
            st.dataframe(resumo_vendedor, use_container_width=True, hide_index=True, height=260)

        with r3:
            resumo_locadora = dv["Locadora"].fillna("Sem locadora").astype(str).value_counts().reset_index()
            resumo_locadora.columns = ["Locadora", "Qtd"]
            st.markdown("**Pedidos por Locadora**")
            st.dataframe(resumo_locadora, use_container_width=True, hide_index=True, height=260)

        st.markdown("### 📋 Pedidos Consolidados")
        dv_show = _preparar_exibicao(dv)

        t1, t2, t3 = st.columns([2, 2, 4])
        with t1:
            opcoes_ordem = [
                c
                for c in ["dateLastUpdated", "Data de Inclusão", "Valor Total", "Mensalidade", "Pedido", "Venda", "Status"]
                if c in dv_show.columns
            ]
            ordenar_por = st.selectbox(
                "Ordenar por",
                opcoes_ordem if opcoes_ordem else dv_show.columns.tolist(),
                key="rel_ordem_col",
            )
        with t2:
            ordem_desc = st.checkbox("Ordem decrescente", value=True, key="rel_ordem_desc")
        with t3:
            cols_default = [
                c
                for c in [
                    "Pedido", "Locadora", "Segmento", "Status", "Venda", "Nome",
                    "Modelo Oficial", "Mensalidade", "Valor Total", "dateLastUpdated",
                    "Placa", "Chassi",
                ]
                if c in dv_show.columns
            ]

            cols_visiveis = st.multiselect(
                "Colunas visíveis",
                dv_show.columns.tolist(),
                default=cols_default if cols_default else dv_show.columns.tolist()[:10],
                key="rel_cols",
            )

        if ordenar_por in dv.columns:
            serie_ord = dv[ordenar_por]
            if ordenar_por in [
                "Valor Total", "Mensalidade", "Comissão Carrera", "Comissão Vendedor R$", "Preço NF", "KickBack", "Km", "Período"
            ]:
                serie_ord = _to_num_serie(serie_ord)
            elif ordenar_por in [
                "dateLastUpdated", "Data de Inclusão", "Data de Status", "Data da retirada", "Vigência Final do contrato", "Data Assinatura"
            ]:
                serie_ord = pd.to_datetime(serie_ord, errors="coerce", dayfirst=True)

            dv_show = (
                dv_show.assign(_ord=serie_ord.values)
                .sort_values("_ord", ascending=not ordem_desc, na_position="last")
                .drop(columns="_ord")
            )
        elif ordenar_por in dv_show.columns:
            dv_show = dv_show.sort_values(ordenar_por, ascending=not ordem_desc, na_position="last")

        if cols_visiveis:
            dv_show = dv_show[cols_visiveis]

        st.dataframe(
            dv_show,
            use_container_width=True,
            height=520,
            hide_index=True,
            column_config={
                "Mensalidade": st.column_config.NumberColumn("Mensalidade", format="R$ %.2f"),
                "Valor Total": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
                "Comissão Carrera": st.column_config.NumberColumn("Comissão Carrera", format="R$ %.2f"),
                "Comissão Vendedor R$": st.column_config.NumberColumn("Comissão Vendedor", format="R$ %.2f"),
                "KickBack": st.column_config.NumberColumn("KickBack", format="R$ %.2f"),
                "Preço NF": st.column_config.NumberColumn("Preço NF", format="R$ %.2f"),
                "Km": st.column_config.NumberColumn("Km", format="%d"),
                "Período": st.column_config.NumberColumn("Período", format="%d"),
            },
        )

        st.markdown("### 🔎 Detalhe do Pedido")
        if "Pedido" in dv.columns and not dv.empty:
            pedidos_unicos = sorted(dv["Pedido"].astype(str).dropna().unique().tolist())
            pedido_sel = st.selectbox(
                "Selecione um pedido",
                [""] + pedidos_unicos,
                key="rel_det_pedido",
            )

            if pedido_sel:
                detalhe = dv[dv["Pedido"].astype(str) == str(pedido_sel)].copy()
                detalhe_show = _preparar_exibicao(detalhe)
                st.dataframe(detalhe_show, use_container_width=True, hide_index=True, height=220)

        buf = io.BytesIO()
        dv_export = _preparar_exibicao(dv)
        dv_export.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)

        st.download_button(
            "📥 Exportar Excel",
            data=buf.getvalue(),
            file_name=f"relatorio_carrera_{datetime.date.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="rel_download",
        )

    # ──────────────────────────────────────────────────────────────────────
    # ABA DADOS
    # ──────────────────────────────────────────────────────────────────────
    if pode_editar:
        with abas[1]:
            st.markdown(f"<p class='page-title' style='font-size:24px'>📤 Gestão de Dados</p>", unsafe_allow_html=True)
            st.markdown("#### 🤖 Extrações LM")
            st.caption("Execute os scripts em sequência. Cada etapa depende da anterior.")

            scripts = [
                ("1️⃣ Extrair Pedidos LM", "Extracao_LM.py", "Extrai pedidos da API → Lista_LM.xlsx"),
                ("2️⃣ Detalhar Carros", "Estrutura_Carros.py", "Detalha carros por pedido → vListaCarrosDetalhes.xlsx"),
                ("3️⃣ Extrair Preços/Ofertas", "Executa_Precos.py", "Extrai ofertas por canal → Ofertas_Todos_SalesChannels.xlsx"),
                ("4️⃣ Consolidar Base LM", "Consolida_base.py", "Merge de todas as bases → base_consolidada_completa.xlsx"),
            ]

            for label, script, desc in scripts:
                c1, c2 = st.columns([2, 6])
                script_path = os.path.join(DADOS_DIR, script)
                existe = os.path.exists(script_path)

                with c1:
                    if st.button(
                        label,
                        key=f"run_{script}",
                        use_container_width=True,
                        disabled=not existe,
                        type="primary",
                    ):
                        st.session_state[f"run_{script}_ok"] = True

                with c2:
                    st.caption("⚠️ Não encontrado" if not existe else desc)

                if st.session_state.pop(f"run_{script}_ok", False):
                    with st.expander(f"📋 Log — {label}", expanded=True):
                        try:
                            proc = subprocess.Popen(
                                [sys.executable, script_path],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                text=True,
                                cwd=DADOS_DIR,
                            )

                            output = []
                            placeholder = st.empty()

                            for line in proc.stdout:
                                output.append(line.rstrip())
                                placeholder.code("\n".join(output[-30:]))

                            proc.wait()

                            if proc.returncode == 0:
                                st.cache_data.clear()
                                st.success("✅ Concluído!")
                            else:
                                st.error("❌ Erro na execução.")
                        except Exception as e:
                            st.error(f"Erro: {e}")

            st.divider()
            st.markdown("#### 📁 Arquivos encontrados em Dados")

            arquivos_status = [
                ("Base consolidada XLSX", ARQ_BASE_PRINCIPAL_XLSX),
                ("Base consolidada Parquet", ARQ_BASE_PRINCIPAL_PARQUET),
                ("Base Salesforce", ARQ_SALESFORCE),
                ("Pedidos manuais", ARQ_MANUAIS),
                ("Cockpit Carrera", ARQ_COCKPIT),
            ]

            for nome, caminho in arquivos_status:
                if os.path.exists(caminho):
                    dt = datetime.datetime.fromtimestamp(os.path.getmtime(caminho)).strftime("%d/%m/%Y %H:%M")
                    st.success(f"{nome}: encontrado · atualizado em {dt}")
                else:
                    st.warning(f"{nome}: não encontrado")

    # ──────────────────────────────────────────────────────────────────────
    # ABA CADASTRO MANUAL
    # ──────────────────────────────────────────────────────────────────────
    if pode_editar:
        with abas[2]:
            st.markdown(f"<p class='page-title' style='font-size:24px'>➕ Cadastro Manual de Pedidos</p>", unsafe_allow_html=True)
            st.markdown(
                "<p class='mini-note'>Para pedidos que não constam na base principal. "
                "O consultor pode ser preenchido automaticamente via Salesforce local.</p>",
                unsafe_allow_html=True,
            )

            df_sf = _ler_salesforce_local()

            locadoras_opts = ["LM FROTAS", "RCI", "TOOT", "GM Fleet", "Arval", "Localiza", "Outra"]
            segmentos_opts = ["Sign & Drive", "S&D Empresas", "Nissan Move", "AssineCar GWM", "GM Fleet", "GAC Go and Drive", "AssineCar Multbrand", "Outro"]
            status_opts = ["Em locação", "Contrato assinado", "Pedido concluído", "Cancelado", "Aguardando", "Outro"]

            with st.form("form_manual"):
                st.markdown("**📋 Identificação**")
                m1, m2, m3 = st.columns(3)
                with m1:
                    loc = st.selectbox("Locadora *", locadoras_opts)
                    seg = st.selectbox("Segmento *", segmentos_opts)
                with m2:
                    pedido = st.text_input("Nº Pedido *")
                    cliente = st.text_input("Cliente *")
                with m3:
                    doc = st.text_input("CPF / CNPJ *")
                    status = st.selectbox("Status", status_opts)

                st.markdown("**🚗 Veículo**")
                v1, v2, v3 = st.columns(3)
                with v1:
                    modelo = st.text_input("Modelo")
                    cor = st.text_input("Cor")
                with v2:
                    chassi = st.text_input("Chassi")
                    placa = st.text_input("Placa")
                with v3:
                    marca = st.text_input("Marca")
                    opcional = st.text_input("Opcional")

                st.markdown("**📅 Contrato**")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    data_ass = st.date_input("Data Assinatura", value=None, format="DD/MM/YYYY")
                with c2:
                    plano = st.number_input("Plano (meses)", min_value=0, step=6, value=0)
                with c3:
                    km = st.number_input("KM Mensal", min_value=0, step=500, value=0)
                with c4:
                    mensalidade = st.number_input("Mensalidade (R$)", min_value=0.0, step=100.0, value=0.0)

                st.markdown("**📍 Local**")
                l1, l2, l3 = st.columns(3)
                with l1:
                    local_venda = st.text_input("Local de Venda")
                with l2:
                    uf = st.text_input("UF")
                with l3:
                    city = st.text_input("Cidade")

                consultor_preview = _lookup_consultor(df_sf, pedido) if pedido else "—"
                if pedido:
                    cor_info = "#22c55e" if consultor_preview != "Não encontrado" else "#f59e0b"
                    st.markdown(
                        f"<p style='font-size:13px;color:{cor_info}'>👤 Consultor: <b>{consultor_preview}</b></p>",
                        unsafe_allow_html=True,
                    )

                enviado = st.form_submit_button("💾 Cadastrar Pedido", use_container_width=True, type="primary")

            if enviado:
                if not pedido or not cliente or not doc:
                    st.error("Nº Pedido, Cliente e CPF/CNPJ são obrigatórios.")
                else:
                    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                    dados = {
                        "Locadora": loc,
                        "Segmento": seg,
                        "Pedido": pedido,
                        "Nome": cliente,
                        "Documento": doc,
                        "Tipo": _tipo_cliente(doc),
                        "Status": status,
                        "Modelo Oficial": modelo,
                        "Cor": cor,
                        "Chassi": chassi,
                        "Placa": placa,
                        "Marca": marca,
                        "Opcional": opcional,
                        "Data Assinatura": data_ass.strftime("%d/%m/%Y") if data_ass else "",
                        "Período": str(plano),
                        "Km": str(km),
                        "Mensalidade": str(mensalidade),
                        "Local de Venda": local_venda,
                        "UF": uf,
                        "City": city,
                        "Venda": consultor_preview,
                        "Data de Inclusão": agora,
                        "Origem venda": "Manual",
                    }

                    pg = st.progress(0, text="Salvando...")
                    pg.progress(60, text="Gravando arquivo local...")

                    if _gravar_manual_local(dados):
                        pg.progress(100, text="Concluído!")
                        _ler_manuais_local.clear()
                        st.cache_data.clear()
                        st.success(f"✅ Pedido **{pedido}** cadastrado!")
                        st.balloons()

            st.divider()
            st.markdown("**📋 Pedidos cadastrados manualmente**")
            df_man = _ler_manuais_local()
            if df_man.empty:
                st.info("Nenhum pedido manual cadastrado ainda.")
            else:
                st.dataframe(df_man, use_container_width=True, height=300, hide_index=True)