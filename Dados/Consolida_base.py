# -*- coding: utf-8 -*-
"""
============================================================
CONSOLIDADOR BASE LM — CARRERA SIGNATURE
Versão reestruturada
============================================================

Lógica:
1) Base principal por pedido
   - Lista_LM.xlsx
   - Lista_LM_Concluidos.xlsx
   - vListaConsultoresDetalhes.xlsx
   - Lista_DN.xlsx

2) Base detalhada por carro/item
   - vListaCarrosDetalhes.xlsx
   - Ofertas_Todos_SalesChannels.xlsx

3) Enriquecimento externo
   - Base Salesforce.xlsx

4) Exportação final
   - 1 linha por carro do pedido
"""

import os
import sys
import traceback
import ast
from datetime import datetime

import pandas as pd


# ============================================================
# CONFIG
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ARQ_PEDIDOS = os.path.join(BASE_DIR, "Lista_LM.xlsx")
ARQ_CONCLUIDOS = os.path.join(BASE_DIR, "Lista_LM_Concluidos.xlsx")
ARQ_CONSULTORES = os.path.join(BASE_DIR, "vListaConsultoresDetalhes.xlsx")
ARQ_CARROS = os.path.join(BASE_DIR, "vListaCarrosDetalhes.xlsx")
ARQ_DN = os.path.join(BASE_DIR, "Lista_DN.xlsx")
ARQ_OFERTAS = os.path.join(BASE_DIR, "Ofertas_Todos_SalesChannels.xlsx")
ARQ_SALESFORCE = os.path.join(BASE_DIR, "Base Salesforce.xlsx")

ARQ_SAIDA = os.path.join(BASE_DIR, "base_consolidada_completa.xlsx")


# ============================================================
# LOG
# ============================================================
def log(msg=""):
    print(msg)


def linha():
    print("=" * 60)


# ============================================================
# UTILITÁRIOS
# ============================================================
def carregar_excel(caminho):
    if not os.path.exists(caminho):
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
    return pd.read_excel(caminho)


def limpar_nomes_colunas(df, nome_df="DataFrame"):
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()

    duplicadas = df.columns[df.columns.duplicated()].tolist()
    if duplicadas:
        log(f"  ⚠️ {nome_df}: colunas duplicadas encontradas e removidas: {duplicadas}")
        df = df.loc[:, ~df.columns.duplicated()]

    return df


def padronizar_id_generico(x):
    try:
        if pd.isna(x):
            return None
        txt = str(x).strip()
        if txt == "":
            return None

        # tenta converter 123.0 -> 123
        if txt.endswith(".0"):
            txt = txt[:-2]

        try:
            return str(int(float(txt)))
        except Exception:
            return txt.strip()
    except Exception:
        return None


def padronizar_coluna_id(df, coluna):
    df = df.copy()
    if coluna in df.columns:
        df[coluna] = df[coluna].apply(padronizar_id_generico)
    return df


def selecionar_colunas_existentes(df, colunas):
    return [c for c in colunas if c in df.columns]


def auditar_chave(df, chave, nome_df):
    if chave not in df.columns:
        log(f"  ⚠️ {nome_df}: coluna-chave '{chave}' não existe.")
        return

    total_linhas = len(df)
    total_unicos = df[chave].nunique(dropna=True)
    repetidos = total_linhas - total_unicos

    log(f"  🔎 {nome_df}: {total_linhas} linhas | {total_unicos} {chave} únicos | {repetidos} repetidos")


def remover_duplicidade_por_chave(df, chave, nome_df, keep="first"):
    df = df.copy()

    if chave not in df.columns:
        raise ValueError(f"{nome_df}: coluna '{chave}' não encontrada para remover duplicidade.")

    antes = len(df)
    df = df.drop_duplicates(subset=[chave], keep=keep)
    depois = len(df)

    if antes != depois:
        log(f"  ⚠️ {nome_df}: removidas {antes - depois} linhas duplicadas por '{chave}'")

    return df


