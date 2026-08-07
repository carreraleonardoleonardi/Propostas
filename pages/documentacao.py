# =========================================================
# pages/documentacao.py — Documentação / Criptografia
# =========================================================
#
# Formulário de cadastro que:
#   1) coleta os dados do cliente/proposta;
#   2) se "Pronta Entrega" = Sim, busca o veículo pelo Chassi no
#      mesmo estoque usado em pages/gestao_veiculos.py (gv_carregar);
#   3) recebe até 8 PDFs;
#   4) ao clicar em Concluir:
#        - monta um texto formatado pronto para colar em e-mail
#        - empacota os PDFs num .zip protegido por senha aleatória
#          de 5 dígitos, nome do zip = NomeCompleto_CPFCNPJ.zip
#        - a senha só é exibida na tela (não é salva em lugar nenhum)
#
# Sem dependências externas: a criptografia do .zip é feita por
# pages/zipcrypto_util.py, uma implementação própria e pura em Python do
# ZipCrypto (não usa pyzipper, nem chama binário `zip` do sistema — não
# precisa de requirements.txt nem packages.txt extra). Compatível com o
# "Extrair Tudo" nativo do Windows/macOS, WinRAR e 7-Zip.
#
# Os documentos ficam organizados DENTRO de uma pasta no zip (nome igual
# ao do arquivo zip, sem a extensão), em vez de soltos na raiz.

import re
import random
import unicodedata
import datetime

import streamlit as st

from pages.gestao_veiculos import gv_carregar
from pages.zipcrypto_util import gerar_zip_com_senha_bytes


# =========================================================
# Helpers
# =========================================================

