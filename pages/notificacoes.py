"""
notificacoes.py — Carrera Signature
Sistema de notificações in-app: sino no topo com contador de não lidas.

Fonte de dados: aba "notificacoes" na mesma planilha do estoque de veículos
(reaproveita o mesmo webhook/planilha de pages/gestao_veiculos.py).

Regras implementadas (ver notif_gerar_periodicas / hooks nos outros módulos):
  1. Carro novo em estoque com status Livre/Trânsito Livre  -> destinatário "TODOS"
  2. Carro novo com consultor preenchido                     -> destinatário = nome do consultor
  3. Carro entregue                                          -> consultor do carro + "STAFF"
  4. Carro com status Aditivo/Distrato/Avariado               -> "STAFF", 1x/dia

⚠️ Limitação importante: este app não tem um agendador de tarefas (cron) de
verdade — ele só roda quando alguém abre a página. As regras "todo dia às
10h" são aproximadas: a checagem roda toda vez que a aba Estoque é aberta,
e só cria a notificação se ainda não existir uma do mesmo tipo/veículo
criada HOJE E se já passou das 10h. Se ninguém abrir o app depois das 10h
num dia, a notificação sai atrasada (na próxima vez que alguém abrir).
"""

import datetime
import json

import pandas as pd
import requests
import streamlit as st

NOTIF_SHEET_URL = "https://docs.google.com/spreadsheets/d/1BpAtiXz4AEuQg4kVx8OFonohPlvbScdOgWPIZRxQnxo/export?format=csv&gid=1570828268"
NOTIF_WEBHOOK   = "https://script.google.com/macros/s/AKfycbzFP-ezBsVx7W7VhYATKgaqdAg485o0AQb8s9FdGTlvmdzK1YRj7dCUVfTrXNgJOToc/exec"

NOTIF_COLUNAS = ["id", "tipo", "destinatario", "mensagem", "chassi", "modelo",
                 "criado_em", "data_evento", "lida_por"]

STATUS_ATENCAO = {"Aditivo", "Distrato", "Avariado"}
STATUS_NOVO_ESTOQUE = {"Livre", "Trânsito Livre"}
HORA_CHECAGEM_DIARIA = 10  # 10h


# ── Infra (carregar / enviar) ────────────────────────────────────────────
@st.cache_data(ttl=30)
def notif_carregar() -> pd.DataFrame:
    try:
        df = pd.read_csv(NOTIF_SHEET_URL, header=0)
        df.columns = [c.strip().lower() for c in df.columns]
        for c in NOTIF_COLUNAS:
            if c not in df.columns:
                df[c] = ""
        return df
    except Exception:
        return pd.DataFrame(columns=NOTIF_COLUNAS)


def notif_enviar(payload) -> bool:
    try:
        requests.post(NOTIF_WEBHOOK, data=json.dumps(payload),
                      headers={"Content-Type": "text/plain"}, timeout=30)
        return True
    except Exception:
        return False


def notif_novo_id() -> str:
    return "NOT" + datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]


def notif_criar(tipo: str, destinatario: str, mensagem: str, chassi: str = "", modelo: str = "") -> None:
    """Cria uma notificação nova. destinatario: 'TODOS', 'STAFF' ou nome exato de um usuário."""
    agora = datetime.datetime.now()
    linha = [
        notif_novo_id(), tipo, destinatario, mensagem, chassi, modelo,
        agora.strftime("%d/%m/%Y %H:%M"), agora.strftime("%d/%m/%Y"), "",
    ]
    notif_enviar({"aba": "notificacoes", "acao": "inserir", "linha": linha})
    notif_carregar.clear()


def notif_marcar_lida(id_notif: str, usuario: str) -> None:
    df = notif_carregar()
    if df.empty or "id" not in df.columns:
        return
    match = df[df["id"].astype(str) == str(id_notif)]
    if match.empty:
        return
    idx = match.index[0]
    linha_num = int(idx) + 2
    lida_por_atual = str(match.iloc[0].get("lida_por", "") or "").strip()
    nomes = [n.strip() for n in lida_por_atual.split(";") if n.strip()]
    if usuario not in nomes:
        nomes.append(usuario)
    novo_valor = ";".join(nomes)
    col_idx = NOTIF_COLUNAS.index("lida_por") + 1
    notif_enviar({"aba": "notificacoes", "acao": "atualizar_linha", "linha_num": linha_num,
                  "valores": [{"col": col_idx, "valor": novo_valor}]})
    notif_carregar.clear()


def notif_marcar_todas_lidas(ids: list, usuario: str) -> None:
    for id_notif in ids:
        notif_marcar_lida(id_notif, usuario)


# ── Seleção das notificações do usuário atual ────────────────────────────
def _nao_lida(row, usuario: str) -> bool:
    lidos = [n.strip() for n in str(row.get("lida_por", "") or "").split(";") if n.strip()]
    return usuario not in lidos


