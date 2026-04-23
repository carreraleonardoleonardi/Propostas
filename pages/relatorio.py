# -*- coding: utf-8 -*-
"""
pages/relatorio.py
Relatório principal baseado na extração LM gerada em Dados/base_pedidos.parquet
ou Dados/base_pedidos.xlsx
"""

from __future__ import annotations

import calendar
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# =========================================================
# CONFIG VISUAL
# =========================================================
AZUL = "#213144"
DOURADO = "#C9A84C"
AZUL_CLARO = "#2E4A6A"
VERDE = "#22c55e"
VERMELHO = "#ef4444"
AMARELO_PLOT = "gold"
AZUL_PLOT = "#4A90D9"
VERDE_PLOT = "#2ecc71"

FASES_ENTREGUE = {
    "entregue",
    "pedido concluído",
    "pedido concluido",
    "concluído",
    "concluido",
}

STATUS_ASSINADOS = {
    "assinado",
    "signed",
}

BASE_DIR = Path(__file__).resolve().parent.parent
DADOS_DIR = BASE_DIR / "Dados"

ARQ_PEDIDOS_PARQUET = DADOS_DIR / "base_pedidos.parquet"
ARQ_PEDIDOS_EXCEL = DADOS_DIR / "base_pedidos.xlsx"
ARQ_SF = DADOS_DIR / "tbSalesforce.xlsx"
ARQ_COLAB = DADOS_DIR / "tbColaboradores.xlsx"
ARQ_SEG = DADOS_DIR / "tbSegmentos.xlsx"

CSS = f"""
<style>
.block-container {{
    padding-top: 1.2rem;
}}
h1, h2, h3 {{
    color: {AZUL};
}}
.kpi-card {{
    background: white;
    border: 1px solid #e8edf3;
    border-radius: 16px;
    padding: 16px 18px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.04);
}}
.kpi-title {{
    color: #6b7280;
    font-size: 0.92rem;
    margin-bottom: 4px;
}}
.kpi-value {{
    color: {AZUL};
    font-size: 1.8rem;
    font-weight: 700;
}}
.kpi-sub {{
    color: #6b7280;
    font-size: 0.86rem;
}}
hr {{
    margin-top: 1rem;
    margin-bottom: 1rem;
}}
</style>
"""


# =========================================================
# HELPERS
# =========================================================
def _brl(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def _num(v) -> float:
    if pd.isna(v):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)

    s = str(v).strip().replace("R$", "").replace(" ", "")
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def _texto(v) -> str:
    if pd.isna(v) or v is None:
        return ""
    return str(v).strip()


def _normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _padronizar_datas(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    return df


def _render_kpi(col, titulo: str, valor: str, subtitulo: str = "") -> None:
    col.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">{titulo}</div>
            <div class="kpi-value">{valor}</div>
            <div class="kpi-sub">{subtitulo}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# CARGA
# =========================================================
@st.cache_data(ttl=300)
def carregar_pedidos() -> pd.DataFrame:
    if ARQ_PEDIDOS_PARQUET.exists():
        df = pd.read_parquet(ARQ_PEDIDOS_PARQUET)
    elif ARQ_PEDIDOS_EXCEL.exists():
        df = pd.read_excel(ARQ_PEDIDOS_EXCEL)
    else:
        return pd.DataFrame()

    df = _normalizar_colunas(df)
    df = _padronizar_datas(
        df,
        ["data_criacao", "data_assinatura", "data_agendamento", "data_entrega"]
    )

    if "valor_total" in df.columns:
        df["valor_total"] = df["valor_total"].apply(_num)
    if "preco_nf" in df.columns:
        df["preco_nf"] = df["preco_nf"].apply(_num)
    if "quantidade_veiculos" in df.columns:
        df["quantidade_veiculos"] = pd.to_numeric(df["quantidade_veiculos"], errors="coerce").fillna(1)

    return df


@st.cache_data(ttl=300)
def carregar_colaboradores() -> pd.DataFrame:
    if not ARQ_COLAB.exists():
        return pd.DataFrame()
    df = pd.read_excel(ARQ_COLAB)
    return _normalizar_colunas(df)


@st.cache_data(ttl=300)
def carregar_segmentos() -> pd.DataFrame:
    if not ARQ_SEG.exists():
        return pd.DataFrame()
    df = pd.read_excel(ARQ_SEG)
    return _normalizar_colunas(df)


@st.cache_data(ttl=300)
def carregar_salesforce() -> pd.DataFrame:
    if not ARQ_SF.exists():
        return pd.DataFrame()

    df = pd.read_excel(ARQ_SF)
    df = _normalizar_colunas(df)

    cols_datas = [
        "Data Assinatura Contrat",
        "DataHora Agendamento",
        "Data agendamento",
    ]
    for c in cols_datas:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)

    return df