def _somente_digitos(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _sanitizar_nome_arquivo(s: str) -> str:
    """Remove acentos e caracteres inválidos p/ nome de arquivo."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Za-z0-9]+", "", s)
    return s or "SemNome"


def _gerar_senha_5_digitos() -> str:
    return f"{random.randint(0, 99999):05d}"


def _buscar_veiculo_por_chassi(chassi: str) -> dict | None:
    """Busca no mesmo estoque (planilha) usado em Estoque/Gestão de Veículos."""
    chassi_norm = (chassi or "").strip().upper()
    if not chassi_norm:
        return None
    df = gv_carregar()
    if df.empty or "chassi" not in df.columns:
        return None
    match = df[df["chassi"].astype(str).str.strip().str.upper() == chassi_norm]
    if match.empty:
        return None
    row = match.iloc[0]

    def g(col):
        v = row.get(col, "")
        s = "" if v is None else str(v).strip()
        return "" if s.lower() in ("nan", "none", "nat", "—") else s

    return {
        "chassi":     g("chassi"),
        "fabricante": g("fabricante"),
        "modelo":     g("modelo"),
        "cor":        g("cor"),
        "placa":      g("placa"),
        "status":     g("status"),
        "local_atual": g("local_atual"),
    }


def _callback_buscar_chassi():
    """Disparado pelo on_change do campo Chassi (fora do form)."""
    chassi_digitado = st.session_state.get("doc_chassi_input", "")
    resultado = _buscar_veiculo_por_chassi(chassi_digitado)
    st.session_state["doc_estoque_encontrado"] = resultado
    if resultado:
        st.session_state["doc_modelo_autofill"] = resultado["modelo"]
        st.session_state["doc_cor_autofill"]    = resultado["cor"]


def _montar_texto_email(dados: dict) -> str:
    linhas = []
    linhas.append("NOVO CADASTRO — DOCUMENTAÇÃO")
    linhas.append("=" * 50)
    linhas.append(f"Nome completo: {dados['nome']}")
    linhas.append(f"CPF/CNPJ: {dados['cpf_cnpj']}")
    linhas.append(f"Telefone: {dados['telefone']}")
    linhas.append(f"E-mail: {dados['email']}")
    linhas.append("")
    linhas.append(f"Modelo: {dados['modelo']}")
    linhas.append(f"Cor: {dados['cor']}")
    linhas.append(f"Plano: {dados['plano']}")
    linhas.append(f"Km: {dados['km']}")
    linhas.append(f"Pronta Entrega: {dados['pronta_entrega']}")

    if dados["pronta_entrega"] == "Sim":
        linhas.append("")
        linhas.append("— Dados do estoque (veículo vinculado) —")
        est = dados.get("estoque") or {}
        if est:
            linhas.append(f"Chassi: {est.get('chassi','')}")
            linhas.append(f"Fabricante: {est.get('fabricante','')}")
            linhas.append(f"Placa: {est.get('placa','')}")
            linhas.append(f"Status no estoque: {est.get('status','')}")
            linhas.append(f"Local atual: {est.get('local_atual','')}")
        else:
            linhas.append(f"Chassi informado: {dados.get('chassi','')} (NÃO encontrado no estoque)")

    linhas.append("")
    linhas.append(f"Documentos anexados: {dados['qtd_docs']} arquivo(s)")
    if dados.get("nomes_docs"):
        for nd in dados["nomes_docs"]:
            linhas.append(f"  - {nd}")
    linhas.append("")
    linhas.append(f"Arquivo compactado: {dados['nome_zip']}")
    linhas.append("(senha enviada em canal separado)")
    linhas.append("")
    linhas.append(f"Gerado em: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
    return "\n".join(linhas)


def _gerar_zip_com_senha(arquivos, senha: str, nome_pasta: str) -> bytes:
    """
    arquivos: lista de UploadedFile do st.file_uploader.
    Os PDFs ficam dentro de uma pasta (nome_pasta) dentro do zip, em vez
    de soltos na raiz. Ex.: LeonardoRibeiroLeonardi_12345678910/doc1.pdf
    """
    itens = [(f"{nome_pasta}/{arq.name}", arq.getvalue()) for arq in arquivos]
    return gerar_zip_com_senha_bytes(itens, senha)


# =========================================================
# Render principal
# =========================================================

def render():
    st.markdown("## 🔒 Documentação / Criptografia")
    st.caption("Cadastro de documentos do cliente com geração de pacote protegido por senha.")

    for key, val in [
        ("doc_estoque_encontrado", None),
        ("doc_modelo_autofill", ""),
        ("doc_cor_autofill", ""),
        ("doc_resultado", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = val

    # ── Pronta Entrega + busca de Chassi (fora do form, precisa reagir ao colar) ──
    pronta_entrega = st.radio("Pronta Entrega?", ["Não", "Sim"], horizontal=True, key="doc_pronta_entrega")

    chassi_valor = ""
    if pronta_entrega == "Sim":
        chassi_valor = st.text_input(
            "Chassi (cole aqui — busca automática no estoque)",
            key="doc_chassi_input",
            on_change=_callback_buscar_chassi,
            max_chars=17,
        )
        achou = st.session_state["doc_estoque_encontrado"]
        if chassi_valor.strip():
            if achou:
                st.success(
                    f"✅ Veículo encontrado: **{achou['modelo']}** · {achou['fabricante']} · "
                    f"Cor: {achou['cor']} · Placa: {achou['placa']} · Status: {achou['status']}"
                )
            else:
                st.error("⚠️ Chassi não encontrado no estoque. Confira o valor colado.")

    # ── Formulário principal ─────────────────────────────────────────────
    with st.form("form_documentacao", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            nome     = st.text_input("Nome completo *")
            cpf_cnpj = st.text_input("CPF/CNPJ *")
            telefone = st.text_input("Telefone *")
            email    = st.text_input("E-mail *")
        with c2:
            modelo = st.text_input("Modelo *", value=st.session_state["doc_modelo_autofill"])
            cor    = st.text_input("Cor *", value=st.session_state["doc_cor_autofill"])
            plano  = st.text_input("Plano *")
            km     = st.text_input("Km *")

        st.markdown("##### 📎 Documentos (até 8 arquivos PDF)")
        arquivos = st.file_uploader(
            "Selecione até 8 PDFs",
            type=["pdf"],
            accept_multiple_files=True,
            key="doc_arquivos",
        )

        enviado = st.form_submit_button("✅ Concluir", use_container_width=True)

    if not enviado:
        return

    # ── Validações ─────────────────────────────────────────────────────
    erros = []
    if not nome.strip():          erros.append("Nome completo é obrigatório.")
    if not cpf_cnpj.strip():      erros.append("CPF/CNPJ é obrigatório.")
    if not telefone.strip():      erros.append("Telefone é obrigatório.")
    if not email.strip():         erros.append("E-mail é obrigatório.")
    if not modelo.strip():        erros.append("Modelo é obrigatório.")
    if not cor.strip():           erros.append("Cor é obrigatória.")
    if not plano.strip():         erros.append("Plano é obrigatório.")
    if not km.strip():            erros.append("Km é obrigatório.")
    if pronta_entrega == "Sim" and not chassi_valor.strip():
        erros.append("Informe o Chassi (Pronta Entrega = Sim).")
    if arquivos and len(arquivos) > 8:
        erros.append(f"Máximo de 8 documentos (você selecionou {len(arquivos)}).")
    if not arquivos:
        erros.append("Anexe ao menos 1 documento PDF.")

    if erros:
        for e in erros:
            st.error(e)
        return

    # ── Monta pacote ──────────────────────────────────────────────────
    senha = _gerar_senha_5_digitos()
    nome_base = f"{_sanitizar_nome_arquivo(nome)}_{_somente_digitos(cpf_cnpj)}"
    nome_zip = f"{nome_base}.zip"

    zip_bytes = _gerar_zip_com_senha(arquivos, senha, nome_pasta=nome_base)

    dados = {
        "nome": nome.strip(),
        "cpf_cnpj": cpf_cnpj.strip(),
        "telefone": telefone.strip(),
        "email": email.strip(),
        "modelo": modelo.strip(),
        "cor": cor.strip(),
        "plano": plano.strip(),
        "km": km.strip(),
        "pronta_entrega": pronta_entrega,
        "chassi": chassi_valor.strip(),
        "estoque": st.session_state["doc_estoque_encontrado"],
        "qtd_docs": len(arquivos),
        "nomes_docs": [a.name for a in arquivos],
        "nome_zip": nome_zip,
    }
    texto_email = _montar_texto_email(dados)

    st.session_state["doc_resultado"] = {
        "texto_email": texto_email,
        "zip_bytes": zip_bytes,
        "nome_zip": nome_zip,
        "senha": senha,
    }

    # ── Reset dos campos de busca p/ próximo cadastro ───────────────────
    st.session_state["doc_estoque_encontrado"] = None
    st.session_state["doc_modelo_autofill"] = ""
    st.session_state["doc_cor_autofill"] = ""

    _exibir_resultado()


def _exibir_resultado():
    res = st.session_state.get("doc_resultado")
    if not res:
        return

    st.markdown("---")
    st.markdown("### ✅ Cadastro concluído")

    st.warning(
        f"🔑 **Senha do arquivo .zip: `{res['senha']}`** — anote agora, ela **não é salva** "
        "em nenhum lugar e não será mostrada novamente."
    )

    st.download_button(
        f"📦 Baixar {res['nome_zip']}",
        data=res["zip_bytes"],
        file_name=res["nome_zip"],
        mime="application/zip",
        use_container_width=True,
    )

    st.markdown("##### ✉️ Texto formatado para e-mail")
    st.text_area("Copie o texto abaixo:", value=res["texto_email"], height=380, key="doc_texto_email_area")


if __name__ == "__main__":
    render()