def merge_seguro(
    df_esq,
    df_dir,
    on,
    how="left",
    nome_esq="Base esquerda",
    nome_dir="Base direita",
    validate=None,
    suffixes=("", "_dup")
):
    if on not in df_esq.columns:
        raise ValueError(f"{nome_esq}: coluna '{on}' não encontrada.")
    if on not in df_dir.columns:
        raise ValueError(f"{nome_dir}: coluna '{on}' não encontrada.")

    antes = len(df_esq)

    df_merge = df_esq.merge(
        df_dir,
        on=on,
        how=how,
        validate=validate,
        suffixes=suffixes
    )

    depois = len(df_merge)

    log(f"  🔗 Merge {nome_esq} + {nome_dir} por '{on}'")
    log(f"     Linhas antes: {antes} | depois: {depois}")

    if depois > antes and how == "left":
        log("  ⚠️ O merge aumentou a quantidade de linhas. Verifique a cardinalidade da base da direita.")

    return df_merge


def converter_string_para_lista(val):
    try:
        if pd.isna(val):
            return []
        if isinstance(val, list):
            return val
        if isinstance(val, dict):
            return [val]
        return ast.literal_eval(val)
    except Exception:
        return []


def extrair_chassi_placa(lista):
    if isinstance(lista, list) and len(lista) > 0:
        item = lista[0]
        if isinstance(item, dict):
            chassi = item.get("chassis")
            placa = item.get("deliveryPlate")
            return pd.Series({
                "chassis": chassi,
                "deliveryPlate": placa
            })

    return pd.Series({
        "chassis": None,
        "deliveryPlate": None
    })


def status_concluido_por_orderid(df_concluidos):
    """
    Cria uma base resumida 1 linha por orderId para marcar pedidos concluídos.
    """
    df = df_concluidos.copy()
    df = limpar_nomes_colunas(df, "Concluídos")

    if "orderId" not in df.columns:
        raise ValueError("Lista_LM_Concluidos.xlsx não possui a coluna 'orderId'.")

    df = padronizar_coluna_id(df, "orderId")
    df = df.dropna(subset=["orderId"]).copy()

    resumo = (
        df.groupby("orderId", as_index=False)
          .size()
          .rename(columns={"size": "qtd_registros_concluidos"})
    )

    resumo["pedido_concluido"] = "Sim"
    return resumo


def preparar_consultores(df_cons):
    """
    Prepara a base de consultores para merge por orderId.
    Mantém 1 linha por pedido.
    """
    log("\n👤 Preparando base de consultores")

    df_cons = limpar_nomes_colunas(df_cons, "Consultores")

    if "orderId" not in df_cons.columns:
        raise ValueError("vListaConsultoresDetalhes.xlsx não possui a coluna 'orderId'.")

    df_cons = padronizar_coluna_id(df_cons, "orderId")
    df_cons = df_cons.dropna(subset=["orderId"]).copy()

    # Colunas desejadas — traz o que existir
    colunas_desejadas = [
        "orderId",
        "userId",
        "name",
        "email",
        "phone",
        "document",
        "locationId",
        "dealershipGroupId",
        "isActive"
    ]

    cols = selecionar_colunas_existentes(df_cons, colunas_desejadas)
    df_cons = df_cons[cols].copy()

    # Renomeia para nomes mais claros se existirem
    ren = {}
    if "name" in df_cons.columns:
        ren["name"] = "consultorNome"
    if "email" in df_cons.columns:
        ren["email"] = "consultorEmail"
    if "phone" in df_cons.columns:
        ren["phone"] = "consultorTelefone"
    if "document" in df_cons.columns:
        ren["document"] = "consultorDocumento"
    if "userId" in df_cons.columns:
        ren["userId"] = "consultorId"
    if "isActive" in df_cons.columns:
        ren["isActive"] = "consultorAtivo"

    df_cons.rename(columns=ren, inplace=True)

    auditar_chave(df_cons, "orderId", "Consultores")

    # Mantém 1 linha por pedido
    df_cons = remover_duplicidade_por_chave(df_cons, "orderId", "Consultores", keep="first")

    log(f"  ✅ Consultores prontos: {len(df_cons)} linhas")
    return df_cons


