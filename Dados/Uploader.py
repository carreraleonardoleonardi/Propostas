"""
uploader.py — Carrera Signature
Sobe Consolidado_LM.xlsx e Cockpit_Carrera.xlsx pro Google Sheets.
Pode ser rodado:
  - Via terminal: python Dados/uploader.py
  - Via botão no Streamlit (pages/relatorio.py chama este módulo)
"""

import os
import sys
import json
import time
import datetime
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ── Caminhos ────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # .../propostas/Dados/

ARQUIVOS = {
    "lm":      os.path.join(BASE_DIR, "Consolidado_LM.xlsx"),
    "cockpit": os.path.join(BASE_DIR, "Cockpit_Carrera.xlsx"),
}

# ── Autenticação Google ──────────────────────────────────────────────────────

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

def _credenciais():
    """
    Tenta ler credenciais de 3 fontes, nesta ordem:
    1. st.secrets (quando rodando dentro do Streamlit)
    2. credentials.json na pasta Dados/
    3. Variável de ambiente GOOGLE_CREDENTIALS (JSON string)
    """
    # 1 — Streamlit secrets
    try:
        import streamlit as st
        info = dict(st.secrets["gcp_service_account"])
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception:
        pass

    # 2 — Arquivo local credentials.json
    cred_path = os.path.join(BASE_DIR, "credentials.json")
    if os.path.exists(cred_path):
        return Credentials.from_service_account_file(cred_path, scopes=SCOPES)

    # 3 — Variável de ambiente
    env = os.environ.get("GOOGLE_CREDENTIALS")
    if env:
        info = json.loads(env)
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    raise FileNotFoundError(
        "Credenciais Google não encontradas.\n"
        "Coloque credentials.json em propostas/Dados/ "
        "ou configure st.secrets['gcp_service_account']."
    )


def _cliente_sheets():
    return gspread.authorize(_credenciais())


# ── Helpers ──────────────────────────────────────────────────────────────────

