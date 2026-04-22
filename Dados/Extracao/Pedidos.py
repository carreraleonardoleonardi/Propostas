import os
import time
import json
import hashlib
from pathlib import Path
from datetime import datetime

import pandas as pd
import requests

# =========================================================
# CONFIG
# =========================================================
URL = "https://backend.vwsignanddrive.com.br/api/dealership-management"
TOKEN = "Bearer SEU_TOKEN_AQUI"

HEADERS = {
    "Authorization": TOKEN,
    "Content-Type": "application/json",
    "accept": "application/json, text/plain, */*",
    "origin": "https://portaldealer.lmmobilidade.com.br/my-orders",
}

DEALERSHIP_ID = "21"
DEALERSHIP_GROUP_ID = "234"
ROLE = "Admin do Grupo"

PER_PAGE = 20
MAX_PAGINAS = 0  # 0 = todas

BASE_DIR = Path(__file__).resolve().parent
DADOS_DIR = BASE_DIR / "dados"
SNAPSHOTS_DIR = DADOS_DIR / "snapshots"
HISTORICO_DIR = DADOS_DIR / "historico"
ATUAL_DIR = DADOS_DIR / "atual"
LOGS_DIR = DADOS_DIR / "logs"

for pasta in [SNAPSHOTS_DIR, HISTORICO_DIR, ATUAL_DIR, LOGS_DIR]:
    pasta.mkdir(parents=True, exist_ok=True)

ARQ_HISTORICO = HISTORICO_DIR / "lm_historico.parquet"
ARQ_ATUAL = ATUAL_DIR / "lm_atual.parquet"
ARQ_LOG = LOGS_DIR / "lm_execucoes.csv"

# =========================================================
# HELPERS
# =========================================================
def agora_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def timestamp_arquivo():
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def tentar_converter_datas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        nome = str(col).lower()
        if any(p in nome for p in ["date", "data", "created", "updated", "schedule"]):
            try:
                df[col] = pd.to_datetime(df[col], errors="ignore")
            except Exception:
                pass
    return df


def detectar_chave(df: pd.DataFrame) -> str:
    candidatos = [
        "orderId",
        "orderID",
        "orderNumber",
        "proposalId",
        "proposalID",
        "id",
        "Nro do Pedido",
        "numeroPedido",
    ]
    for c in candidatos:
        if c in df.columns:
            return c
    raise ValueError(
        "Não encontrei uma chave única automática. "
        "Defina manualmente a coluna identificadora do pedido."
    )


def construir_chave(df: pd.DataFrame, coluna_chave: str) -> pd.Series:
    return df[coluna_chave].astype(str).str.strip()


def colunas_estado(df: pd.DataFrame) -> list[str]:
    preferidas = [
        "orderStatus",
        "deliveryStatus",
        "scheduledDate",
        "scheduleDate",
        "store",
        "withdrawBy",
        "plate",
        "chassis",
        "phase",
        "status",
        "deliveryStore",
        "deliveryDate",
    ]
    existentes = [c for c in preferidas if c in df.columns]

    if not existentes:
        ignorar = {
            "snapshot_id",
            "data_extracao",
            "arquivo_snapshot",
            "hash_estado",
            "chave_registro",
            "ultima_atualizacao",
        }
        existentes = [c for c in df.columns if c not in ignorar]

    return existentes


def gerar_hash_estado(df: pd.DataFrame, cols_estado: list[str]) -> pd.Series:
    def _hash_linha(row):
        payload = "||".join("" if pd.isna(row[c]) else str(row[c]).strip() for c in cols_estado)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    return df.apply(_hash_linha, axis=1)


def registrar_log(evento: str, detalhe: str = "", qtd: int | None = None):
    linha = pd.DataFrame([{
        "datahora": agora_str(),
        "evento": evento,
        "detalhe": detalhe,
        "quantidade": qtd,
    }])

    if ARQ_LOG.exists():
        base = pd.read_csv(ARQ_LOG)
        base = pd.concat([base, linha], ignore_index=True)
    else:
        base = linha

    base.to_csv(ARQ_LOG, index=False, encoding="utf-8-sig")


# =========================================================
# EXTRAÇÃO
# =========================================================
def consulta_lm(page_select: int, per_page: int, tentativas: int = 3):
    params = {
        "dealershipId": DEALERSHIP_ID,
        "dealershipGroupId": DEALERSHIP_GROUP_ID,
        "role": ROLE,
        "QuantityPerPage": per_page,
        "CurrentPage": page_select,
    }

    timeout_usado = 120 if page_select >= 10 else 30

    for tentativa in range(1, tentativas + 1):
        try:
            response = requests.get(
                URL,
                headers=HEADERS,
                params=params,
                timeout=timeout_usado,
            )

            print(f"📡 Página {page_select} | HTTP {response.status_code}")
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            espera = 2 ** tentativa
            print(f"⚠️ Timeout página {page_select}, tentativa {tentativa}/{tentativas}. Esperando {espera}s...")
            time.sleep(espera)

        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP erro página {page_select}: {e}")
            if response.status_code >= 500 and tentativa < tentativas:
                time.sleep(2)
                continue
            return None

        except requests.exceptions.RequestException as e:
            print(f"❌ Erro de conexão página {page_select}: {e}")
            time.sleep(3)

        except Exception as e:
            print(f"❌ Erro inesperado página {page_select}: {e}")
            time.sleep(2)

    return None


