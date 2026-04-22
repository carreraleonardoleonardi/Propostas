# =========================================================
# pages/relatorio.py
# Relatório de Vendas e Entregas — Carrera Signature
# =========================================================
#
# ESTRUTURA DE ARQUIVOS ESPERADA:
#   Dados/
#     tbSalesforce.xlsx      ← base principal (Salesforce)
#     tbColaboradores.xlsx   ← mapa vendedor → frente, gerente
#     tbSegmentos.xlsx       ← mapa segmento → locadora
#     tbFabricante.xlsx      ← lista de marcas (opcional)
#     tbCalendario.xlsx      ← dimensão calendário (opcional)
#
# COLUNAS CHAVE (tbSalesforce):
#   "Data Assinatura Contrat", "Proprietário da oportunidade",
#   "Nro do Pedido", "Fase", "Status da Entrega",
#   "Quantidade de veículos", "Comissionamento",
#   "Fornecedor", "Origem da venda", "Loja da Entrega",
#   "DataHora Agendamento", "Data agendamento",
#   "Nome da conta", "Cliente da Nota Fiscal",
#   "Chassi", "Placa", "Cidade de cobrança"
# =========================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import datetime
import os
from io import BytesIO
from pathlib import Path

# ── Cores Carrera ─────────────────────────────────────────
AZUL         = "#213144"
DOURADO      = "#C9A84C"
AZUL_CLARO   = "#2E4A6A"
VERDE        = "#22c55e"
VERMELHO     = "#ef4444"
AMARELO_PLOT = "gold"
AZUL_PLOT    = "#4A90D9"
VERDE_PLOT   = "#2ecc71"

# ── Caminhos ──────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent   # raiz do projeto
DADOS_DIR  = BASE_DIR / "Dados"

ARQ_SF     = DADOS_DIR / "tbSalesforce.xlsx"
ARQ_COLAB  = DADOS_DIR / "tbColaboradores.xlsx"
ARQ_SEG    = DADOS_DIR / "tbSegmentos.xlsx"
ARQ_FAB    = DADOS_DIR / "tbFabricante.xlsx"

# ── Fases que contam como "entregue" ──────────────────────
FASES_ENTREGUE = {"entregue", "pedido concluído", "concluído", "concluido"}

# =========================================================
# CSS
# =========================================================
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

.rel-wrap  {{ font-family: 'Montserrat', sans-serif; }}

/* ── Header ── */
.rel-header {{
    background: linear-gradient(135deg, {AZUL} 0%, {AZUL_CLARO} 100%);
    border-radius: 18px; padding: 28px 36px; margin-bottom: 26px;
    display: flex; align-items: center; justify-content: space-between;
    box-shadow: 0 8px 32px rgba(33,49,68,0.18);
}}
.rel-header-title {{
    font-size: 26px; font-weight: 800; color: #fff;
    margin: 0 0 4px 0; letter-spacing: -0.5px;
}}
.rel-header-sub {{
    font-size: 13px; font-weight: 500;
    color: rgba(255,255,255,0.6); margin: 0;
}}
.rel-header-badge {{
    background: {DOURADO}; color: #fff; font-size: 11px;
    font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase;
    padding: 6px 14px; border-radius: 20px; white-space: nowrap;
}}