@st.cache_data(ttl=300)
def montar_base() -> pd.DataFrame:
    df = carregar_pedidos()
    if df.empty:
        return df

    df = df.copy()

    # -----------------------------------------------------
    # Colaboradores
    # -----------------------------------------------------
    colab = carregar_colaboradores()
    if not colab.empty and "consultor" in df.columns and "Colaborador" in colab.columns:
        colunas_colab = [
            c for c in ["Colaborador", "Frente", "Gerente", "Resultado", "Tipo_Acesso"]
            if c in colab.columns
        ]
        if colunas_colab:
            df = df.merge(
                colab[colunas_colab].drop_duplicates("Colaborador"),
                left_on="consultor",
                right_on="Colaborador",
                how="left",
                suffixes=("", "_colab"),
            )

    # -----------------------------------------------------
    # Segmentos
    # -----------------------------------------------------
    seg = carregar_segmentos()
    if not seg.empty and "segmento" in df.columns and "Segmento" in seg.columns:
        colunas_seg = [c for c in ["Segmento", "Locadora"] if c in seg.columns]
        if colunas_seg:
            df = df.merge(
                seg[colunas_seg].drop_duplicates("Segmento"),
                left_on="segmento",
                right_on="Segmento",
                how="left",
            )

    # -----------------------------------------------------
    # Salesforce como apoio
    # -----------------------------------------------------
    sf = carregar_salesforce()
    if not sf.empty and "pedido_id" in df.columns and "Nro do Pedido" in sf.columns:
        df = df.merge(
            sf.drop_duplicates("Nro do Pedido"),
            left_on="pedido_id",
            right_on="Nro do Pedido",
            how="left",
            suffixes=("", "_sf"),
        )

    # -----------------------------------------------------
    # Colunas derivadas
    # -----------------------------------------------------
    if "status_pedido" in df.columns:
        df["status_pedido_norm"] = df["status_pedido"].astype(str).str.strip().str.lower()
    else:
        df["status_pedido_norm"] = ""

    if "fase" in df.columns:
        df["fase_norm"] = df["fase"].astype(str).str.strip().str.lower()
    else:
        df["fase_norm"] = ""

    if "status_entrega" in df.columns:
        df["status_entrega_norm"] = df["status_entrega"].astype(str).str.strip().str.lower()
    else:
        df["status_entrega_norm"] = ""

    df["assinado_flag"] = (
        df["status_pedido_norm"].isin(STATUS_ASSINADOS)
        | df.get("data_assinatura", pd.Series(index=df.index)).notna()
    )

    df["entregue_flag"] = (
        df["fase_norm"].isin(FASES_ENTREGUE)
        | df["status_entrega_norm"].isin(FASES_ENTREGUE)
        | df.get("data_entrega", pd.Series(index=df.index)).notna()
    )

    if "quantidade_veiculos" not in df.columns:
        df["quantidade_veiculos"] = 1

    df["quantidade_veiculos"] = pd.to_numeric(df["quantidade_veiculos"], errors="coerce").fillna(1)

    if "valor_total" not in df.columns:
        df["valor_total"] = 0.0

    if "preco_nf" not in df.columns:
        df["preco_nf"] = 0.0

    # Data principal para análises
    if "data_assinatura" in df.columns:
        df["data_referencia"] = df["data_assinatura"]
    else:
        df["data_referencia"] = pd.NaT

    if "data_criacao" in df.columns:
        sem_assinatura = df["data_referencia"].isna()
        df.loc[sem_assinatura, "data_referencia"] = df.loc[sem_assinatura, "data_criacao"]

    return df


