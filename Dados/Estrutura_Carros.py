# -*- coding: utf-8 -*-
import requests
import pandas as pd
import time as tm
import json
from plyer import notification 
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os

# ── Caminho padrão para pasta Dados\ ─────────────────────────────────────────
import os as _os
_DADOS_DIR = os.path.dirname(os.path.abspath(__file__))

def _dados_path(nome):
    """Retorna caminho completo dentro de Dados/"""
    return os.path.join(_DADOS_DIR, nome)
# ─────────────────────────────────────────────────────────────────────────────

# 1. CONFIGURAÇÃO DE CONEXÃO (Evita erros de SSL e EOF)
def criar_sessao_segura(token):
    sessao = requests.Session()
    # Tenta novamente 3 vezes se o servidor oscilar
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    sessao.mount("https://", adapter)
    
    # Headers oficiais para simular navegador e enviar o Token
    sessao.headers.update({
        "authorization": f"Bearer {token}",
        "accept": "application/json, text/plain, */*",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    return sessao

# ---------------------------------------------------------
# CONFIGURAÇÕES INICIAIS (Ajuste aqui)
# ---------------------------------------------------------
TOKEN_ATUAL = "COLE_AQUI_SEU_TOKEN_BEARER_COMPLETO" 
ARQUIVO_EXCEL = _dados_path("Lista_LM.xlsx")
ABA_DADOS = "Dados"

http = criar_sessao_segura(TOKEN_ATUAL)

# 2. FUNÇÕES DE BUSCA COM FEEDBACK NO TERMINAL
def vListaCarros(vID): 
    url = "https://backend.vwsignanddrive.com.br/api/orderitems"
    try:
        response = http.get(url, params={"orderId": vID}, timeout=20)
        if response.status_code == 200:
            dados = response.json()
            print(f"   ∟ 🚗 Carros: OK ({len(dados)} itens encontrados)")
            return pd.DataFrame(dados)
        else:
            print(f"   ∟ 🚗 Carros: ERRO {response.status_code}")
            return pd.DataFrame()
    except Exception as e:
        print(f"   ∟ 🚗 Carros: FALHA (Verifique conexão/SSL)")
        return pd.DataFrame()

def vListaConsultor(vID):
    url = f"https://backend.vwsignanddrive.com.br/api/orders/{vID}"
    try:
        response = http.get(url, timeout=20)
        if response.status_code == 200:
            print(f"   ∟ 👤 Consultor: OK")
            return pd.DataFrame(response.json(), index=[0])
        else:
            print(f"   ∟ 👤 Consultor: ERRO {response.status_code}")
            return pd.DataFrame()
    except Exception as e:
        print(f"   ∟ 👤 Consultor: FALHA (Verifique conexão/SSL)")
        return pd.DataFrame()

# 3. FLUXO PRINCIPAL
try:
    print("="*60)
    print("        INICIANDO EXTRAÇÃO - CARRERA SIGNATURE")
    print("="*60)
    
    # Lendo a planilha de entrada
    tbPedido = pd.read_excel(ARQUIVO_EXCEL, sheet_name=ABA_DADOS)
    total_pedidos = len(tbPedido)
    
    vLista_Carros = []
    vLista_Consultores = []

    for idx, pedido in enumerate(tbPedido["orderId"], start=1):
        percentual = (idx / total_pedidos) * 100
        print(f"\n[{idx}/{total_pedidos}] {percentual:.1f}% | Processando Pedido: {pedido}")
        
        # Chamadas das APIs
        df_c = vListaCarros(pedido)
        if not df_c.empty:
            df_c["orderId_ref"] = pedido # Coluna de amarração
            vLista_Carros.append(df_c)

        df_cons = vListaConsultor(pedido)
        if not df_cons.empty:
            df_cons["orderId_ref"] = pedido # Coluna de amarração
            vLista_Consultores.append(df_cons)

        # Pausa curta para não sobrecarregar a API
        tm.sleep(0.4)

    # 4. CONSOLIDAÇÃO E EXPORTAÇÃO
    print("\n" + "="*60)
    print("🏁 FINALIZANDO: Gerando arquivos Excel...")
    
    if vLista_Carros:
        final_carros = pd.concat(vLista_Carros, ignore_index=True)
        final_carros.to_excel(_dados_path("vListaCarrosDetalhes.xlsx"), index=False)
        print(f"✅ Arquivo Carros gerado: {len(final_carros)} linhas.")
    
    if vLista_Consultores:
        final_cons = pd.concat(vLista_Consultores, ignore_index=True)
        final_cons.to_excel(_dados_path("vListaConsultoresDetalhes.xlsx"), index=False)
        print(f"✅ Arquivo Consultores gerado: {len(final_cons)} linhas.")

    print("="*60)
    notification.notify(title="Processo Concluído", message="Arquivos salvos com sucesso!", timeout=5)

except Exception as err:
    print(f"\n❌ ERRO GERAL NO SCRIPT: {err}")