def notif_para_usuario(nome: str, tipo_acesso: str) -> pd.DataFrame:
    """Retorna as notificações NÃO LIDAS destinadas a este usuário (TODOS, STAFF-se-aplicável, ou nominal)."""
    df = notif_carregar()
    if df.empty:
        return df
    destinatarios_validos = {"TODOS", nome}
    if tipo_acesso == "Staff":
        destinatarios_validos.add("STAFF")
    df_alvo = df[df["destinatario"].astype(str).str.strip().isin(destinatarios_validos)]
    if df_alvo.empty:
        return df_alvo
    mask_nao_lida = df_alvo.apply(lambda r: _nao_lida(r, nome), axis=1)
    df_alvo = df_alvo[mask_nao_lida]
    if "criado_em" in df_alvo.columns:
        df_alvo = df_alvo.assign(
            _dt=pd.to_datetime(df_alvo["criado_em"], dayfirst=True, errors="coerce")
        ).sort_values("_dt", ascending=False).drop(columns="_dt")
    return df_alvo


# ── UI: sino de notificações ──────────────────────────────────────────────
_ICONES_TIPO = {
    "novo_estoque": "🚗", "novo_estoque_consultor": "🔑", "entregue": "📦",
    "status_atencao": "⚠️",
}


def notif_render_sino():
    """Renderiza o sino com contador — chamar uma vez no topo do app (ex.: app.py)."""
    nome = st.session_state.get("auth_nome", "")
    tipo_acesso = st.session_state.get("auth_tipo", "")
    if not nome:
        return  # não logado

    pendentes = notif_para_usuario(nome, tipo_acesso)
    qtd = len(pendentes)
    rotulo = f"🔔 {qtd}" if qtd > 0 else "🔔"

    with st.popover(rotulo, use_container_width=False):
        st.markdown("**Notificações**")
        if pendentes.empty:
            st.caption("Nenhuma notificação nova. ✅")
        else:
            if st.button("Marcar todas como lidas", key="notif_marcar_todas", use_container_width=True):
                notif_marcar_todas_lidas(pendentes["id"].tolist(), nome)
                st.rerun()
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            for _, r in pendentes.iterrows():
                icone = _ICONES_TIPO.get(str(r.get("tipo", "")), "🔔")
                col_msg, col_btn = st.columns([5, 1])
                with col_msg:
                    st.markdown(
                        f"<div style='font-size:13px;padding:6px 0;border-bottom:1px solid #eee'>"
                        f"{icone} {r.get('mensagem','')}"
                        f"<div style='font-size:10px;color:#94a3b8;margin-top:2px'>{r.get('criado_em','')}</div>"
                        f"</div>", unsafe_allow_html=True,
                    )
                with col_btn:
                    if st.button("✓", key=f"notif_lida_{r['id']}", help="Marcar como lida"):
                        notif_marcar_lida(r["id"], nome)
                        st.rerun()


# ── Geração automática (hooks chamados por outros módulos) ───────────────
def notif_novo_veiculo(status: str, consultor: str, chassi: str, modelo: str) -> None:
    """Chamar após cadastrar um veículo novo com sucesso."""
    if status in STATUS_NOVO_ESTOQUE:
        notif_criar("novo_estoque", "TODOS",
                     f"Novo veículo em estoque: {modelo} ({status})", chassi, modelo)
    consultor = (consultor or "").strip()
    if consultor and consultor not in ("—", "-"):
        notif_criar("novo_estoque_consultor", consultor,
                     f"Veículo {modelo} foi vinculado a você", chassi, modelo)


def notif_veiculo_entregue(consultor: str, chassi: str, modelo: str) -> None:
    """Chamar sempre que o status de um veículo mudar para 'Entregue'."""
    consultor = (consultor or "").strip()
    if consultor and consultor not in ("—", "-"):
        notif_criar("entregue", consultor, f"Veículo entregue: {modelo}", chassi, modelo)
    notif_criar("entregue", "STAFF", f"Veículo entregue: {modelo} (consultor: {consultor or '—'})", chassi, modelo)


def _ja_notificado_hoje(df_notif: pd.DataFrame, tipo: str, chassi: str) -> bool:
    if df_notif.empty:
        return False
    hoje_str = datetime.date.today().strftime("%d/%m/%Y")
    match = df_notif[
        (df_notif["tipo"] == tipo)
        & (df_notif["chassi"].astype(str) == str(chassi))
        & (df_notif["data_evento"].astype(str) == hoje_str)
    ]
    return not match.empty


def notif_gerar_periodicas(df_gv: pd.DataFrame) -> None:
    """
    Verifica as regras recorrentes (status de atenção) e cria notificações
    novas se ainda não tiver sido feito hoje. Chamar 1x ao carregar a aba
    Estoque (idempotente — seguro chamar toda vez).
    """
    agora = datetime.datetime.now()
    if agora.hour < HORA_CHECAGEM_DIARIA:
        return  # ainda não é hora de disparar as notificações do dia
    if df_gv.empty or "status" not in df_gv.columns:
        return

    df_notif = notif_carregar()

    # Regra — status de atenção (Aditivo / Distrato / Avariado)
    atencao = df_gv[df_gv["status"].isin(STATUS_ATENCAO)]
    for _, row in atencao.iterrows():
        chassi = str(row.get("chassi", ""))
        if chassi and not _ja_notificado_hoje(df_notif, "status_atencao", chassi):
            notif_criar("status_atencao", "STAFF",
                        f"Veículo com status '{row.get('status','')}': {row.get('modelo','')} ({chassi})",
                        chassi, row.get("modelo", ""))