# =========================================================
# FILTROS
# =========================================================
def aplicar_filtros(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.markdown("## Filtros")

    if "data_referencia" in df.columns and df["data_referencia"].notna().any():
        data_min = df["data_referencia"].min()
        data_max = df["data_referencia"].max()
        periodo_padrao = (
            data_min.date(),
            data_max.date(),
        )
    else:
        hoje = pd.Timestamp.today().date()
        periodo_padrao = (hoje, hoje)

    periodo = st.sidebar.date_input("Período", value=periodo_padrao)

    frente_opts = sorted([x for x in df.get("Frente", pd.Series(dtype=str)).dropna().astype(str).unique() if x.strip()])
    gerente_opts = sorted([x for x in df.get("Gerente", pd.Series(dtype=str)).dropna().astype(str).unique() if x.strip()])
    consultor_opts = sorted([x for x in df.get("consultor", pd.Series(dtype=str)).dropna().astype(str).unique() if x.strip()])
    segmento_opts = sorted([x for x in df.get("segmento", pd.Series(dtype=str)).dropna().astype(str).unique() if x.strip()])
    fornecedor_opts = sorted([x for x in df.get("fornecedor", pd.Series(dtype=str)).dropna().astype(str).unique() if x.strip()])
    locadora_opts = sorted([x for x in df.get("Locadora", pd.Series(dtype=str)).dropna().astype(str).unique() if x.strip()])
    dealer_opts = sorted([x for x in df.get("dealer", pd.Series(dtype=str)).dropna().astype(str).unique() if x.strip()])

    frentes = st.sidebar.multiselect("Frente", frente_opts)
    gerentes = st.sidebar.multiselect("Gerente", gerente_opts)
    consultores = st.sidebar.multiselect("Consultor", consultor_opts)
    segmentos = st.sidebar.multiselect("Segmento", segmento_opts)
    fornecedores = st.sidebar.multiselect("Fornecedor", fornecedor_opts)
    locadoras = st.sidebar.multiselect("Locadora", locadora_opts)
    dealers = st.sidebar.multiselect("Dealer", dealer_opts)

    out = df.copy()

    if isinstance(periodo, tuple) and len(periodo) == 2 and "data_referencia" in out.columns:
        ini = pd.to_datetime(periodo[0])
        fim = pd.to_datetime(periodo[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        out = out[(out["data_referencia"] >= ini) & (out["data_referencia"] <= fim)]

    if frentes and "Frente" in out.columns:
        out = out[out["Frente"].astype(str).isin(frentes)]

    if gerentes and "Gerente" in out.columns:
        out = out[out["Gerente"].astype(str).isin(gerentes)]

    if consultores and "consultor" in out.columns:
        out = out[out["consultor"].astype(str).isin(consultores)]

    if segmentos and "segmento" in out.columns:
        out = out[out["segmento"].astype(str).isin(segmentos)]

    if fornecedores and "fornecedor" in out.columns:
        out = out[out["fornecedor"].astype(str).isin(fornecedores)]

    if locadoras and "Locadora" in out.columns:
        out = out[out["Locadora"].astype(str).isin(locadoras)]

    if dealers and "dealer" in out.columns:
        out = out[out["dealer"].astype(str).isin(dealers)]

    return out


# =========================================================
# KPIS
# =========================================================
def render_kpis(df: pd.DataFrame) -> None:
    contratos_assinados = int(df["assinado_flag"].sum()) if "assinado_flag" in df.columns else 0
    carros_assinados = int(df.loc[df["assinado_flag"], "quantidade_veiculos"].sum()) if "assinado_flag" in df.columns else 0
    carros_entregues = int(df.loc[df["entregue_flag"], "quantidade_veiculos"].sum()) if "entregue_flag" in df.columns else 0

    previsao_entrega = 0
    if "data_agendamento" in df.columns and "entregue_flag" in df.columns:
        previsao_entrega = int(
            df.loc[
                df["data_agendamento"].notna() & (~df["entregue_flag"]),
                "quantidade_veiculos"
            ].sum()
        )

    ticket_medio = df.loc[df["valor_total"] > 0, "valor_total"].mean() if "valor_total" in df.columns else 0

    top_vendedor = "—"
    if "consultor" in df.columns and "quantidade_veiculos" in df.columns and not df.empty:
        ranking = (
            df.groupby("consultor", dropna=False)["quantidade_veiculos"]
            .sum()
            .sort_values(ascending=False)
        )
        if not ranking.empty:
            top_vendedor = str(ranking.index[0])

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    _render_kpi(c1, "Contratos Assinados", f"{contratos_assinados}")
    _render_kpi(c2, "Carros Assinados", f"{carros_assinados}")
    _render_kpi(c3, "Previsão de Entrega", f"{previsao_entrega}")
    _render_kpi(c4, "Carros Entregues", f"{carros_entregues}")
    _render_kpi(c5, "Ticket Médio", _brl(ticket_medio))
    _render_kpi(c6, "Top Vendedor", top_vendedor)


# =========================================================
# CURVA
# =========================================================
def render_curva_mensal(df: pd.DataFrame) -> None:
    st.subheader("Curva de Performance")

    if "data_referencia" not in df.columns:
        st.info("Sem dados suficientes para exibir a curva.")
        return

    base = df.copy()
    base = base[base["data_referencia"].notna()]

    if base.empty:
        st.info("Sem dados suficientes para exibir a curva.")
        return

    base["_ano"] = base["data_referencia"].dt.year
    base["_mes"] = base["data_referencia"].dt.month
    base["_dia"] = base["data_referencia"].dt.day

    diario = (
        base.groupby(["_ano", "_mes", "_dia"], as_index=False)["quantidade_veiculos"]
        .sum()
        .rename(columns={"quantidade_veiculos": "carros"})
    )

    hoje = pd.Timestamp.today()
    ano_atual = hoje.year
    mes_atual = hoje.month

    if mes_atual == 1:
        ano_passado = ano_atual - 1
        mes_passado = 12
    else:
        ano_passado = ano_atual
        mes_passado = mes_atual - 1

    mensal = (
        base.groupby(["_ano", "_mes"], as_index=False)["quantidade_veiculos"]
        .sum()
        .rename(columns={"quantidade_veiculos": "carros"})
    )

    melhor = mensal.sort_values("carros", ascending=False).head(1)
    if melhor.empty:
        melhor_ano, melhor_mes = ano_atual, mes_atual
    else:
        melhor_ano = int(melhor.iloc[0]["_ano"])
        melhor_mes = int(melhor.iloc[0]["_mes"])

    def curva(ano: int, mes: int) -> pd.DataFrame:
        sub = diario[(diario["_ano"] == ano) & (diario["_mes"] == mes)][["_dia", "carros"]].copy()
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        dias = pd.DataFrame({"_dia": range(1, ultimo_dia + 1)})
        sub = dias.merge(sub, on="_dia", how="left")
        sub["carros"] = sub["carros"].fillna(0).cumsum()
        return sub

    df_atual = curva(ano_atual, mes_atual)
    df_passado = curva(ano_passado, mes_passado)
    df_melhor = curva(melhor_ano, melhor_mes)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_passado["_dia"], y=df_passado["carros"],
        mode="lines", name="Mês passado",
        line=dict(color=AZUL_PLOT, width=3)
    ))
    fig.add_trace(go.Scatter(
        x=df_melhor["_dia"], y=df_melhor["carros"],
        mode="lines", name="Melhor mês",
        line=dict(color=VERDE_PLOT, width=3)
    ))
    fig.add_trace(go.Scatter(
        x=df_atual["_dia"], y=df_atual["carros"],
        mode="lines", name="Mês atual",
        line=dict(color=AMARELO_PLOT, width=3)
    ))

    fig.update_layout(
        height=420,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis_title="Dia do mês",
        yaxis_title="Carros acumulados",
        legend_title="Séries",
    )

    st.plotly_chart(fig, use_container_width=True)


# =========================================================
# GRÁFICOS
# =========================================================
def render_graficos(df: pd.DataFrame) -> None:
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Evolução mensal de carros assinados")
        if "data_referencia" not in df.columns:
            st.info("Sem dados.")
        else:
            base = df[df["data_referencia"].notna()].copy()

            if base.empty:
                st.info("Sem dados.")
            else:
                base["ano_mes"] = base["data_referencia"].dt.to_period("M").astype(str)
                mensal = (
                    base.groupby("ano_mes", as_index=False)["quantidade_veiculos"]
                    .sum()
                )

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=mensal["ano_mes"],
                    y=mensal["quantidade_veiculos"],
                    name="Carros",
                    marker_color=AZUL
                ))
                fig.update_layout(
                    height=380,
                    paper_bgcolor="white",
                    plot_bgcolor="white",
                    margin=dict(l=20, r=20, t=20, b=20),
                    xaxis_title="Mês",
                    yaxis_title="Quantidade",
                )
                st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Ranking de vendedores")
        if "consultor" not in df.columns or df.empty:
            st.info("Sem dados.")
        else:
            ranking = (
                df.groupby("consultor", as_index=False)["quantidade_veiculos"]
                .sum()
                .sort_values("quantidade_veiculos", ascending=False)
                .head(10)
            )

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=ranking["quantidade_veiculos"],
                y=ranking["consultor"],
                orientation="h",
                marker_color=DOURADO
            ))
            fig.update_layout(
                height=380,
                paper_bgcolor="white",
                plot_bgcolor="white",
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis_title="Carros",
                yaxis_title="Consultor",
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig, use_container_width=True)

    c3, c4 = st.columns(2)

    with c3:
        st.subheader("Entregas por fornecedor")
        if "fornecedor" not in df.columns or df.empty or "entregue_flag" not in df.columns:
            st.info("Sem dados.")
        else:
            entregas = (
                df[df["entregue_flag"]]
                .groupby("fornecedor", as_index=False)["quantidade_veiculos"]
                .sum()
                .sort_values("quantidade_veiculos", ascending=False)
                .head(10)
            )

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=entregas["fornecedor"],
                y=entregas["quantidade_veiculos"],
                marker_color=VERDE
            ))
            fig.update_layout(
                height=380,
                paper_bgcolor="white",
                plot_bgcolor="white",
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis_title="Fornecedor",
                yaxis_title="Carros entregues",
            )
            st.plotly_chart(fig, use_container_width=True)

    with c4:
        st.subheader("Agendamentos futuros")
        if "data_agendamento" not in df.columns:
            st.info("Sem dados.")
        else:
            futuro = df[
                df["data_agendamento"].notna()
                & (df["data_agendamento"] >= pd.Timestamp.today().normalize())
            ].copy()

            if futuro.empty:
                st.info("Sem agendamentos futuros.")
            else:
                futuro["dia"] = futuro["data_agendamento"].dt.date.astype(str)
                agenda = (
                    futuro.groupby("dia", as_index=False)["quantidade_veiculos"]
                    .sum()
                    .sort_values("dia")
                )

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=agenda["dia"],
                    y=agenda["quantidade_veiculos"],
                    mode="lines+markers",
                    line=dict(color=AZUL_CLARO, width=3)
                ))
                fig.update_layout(
                    height=380,
                    paper_bgcolor="white",
                    plot_bgcolor="white",
                    margin=dict(l=20, r=20, t=20, b=20),
                    xaxis_title="Data",
                    yaxis_title="Carros agendados",
                )
                st.plotly_chart(fig, use_container_width=True)


