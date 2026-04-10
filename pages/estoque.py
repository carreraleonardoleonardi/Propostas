import streamlit as st
import pandas as pd


URL_ESTOQUE = "https://docs.google.com/spreadsheets/d/1BpAtiXz4AEuQg4kVx8OFonohPlvbScdOgWPIZRxQnxo/export?format=csv&gid=0"


@st.cache_data(ttl=300)
def carregar_estoque():
    df = pd.read_csv(URL_ESTOQUE)
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("utf-8")
        .str.replace(" ", "", regex=False)
        .str.replace(":", "", regex=False)
    )
    return df


def render():
    st.title("📦 Estoque — Veículos a Pronta Entrega")
    st.caption("Visualize os veículos disponíveis em estoque. Utilize os filtros para refinar a busca.")

    col_reload, _ = st.columns([1, 8])
    with col_reload:
        if st.button("🔄 Atualizar", key="btn_atualizar_estoque"):
            carregar_estoque.clear()
            st.rerun()

    try:
        df_estoque = carregar_estoque()
    except Exception as e:
        st.error(f"Erro ao carregar base de estoque: {e}")
        return

    if df_estoque.empty:
        st.warning("Nenhum veículo encontrado na base de estoque.")
        return

    col1, col2, col3, col4 = st.columns(4)

    def opcoes(col):
        if col in df_estoque.columns:
            return ["Todos"] + sorted(df_estoque[col].dropna().astype(str).unique().tolist())
        return ["Todos"]

    with col1:
        fabricante_sel = st.selectbox("Fabricante", opcoes("fabricante"), key="est_fabricante")
    with col2:
        modelo_sel     = st.selectbox("Modelo",     opcoes("modelo"),     key="est_modelo")
    with col3:
        cor_sel        = st.selectbox("Cor",        opcoes("cor"),        key="est_cor")
    with col4:
        locadora_sel   = st.selectbox("Locadora",   opcoes("locadora"),   key="est_locadora")

    df_filtrado = df_estoque.copy()

    if fabricante_sel != "Todos" and "fabricante" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["fabricante"].astype(str) == fabricante_sel]
    if modelo_sel != "Todos" and "modelo" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["modelo"].astype(str) == modelo_sel]
    if cor_sel != "Todos" and "cor" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["cor"].astype(str) == cor_sel]
    if locadora_sel != "Todos" and "locadora" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["locadora"].astype(str) == locadora_sel]

    colunas_disponiveis = [c for c in df_filtrado.columns if c in [
        "fabricante", "modelo", "cor", "locadora", "status",
        "localatual", "datachegada", "idade", "pedido",
        "consultor", "cliente", "chassi", "placa",
        "rodizio", "anoxmodelo", "km",
        "lojadeentrega", "dataentrega", "horaentrega",
        "entregador", "obs"
    ]]

    df_show = df_filtrado[colunas_disponiveis] if colunas_disponiveis else df_filtrado

    rename_map = {
        "fabricante":    "Fabricante",
        "modelo":        "Modelo",
        "cor":           "Cor",
        "locadora":      "Locadora",
        "status":        "Status",
        "localatual":    "Local Atual",
        "datachegada":   "Data Chegada",
        "idade":         "Idade",
        "pedido":        "Pedido",
        "consultor":     "Consultor",
        "cliente":       "Cliente",
        "chassi":        "Chassi",
        "placa":         "Placa",
        "rodizio":       "Rodízio",
        "anoxmodelo":    "Ano x Modelo",
        "km":            "KM",
        "lojadeentrega": "Loja de Entrega",
        "dataentrega":   "Data Entrega",
        "horaentrega":   "Hora Entrega",
        "entregador":    "Entregador",
        "obs":           "OBS"
    }

    df_show = df_show.rename(columns=rename_map)

    st.markdown(f"**{len(df_filtrado)} veículo(s) encontrado(s)**")
    st.divider()
    st.dataframe(df_show, width="stretch", hide_index=True)