def preparar_dn(df_dn):
    log("\n🏢 Preparando base DN")

    df_dn = limpar_nomes_colunas(df_dn, "Lista_DN")

    if "dealershipGroupId" not in df_dn.columns:
        raise ValueError("Lista_DN.xlsx não possui a coluna 'dealershipGroupId'.")

    if "name" in df_dn.columns:
        df_dn = df_dn.rename(columns={"name": "dealerDelivery"})
    if "uf" in df_dn.columns:
        df_dn = df_dn.rename(columns={"uf": "estado"})

    df_dn = padronizar_coluna_id(df_dn, "dealershipGroupId")
    df_dn = df_dn.dropna(subset=["dealershipGroupId"]).copy()

    colunas_dn = [
        "dealershipGroupId",
        "dealerDelivery",
        "referenceCode",
        "city",
        "estado",
        "address",
        "number",
        "district",
        "phone",
        "cnpj"
    ]

    cols = selecionar_colunas_existentes(df_dn, colunas_dn)
    df_dn = df_dn[cols].copy()

    auditar_chave(df_dn, "dealershipGroupId", "Lista_DN")
    df_dn = remover_duplicidade_por_chave(df_dn, "dealershipGroupId", "Lista_DN", keep="first")

    log(f"  ✅ DN pronta: {len(df_dn)} linhas")
    return df_dn


def preparar_ofertas(df_ofertas):
    log("\n💰 Preparando base de ofertas")

    df_ofertas = limpar_nomes_colunas(df_ofertas, "Ofertas")

    if "productId" not in df_ofertas.columns:
        raise ValueError("Ofertas_Todos_SalesChannels.xlsx não possui a coluna 'productId'.")

    df_ofertas["productId"] = df_ofertas["productId"].astype(str).str.strip()
    df_ofertas = df_ofertas.dropna(subset=["productId"]).copy()

    colunas_ofertas = [
        "productId",
        "brand",
        "monthlyInstallment",
        "vehicleValue",
        "monthlyKmValue",
        "kickback",
        "publicPrice"
    ]

    cols = selecionar_colunas_existentes(df_ofertas, colunas_ofertas)
    df_ofertas = df_ofertas[cols].copy()

    auditar_chave(df_ofertas, "productId", "Ofertas")
    df_ofertas = remover_duplicidade_por_chave(df_ofertas, "productId", "Ofertas", keep="first")

    log(f"  ✅ Ofertas prontas: {len(df_ofertas)} linhas")
    return df_ofertas


def preparar_salesforce(df_sf):
    log("\n📊 Preparando base Salesforce")

    df_sf = limpar_nomes_colunas(df_sf, "Salesforce")

    if "Nro do Pedido" not in df_sf.columns:
        raise ValueError("Base Salesforce.xlsx não possui a coluna 'Nro do Pedido'.")

    df_sf["Nro do Pedido"] = (
        df_sf["Nro do Pedido"]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.strip()
    )

    df_sf.rename(columns={"Nro do Pedido": "orderId"}, inplace=True)
    df_sf = padronizar_coluna_id(df_sf, "orderId")
    df_sf = df_sf.dropna(subset=["orderId"]).copy()

    ren = {}
    if "Proprietário da oportunidade" in df_sf.columns:
        ren["Proprietário da oportunidade"] = "Vendedor"
    df_sf.rename(columns=ren, inplace=True)

    colunas_sf = [
        "orderId",
        "Vendedor",
        "Cliente da Nota Fiscal",
        "Nome da conta",
        "Fase",
        "Data Assinatura Contrat",
        "Chassi",
        "Placa",
        "Quantidade de veículos",
        "Fornecedor",
        "CPF_CNPJ",
        "Estado/Província de cobrança",
        "Cidade de cobrança",
        "DataHora Agendamento",
        "Comissionamento",
        "Telefone",
        "Origem da venda",
        "Loja da Entrega",
        "Status da Entrega",
        "Quem Retira",
        "Data agendamento"
    ]

    cols = selecionar_colunas_existentes(df_sf, colunas_sf)
    df_sf = df_sf[cols].copy()

    auditar_chave(df_sf, "orderId", "Salesforce")
    df_sf = remover_duplicidade_por_chave(df_sf, "orderId", "Salesforce", keep="first")

    log(f"  ✅ Salesforce pronta: {len(df_sf)} linhas")
    return df_sf


