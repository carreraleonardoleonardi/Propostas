# -*- coding: utf-8 -*-
"""
Consolida_Base_LM.py — Carrera Signature
============================================================
Gera base_consolidada_completa.xlsx com 1 linha por carro.

Campos finais:
  orderId, clientType, prefix, segmentName, name, cpfCnpj,
  dateCreated, dateLastUpdated, userId, Proprietario da Oportunidade,
  orderStatus, dealershipId, dealershipGroupId, monthlyKmValue,
  deadline, total_km, modelCode, model, color, typeOfPainting,
  optional, vehicleValue, publicPrice, monthlyInstallment,
  overrunKm, finalPlate, deadlineInfo, kickback, chassis, deliveryPlate

Fontes:
  1. Lista_LM.xlsx                    → campos do pedido
  2. vListaCarrosDetalhes.xlsx        → 1 linha por carro (expande)
  3. orderItemStatus (JSON)           → chassis, deliveryPlate
  4. Ofertas_Todos_SalesChannels.xlsx → preços via productId
  5. Base Salesforce.xlsx             → Proprietario da Oportunidade

Ordem dos joins:
  pedidos → salesforce (1:1, antes de expandir)
  pedidos × carros     (1:N, expande para 1 linha/carro)
  carros  → ofertas    (N:1, via productId)
  extrai  orderItemStatus → chassis, deliveryPlate
"""

import os
import sys
import ast
import traceback
from datetime import datetime

import pandas as pd


# ============================================================
# CONFIG
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _p(nome): return os.path.join(BASE_DIR, nome)

ARQ_PEDIDOS    = _p("Lista_LM.xlsx")
ARQ_CARROS     = _p("vListaCarrosDetalhes.xlsx")
ARQ_OFERTAS    = _p("Ofertas_Todos_SalesChannels.xlsx")
ARQ_SALESFORCE = _p("Base Salesforce.xlsx")
ARQ_SAIDA      = _p("base_consolidada_completa.xlsx")

# Campos finais desejados — na ordem exata
CAMPOS_FINAIS = [
    "orderId",
    "clientType",
    "prefix",
    "segmentName",
    "name",
    "cpfCnpj",
    "dateCreated",
    "dateLastUpdated",
    "userId",
    "Proprietario da Oportunidade",
    "orderStatus",
    "dealershipId",
    "dealershipGroupId",
    "monthlyKmValue",
    "deadline",
    "total_km",
    "modelCode",
    "model",
    "color",
    "typeOfPainting",
    "optional",
    "vehicleValue",
    "publicPrice",
    "monthlyInstallment",
    "overrunKm",
    "finalPlate",
    "deadlineInfo",
    "kickback",
    "chassis",
    "deliveryPlate",
]


# ============================================================
# LOG
# ============================================================
def log(msg=""): print(msg)
def sep(): print("=" * 62)


# ============================================================
# UTILITÁRIOS
# ============================================================
def _ler(caminho, obrigatorio=True):
    if not os.path.exists(caminho):
        if obrigatorio:
            raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
        log(f"  ⚠️  {os.path.basename(caminho)} não encontrado — pulando.")
        return pd.DataFrame()
    df = pd.read_excel(caminho)
    df.columns = df.columns.astype(str).str.strip()
    # Remove colunas duplicadas
    if df.columns.duplicated().any():
        dups = df.columns[df.columns.duplicated()].tolist()
        df = df.loc[:, ~df.columns.duplicated()]
        log(f"  ⚠️  Colunas duplicadas removidas: {dups}")
    log(f"  📄 {os.path.basename(caminho)} — {len(df)} linhas, {len(df.columns)} colunas")
    return df


def _pad(x):
    """Normaliza IDs: 123.0 → '123'"""
    try:
        if pd.isna(x): return None
        s = str(x).strip()
        if not s: return None
        try:    return str(int(float(s)))
        except: return s
    except: return None


def _pad_col(df, col):
    if col in df.columns:
        df[col] = df[col].apply(_pad)
    return df


def _dedup(df, chave, nome):
    antes = len(df)
    df = df.drop_duplicates(subset=[chave], keep="first")
    if len(df) < antes:
        log(f"  ⚠️  {nome}: {antes - len(df)} duplicatas removidas por '{chave}'")
    return df


def _conv_lista(val):
    try:
        if pd.isna(val): return []
        if isinstance(val, list): return val
        if isinstance(val, dict): return [val]
        return ast.literal_eval(str(val))
    except: return []


def _extrair_chassis_placa(lista):
    """Extrai chassis e deliveryPlate do orderItemStatus[0]."""
    if isinstance(lista, list) and lista and isinstance(lista[0], dict):
        item = lista[0]
        return pd.Series({
            "chassis":       item.get("chassis"),
            "deliveryPlate": item.get("deliveryPlate"),
        })
    return pd.Series({"chassis": None, "deliveryPlate": None})


