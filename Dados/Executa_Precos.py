import requests
import pandas as pd
import time
import os


# ── Caminho padrão para pasta Dados\ ─────────────────────────────────────────
import os as _os
_DADOS_DIR = os.path.dirname(os.path.abspath(__file__))

def _dados_path(nome):
    """Retorna caminho completo dentro de Dados/"""
    return os.path.join(_DADOS_DIR, nome)
# ─────────────────────────────────────────────────────────────────────────────

# 🔑 URL e Token
url = "https://backend.vwsignanddrive.com.br/api/offers"
token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6Imxlb25hcmRvLmxlb25hcmRpQGNhcnJlcmEuY29tLmJyIiwidW5pcXVlX25hbWUiOiIwMDE3MDBCQzAwRkQwMERDMDBBMjAwOUYwMDQ4MDBDMjAwRkQwMDA4MDBFMjAwNjMwMENFMDBGRjAwQkUwMENEMDBFMzAwRUYwMDNCMDBFMjAwQ0YwMDg1MDA2QTAwMjcwMDY1MDBERDAwQzIwMENFMDAyQTAwQTUwMDM2MDBCNzAwNzgwMDczMDBEMzAwNkUwMDQxMDBDRjAwMkYwMDJCMDAyOTAwMzcwMEI3MDBCNjAwMUQwMDZDMDAxNjAwODkwMDlDMDA0NDAwNjgwMDE0MDA5QTAwM0YwMDQ2MDAwRjAwMTQwMDRCMDAzQjAwNzcwMDM0MDBDMzAwQjkwMDFEIiwiaXNzIjoiblR0SVlnazN3YzFlSnpRMzJWV05Pck11RXdNZkkyZ1QiLCJkaWQiOiIyMSIsIm9sdCI6Ik5URTNORFE9IiwiY2FucmVuZXciOiJGYWxzZSIsInZlbmRlZG9ybWFzdGVyIjoiVHJ1ZSIsImRwbCI6IiIsInByYyI6IiIsImtpY2siOiJDYW5hbCBJbmRpcmV0byAyLDUwJSAoUG9ydGFsKXxDYW5hbCBJbmRpcmV0byAzLDUlIChQb3J0YWwpfENhbmFsIEluZGlyZXRvIDElIEROfE11bHRpYnJhbmQgUEpcdTAwQTA1JSBORnxNdWx0aWJyYW5kIFBGIDUlIE5GfE11bHRpYnJhbmQgUEogNSUgTkZ8QXNzaW5lY2FyIEdXTSBFc3BlY2lhbCBQSnxBc3NpbmVjYXIgR1dNIEVzcGVjaWFsIFBGfE11bHRpYnJhbmQgUEYgMyw1JSBORnxNdWx0aWJyYW5kIFBKIDMsNSUgTkZ8R0FDIEdvIGFuZCBEcml2ZSAtIFBGfEdBQyBHbyBhbmQgRHJpdmUgLSBQSnxJRCAtIEJVWlogLSBQb3J0YWwgZSBQSnxJRC40IC0gMywwJSBWZW5kYSAtIDEsMCUgRW50cmVnYXxJRC40IC0gMywwJSBWZW5kYSAtIDEsMCUgRW50cmVnYSAtIFBKfElEIC0gNCAtIFBvcnRhbCBlIFBKfFMmRCAtIDMsNTAlfFMmRHxBc3NpbmUywrpDaWNsbyAtIDUlIEJhY2tsb2d8QXNzaW5lQ2FyIE1CIDAlfEFzc2luZWNhciBHV00gUEZ8QXNzaW5lY2FyIEdXTSBQSnxBc3NpbmVjYXIgR1dNIEVzcGVjaWFsIFBKfEFzc2luZWNhciBHV00gRXNwZWNpYWwgUEZ8QXNzaW5lY2FyIFBGIDYlIEJhY2tsb2d8QXNzaW5lY2FyIFBKIDYlIEJhY2tsb2d8RmFpeGEgMiAtIEFzc2luZWNhciBQRnxGYWl4YSAyIC0gQXNzaW5lY2FyIFBKfFZvbHZvIC0gUEZ8Vm9sdm8gLSBQSiIsInZsIjoiMjAyNi0wMy0yOCAxMTozNToyOSIsImV4cCI6MTc3NDcwMDEyOX0.VdqJecIGLCGMStjCL6p1CcdKxnGcXcPZG4fIWp_7QWc"
# 🔐 Substituir pelo token válido # <-- Coloque seu token válido

