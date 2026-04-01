import streamlit as st
import pandas as pd
import requests
import json
import datetime
import time
import os
from pdf_generator import gerar_pdf

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="Gerador de Propostas",
    page_icon="🚗",
    layout="wide"
)

# =========================================================
# SENHAS NO CÓDIGO
# =========================================================
SENHA_DESATIVAR = "DesativaSignature#2026"
SENHA_ATIVAR = "AtivaSignature#2026"
ARQUIVO_STATUS = "status_sistema.json"

# =========================================================
# WEBHOOK / PLANILHA RELATÓRIO
# =========================================================
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxzzTh8nlzwFmAdrB7-qXrhUiEeWGGOwH7ZGAuQeaGZHcTVRa1jASmrpU-ADQcCLZgTKw/exec"
URL_RELATORIO = "https://docs.google.com/spreadsheets/d/1bxjKSfD2MpBpV4swaBCjkhi8ElHV_8M97zxI6jgtv0w/export?format=csv"

# =========================================================
# CSS GLOBAL
# =========================================================
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.block-container {
    padding-top: 1.5rem;
}

.manutencao-wrapper {
    min-height: 72vh;
    display: flex;
    align-items: center;
    justify-content: center;
}

.manutencao-card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 22px;
    padding: 42px 32px;
    text-align: center;
    max-width: 760px;
    width: 100%;
    box-shadow: 0 10px 30px rgba(0,0,0,0.08);
}

.manutencao-titulo {
    font-size: 40px;
    font-weight: 700;
    color: #213144;
    margin-bottom: 12px;
}

.manutencao-subtitulo {
    font-size: 18px;
    color: #6B7280;
    line-height: 1.6;
    margin-bottom: 10px;
}

.card-gerenciamento {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 18px;
    padding: 24px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.06);
    margin-bottom: 20px;
}

.status-card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 18px;
    padding: 24px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.06);
    margin-bottom: 20px;
}

.small-muted {
    color: #6B7280;
    font-size: 0.92rem;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# BASES
# =========================================================
BASES = {
    "Sign & Drive": "https://docs.google.com/spreadsheets/d/1PfEemQ0vJ4TlS-q-x9hfU-IK1AqUVPun8It_Wi7pzgE/export?format=csv&gid=2034069788",
    "Sign & Drive Empresas": "https://docs.google.com/spreadsheets/d/1puuB21uOsC8-UXe4MpuGE_oSpgyj-tyoihT6u68InMk/export?format=csv",
    "Assine Car GWM": "https://docs.google.com/spreadsheets/d/1y9wBzxq6mb3OItBQ6IjrOpGW2t5QV8EADekDfLtkbRw/export?format=csv&gid=676006877",
    "Assine Car GWM - Blindado": "https://docs.google.com/spreadsheets/d/1zJB5EBhtB78RtJhqHSP6OQDX1_s0wrmMsz1C_tUKsMI/export?format=csv&gid=1332991446",
    "GAC Go and Drive": "https://docs.google.com/spreadsheets/d/1xvD_QyO9opePn2X-Z2fHZGySOPm9AgQ7EbUcwoddjPo/export?format=csv&gid=676006877",
    "Assine Car One": "https://docs.google.com/spreadsheets/d/1FgVXCyGyhqXyeXz3cYePDSZjRGgmJu9Jj6rAmasjeQQ/export?format=csv&gid=676006877",
    "Nissan Move": "https://docs.google.com/spreadsheets/d/1pmK--_5SGVKW-LRXUK7TIjptP5DNxfYQMHS-cXA_rzw/export?format=csv&gid=1044813671",
    "Assine Car Multbrand": "https://docs.google.com/spreadsheets/d/1l6exo6brmYVMm-16zhIt7MDiJp7YxGrGZd2-kYk4a7k/export?format=csv&gid=1489579420",
    "GM Fleet Rede": "https://docs.google.com/spreadsheets/d/1AZiK2C7FjZ_-lNSJ-3fICfWB7hzRnEU8a_WCGgmubak/export?format=csv&gid=1332991446",
    "GM Fleet PF": "https://docs.google.com/spreadsheets/d/153a41nRCYW65S1AtODo3u9aIJp2co20K2lAexpYHoGc/export?format=csv&gid=1332991446",
    "GM Fleet Elétricos": "https://docs.google.com/spreadsheets/d/1-Tnbo6s8QXew8gz8xAWwklusMgtB3KbfRU9DYuA90NI/export?format=csv&gid=1332991446"
}

# =========================================================
# SESSION STATE
# =========================================================
if "abrir_confirmacao_desativar" not in st.session_state:
    st.session_state.abrir_confirmacao_desativar = False

if "abrir_confirmacao_reativar" not in st.session_state:
    st.session_state.abrir_confirmacao_reativar = False

if "ultima_atualizacao" not in st.session_state:
    st.session_state["ultima_atualizacao"] = None

# =========================================================
# FUNÇÕES - STATUS LOCAL
# =========================================================
def salvar_status_manutencao(status: bool, responsavel: str = "") -> None:
    dados = {
        "modo_manutencao": status,
        "atualizado_em": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "atualizado_por": responsavel
    }
    with open(ARQUIVO_STATUS, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)


def carregar_status_manutencao() -> dict:
    if not os.path.exists(ARQUIVO_STATUS):
        salvar_status_manutencao(False, "")
        return {
            "modo_manutencao": False,
            "atualizado_em": "",
            "atualizado_por": ""
        }

    try:
        with open(ARQUIVO_STATUS, "r", encoding="utf-8") as f:
            dados = json.load(f)
            return {
                "modo_manutencao": bool(dados.get("modo_manutencao", False)),
                "atualizado_em": dados.get("atualizado_em", ""),
                "atualizado_por": dados.get("atualizado_por", "")
            }
    except Exception:
        return {
            "modo_manutencao": False,
            "atualizado_em": "",
            "atualizado_por": ""
        }

# =========================================================
# FUNÇÕES - DADOS
# =========================================================
@st.cache_data
def carregar_base(url):
    df = pd.read_csv(url)

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("utf-8")
        .str.replace(" ", "", regex=False)
    )

    return df