# ============================================================
# ETAPA 1 — Pedidos
# ============================================================
def etapa_1_pedidos():
    log("\n📋 Etapa 1 — Pedidos LM")
    df = _ler(ARQ_PEDIDOS)

    if "orderId" not in df.columns:
        raise ValueError("Lista_LM.xlsx não possui a coluna 'orderId'.")

    df = _pad_col(df, "orderId")
    df = _pad_col(df, "dealershipId")
    df = _pad_col(df, "dealershipGroupId")
    df = _pad_col(df, "userId")
    df = _dedup(df, "orderId", "Pedidos")

    # Garante campos obrigatórios
    for col in ["prefix","segmentName","name","cpfCnpj","dateCreated",
                "dateLastUpdated","clientType","orderStatus"]:
        if col not in df.columns:
            df[col] = None

    # Datas
    for col in ["dateCreated","dateLastUpdated"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    log(f"  ✅ {len(df)} pedidos únicos")
    return df


# ============================================================
# ETAPA 2 — Salesforce (antes de expandir — 1:1)
# ============================================================
def etapa_2_salesforce(df):
    log("\n📊 Etapa 2 — Salesforce")
    df_sf = _ler(ARQ_SALESFORCE, obrigatorio=False)

    df["Proprietario da Oportunidade"] = None   # garante a coluna

    if df_sf.empty:
        log("  ⚠️  Salesforce não disponível — coluna ficará vazia.")
        return df

    col_pedido = "Nro do Pedido"
    col_prop   = "Proprietário da oportunidade"

    if col_pedido not in df_sf.columns or col_prop not in df_sf.columns:
        log(f"  ⚠️  Colunas necessárias não encontradas no Salesforce.")
        return df

    df_sf["orderId"] = (
        df_sf[col_pedido]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.strip()
    )
    df_sf = _pad_col(df_sf, "orderId")
    df_sf = df_sf.dropna(subset=["orderId"])
    df_sf = df_sf[["orderId", col_prop]].rename(
        columns={col_prop: "Proprietario da Oportunidade"}
    )
    df_sf = _dedup(df_sf, "orderId", "Salesforce")

    df = df.merge(df_sf, on="orderId", how="left", suffixes=("", "_sf"))

    # Consolida coluna (se já existia da garantia acima)
    if "Proprietario da Oportunidade_sf" in df.columns:
        df["Proprietario da Oportunidade"] = df["Proprietario da Oportunidade"].fillna(
            df["Proprietario da Oportunidade_sf"]
        )
        df = df.drop(columns=["Proprietario da Oportunidade_sf"])

    encontrados = df["Proprietario da Oportunidade"].notna().sum()
    log(f"  ✅ {encontrados}/{len(df)} proprietários encontrados")
    return df


# ============================================================
# ETAPA 3 — Carros + Ofertas (EXPANDE para 1 linha por carro)
# ============================================================
def etapa_3_carros_e_ofertas(df):
    log("\n🚗 Etapa 3 — Carros + Ofertas (expande para 1 linha/carro)")

    # ── Carros ───────────────────────────────────────────────
    df_c = _ler(ARQ_CARROS)

    for col in ["orderId","orderItemId"]:
        if col not in df_c.columns:
            raise ValueError(f"vListaCarrosDetalhes.xlsx não possui '{col}'.")

    df_c = _pad_col(df_c, "orderId")
    df_c = _pad_col(df_c, "orderItemId")

    if "productId" in df_c.columns:
        df_c["productId"] = df_c["productId"].astype(str).str.strip()

    # Remove duplicatas por orderId + orderItemId
    antes = len(df_c)
    df_c  = df_c.drop_duplicates(subset=["orderId","orderItemId"], keep="first")
    if len(df_c) < antes:
        log(f"  ⚠️  Carros: {antes - len(df_c)} duplicatas removidas")

    # Numéricos
    for col in ["monthlyKmValue","deadline","overrunKm","finalPlate"]:
        if col in df_c.columns:
            df_c[col] = pd.to_numeric(df_c[col], errors="coerce")

    # total_km
    if "monthlyKmValue" in df_c.columns and "deadline" in df_c.columns:
        df_c["total_km"] = df_c["monthlyKmValue"] * df_c["deadline"]
    else:
        df_c["total_km"] = None

    # Extrai chassis e deliveryPlate do orderItemStatus
    if "orderItemStatus" in df_c.columns:
        parsed = df_c["orderItemStatus"].apply(_conv_lista)
        df_c[["chassis","deliveryPlate"]] = parsed.apply(_extrair_chassis_placa)
    else:
        df_c["chassis"]       = None
        df_c["deliveryPlate"] = None

    # Garante campos do carro
    for col in ["modelCode","model","color","typeOfPainting","optional","finalPlate"]:
        if col not in df_c.columns:
            df_c[col] = None

    # ── Ofertas ───────────────────────────────────────────────
    df_of = _ler(ARQ_OFERTAS, obrigatorio=False)
    if not df_of.empty and "productId" in df_of.columns and "productId" in df_c.columns:
        df_of["productId"] = df_of["productId"].astype(str).str.strip()
        df_of = _dedup(df_of, "productId", "Ofertas")

        COLS_OFERTA = [
            "productId","vehicleValue","publicPrice","monthlyInstallment",
            "overrunKm","deadlineInfo","kickback",
        ]
        cols_ok = [c for c in COLS_OFERTA if c in df_of.columns]
        df_of   = df_of[cols_ok]

        # Numéricos das ofertas
        for col in ["vehicleValue","publicPrice","monthlyInstallment","overrunKm","kickback"]:
            if col in df_of.columns:
                df_of[col] = pd.to_numeric(df_of[col], errors="coerce")

        antes = len(df_c)
        df_c  = df_c.merge(df_of, on="productId", how="left",
                            suffixes=("","_oferta"))

        # Se overrunKm existia nos dois, usa a da oferta
        if "overrunKm_oferta" in df_c.columns:
            df_c["overrunKm"] = df_c["overrunKm"].fillna(df_c["overrunKm_oferta"])
            df_c = df_c.drop(columns=["overrunKm_oferta"])

        log(f"  🔗 Carros × Ofertas: {antes} → {len(df_c)} linhas")

        # Garante campos de oferta
        for col in ["vehicleValue","publicPrice","monthlyInstallment","deadlineInfo","kickback"]:
            if col not in df_c.columns:
                df_c[col] = None
    else:
        for col in ["vehicleValue","publicPrice","monthlyInstallment","deadlineInfo","kickback"]:
            df_c[col] = None

    # ── Merge principal (expande) ─────────────────────────────
    antes = len(df)
    df = df.merge(df_c, on="orderId", how="left",
                  validate="one_to_many", suffixes=("","_carro"))
    log(f"  🔗 Pedidos × Carros: {antes} → {len(df)} linhas")

    # Remove colunas _carro duplicadas desnecessárias
    colunas_carro = [c for c in df.columns if c.endswith("_carro")]
    df = df.drop(columns=colunas_carro)

    log(f"  ✅ {len(df)} linhas após expansão")
    return df


# ============================================================
# ETAPA 4 — Seleciona e exporta apenas os campos finais
# ============================================================
def etapa_4_exportar(df):
    log("\n📐 Etapa 4 — Seleção dos campos finais")

    # Garante que todos os campos existem
    for col in CAMPOS_FINAIS:
        if col not in df.columns:
            df[col] = None
            log(f"  ⚠️  Campo '{col}' não encontrado — preenchido com None")

    # Seleciona na ordem exata
    df_final = df[CAMPOS_FINAIS].copy()

    # Formata datas
    for col in ["dateCreated","dateLastUpdated"]:
        if col in df_final.columns:
            df_final[col] = pd.to_datetime(df_final[col], errors="coerce").dt.strftime("%d/%m/%Y %H:%M").fillna("")

    log(f"  ✅ {len(df_final)} linhas | {len(df_final.columns)} colunas")

    log(f"\n💾 Exportando → {ARQ_SAIDA}")
    df_final.to_excel(ARQ_SAIDA, index=False)
    log(f"  ✅ Arquivo gerado com sucesso")
    return df_final


# ============================================================
# MAIN
# ============================================================
def main():
    sep()
    log("   CONSOLIDADOR BASE LM — CARRERA SIGNATURE")
    log(f"   {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    sep()

    try:
        df = etapa_1_pedidos()
        df = etapa_2_salesforce(df)       # 1 linha/pedido — antes de expandir
        df = etapa_3_carros_e_ofertas(df) # expande → 1 linha/carro
        df = etapa_4_exportar(df)

        sep()
        log("✅ Consolidação finalizada!")
        log(f"📦 Total de linhas : {len(df)}")
        log(f"🧾 Total de colunas: {len(df.columns)}")
        log(f"📁 Arquivo         : {ARQ_SAIDA}")
        sep()

        try:
            from plyer import notification
            notification.notify(
                title="Consolidador LM ✅",
                message=f"{len(df)} linhas geradas em base_consolidada_completa.xlsx",
                timeout=5,
            )
        except Exception:
            pass

    except Exception as e:
        log(f"\n❌ Erro: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()