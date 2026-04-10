import streamlit as st
import datetime
import json
import os


ARQUIVO_STATUS = "status_sistema.json"


def salvar_status_manutencao(status: bool, responsavel: str = "") -> None:
    dados = {
        "modo_manutencao": status,
        "atualizado_em":   datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "atualizado_por":  responsavel
    }
    with open(ARQUIVO_STATUS, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)


def render(status_sistema: dict, modo_manutencao: bool, SENHA_DESATIVAR: str):
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
        atualizado_em  = status_sistema.get("atualizado_em",  "-") or "-"
        st.write("O sistema está em modo manutenção." if modo_manutencao else "O sistema está ativo e disponível normalmente.")
        st.markdown(
            f"<div class='small-muted'><b>Última alteração:</b> {atualizado_em} | <b>Por:</b> {atualizado_por}</div>",
            unsafe_allow_html=True
        )

    st.subheader("Controle do sistema")

    responsavel_admin = st.text_input("Nome do responsável",
        value=status_sistema.get("atualizado_por", "") or "Administrador",
        key="responsavel_admin")

    if not modo_manutencao:
        st.warning("Ao desativar o sistema, todos os usuários verão a tela de manutenção.")

        if st.button("🔴 Tirar sistema do ar", use_container_width=True):
            st.session_state.abrir_confirmacao_desativar = True

        if st.session_state.abrir_confirmacao_desativar:
            senha_desativar = st.text_input("Senha de desativação", type="password", key="senha_desativacao_gerenciamento")
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
        st.info("O sistema já está em manutenção. A reativação deve ser feita pela tela principal.")