headers = {
    "Authorization": f"{token}",
    "Content-Type": "application/json",
    "accept": "application/json, text/plain, */*",
    "origin": "https://portaldealer.lmmobilidade.com.br/offers/pf/9",
}

quantityPerPage = 100  # Máximo permitido


# Função para buscar ofertas por salesChannel
def consulta_ofertas_por_channel(channel):
    page_select = 1
    has_next_page = True
    ofertas = []
    
    while has_next_page:
        params = {
            "page": page_select,
            "quantityPerPage": quantityPerPage
        }
        
        if channel is not None:
            params["salesChannel"] = channel
            
        try:
            response = requests.get(url, headers=headers, params=params, timeout=120)
            response.raise_for_status()
            resultado = response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Erro na página {page_select} do canal {channel}: {e}")
            break
            
        if isinstance(resultado, dict):
            itens = resultado.get("itens", [])
            has_next_page = resultado.get("hasNextPage", False)
        elif isinstance(resultado, list):
            itens = resultado
            has_next_page = False
        else:
            print(f"⚠️ Estrutura inesperada no canal {channel}")
            break
            
        ofertas.extend(itens)
        page_select += 1
        time.sleep(0.5)
        
    return ofertas


# Função para buscar especificamente por idSegment = 9 (Sign and Drive)
def consulta_sign_and_drive():
    page_select = 1
    has_next_page = True
    ofertas = []
    
    while has_next_page:
        params = {
            "page": page_select,
            "quantityPerPage": quantityPerPage,
            "idSegment": 9
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=60)
            response.raise_for_status()
            resultado = response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Erro na página {page_select} do Sign and Drive: {e}")
            break
            
        if isinstance(resultado, dict):
            itens = resultado.get("itens", [])
            has_next_page = resultado.get("hasNextPage", False)
        elif isinstance(resultado, list):
            itens = resultado
            has_next_page = False
        else:
            print(f"⚠️ Estrutura inesperada na consulta do Sign and Drive")
            break
            
        ofertas.extend(itens)
        page_select += 1
        time.sleep(0.5)
        
    return ofertas


# Passo 1 → Buscar todos os salesChannels existentes
print("🔍 Coletando lista de salesChannel disponíveis...")
todas_ofertas = consulta_ofertas_por_channel(None)
sales_channels = sorted(set(item.get("salesChannel", "Sem Canal") for item in todas_ofertas))
print(f"📌 SalesChannels encontrados: {sales_channels}")

# Extra: verificar se existe alguma oferta com idSegment = 9
sign_drive_test = [o for o in todas_ofertas if o.get("idSegment") == 9]
print(f"🔎 Ofertas encontradas com idSegment=9 na busca geral: {len(sign_drive_test)}")


# Passo 2 → Extrair cada salesChannel separadamente
df_total = pd.DataFrame()

for channel in sales_channels:
    print(f"\n📥 Extraindo ofertas do canal: {channel}")
    ofertas_channel = consulta_ofertas_por_channel(channel if channel != "Sem Canal" else None)
    
    if ofertas_channel:
        df = pd.json_normalize(ofertas_channel)
        df["salesChannel"] = channel
        df_total = pd.concat([df_total, df], ignore_index=True)
        df.to_excel(_dados_path(f"Ofertas_{str(channel).replace(' ', '_')}.xlsx"), index=False)
        print(f"✅ Arquivo salvo: Ofertas_{str(channel).replace(' ', '_')}.xlsx")
    else:
        print(f"⚠️ Nenhuma oferta encontrada para {channel}")


# Passo 3 → Tentar extrair Sign and Drive direto por idSegment=9
print("\n📥 Tentando extração direta do Sign and Drive (idSegment=9)")
ofertas_sd = consulta_sign_and_drive()

if ofertas_sd:
    df_sd = pd.json_normalize(ofertas_sd)
    df_sd["salesChannel"] = "Sign and Drive"
    df_total = pd.concat([df_total, df_sd], ignore_index=True)
    df_sd.to_excel(_dados_path("Ofertas_Sign_and_Drive.xlsx"), index=False)
    print("✅ Arquivo salvo: Ofertas_Sign_and_Drive.xlsx")
else:
    print("⚠️ Nenhuma oferta encontrada para Sign and Drive via idSegment")


# Passo 4 → Salvar consolidado
if not df_total.empty:
    df_total.to_excel(_dados_path("Ofertas_Todos_SalesChannels.xlsx"), index=False)
    print("\n📄 Arquivo consolidado salvo: Ofertas_Todos_SalesChannels.xlsx")
else:
    print("\n🚫 Nenhum dado encontrado em nenhum canal.")