/* ── KPIs ── */
.kpi-row {{
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px; margin-bottom: 26px;
}}
.kpi-card {{
    background: #fff; border-radius: 14px; padding: 18px 16px;
    border: 1px solid #E8ECF0;
    box-shadow: 0 2px 10px rgba(33,49,68,0.06);
    position: relative; overflow: hidden;
}}
.kpi-card::before {{
    content:''; position:absolute; top:0; left:0; right:0; height:3px;
    background: linear-gradient(90deg, {AZUL}, {DOURADO});
}}
.kpi-icon  {{ font-size:18px; margin-bottom:6px; }}
.kpi-label {{
    font-size:9px; font-weight:700; color:#94A3B8;
    text-transform:uppercase; letter-spacing:1px; margin-bottom:3px;
}}
.kpi-value {{ font-size:20px; font-weight:800; color:{AZUL}; line-height:1.1; }}
.kpi-sub   {{ font-size:11px; font-weight:600; color:#64748B; margin-top:3px; }}
.kpi-delta {{ font-size:10px; font-weight:600; margin-top:4px; color:{VERDE}; }}
.kpi-delta.neg {{ color:{VERMELHO}; }}

/* ── Section title ── */
.sec-title {{
    font-size:14px; font-weight:700; color:{AZUL};
    margin:0 0 12px 0; padding-bottom:8px;
    border-bottom:2px solid {DOURADO}; display:inline-block;
}}

/* ── Filtros ── */
.filtro-bar {{
    background:#fff; border:1px solid #E8ECF0; border-radius:14px;
    padding:14px 18px; margin-bottom:18px;
    box-shadow:0 2px 8px rgba(33,49,68,0.04);
}}

/* ── Badges status ── */
.badge-e {{ background:#dcfce7; color:#16a34a; padding:2px 9px; border-radius:20px; font-size:10px; font-weight:700; }}
.badge-p {{ background:#fef9c3; color:#ca8a04; padding:2px 9px; border-radius:20px; font-size:10px; font-weight:700; }}
.badge-c {{ background:#fee2e2; color:#dc2626; padding:2px 9px; border-radius:20px; font-size:10px; font-weight:700; }}

/* ── Info card ── */
.info-box {{
    background:#F0F4F8; border-left:4px solid {DOURADO};
    border-radius:8px; padding:12px 16px; font-size:13px;
    color:#374151; margin-bottom:18px;
}}

.empty-state      {{ text-align:center; padding:40px 24px; color:#94A3B8; }}
.empty-state-icon {{ font-size:44px; margin-bottom:10px; }}
.empty-state-text {{ font-size:14px; font-weight:600; }}

[data-testid="stDataFrame"] {{ font-family:'Montserrat',sans-serif !important; }}
</style>
"""


# =========================================================
# HELPERS
# =========================================================

def _brl(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except Exception:
        return "—"


def _num(v) -> float:
    if pd.isna(v):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("R$","").replace(" ","").replace(".","").replace(",",".")
    try:
        return float(s)
    except Exception:
        return 0.0


def _has(df: pd.DataFrame, col: str) -> bool:
    return col in df.columns


def _delta(atual, anterior) -> str:
    try:
        a, b = float(atual), float(anterior)
        if b != 0:
            pct   = (a - b) / b * 100
            sinal = "+" if pct >= 0 else ""
            cls   = "" if pct >= 0 else "neg"
            return f'<div class="kpi-delta {cls}">{sinal}{pct:.1f}% vs mês ant.</div>'
    except Exception:
        pass
    return ""


def _cls_fase(s: str) -> str:
    low = str(s).lower().strip()
    if any(k in low for k in FASES_ENTREGUE):
        return "entregue"
    if any(k in low for k in ("cancelad", "recusad")):
        return "cancelado"
    return "pendente"


def _col_first(df, *names):
    """Retorna o primeiro nome de coluna que existe no df."""
    for n in names:
        if n in df.columns:
            return n
    return None


# =========================================================
# CARGA DAS TABELAS
# =========================================================

@st.cache_data(ttl=300)
def _carregar_salesforce() -> pd.DataFrame:
    if not ARQ_SF.exists():
        return pd.DataFrame()

    df = pd.read_excel(ARQ_SF)
    df.columns = [str(c).strip() for c in df.columns]

    # Datas
    for c in ["Data Assinatura Contrat", "DataHora Agendamento", "Data agendamento"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)

    # Numéricos
    if "Comissionamento" in df.columns:
        df["Comissionamento"] = df["Comissionamento"].apply(_num)
    if "Quantidade de veículos" in df.columns:
        df["Quantidade de veículos"] = pd.to_numeric(df["Quantidade de veículos"], errors="coerce").fillna(0)

    # Nro do Pedido como string
    if "Nro do Pedido" in df.columns:
        df["Nro do Pedido"] = df["Nro do Pedido"].astype(str).str.strip()

    # Preenche textuais
    for c in ["Fornecedor","Origem da venda","Loja da Entrega",
              "Status da Entrega","Fase","Gerente","Frente"]:
        if c in df.columns:
            df[c] = df[c].fillna("Não informado")

    # Colunas de tempo derivadas
    if "Data Assinatura Contrat" in df.columns:
        df["_AnoMes"] = df["Data Assinatura Contrat"].dt.to_period("M").astype(str)
        df["_Ano"]    = df["Data Assinatura Contrat"].dt.year
        df["_Mes"]    = df["Data Assinatura Contrat"].dt.month
        df["_Dia"]    = df["Data Assinatura Contrat"].dt.day

    return df


@st.cache_data(ttl=600)
def _carregar_colaboradores() -> pd.DataFrame:
    if not ARQ_COLAB.exists():
        return pd.DataFrame()
    df = pd.read_excel(ARQ_COLAB)
    df.columns = [str(c).strip() for c in df.columns]
    return df


@st.cache_data(ttl=600)
def _carregar_segmentos() -> pd.DataFrame:
    if not ARQ_SEG.exists():
        return pd.DataFrame()
    df = pd.read_excel(ARQ_SEG)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _montar_base() -> pd.DataFrame:
    df   = _carregar_salesforce()
    colab = _carregar_colaboradores()
    seg   = _carregar_segmentos()

    if df.empty:
        return df

    # Join com Colaboradores → traz Frente, Gerente, Resultado
    col_vend = "Proprietário da oportunidade"
    if not colab.empty and col_vend in df.columns and "Colaborador" in colab.columns:
        campos_colab = [c for c in ["Colaborador","Frente","Gerente","Resultado","Tipo_Acesso"]
                        if c in colab.columns]
        df = df.merge(
            colab[campos_colab].drop_duplicates("Colaborador"),
            left_on=col_vend, right_on="Colaborador", how="left",
            suffixes=("","_colab")
        )
        # Preenche Gerente/Frente que já existiam no SF com os da tabela
        for campo in ["Gerente","Frente"]:
            col_orig  = campo
            col_colab = campo + "_colab"
            if col_orig in df.columns and col_colab in df.columns:
                df[col_orig] = df[col_orig].where(df[col_orig] != "Não informado", df[col_colab])
                df.drop(columns=[col_colab], inplace=True)
            elif col_colab in df.columns:
                df.rename(columns={col_colab: col_orig}, inplace=True)

    # Join com Segmentos → traz Locadora
    col_forn = "Fornecedor"
    if not seg.empty and col_forn in df.columns and "Segmento" in seg.columns:
        df = df.merge(
            seg[["Segmento","Locadora"]].drop_duplicates("Segmento"),
            left_on=col_forn, right_on="Segmento", how="left"
        )

    return df


# =========================================================
# SEÇÃO: KPIs
# =========================================================

def _render_kpis(df: pd.DataFrame, df_ant: pd.DataFrame):
    # Contratos / pedidos únicos
    col_ped = "Nro do Pedido"
    contratos    = df[col_ped].nunique()          if _has(df, col_ped) else len(df)
    contratos_ant= df_ant[col_ped].nunique()      if (not df_ant.empty and _has(df_ant, col_ped)) else 0

    # Carros assinados
    col_qtd = "Quantidade de veículos"
    carros_ass = int(df[col_qtd].sum())           if _has(df, col_qtd) else 0

    # Carros entregues
    carros_ent = 0
    col_fase = _col_first(df, "Fase","phase","orderStatus")
    if col_fase:
        mask_ent   = df[col_fase].astype(str).str.lower().str.strip().isin(FASES_ENTREGUE)
        if _has(df, col_qtd):
            carros_ent = int(df.loc[mask_ent, col_qtd].sum())
        else:
            carros_ent = int(mask_ent.sum())

    # Previsão a entregar (com agendamento)
    col_ag = _col_first(df, "DataHora Agendamento", "Data agendamento", "scheduledDate")
    previsao = 0
    if col_ag:
        mask_ag = df[col_ag].notna()
        previsao = int(df.loc[mask_ag, col_qtd].sum()) if _has(df, col_qtd) else int(mask_ag.sum())

    # Comissionamento / ticket médio
    comissao  = df["Comissionamento"].sum()          if _has(df, "Comissionamento") else 0
    ticket    = comissao / contratos                  if contratos > 0 else 0

    # Top vendedor
    col_v = _col_first(df, "Proprietário da oportunidade", "Vendedor", "consultor")
    top_v = df[col_v].mode()[0] if (col_v and not df[col_v].dropna().empty) else "—"

    kpis = [
        ("📄", "Contratos",          f"{contratos:,}",       "",               _delta(contratos, contratos_ant)),
        ("🚗", "Carros Assinados",   f"{carros_ass:,}",      "",               ""),
        ("📦", "Carros Entregues",   f"{carros_ent:,}",      "",               ""),
        ("📅", "Previsão Entrega",   f"{previsao:,}",        "com agendamento",""),
        ("💰", "Comissionamento",    _brl(comissao),         "",               ""),
        ("🏆", "Top Vendedor",       top_v,                  "no período",     ""),
    ]

    html = '<div class="kpi-row">'
    for icon, label, value, sub, delta in kpis:
        sub_html   = f'<div class="kpi-sub">{sub}</div>'   if sub   else ""
        html += f"""
        <div class="kpi-card">
            <div class="kpi-icon">{icon}</div>
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {sub_html}{delta}
        </div>"""
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# =========================================================
# SEÇÃO: Curva de Contratos (Plotly)
# =========================================================

def _render_curva(df: pd.DataFrame):
    st.markdown('<p class="sec-title">📈 Curva de Contratos — Mês Atual vs Anterior vs Melhor</p>',
                unsafe_allow_html=True)

    col_data = "Data Assinatura Contrat"
    col_ped  = "Nro do Pedido"

    if col_data not in df.columns or col_ped not in df.columns:
        st.info("Colunas de data ou pedido não encontradas para montar a curva.")
        return

    base = df[df[col_data].notna()].copy()
    if base.empty:
        st.info("Sem dados com data de assinatura no período.")
        return

    base["_A"] = base[col_data].dt.year
    base["_M"] = base[col_data].dt.month
    base["_D"] = base[col_data].dt.day

    diario = (
        base.groupby(["_A","_M","_D"])[col_ped]
        .nunique()
        .reset_index(name="Contratos")
    )

    totais_mes = (
        diario.groupby(["_A","_M"], as_index=False)["Contratos"]
        .sum()
        .sort_values("Contratos", ascending=False)
    )

    ref         = base[col_data].max()
    ano_at      = int(ref.year)
    mes_at      = int(ref.month)
    mes_p_num   = mes_at - 1  if mes_at > 1 else 12
    ano_p_num   = ano_at      if mes_at > 1 else ano_at - 1

    melhor      = totais_mes.iloc[0]
    ano_mel     = int(melhor["_A"])
    mes_mel     = int(melhor["_M"])

    def curva(ano, mes):
        sub = diario[(diario["_A"]==ano) & (diario["_M"]==mes)][["_D","Contratos"]].copy()
        dias = pd.DataFrame({"_D": range(1, 32)})
        sub  = dias.merge(sub, on="_D", how="left")
        sub["Contratos"] = sub["Contratos"].fillna(0).cumsum()
        return sub

    c_at  = curva(ano_at,    mes_at)
    c_ant = curva(ano_p_num, mes_p_num)
    c_mel = curva(ano_mel,   mes_mel)

    lbl_at  = f"{ano_at}-{str(mes_at).zfill(2)}"
    lbl_ant = f"{ano_p_num}-{str(mes_p_num).zfill(2)}"
    lbl_mel = f"{ano_mel}-{str(mes_mel).zfill(2)}"

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=c_ant["_D"], y=c_ant["Contratos"],
        mode="lines+markers", name=f"Mês Anterior ({lbl_ant})",
        line=dict(color=AZUL_PLOT, width=2, dash="dot"),
        marker=dict(size=5)
    ))
    fig.add_trace(go.Scatter(
        x=c_mel["_D"], y=c_mel["Contratos"],
        mode="lines+markers", name=f"Melhor Mês ({lbl_mel})",
        line=dict(color=VERDE_PLOT, width=2),
        marker=dict(size=5)
    ))
    fig.add_trace(go.Scatter(
        x=c_at["_D"], y=c_at["Contratos"],
        mode="lines+markers", name=f"Mês Atual ({lbl_at})",
        line=dict(color=AMARELO_PLOT, width=3),
        marker=dict(size=6),
        fill="tozeroy",
        fillcolor="rgba(201,168,76,0.08)"
    ))

    fig.update_layout(
        xaxis_title="Dia do mês",
        yaxis_title="Contratos acumulados",
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="#FAFBFC",
        paper_bgcolor="#FAFBFC",
        font=dict(family="Montserrat, sans-serif", size=12),
        xaxis=dict(showgrid=True, gridcolor="#E8ECF0", dtick=5),
        yaxis=dict(showgrid=True, gridcolor="#E8ECF0"),
    )

    st.plotly_chart(fig, use_container_width=True)


# =========================================================
# SEÇÃO: Evolução Mensal por Fornecedor
# =========================================================

def _render_evolucao_mensal(df: pd.DataFrame):
    st.markdown('<p class="sec-title">📊 Volume Mensal por Fornecedor</p>', unsafe_allow_html=True)

    if not _has(df, "_AnoMes") or not _has(df, "Nro do Pedido"):
        st.info("Sem dados suficientes para evolução mensal.")
        return

    col_forn = _col_first(df, "Fornecedor", "salesChannel", "Locadora")
    if not col_forn:
        st.info("Coluna de fornecedor não encontrada.")
        return

    evo = (
        df.groupby(["_AnoMes", col_forn])["Nro do Pedido"]
        .nunique()
        .reset_index(name="Contratos")
        .sort_values("_AnoMes")
    )

    fig = go.Figure()
    for forn in evo[col_forn].unique():
        sub = evo[evo[col_forn] == forn]
        fig.add_trace(go.Bar(
            x=sub["_AnoMes"], y=sub["Contratos"],
            name=str(forn)
        ))

    fig.update_layout(
        barmode="stack",
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="#FAFBFC",
        paper_bgcolor="#FAFBFC",
        font=dict(family="Montserrat, sans-serif", size=11),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="#E8ECF0"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)


# =========================================================
# SEÇÃO: Ranking Vendedores
# =========================================================

def _render_ranking(df: pd.DataFrame):
    st.markdown('<p class="sec-title">🏆 Ranking de Vendedores</p>', unsafe_allow_html=True)

    col_v = _col_first(df, "Proprietário da oportunidade", "Vendedor")
    if not col_v:
        st.info("Coluna de vendedor não encontrada.")
        return

    agg = {"Contratos": ("Nro do Pedido", "nunique") if _has(df, "Nro do Pedido") else (col_v, "count")}
    if _has(df, "Quantidade de veículos"):
        agg["Veículos"] = ("Quantidade de veículos", "sum")
    if _has(df, "Comissionamento"):
        agg["Comissão"] = ("Comissionamento", "sum")

    ranking = (
        df.groupby(col_v).agg(**agg)
        .reset_index()
        .rename(columns={col_v: "Vendedor"})
        .sort_values("Contratos", ascending=False)
        .reset_index(drop=True)
    )

    # Frente do colaborador, se disponível
    if _has(df, "Frente"):
        frentes = df[[col_v,"Frente"]].drop_duplicates(col_v)
        ranking = ranking.merge(frentes, left_on="Vendedor", right_on=col_v, how="left")
        ranking.drop(columns=[col_v], inplace=True, errors="ignore")

    medalhas = {0:"🥇", 1:"🥈", 2:"🥉"}
    ranking["Vendedor"] = [
        f"{medalhas.get(i,'')} {n}".strip() for i, n in enumerate(ranking["Vendedor"])
    ]

    if "Comissão" in ranking.columns:
        ranking["Comissão"] = ranking["Comissão"].apply(_brl)

    col_cfg = {
        "Vendedor":   st.column_config.TextColumn("👤 Vendedor"),
        "Contratos":  st.column_config.NumberColumn("📄 Contratos", format="%d"),
        "Veículos":   st.column_config.NumberColumn("🚗 Veículos",  format="%d"),
        "Comissão":   st.column_config.TextColumn("💰 Comissão"),
        "Frente":     st.column_config.TextColumn("🏪 Frente"),
    }

    st.dataframe(ranking, use_container_width=True, hide_index=True,
                 column_config={k: v for k, v in col_cfg.items() if k in ranking.columns})


# =========================================================
# SEÇÃO: Status de Entregas
# =========================================================

def _render_entregas(df: pd.DataFrame):
    st.markdown('<p class="sec-title">🚚 Status de Entregas</p>', unsafe_allow_html=True)

    col_fase   = _col_first(df, "Fase", "Status da Entrega", "orderStatus")
    col_status = _col_first(df, "Status da Entrega", "Fase")

    if not col_fase:
        st.info("Coluna de fase/status não encontrada.")
        return

    col_esq, col_dir = st.columns([1, 2], gap="large")

    with col_esq:
        contagem = df[col_fase].value_counts().reset_index()
        contagem.columns = ["Fase", "Qtd"]
        for _, row in contagem.iterrows():
            s   = str(row["Fase"])
            cls = _cls_fase(s)
            badge = "badge-e" if cls=="entregue" else "badge-c" if cls=="cancelado" else "badge-p"
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">'
                f'<span class="{badge}">{s}</span>'
                f'<span style="font-weight:800;color:{AZUL};font-size:18px;">{row["Qtd"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with col_dir:
        contagem_plot = df[col_fase].value_counts().reset_index()
        contagem_plot.columns = ["Fase","Qtd"]
        cores = [
            VERDE_PLOT if _cls_fase(s)=="entregue" else
            VERMELHO   if _cls_fase(s)=="cancelado" else
            AMARELO_PLOT
            for s in contagem_plot["Fase"]
        ]
        fig = go.Figure(go.Bar(
            x=contagem_plot["Fase"], y=contagem_plot["Qtd"],
            marker_color=cores, text=contagem_plot["Qtd"],
            textposition="outside"
        ))
        fig.update_layout(
            height=280, margin=dict(l=0,r=0,t=10,b=0),
            plot_bgcolor="#FAFBFC", paper_bgcolor="#FAFBFC",
            font=dict(family="Montserrat, sans-serif", size=11),
            showlegend=False,
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="#E8ECF0"),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Agenda de Agendamentos ──────────────────────────
    col_ag = _col_first(df, "DataHora Agendamento", "Data agendamento")
    if col_ag:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<p class="sec-title">📅 Próximos Agendamentos</p>', unsafe_allow_html=True)

        cols_ag = [c for c in [
            "Nro do Pedido", "Nome da conta", col_ag,
            "Loja da Entrega","Proprietário da oportunidade",
            "Quem Retira","Status da Entrega","Chassi","Placa"
        ] if _has(df, c)]

        df_ag = (
            df[df[col_ag].notna()][cols_ag]
            .sort_values(col_ag)
            .copy()
        )
        df_ag[col_ag] = pd.to_datetime(df_ag[col_ag], errors="coerce").dt.strftime("%d/%m/%Y %H:%M")

        if df_ag.empty:
            st.info("Nenhum agendamento no período filtrado.")
        else:
            st.dataframe(df_ag, use_container_width=True, hide_index=True)


# =========================================================
# SEÇÃO: Tabela Detalhada
# =========================================================

def _render_tabela(df: pd.DataFrame):
    st.markdown('<p class="sec-title">📋 Registros Detalhados</p>', unsafe_allow_html=True)

    if df.empty:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">🔍</div>
            <div class="empty-state-text">Nenhum registro com os filtros aplicados.</div>
        </div>""", unsafe_allow_html=True)
        return

    colunas_pref = [
        "Data Assinatura Contrat",
        "Nro do Pedido",
        "Proprietário da oportunidade",
        "Gerente",
        "Frente",
        "Nome da conta",
        "Cliente da Nota Fiscal",
        "Fornecedor",
        "Locadora",
        "Quantidade de veículos",
        "Fase",
        "Status da Entrega",
        "DataHora Agendamento",
        "Data agendamento",
        "Loja da Entrega",
        "Comissionamento",
        "Chassi",
        "Placa",
        "Cidade de cobrança",
        "Estado/Província de cobrança",
        "Origem da venda",
    ]

    cols_exib = [c for c in colunas_pref if _has(df, c)]
    df_show   = df[cols_exib].copy().sort_values(
        "Data Assinatura Contrat", ascending=False
    ) if "Data Assinatura Contrat" in df.columns else df[cols_exib].copy()

    # Formata data
    if "Data Assinatura Contrat" in df_show.columns:
        df_show["Data Assinatura Contrat"] = pd.to_datetime(
            df_show["Data Assinatura Contrat"], errors="coerce"
        ).dt.strftime("%d/%m/%Y")

    for c_ag in ["DataHora Agendamento","Data agendamento"]:
        if c_ag in df_show.columns:
            df_show[c_ag] = pd.to_datetime(
                df_show[c_ag], errors="coerce"
            ).dt.strftime("%d/%m/%Y")

    # Formata moeda
    if "Comissionamento" in df_show.columns:
        df_show["Comissionamento"] = df_show["Comissionamento"].apply(
            lambda v: _brl(v) if pd.notna(v) and v != 0 else "—"
        )

    st.dataframe(df_show, use_container_width=True, hide_index=True)

    # Exportação
    c1, c2, _ = st.columns([1, 1, 6])
    with c1:
        csv = df_show.to_csv(index=False, sep=";", encoding="utf-8-sig")
        st.download_button("⬇️ CSV", csv,
            file_name=f"relatorio_{datetime.date.today():%Y%m%d}.csv",
            mime="text/csv", use_container_width=True)
    with c2:
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df_show.to_excel(w, index=False, sheet_name="Relatório")
        buf.seek(0)
        st.download_button("⬇️ Excel", buf,
            file_name=f"relatorio_{datetime.date.today():%Y%m%d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True)


# =========================================================
# RENDER PRINCIPAL
# =========================================================

def render():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="rel-wrap">', unsafe_allow_html=True)

    hoje = datetime.date.today()

    # ── Header ──────────────────────────────────────────
    st.markdown(f"""
    <div class="rel-header">
        <div>
            <p class="rel-header-title">📈 Performance de Vendas e Entregas</p>
            <p class="rel-header-sub">Relatório consolidado · Carrera Signature</p>
        </div>
        <div class="rel-header-badge">Atualizado: {hoje:%d/%m/%Y}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Verificação de arquivos ─────────────────────────
    arquivos_faltando = [str(f) for f in [ARQ_SF] if not f.exists()]
    if arquivos_faltando:
        st.markdown(f"""
        <div class="info-box">
            ⚠️ <strong>Arquivo não encontrado:</strong> {', '.join(arquivos_faltando)}<br><br>
            Coloque os arquivos na pasta <code>Dados/</code> na raiz do projeto:<br>
            <code>Dados/tbSalesforce.xlsx</code> &nbsp;·&nbsp;
            <code>Dados/tbColaboradores.xlsx</code> &nbsp;·&nbsp;
            <code>Dados/tbSegmentos.xlsx</code>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ── Carga ────────────────────────────────────────────
    with st.spinner("Carregando dados..."):
        df = _montar_base()

    if df.empty:
        st.warning("Base vazia. Verifique o arquivo `Dados/tbSalesforce.xlsx`.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ── Info colunas (debug colapsável) ─────────────────
    with st.expander("ℹ️ Colunas disponíveis na base", expanded=False):
        st.code(", ".join(sorted(df.columns.tolist())))
        st.caption(f"Total de linhas: {len(df):,}")

    # ── Filtros ─────────────────────────────────────────
    st.markdown('<div class="filtro-bar">', unsafe_allow_html=True)
    c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5])

    # Período
    with c1:
        col_data = "Data Assinatura Contrat"
        if _has(df, col_data) and df[col_data].notna().any():
            d_min = df[col_data].min().date()
            d_max = df[col_data].max().date()
        else:
            d_min = d_max = hoje
        rv = st.date_input("📅 Período", value=(d_min, d_max),
                           min_value=d_min, max_value=d_max, key="rel_periodo")
        d_ini, d_fim = rv if len(rv) == 2 else (d_min, d_max)

    def _opts(col):
        return ["Todos"] + sorted(df[col].dropna().unique().tolist()) if _has(df, col) else ["Todos"]

    with c2:
        v_sel = st.selectbox("👤 Vendedor",  _opts("Proprietário da oportunidade"), key="rel_vend")
    with c3:
        g_sel = st.selectbox("🎯 Gerente",   _opts("Gerente"),                      key="rel_ger")
    with c4:
        fr_sel= st.selectbox("🏪 Frente",    _opts("Frente"),                       key="rel_fr")
    with c5:
        fn_sel= st.selectbox("🏷️ Fornecedor",_opts("Fornecedor"),                  key="rel_forn")
    with c6:
        st_sel= st.selectbox("🚚 Fase",      _opts("Fase"),                         key="rel_fase")
    with c7:
        lj_sel= st.selectbox("📍 Loja",      _opts("Loja da Entrega"),              key="rel_loja")

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Aplica filtros ────────────────────────────────────
    m = pd.Series(True, index=df.index)

    if _has(df, col_data) and df[col_data].notna().any():
        m &= (df[col_data].dt.date >= d_ini) & (df[col_data].dt.date <= d_fim)

    filtros_col = {
        "Proprietário da oportunidade": v_sel,
        "Gerente":                       g_sel,
        "Frente":                        fr_sel,
        "Fornecedor":                    fn_sel,
        "Fase":                          st_sel,
        "Loja da Entrega":               lj_sel,
    }
    for col, val in filtros_col.items():
        if val != "Todos" and _has(df, col):
            m &= df[col] == val

    df_fil = df[m].copy()

    # Mês anterior para delta
    mes_ini = hoje.replace(day=1)
    mes_ant = (mes_ini - datetime.timedelta(days=1)).replace(day=1)
    if _has(df, col_data) and df[col_data].notna().any():
        df_ant = df[
            (df[col_data].dt.year  == mes_ant.year) &
            (df[col_data].dt.month == mes_ant.month)
        ]
    else:
        df_ant = pd.DataFrame()

    # Contador
    st.caption(f"**{len(df_fil):,}** registros · "
               f"**{df_fil['Nro do Pedido'].nunique() if _has(df_fil,'Nro do Pedido') else len(df_fil):,}** "
               f"pedidos únicos · {d_ini:%d/%m/%Y} → {d_fim:%d/%m/%Y}")

    # ── KPIs ─────────────────────────────────────────────
    _render_kpis(df_fil, df_ant)

    # ── Curva de Contratos ────────────────────────────────
    _render_curva(df_fil)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Evolução + Ranking ───────────────────────────────
    col_evo, col_rank = st.columns([3, 2], gap="large")
    with col_evo:
        _render_evolucao_mensal(df_fil)
    with col_rank:
        _render_ranking(df_fil)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Entregas + Agendamentos ───────────────────────────
    _render_entregas(df_fil)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabela detalhada ─────────────────────────────────
    _render_tabela(df_fil)

    st.markdown('</div>', unsafe_allow_html=True)