@st.cache_data
def carregar_relatorio():
    df = pd.read_csv(URL_RELATORIO)

    df = df.loc[:, ~df.columns.duplicated()]

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("utf-8")
        .str.replace(" ", "", regex=False)
    )

    colunas_esperadas = [
        "data", "proposta_id", "consultor", "cliente",
        "segmento", "modelo", "prazo", "km", "valor"
    ]

    df = df[[c for c in colunas_esperadas if c in df.columns]]

    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")

    if "valor" in df.columns:
        df["valor"] = (
            df["valor"].astype(str)
            .str.replace("R$", "", regex=False)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.strip()
        )
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")

    return df


def salvar_proposta(cotacoes, vendedor, cliente):
    proposta_id = "CS" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")

    for c in cotacoes:
        payload = {
            "consultor": vendedor,
            "cliente": cliente,
            "segmento": c["segmento"],
            "modelo": c["modelo"],
            "prazo": c["prazo"],
            "km": c["km"],
            "valor": c["valor"],
            "proposta_id": proposta_id
        }

        try:
            requests.post(
                WEBHOOK_URL,
                data=json.dumps(payload),
                headers={"Content-Type": "text/plain"},
                timeout=30
            )
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

    return proposta_id

# =========================================================
# STATUS ATUAL
# =========================================================
status_sistema = carregar_status_manutencao()
modo_manutencao = status_sistema.get("modo_manutencao", False)

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.image(
        "https://i.postimg.cc/HWrrsnvR/LOGO-SIGNATURE-AZUL-E-DOURADO.png",
        width=180
    )

    if not modo_manutencao:
        st.markdown("### 👤 Dados da Proposta")
        vendedor = st.text_input("Consultor *")
        cliente = st.text_input("Cliente *")
        qtd = st.selectbox("Qtd ofertas", [1, 2, 3], index=2)
        progress_container = st.empty()
    else:
        vendedor = ""
        cliente = ""
        qtd = 3
        progress_container = st.empty()

