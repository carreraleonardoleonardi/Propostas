import streamlit as st
import pandas as pd
import requests
import json
import datetime
import time

from pdf_generator import gerar_pdf
from utils import formatar_valor_brl
from data import BASES, carregar_base, obter_veiculos, obter_dados_veiculo, calcular_valor

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxzzTh8nlzwFmAdrB7-qXrhUiEeWGGOwH7ZGAuQeaGZHcTVRa1jASmrpU-ADQcCLZgTKw/exec"


def salvar_proposta(cotacoes, vendedor, cliente):
    proposta_id = "CS" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    for c in cotacoes:
        payload = {
            "consultor":   vendedor,
            "cliente":     cliente,
            "segmento":    c["segmento"],
            "modelo":      c["modelo"],
            "prazo":       c["prazo"],
            "km":          c["km"],
            "valor":       c["valor"],
            "proposta_id": proposta_id
        }
        try:
            requests.post(WEBHOOK_URL, data=json.dumps(payload),
                headers={"Content-Type": "text/plain"}, timeout=30)
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")
    return proposta_id


def render():
    st.title("🚗 Gerador de Propostas da Carrera Signature")

    # ── Dados da Proposta ────────────────────────────────
    with st.container():
        d1, d2, d3 = st.columns(3)
        with d1:
            vendedor = st.text_input("Consultor *", key="prop_vendedor")
        with d2:
            cliente = st.text_input("Cliente *", key="prop_cliente")
        with d3:
            qtd = st.selectbox("Qtd ofertas", [1, 2, 3], index=2, key="prop_qtd")

    progress_container = st.empty()
    st.divider()

    # ── Ofertas ──────────────────────────────────────────
    cotacoes = []
    cols     = st.columns(3)

    for i in range(3):
        with cols[i]:
            if i < qtd:
                st.subheader(f"Oferta {i + 1}:")

                segmento = st.selectbox("Segmento", list(BASES.keys()), key=f"seg_{i}")
                df       = carregar_base(BASES[segmento])

                if "nome" not in df.columns:
                    st.error(f"A base '{segmento}' não possui a coluna 'nome'.")
                    continue

                veiculos = obter_veiculos(df)
                if not veiculos:
                    st.warning(f"Sem veículos para {segmento}.")
                    continue

                veiculo = st.selectbox("Veículo", veiculos, key=f"vei_{i}", index=1 if len(veiculos) > 1 else 0)
                dados   = obter_dados_veiculo(df, veiculo)

                if dados is None:
                    st.warning("Veículo não encontrado.")
                    continue

                if "imagem" in dados.index and pd.notna(dados["imagem"]):
                    st.image(dados["imagem"], width="stretch")

                prazo = st.selectbox("Prazo", [12, 18, 24, 36, 48], key=f"prazo_{i}")
                km    = st.selectbox("KM", [500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000], key=f"km_{i}")

                valor = calcular_valor(df, dados, km, prazo)
                st.success(str(valor))

                cotacoes.append({
                    "segmento": segmento,
                    "modelo":   veiculo,
                    "prazo":    prazo,
                    "km":       km,
                    "valor":    str(valor),
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