def _limpar_df(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara DataFrame para upload: NaN → '', tipos → str compatível."""
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == "datetime64[ns]":
            df[col] = df[col].dt.strftime("%d/%m/%Y").fillna("")
        else:
            df[col] = df[col].fillna("").astype(str).str.strip()
    return df


def _upload_aba(planilha, nome_aba: str, df: pd.DataFrame, log=print):
    """Cria ou limpa a aba e sobe o DataFrame."""
    df = _limpar_df(df)
    dados = [df.columns.tolist()] + df.values.tolist()

    # Cria aba se não existir
    abas = [ws.title for ws in planilha.worksheets()]
    if nome_aba in abas:
        ws = planilha.worksheet(nome_aba)
        ws.clear()
    else:
        ws = planilha.add_worksheet(title=nome_aba, rows=len(df) + 10, cols=len(df.columns) + 5)

    # Upload em lotes de 5000 linhas para evitar timeout
    LOTE = 5000
    ws.update("A1", dados[:LOTE])
    for i in range(LOTE, len(dados), LOTE):
        time.sleep(1)
        ws.append_rows(dados[i:i + LOTE], value_input_option="USER_ENTERED")

    log(f"  ✅ Aba '{nome_aba}': {len(df)} linhas enviadas.")
    return len(df)


# ── Funções principais ───────────────────────────────────────────────────────

def criar_planilha(nome: str = "Carrera — Base Consolidada", log=print) -> str:
    """Cria uma nova planilha no Drive e retorna o ID."""
    gc = _cliente_sheets()
    sh = gc.create(nome)
    sh.share(None, perm_type="anyone", role="reader")  # leitura pública
    log(f"📄 Planilha criada: {sh.url}")
    log(f"   ID: {sh.id}")
    log("   ⚠️  Copie o ID acima e adicione ao secrets.toml como SHEET_ID_DADOS")
    return sh.id


def subir_lm(sheet_id: str, log=print) -> dict:
    """
    Sobe Consolidado_LM.xlsx para o Sheets.
    Cria as abas: lm_pedidos, lm_carros (se existirem no Excel)
    """
    resultado = {}
    path = ARQUIVOS["lm"]

    if not os.path.exists(path):
        log(f"⚠️  Arquivo não encontrado: {path}")
        return resultado

    log(f"📂 Lendo {os.path.basename(path)}...")
    gc = _cliente_sheets()
    sh = gc.open_by_key(sheet_id)

    # Lê todas as abas do Excel
    xls = pd.ExcelFile(path)
    for aba in xls.sheet_names:
        df = pd.read_excel(path, sheet_name=aba)
        if df.empty:
            log(f"  ⚠️  Aba '{aba}' vazia, pulando.")
            continue
        nome_aba = f"lm_{aba.lower().replace(' ', '_')}"
        n = _upload_aba(sh, nome_aba, df, log)
        resultado[nome_aba] = n
        time.sleep(1)  # respeita quota da API

    return resultado


def subir_cockpit(sheet_id: str, log=print) -> dict:
    """
    Sobe Cockpit_Carrera.xlsx (RCI/TOOT) para o Sheets.
    Aba destino: rci_toot
    """
    resultado = {}
    path = ARQUIVOS["cockpit"]

    if not os.path.exists(path):
        log(f"⚠️  Arquivo não encontrado: {path}")
        return resultado

    log(f"📂 Lendo {os.path.basename(path)}...")
    gc = _cliente_sheets()
    sh = gc.open_by_key(sheet_id)

    df = pd.read_excel(path)
    if df.empty:
        log("  ⚠️  Arquivo vazio.")
        return resultado

    n = _upload_aba(sh, "rci_toot", df, log)
    resultado["rci_toot"] = n
    return resultado


def subir_tudo(sheet_id: str, log=print) -> dict:
    """Sobe LM + Cockpit e registra timestamp na aba 'log_upload'."""
    log("🚀 Iniciando upload para Google Sheets...")
    log(f"   Sheet ID: {sheet_id}")
    log("")

    resultado = {}

    log("1️⃣  Subindo base LM...")
    resultado.update(subir_lm(sheet_id, log))
    log("")

    log("2️⃣  Subindo Cockpit (RCI/TOOT)...")
    resultado.update(subir_cockpit(sheet_id, log))
    log("")

    # Registra log de upload
    try:
        gc = _cliente_sheets()
        sh = gc.open_by_key(sheet_id)
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        linhas_log = [[agora, aba, qtd] for aba, qtd in resultado.items()]
        abas = [ws.title for ws in sh.worksheets()]
        if "log_upload" not in abas:
            ws_log = sh.add_worksheet(title="log_upload", rows=1000, cols=5)
            ws_log.update("A1", [["data_hora", "aba", "linhas"]])
        else:
            ws_log = sh.worksheet("log_upload")
        ws_log.append_rows(linhas_log, value_input_option="USER_ENTERED")
    except Exception as e:
        log(f"  ⚠️  Não foi possível gravar log: {e}")

    total = sum(resultado.values())
    log(f"✅ Upload concluído! {total} linhas enviadas em {len(resultado)} aba(s).")
    return resultado


# ── Execução direta via terminal ─────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Uploader Carrera → Google Sheets")
    parser.add_argument("--sheet-id", help="ID da planilha destino no Google Sheets")
    parser.add_argument("--criar",    action="store_true", help="Cria uma nova planilha e imprime o ID")
    parser.add_argument("--lm",       action="store_true", help="Sobe apenas a base LM")
    parser.add_argument("--cockpit",  action="store_true", help="Sobe apenas o Cockpit (RCI/TOOT)")
    args = parser.parse_args()

    if args.criar:
        criar_planilha()
        sys.exit(0)

    sheet_id = args.sheet_id or os.environ.get("SHEET_ID_DADOS")
    if not sheet_id:
        # Tenta ler do secrets.toml via toml
        try:
            import tomllib
            with open(os.path.join(BASE_DIR, "..", ".streamlit", "secrets.toml"), "rb") as f:
                sec = tomllib.load(f)
            sheet_id = sec.get("SHEET_ID_DADOS")
        except Exception:
            pass

    if not sheet_id:
        print("❌ Informe o ID da planilha: --sheet-id SEU_ID")
        print("   Ou crie uma nova: python uploader.py --criar")
        sys.exit(1)

    if args.lm:
        subir_lm(sheet_id)
    elif args.cockpit:
        subir_cockpit(sheet_id)
    else:
        subir_tudo(sheet_id)