def preparar_carros(df_carros):
    log("\n🚗 Preparando base de carros")

    df_carros = limpar_nomes_colunas(df_carros, "Carros")

    colunas_obrigatorias = ["orderId", "orderItemId"]
    for c in colunas_obrigatorias:
        if c not in df_carros.columns:
            raise ValueError(f"vListaCarrosDetalhes.xlsx não possui a coluna obrigatória '{c}'.")

    df_carros = padronizar_coluna_id(df_carros, "orderId")
    df_carros = padronizar_coluna_id(df_carros, "orderItemId")

    if "productId" in df_carros.columns:
        df_carros["productId"] = df_carros["productId"].astype(str).str.strip()

    # remove duplicidade natural da base
    antes = len(df_carros)
    df_carros = df_carros.drop_duplicates(subset=["orderId", "orderItemId"], keep="first")
    depois = len(df_carros)
    if antes != depois:
        log(f"  ⚠️ Carros: removidas {antes - depois} linhas duplicadas por orderId + orderItemId")

    # trata orderItemStatus
    if "orderItemStatus" in df_carros.columns:
        df_carros["orderItemStatus"] = df_carros["orderItemStatus"].apply(converter_string_para_lista)
        df_carros[["chassis", "deliveryPlate"]] = df_carros["orderItemStatus"].apply(extrair_chassi_placa)

    # numéricos
    if "monthlyKmValue" in df_carros.columns:
        df_carros["monthlyKmValue"] = pd.to_numeric(df_carros["monthlyKmValue"], errors="coerce").fillna(0)

    if "deadline" in df_carros.columns:
        df_carros["deadline"] = pd.to_numeric(df_carros["deadline"], errors="coerce").fillna(0)

    if "monthlyKmValue" in df_carros.columns and "deadline" in df_carros.columns:
        df_carros["total_km"] = df_carros["monthlyKmValue"] * df_carros["deadline"]

    log(f"  ✅ Carros prontos: {len(df_carros)} linhas")
    return df_carros


# ============================================================
# ETAPAS
# ============================================================
def etapa_1_base_principal():
    log("\n📋 Etapa 1 — Base principal de pedidos")

    df_pedidos = carregar_excel(ARQ_PEDIDOS)
    df_pedidos = limpar_nomes_colunas(df_pedidos, "Pedidos")

    if "orderId" not in df_pedidos.columns:
        raise ValueError("Lista_LM.xlsx não possui a coluna 'orderId'.")

    df_pedidos = padronizar_coluna_id(df_pedidos, "orderId")

    if "dealershipGroupId" in df_pedidos.columns:
        df_pedidos = padronizar_coluna_id(df_pedidos, "dealershipGroupId")

    auditar_chave(df_pedidos, "orderId", "Pedidos")
    df_pedidos = remover_duplicidade_por_chave(df_pedidos, "orderId", "Pedidos", keep="first")

    if "clientType" in df_pedidos.columns:
        df_pedidos["clientType"] = df_pedidos["clientType"].map({1: "Física", 0: "Jurídica"}).fillna(df_pedidos["clientType"])

    if "totalOrder" in df_pedidos.columns:
        df_pedidos["totalOrder"] = pd.to_numeric(df_pedidos["totalOrder"], errors="coerce").fillna(0)
        df_pedidos["comissao"] = df_pedidos["totalOrder"] * 0.08

    log(f"  ✅ Pedidos prontos: {len(df_pedidos)} linhas")
    return df_pedidos