# =========================================================
# TELA DE MANUTENÇÃO
# =========================================================
if modo_manutencao:
    st.markdown("""
    <div class="manutencao-wrapper">
        <div class="manutencao-card">
            <div class="manutencao-titulo">🚧 Sistema em manutenção</div>
            <div class="manutencao-subtitulo">
                Estamos atualizando a base de dados.<br>
                O sistema será reativado em breve.
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("🔓 Reativar sistema")

    responsavel_reativar = st.text_input(
        "Nome do responsável",
        value=status_sistema.get("atualizado_por", "") or "Administrador",
        key="responsavel_reativar"
    )

    if st.button("🟢 Reativar sistema", use_container_width=True):
        st.session_state.abrir_confirmacao_reativar = True

    if st.session_state.abrir_confirmacao_reativar:
        senha_ativar = st.text_input(
            "Senha de reativação",
            type="password",
            key="senha_ativar_input"
        )

        col_a, col_b = st.columns(2)

        with col_a:
            if st.button("Confirmar reativação", use_container_width=True, key="confirmar_reativar"):
                if senha_ativar == SENHA_ATIVAR:
                    salvar_status_manutencao(False, responsavel_reativar or "Administrador")
                    st.session_state.abrir_confirmacao_reativar = False
                    st.success("Sistema reativado com sucesso.")
                    st.rerun()
                else:
                    st.error("Senha incorreta.")

        with col_b:
            if st.button("Cancelar", use_container_width=True, key="cancelar_reativar"):
                st.session_state.abrir_confirmacao_reativar = False
                st.rerun()

    st.stop()

# =========================================================
# ABAS
# =========================================================
tab1, tab2, tab3 = st.tabs(["🚗 Propostas", "📊 Relatório", "🛠️ Gerenciamento"])

# =========================================================
# PROPOSTAS
# =========================================================
with tab1:
    st.title("🚗 Gerador de Propostas da Carrera Signature")

    cotacoes = []
    cols = st.columns(3)

    for i in range(3):
        with cols[i]:
            if i < qtd:
                st.subheader(f"Oferta {i + 1}:")

                segmento = st.selectbox("Segmento", list(BASES.keys()), key=f"seg_{i}")
                df = carregar_base(BASES[segmento])

                if "nome" not in df.columns:
                    st.error(f"A base do segmento '{segmento}' não possui a coluna 'nome'.")
                    continue

                veiculos_disponiveis = df["nome"].dropna().unique()

                if len(veiculos_disponiveis) == 0:
                    st.warning(f"Sem veículos disponíveis para {segmento}.")
                    continue

                veiculo = st.selectbox("Veículo", veiculos_disponiveis, key=f"vei_{i}")
                dados_filtrados = df[df["nome"] == veiculo]

                if dados_filtrados.empty:
                    st.warning("Veículo não encontrado.")
                    continue

                dados = dados_filtrados.iloc[0]

                if "imagem" in dados.index and pd.notna(dados["imagem"]):
                    st.image(dados["imagem"], use_container_width=True)

                prazo = st.selectbox("Prazo", [12, 18, 24, 36, 48], key=f"prazo_{i}")
                km = st.selectbox(
                    "KM",
                    [500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000],
                    key=f"km_{i}"
                )

                col_preco = f"preco{km}{prazo}"
                valor = dados[col_preco] if col_preco in df.columns else "Sob consulta"

                st.success(str(valor))

                cotacoes.append({
                    "segmento": segmento,
                    "modelo": veiculo,
                    "prazo": prazo,
                    "km": km,
                    "valor": str(valor),
                    "url_foto": dados["imagem"] if "imagem" in dados.index else ""
                })

    st.divider()

    if st.button("🚀 Gerar PDF da proposta", use_container_width=True):
        if not vendedor or not cliente:
            st.error("⚠️ Preencha os campos obrigatórios: Consultor e Cliente.")
            st.stop()

        progress = progress_container.progress(0, text="Iniciando...")

        progress.progress(30, text="Salvando proposta...")
        proposta_id = salvar_proposta(cotacoes, vendedor, cliente)

        time.sleep(0.3)

        progress.progress(70, text="Gerando PDF...")
        pdf = gerar_pdf(cliente, vendedor, cotacoes)

        time.sleep(0.3)

        progress.progress(100, text="Finalizado!")

        st.success(f"Proposta gerada: {cliente} - {proposta_id}")

        st.download_button(
            "📥 Baixar PDF",
            data=pdf,
            file_name=f"Proposta Carrera Signature - {cliente}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

# =========================================================
# RELATÓRIO
# =========================================================
with tab2:
    col_title, col_btn = st.columns([6, 1])

    with col_title:
        st.title("📊 Dashboard")

        if st.session_state["ultima_atualizacao"] is not None:
            st.caption(
                f"Última atualização: {st.session_state['ultima_atualizacao'].strftime('%H:%M:%S')}"
            )

    with col_btn:
        if st.button("🔄 Atualizar"):
            carregar_relatorio.clear()
            st.rerun()

    df = carregar_relatorio()
    st.session_state["ultima_atualizacao"] = datetime.datetime.now()

    if df.empty:
        st.warning("Sem dados ainda...")
        st.stop()

    col1, col2, col3 = st.columns(3)

    with col1:
        data_min = df["data"].min() if "data" in df.columns and not df["data"].dropna().empty else datetime.datetime.now().date()
        data_inicio = st.date_input("Data início", data_min)

    with col2:
        data_max = df["data"].max() if "data" in df.columns and not df["data"].dropna().empty else datetime.datetime.now().date()
        data_fim = st.date_input("Data fim", data_max)

    with col3:
        lista_consultores = ["Todos"]
        if "consultor" in df.columns:
            lista_consultores += list(df["consultor"].dropna().unique())
        consultor = st.selectbox("Consultor", lista_consultores)

    df_filtro = df.copy()

    if "data" in df_filtro.columns:
        df_filtro = df_filtro[
            (df_filtro["data"] >= pd.to_datetime(data_inicio)) &
            (df_filtro["data"] <= pd.to_datetime(data_fim))
        ]

    if consultor != "Todos" and "consultor" in df_filtro.columns:
        df_filtro = df_filtro[df_filtro["consultor"] == consultor]

    col1, col2, col3, col4 = st.columns(4)

    propostas = df_filtro["proposta_id"].nunique() if "proposta_id" in df_filtro.columns else 0
    veiculos = len(df_filtro)
    top_consultor = df_filtro["consultor"].mode()[0] if ("consultor" in df_filtro.columns and not df_filtro.empty and not df_filtro["consultor"].dropna().empty) else "-"
    top_modelo = df_filtro["modelo"].mode()[0] if ("modelo" in df_filtro.columns and not df_filtro.empty and not df_filtro["modelo"].dropna().empty) else "-"

    col1.metric("Propostas", propostas)
    col2.metric("Veículos", veiculos)
    col3.metric("Top Consultor", top_consultor)
    col4.metric("Top Modelo", top_modelo)

    st.divider()

    if not df_filtro.empty and "data" in df_filtro.columns and "proposta_id" in df_filtro.columns:
        st.subheader("📈 Propostas por dia")
        df_dia = df_filtro.groupby(df_filtro["data"].dt.date)["proposta_id"].nunique()
        st.bar_chart(df_dia)

    if not df_filtro.empty and "consultor" in df_filtro.columns:
        st.subheader("🏆 Ranking Consultores")
        st.bar_chart(df_filtro["consultor"].value_counts())

    if not df_filtro.empty and "segmento" in df_filtro.columns:
        st.subheader("🚗 Segmentos")
        st.bar_chart(df_filtro["segmento"].value_counts())

    if not df_filtro.empty and "modelo" in df_filtro.columns and "proposta_id" in df_filtro.columns:
        st.subheader("🔥 Modelos mais ofertados")
        df_carro = df_filtro.groupby("modelo")["proposta_id"].nunique().sort_values(ascending=False)
        st.bar_chart(df_carro)

# =========================================================
# GERENCIAMENTO
# =========================================================
with tab3:
    st.title("🛠️ Gerenciamento")
    st.caption("Área administrativa para controle do sistema.")

    col_status_1, col_status_2 = st.columns([1, 4])

    with col_status_1:
        if modo_manutencao:
            st.error("🔴 Offline")
        else:
            st.success("🟢 Online")

    with col_status_2:
        atualizado_por = status_sistema.get("atualizado_por", "-") or "-"
        atualizado_em = status_sistema.get("atualizado_em", "-") or "-"

        if modo_manutencao:
            st.write("O sistema está em modo manutenção e indisponível para os usuários.")
        else:
            st.write("O sistema está ativo e disponível normalmente.")

        st.markdown(
            f"<div class='small-muted'><b>Última alteração:</b> {atualizado_em} | <b>Por:</b> {atualizado_por}</div>",
            unsafe_allow_html=True
        )

    st.subheader("Controle do sistema")

    responsavel_admin = st.text_input(
        "Nome do responsável",
        value=status_sistema.get("atualizado_por", "") or "Administrador",
        key="responsavel_admin"
    )

    if not modo_manutencao:
        st.warning("Ao desativar o sistema, todos os usuários verão a tela de manutenção.")

        if st.button("🔴 Tirar sistema do ar", use_container_width=True):
            st.session_state.abrir_confirmacao_desativar = True

        if st.session_state.abrir_confirmacao_desativar:
            senha_desativar = st.text_input(
                "Senha de desativação",
                type="password",
                key="senha_desativacao_gerenciamento"
            )

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Confirmar desativação", use_container_width=True, key="btn_desativar_gerenciamento"):
                    if senha_desativar == SENHA_DESATIVAR:
                        salvar_status_manutencao(True, responsavel_admin or "Administrador")
                        st.session_state.abrir_confirmacao_desativar = False
                        st.success("Sistema colocado em manutenção.")
                        st.rerun()
                    else:
                        st.error("Senha incorreta.")

            with col2:
                if st.button("Cancelar", use_container_width=True, key="btn_cancelar_desativacao_gerenciamento"):
                    st.session_state.abrir_confirmacao_desativar = False
                    st.rerun()
    else:
        st.info("O sistema já está em manutenção. A reativação deve ser feita pela tela principal de manutenção.")

    st.markdown('</div>', unsafe_allow_html=True)