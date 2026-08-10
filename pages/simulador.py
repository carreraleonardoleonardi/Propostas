import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import zipfile
import io
import re

from data import (
    BASES,
    carregar_base,
    obter_veiculos,
    extrair_planos_modelo
)


def _nome_arquivo_seguro(texto: str) -> str:
    """Remove caracteres inválidos para nome de arquivo/pasta."""
    return re.sub(r'[\\/*?:"<>|]', "", str(texto)).strip()


def _formatar_data_valido_ate(data):
    """
    Formata a data da coluna validoAte para o formato dd/mm/yyyy.
    Aceita datetime, Timestamp, string ou valores vazios.
    """

    if pd.isna(data) or data in ("", None):
        return ""

    try:
        data_convertida = pd.to_datetime(data, errors="coerce")

        if pd.isna(data_convertida):
            return str(data)

        return data_convertida.strftime("%d/%m/%Y")

    except Exception:
        return str(data)


def render(gerar_card_plano_html, gerar_card_png):

    st.title("🎴 Card de Plano")
    st.caption(
        "Selecione o segmento e o modelo para gerar o card comercial."
    )

    # ─────────────────────────────────────────────
    # Verificação de perfil
    # ─────────────────────────────────────────────

    is_staff = st.session_state.get("auth_tipo", "") == "Staff"

    col1, col2 = st.columns(2)

    # ─────────────────────────────────────────────
    # SEGMENTO
    # ─────────────────────────────────────────────

    with col1:

        segmento_sim = st.selectbox(
            "Segmento",
            list(BASES.keys()),
            key="sim_segmento"
        )

    df_sim = carregar_base(BASES[segmento_sim])

    modelos_disponiveis = obter_veiculos(df_sim)

    # ─────────────────────────────────────────────
    # MODELO
    # ─────────────────────────────────────────────

    with col2:

        modelo_sim = st.selectbox(
            "Modelo",
            modelos_disponiveis,
            key="sim_modelo",
            index=0
        )

    # ─────────────────────────────────────────────
    # BOTÕES
    # ─────────────────────────────────────────────

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:

        gerar = st.button(
            "✨ Montar card do plano",
            use_container_width=True
        )

    # ─────────────────────────────────────────────
    # GERAR PLANOS
    # ─────────────────────────────────────────────

    if gerar:

        planos, imagem, nome_mod, versao_mod = extrair_planos_modelo(
            df_sim,
            modelo_sim
        )

        if not planos:

            st.warning(
                "Não foram encontrados planos para este modelo."
            )

        else:

            st.session_state["sim_planos"] = planos
            st.session_state["sim_imagem"] = imagem
            st.session_state["sim_nome_mod"] = nome_mod
            st.session_state["sim_versao_mod"] = versao_mod
            st.session_state["sim_seg_salvo"] = segmento_sim

    # ─────────────────────────────────────────────
    # EXIBIR CARD
    # ─────────────────────────────────────────────

    if (
        "sim_planos" in st.session_state
        and st.session_state["sim_planos"]
    ):

        planos = st.session_state["sim_planos"]
        imagem = st.session_state["sim_imagem"]
        nome_mod = st.session_state["sim_nome_mod"]
        versao_mod = st.session_state["sim_versao_mod"]
        seg = st.session_state["sim_seg_salvo"]

        # ─────────────────────────────────────────
        # GERA PNG
        # ─────────────────────────────────────────

        png_bytes = gerar_card_png(
            nome_mod,
            planos,
            imagem,
            seg,
            versao_mod
        )

        # ─────────────────────────────────────────
        # DOWNLOAD
        # ─────────────────────────────────────────

        with col_btn2:

            st.download_button(
                "📥 Baixar card em PNG",
                data=png_bytes,
                file_name=f"Card - {modelo_sim}.png",
                mime="image/png",
                use_container_width=True
            )

        st.divider()

        # ─────────────────────────────────────────
        # ESTRUTURA DOS PLANOS
        # ─────────────────────────────────────────

        with st.expander(
            "Ver estrutura dos planos encontrados"
        ):

            linhas = []

            for prazo, itens in planos.items():

                for item in itens:

                    linhas.append(
                        {
                            "Prazo": prazo,
                            "KM por mês": item.get("km", ""),
                            "Valor": item.get("valor", ""),
                            "Válido até": _formatar_data_valido_ate(
                                item.get("validoAte", "")
                            )
                        }
                    )

            if linhas:

                st.dataframe(
                    pd.DataFrame(linhas),
                    use_container_width=True,
                    hide_index=True
                )

    # ═════════════════════════════════════════════
    # EXPORTAR TODOS OS CARDS — SOMENTE STAFF
    # ═════════════════════════════════════════════

    if is_staff:

        st.divider()

        st.markdown(
            "### 📦 Exportar todos os cards em ZIP"
        )

        st.caption(
            "Gera um arquivo ZIP com todos os cards PNG "
            "organizados por segmento. Pode levar alguns minutos."
        )

        segmentos_zip = st.multiselect(
            "Segmentos a incluir",
            options=list(BASES.keys()),
            default=list(BASES.keys()),
            key="zip_segmentos"
        )

        # ─────────────────────────────────────────
        # GERAR ZIP
        # ─────────────────────────────────────────

        if st.button(
            "⬇️ Gerar e baixar ZIP",
            use_container_width=True,
            key="btn_gerar_zip",
            type="primary"
        ):

            if not segmentos_zip:

                st.warning(
                    "Selecione ao menos um segmento."
                )

            else:

                zip_buffer = io.BytesIO()

                total_gerados = 0
                erros = []

                progress = st.progress(
                    0,
                    text="Iniciando geração dos cards..."
                )

                total_segmentos = len(segmentos_zip)

                with zipfile.ZipFile(
                    zip_buffer,
                    "w",
                    zipfile.ZIP_DEFLATED
                ) as zf:

                    # ─────────────────────────────
                    # PERCORRE SEGMENTOS
                    # ─────────────────────────────

                    for s_idx, segmento in enumerate(
                        segmentos_zip
                    ):

                        pasta = _nome_arquivo_seguro(
                            segmento
                        )

                        progress.progress(
                            int(
                                (s_idx / total_segmentos)
                                * 100
                            ),
                            text=(
                                f"Processando "
                                f"{segmento}..."
                            )
                        )

                        try:

                            df_seg = carregar_base(
                                BASES[segmento]
                            )

                            modelos = obter_veiculos(
                                df_seg
                            )

                            # ─────────────────────
                            # PERCORRE MODELOS
                            # ─────────────────────

                            for modelo in modelos:

                                try:

                                    (
                                        planos_m,
                                        imagem_m,
                                        nome_m,
                                        versao_m
                                    ) = extrair_planos_modelo(
                                        df_seg,
                                        modelo
                                    )

                                    if not planos_m:
                                        continue

                                    # ─────────────────
                                    # GERA CARD
                                    # ─────────────────

                                    png = gerar_card_png(
                                        nome_m,
                                        planos_m,
                                        imagem_m,
                                        segmento,
                                        versao_m
                                    )

                                    nome_safe = (
                                        _nome_arquivo_seguro(
                                            modelo
                                        )
                                    )

                                    caminho = (
                                        f"{pasta}/"
                                        f"{nome_safe}.png"
                                    )

                                    zf.writestr(
                                        caminho,
                                        png
                                    )

                                    total_gerados += 1

                                except Exception as e:

                                    erros.append(
                                        f"{segmento} / "
                                        f"{modelo}: {e}"
                                    )

                        except Exception as e:

                            erros.append(
                                f"{segmento}: {e}"
                            )

                # ─────────────────────────────────
                # FINALIZA PROGRESSO
                # ─────────────────────────────────

                progress.progress(
                    100,
                    text="ZIP gerado!"
                )

                # ─────────────────────────────────
                # DOWNLOAD ZIP
                # ─────────────────────────────────

                zip_buffer.seek(0)

                st.download_button(
                    f"📥 Baixar ZIP ({total_gerados} cards)",
                    data=zip_buffer.getvalue(),
                    file_name="Cards_Carrera_Signature.zip",
                    mime="application/zip",
                    use_container_width=True,
                    key="btn_download_zip"
                )

                # ─────────────────────────────────
                # MOSTRA ERROS
                # ─────────────────────────────────

                if erros:

                    with st.expander(
                        f"⚠️ {len(erros)} erro(s) durante a geração"
                    ):

                        for erro in erros:

                            st.caption(erro)