def etapa_2_concluidos(df):
    log("\n✅ Etapa 2 — Concluídos")

    if not os.path.exists(ARQ_CONCLUIDOS):
        log("  ⚠️ Arquivo de concluídos não encontrado. Etapa ignorada.")
        df["pedido_concluido"] = "Não"
        df["qtd_registros_concluidos"] = 0
        return df

    df_concl = carregar_excel(ARQ_CONCLUIDOS)
    resumo = status_concluido_por_orderid(df_concl)

    auditar_chave(resumo, "orderId", "Resumo Concluídos")

    df = merge_seguro(
        df,
        resumo,
        on="orderId",
        how="left",
        nome_esq="Pedidos",
        nome_dir="Concluídos",
        validate="one_to_one"
    )

    if "pedido_concluido" in df.columns:
        df["pedido_concluido"] = df["pedido_concluido"].fillna("Não")

    if "qtd_registros_concluidos" in df.columns:
        df["qtd_registros_concluidos"] = df["qtd_registros_concluidos"].fillna(0)

    log("  ✅ Concluídos incorporados")
    return df


def etapa_3_consultores(df):
    log("\n👤 Etapa 3 — Consultores")

    if not os.path.exists(ARQ_CONSULTORES):
        log("  ⚠️ Arquivo de consultores não encontrado. Etapa ignorada.")
        return df

    df_cons = carregar_excel(ARQ_CONSULTORES)
    df_cons = preparar_consultores(df_cons)

    # Se o df principal é 1 linha por orderId, então deve ser one_to_one
    df = merge_seguro(
        df,
        df_cons,
        on="orderId",
        how="left",
        nome_esq="Pedidos",
        nome_dir="Consultores",
        validate="one_to_one"
    )

    log("  ✅ Consultores incorporados")
    return df


def etapa_4_dn(df):
    log("\n🏢 Etapa 4 — DN / Concessionária")

    if not os.path.exists(ARQ_DN):
        log("  ⚠️ Arquivo Lista_DN não encontrado. Etapa ignorada.")
        return df

    if "dealershipGroupId" not in df.columns:
        log("  ⚠️ Base principal não possui 'dealershipGroupId'. Etapa ignorada.")
        return df

    df_dn = carregar_excel(ARQ_DN)
    df_dn = preparar_dn(df_dn)

    df = merge_seguro(
        df,
        df_dn,
        on="dealershipGroupId",
        how="left",
        nome_esq="Pedidos",
        nome_dir="DN",
        validate="many_to_one"
    )

    log("  ✅ DN incorporado")
    return df


def etapa_5_carros_e_ofertas(df):
    log("\n🚗 Etapa 5 — Carros + Ofertas")

    if not os.path.exists(ARQ_CARROS):
        log("  ⚠️ Arquivo de carros não encontrado. Etapa ignorada.")
        return df

    df_carros = carregar_excel(ARQ_CARROS)
    df_carros = preparar_carros(df_carros)

    if os.path.exists(ARQ_OFERTAS):
        df_ofertas = carregar_excel(ARQ_OFERTAS)
        df_ofertas = preparar_ofertas(df_ofertas)

        if "productId" in df_carros.columns and "productId" in df_ofertas.columns:
            df_carros = merge_seguro(
                df_carros,
                df_ofertas,
                on="productId",
                how="left",
                nome_esq="Carros",
                nome_dir="Ofertas",
                validate="many_to_one"
            )

    # Aqui SIM a base pode expandir para 1 linha por carro
    df = merge_seguro(
        df,
        df_carros,
        on="orderId",
        how="left",
        nome_esq="Base principal",
        nome_dir="Carros",
        validate="one_to_many",
        suffixes=("", "_carro")
    )

    log("  ✅ Carros e ofertas incorporados")
    return df