# =========================================================
# TABELA + EXPORTAÇÃO
# =========================================================
@st.cache_data(ttl=300)
def gerar_excel_download(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Relatorio")
    return output.getvalue()


def render_tabela(df: pd.DataFrame) -> None:
    st.subheader("Base detalhada")

    colunas_preferidas = [
        "pedido_id",
        "order_item_id",
        "cliente",
        "consultor",
        "Gerente",
        "Frente",
        "fornecedor",
        "segmento",
        "Locadora",
        "dealer",
        "modelo",
        "marca",
        "status_pedido",
        "status_entrega",
        "fase",
        "valor_total",
        "preco_nf",
        "quantidade_veiculos",
        "data_criacao",
        "data_assinatura",
        "data_agendamento",
        "data_entrega",
        "cidade",
        "estado",
    ]

    cols_show = [c for c in colunas_preferidas if c in df.columns]
    if not cols_show:
        cols_show = list(df.columns)

    df_show = df[cols_show].copy()

    for c in ["valor_total", "preco_nf"]:
        if c in df_show.columns:
            df_show[c] = df_show[c].apply(_brl)

    st.dataframe(df_show, use_container_width=True, height=520)

    excel_bytes = gerar_excel_download(df_show)
    st.download_button(
        "Baixar Excel",
        data=excel_bytes,
        file_name="relatorio_lm.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


# =========================================================
# MAIN
# =========================================================
def render() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("Relatório de Vendas e Entregas")

    base = montar_base()

    if base.empty:
        st.warning(
            "Não encontrei a base principal de pedidos. "
            "Verifique se existe 'Dados/atual/lm_atual.parquet' ou 'Dados/base_pedidos.xlsx'."
        )
        return

    df = aplicar_filtros(base)

    if df.empty:
        st.info("Nenhum registro encontrado para os filtros selecionados.")
        return

    render_kpis(df)
    st.markdown("<hr>", unsafe_allow_html=True)

    render_curva_mensal(df)
    st.markdown("<hr>", unsafe_allow_html=True)

    render_graficos(df)
    st.markdown("<hr>", unsafe_allow_html=True)

    render_tabela(df)


# compatibilidade
show = render