def extrair_todas_paginas(max_paginas: int = 0, per_page: int = 20) -> pd.DataFrame:
    page_select = 1
    has_next_page = True
    partes = []

    while has_next_page and (max_paginas == 0 or page_select <= max_paginas):
        resultado = consulta_lm(page_select=page_select, per_page=per_page)

        if resultado is None:
            raise RuntimeError(f"Falha na extração da página {page_select}")

        if "items" not in resultado:
            raise RuntimeError(f"Resposta sem chave 'items' na página {page_select}: {resultado}")

        itens = resultado["items"].get("itens", [])
        df_temp = pd.DataFrame(itens)

        if df_temp.empty:
            print(f"⚠️ Página {page_select} sem itens.")
            break

        partes.append(df_temp)
        print(f"✅ Página {page_select} adicionada com {len(df_temp)} registros.")

        has_next_page = resultado["items"].get("hasNextPage", False)
        page_select += 1
        time.sleep(1)

    if not partes:
        return pd.DataFrame()

    df = pd.concat(partes, ignore_index=True)
    df = normalizar_colunas(df)
    df = tentar_converter_datas(df)
    return df


# =========================================================
# PERSISTÊNCIA
# =========================================================
def salvar_snapshot(df: pd.DataFrame) -> Path:
    snap_id = timestamp_arquivo()
    arquivo = SNAPSHOTS_DIR / f"lm_snapshot_{snap_id}.parquet"

    df_snapshot = df.copy()
    df_snapshot["snapshot_id"] = snap_id
    df_snapshot["data_extracao"] = agora_str()
    df_snapshot["arquivo_snapshot"] = arquivo.name

    df_snapshot.to_parquet(arquivo, index=False)
    registrar_log("snapshot_salvo", arquivo.name, len(df_snapshot))
    return arquivo


def carregar_historico() -> pd.DataFrame:
    if ARQ_HISTORICO.exists():
        return pd.read_parquet(ARQ_HISTORICO)
    return pd.DataFrame()


def atualizar_historico(df_novo: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df_novo.empty:
        return pd.DataFrame(), pd.DataFrame()

    df_novo = df_novo.copy()
    chave = detectar_chave(df_novo)
    df_novo["chave_registro"] = construir_chave(df_novo, chave)

    cols_estado = colunas_estado(df_novo)
    df_novo["hash_estado"] = gerar_hash_estado(df_novo, cols_estado)
    df_novo["data_extracao"] = agora_str()
    df_novo["ultima_atualizacao"] = agora_str()

    historico = carregar_historico()

    if historico.empty:
        historico_novo = df_novo.copy()
        historico_novo.to_parquet(ARQ_HISTORICO, index=False)

        base_atual = (
            historico_novo.sort_values("data_extracao")
            .drop_duplicates(subset=["chave_registro"], keep="last")
            .copy()
        )
        base_atual.to_parquet(ARQ_ATUAL, index=False)

        registrar_log("historico_inicializado", "primeira_carga", len(historico_novo))
        return historico_novo, base_atual

    if "chave_registro" not in historico.columns or "hash_estado" not in historico.columns:
        raise RuntimeError(
            "A base histórica existente não tem 'chave_registro' ou 'hash_estado'. "
            "Faça uma migração ou recrie o histórico."
        )

    ultima_versao = (
        historico.sort_values("data_extracao")
        .drop_duplicates(subset=["chave_registro"], keep="last")[["chave_registro", "hash_estado"]]
        .rename(columns={"hash_estado": "hash_estado_anterior"})
    )

    comparacao = df_novo.merge(ultima_versao, on="chave_registro", how="left")

    mudou = comparacao[
        comparacao["hash_estado_anterior"].isna() |
        (comparacao["hash_estado"] != comparacao["hash_estado_anterior"])
    ].copy()

    mudou.drop(columns=["hash_estado_anterior"], inplace=True, errors="ignore")

    if not mudou.empty:
        historico = pd.concat([historico, mudou], ignore_index=True)
        historico.to_parquet(ARQ_HISTORICO, index=False)
        registrar_log("historico_atualizado", "novas_versoes", len(mudou))
    else:
        registrar_log("historico_sem_mudancas", "", 0)

    base_atual = (
        historico.sort_values("data_extracao")
        .drop_duplicates(subset=["chave_registro"], keep="last")
        .copy()
    )
    base_atual.to_parquet(ARQ_ATUAL, index=False)
    registrar_log("base_atual_gerada", ARQ_ATUAL.name, len(base_atual))

    return historico, base_atual


# =========================================================
# EXECUÇÃO
# =========================================================
def main():
    print("🚀 Iniciando extração LM...")
    registrar_log("inicio_execucao")

    df_extraido = extrair_todas_paginas(max_paginas=MAX_PAGINAS, per_page=PER_PAGE)

    if df_extraido.empty:
        print("⚠️ Nenhum dado retornado.")
        registrar_log("execucao_sem_dados")
        return

    print(f"✅ Total extraído: {len(df_extraido)}")
    snap = salvar_snapshot(df_extraido)
    print(f"📦 Snapshot salvo em: {snap}")

    historico, atual = atualizar_historico(df_extraido)

    print(f"🕘 Histórico total: {len(historico)} linhas")
    print(f"📌 Base atual: {len(atual)} linhas")

    print("✅ Processo concluído com sucesso.")
    registrar_log("fim_execucao", "sucesso", len(df_extraido))


if __name__ == "__main__":
    main()