def etapa_6_salesforce(df):
    log("\n📊 Etapa 6 — Salesforce")

    if not os.path.exists(ARQ_SALESFORCE):
        log("  ⚠️ Arquivo Base Salesforce não encontrado. Etapa ignorada.")
        return df

    df_sf = carregar_excel(ARQ_SALESFORCE)
    df_sf = preparar_salesforce(df_sf)

    # Como após a etapa de carros pode haver várias linhas por orderId, agora é many_to_one
    df = merge_seguro(
        df,
        df_sf,
        on="orderId",
        how="left",
        nome_esq="Base consolidada",
        nome_dir="Salesforce",
        validate="many_to_one"
    )

    if "comissao" in df.columns:
        df["comissao_vendedor"] = pd.to_numeric(df["comissao"], errors="coerce").fillna(0) * 0.025

    log("  ✅ Salesforce incorporado")
    return df


def etapa_7_ajustes_finais(df):
    log("\n🧹 Etapa 7 — Ajustes finais")

    # remove colunas duplicadas, se aparecerem após merges
    df = limpar_nomes_colunas(df, "Base final")

    # evita duplicidade de nome causada por merges
    colunas_para_remover = [c for c in df.columns if c.endswith("_dup")]
    if colunas_para_remover:
        df.drop(columns=colunas_para_remover, inplace=True)
        log(f"  ⚠️ Removidas colunas auxiliares duplicadas: {colunas_para_remover}")

    # tenta organizar algumas colunas principais no começo
    colunas_prioridade = [
        "orderId",
        "orderItemId",
        "pedido_concluido",
        "qtd_registros_concluidos",
        "consultorNome",
        "consultorEmail",
        "dealerDelivery",
        "referenceCode",
        "clientType",
        "totalOrder",
        "comissao",
        "comissao_vendedor",
        "productId",
        "brand",
        "monthlyInstallment",
        "vehicleValue",
        "publicPrice",
        "monthlyKmValue",
        "deadline",
        "total_km",
        "chassis",
        "deliveryPlate",
        "Vendedor",
        "Origem da venda",
        "Loja da Entrega",
        "Status da Entrega"
    ]

    colunas_existentes = [c for c in colunas_prioridade if c in df.columns]
    colunas_restantes = [c for c in df.columns if c not in colunas_existentes]
    df = df[colunas_existentes + colunas_restantes]

    log(f"  ✅ Base final ajustada: {len(df)} linhas | {len(df.columns)} colunas")
    return df


def exportar(df):
    log("\n💾 Exportando arquivo final")
    df.to_excel(ARQ_SAIDA, index=False)
    log(f"  ✅ Arquivo gerado com sucesso: {ARQ_SAIDA}")


# ============================================================
# MAIN
# ============================================================
def main():
    linha()
    log("   CONSOLIDADOR BASE LM — CARRERA SIGNATURE")
    log(f"   {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    linha()

    try:
        # 1) Base principal por pedido
        df = etapa_1_base_principal()

        # 2) Enriquecimentos ainda em 1 linha por pedido
        df = etapa_2_concluidos(df)
        df = etapa_3_consultores(df)
        df = etapa_4_dn(df)

        # 3) Expansão intencional para 1 linha por carro
        df = etapa_5_carros_e_ofertas(df)

        # 4) Enriquecimento externo
        df = etapa_6_salesforce(df)

        # 5) Ajustes finais
        df = etapa_7_ajustes_finais(df)

        # 6) Exportação
        exportar(df)

        linha()
        log("✅ Processo finalizado com sucesso")
        log(f"📦 Total de linhas finais: {len(df)}")
        log(f"🧾 Total de colunas finais: {len(df.columns)}")
        linha()

    except Exception as e:
        log("\n❌ Erro inesperado:")
        log(str(e))
        log("\nTraceback completo:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()