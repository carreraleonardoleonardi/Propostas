# -*- coding: utf-8 -*-
"""
Extrator de usuários LM com paginação forçada
"""

import math
import requests
import pandas as pd
import os


# ── Caminho padrão para pasta Dados\ ─────────────────────────────────────────
import os as _os
_DADOS_DIR = os.path.dirname(os.path.abspath(__file__))

def _dados_path(nome):
    """Retorna caminho completo dentro de Dados/"""
    return os.path.join(_DADOS_DIR, nome)
# ─────────────────────────────────────────────────────────────────────────────

url = "https://backend.vwsignanddrive.com.br/api/users/dealership-all-users-filter"

# COLE AQUI SOMENTE O TOKEN, SEM "Bearer "
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6Imxlb25hcmRvLmxlb25hcmRpQGNhcnJlcmEuY29tLmJyIiwidW5pcXVlX25hbWUiOiIwMDE3MDBCQzAwRkQwMERDMDBBMjAwOUYwMDQ4MDBDMjAwRkQwMDA4MDBFMjAwNjMwMENFMDBGRjAwQkUwMENEMDBFMzAwRUYwMDNCMDBFMjAwQ0YwMDg1MDA2QTAwMjcwMDY1MDBERDAwQzIwMENFMDAyQTAwQTUwMDM2MDBCNzAwNzgwMDczMDBEMzAwNkUwMDQxMDBDRjAwMkYwMDJCMDAyOTAwMzcwMEI3MDBCNjAwMUQwMDZDMDAxNjAwODkwMDlDMDA0NDAwNjgwMDE0MDA5QTAwM0YwMDQ2MDAwRjAwMTQwMDRCMDAzQjAwNzcwMDM0MDBDMzAwQjkwMDFEIiwiaXNzIjoiblR0SVlnazN3YzFlSnpRMzJWV05Pck11RXdNZkkyZ1QiLCJkaWQiOiIyMSIsIm9sdCI6Ik5URTNORFE9IiwiY2FucmVuZXciOiJGYWxzZSIsInZlbmRlZG9ybWFzdGVyIjoiVHJ1ZSIsImRwbCI6IiIsInByYyI6IiIsImtpY2siOiJTJkQgLSAzLDUwJXxTJkR8Q2FuYWwgSW5kaXJldG8gMiw1MCUgKFBvcnRhbCl8Q2FuYWwgSW5kaXJldG8gMyw1JSAoUG9ydGFsKXxDYW5hbCBJbmRpcmV0byAxJSBETnxBc3NpbmVDYXIgTUIgMCV8SUQgLSBCVVpaIC0gUG9ydGFsIGUgUEp8SUQuNCAtIDMsMCUgVmVuZGEgLSAxLDAlIEVudHJlZ2F8SUQuNCAtIDMsMCUgVmVuZGEgLSAxLDAlIEVudHJlZ2EgLSBQSnxJRCAtIDQgLSBQb3J0YWwgZSBQSnxNdWx0aWJyYW5kIFBGIDMsNSUgTkZ8TXVsdGlicmFuZCBQSiAzLDUlIE5GfE11bHRpYnJhbmQgUEpcdTAwQTA1JSBORnxNdWx0aWJyYW5kIFBGIDUlIE5GfE11bHRpYnJhbmQgUEogNSUgTkZ8QXNzaW5lY2FyIFBGIDYlIEJhY2tsb2d8QXNzaW5lY2FyIFBKIDYlIEJhY2tsb2d8RmFpeGEgMiAtIEFzc2luZWNhciBQRnxGYWl4YSAyIC0gQXNzaW5lY2FyIFBKfEFzc2luZWNhciBHV00gRXNwZWNpYWwgUEp8QXNzaW5lY2FyIEdXTSBFc3BlY2lhbCBQRnxBc3NpbmVjYXIgR1dNIFBGfEFzc2luZWNhciBHV00gUEp8QXNzaW5lY2FyIEdXTSBFc3BlY2lhbCBQSnxBc3NpbmVjYXIgR1dNIEVzcGVjaWFsIFBGfEFzc2luZTLCukNpY2xvIC0gNSUgQmFja2xvZ3xHQUMgR28gYW5kIERyaXZlIC0gUEZ8R0FDIEdvIGFuZCBEcml2ZSAtIFBKfFZvbHZvIC0gUEZ8Vm9sdm8gLSBQSiIsInZsIjoiMjAyNi0wNC0xOCAxNjo1OToxMSIsImV4cCI6MTc3NjUzMzk1MX0.P5FQW_v7J9RGZFGe3-ALbRZYELNnRkqoqfx8-Slw3WQ"

headers = {
    "accept": "application/json, text/plain, */*",
    "authorization": f"Bearer {token}",
    "origin": "https://portaldealer.fleetbrasil.com.br",
    "user-agent": "Mozilla/5.0"
}

quantidade_por_pagina = 50
todos_dados = []

try:
    # primeira página
    params = {
        "page": "true",
        "currentPage": 1,
        "quantityPerPage": quantidade_por_pagina,
        "dealershipGroupId": 234
    }

    response = requests.get(url, headers=headers, params=params, timeout=60)
    print(f"Status da página 1: {response.status_code}")

    if response.status_code != 200:
        print(response.text)
        raise Exception("Erro ao consultar a página 1")

    js = response.json()
    registros = js.get("itens", [])
    total_amount = js.get("totalAmount", 0)

    todos_dados.extend(registros)

    print(f"Total informado pela API: {total_amount}")
    print(f"Registros na página 1: {len(registros)}")

    # calcula total de páginas com base no totalAmount
    total_paginas = math.ceil(total_amount / quantidade_por_pagina) if total_amount else 1
    print(f"Total de páginas esperado: {total_paginas}")

    # páginas seguintes
    for pagina in range(2, total_paginas + 1):
        print(f"Buscando página {pagina}...")

        params = {
            "page": "true",
            "currentPage": pagina,
            "quantityPerPage": quantidade_por_pagina,
            "dealershipGroupId": 234
        }

        response = requests.get(url, headers=headers, params=params, timeout=60)

        if response.status_code != 200:
            print(f"Erro na página {pagina}: {response.status_code}")
            print(response.text)
            continue

        js = response.json()
        registros = js.get("itens", [])

        print(f"Registros retornados na página {pagina}: {len(registros)}")

        if not registros:
            print(f"Página {pagina} veio vazia. Interrompendo.")
            break

        todos_dados.extend(registros)

    # remove duplicados por userId
    df = pd.json_normalize(todos_dados)
    if "userId" in df.columns:
        df = df.drop_duplicates(subset="userId")

    df = df.rename(columns={
        "dealership.id": "dealership_id",
        "dealership.name": "dealership_name",
        "dealership.number": "dealership_number",
        "dealership.dealershipGroupID": "dealership_group_id",
        "dealership.cnpj": "dealership_cnpj",
        "dealership.email": "dealership_email",
        "role.roleId": "role_id_detalhe",
        "role.role": "role_name",
        "role.fullName": "role_fullname"
    })

    arquivo_saida = "Lista_Usuarios_LM.xlsx"
    with pd.ExcelWriter(arquivo_saida, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="usuarios", index=False)

    print("✅ Arquivo gerado com sucesso")
    print(f"Total final de usuários: {len(df)}")
    print(f"Total de colunas: {len(df.columns)}")

except Exception as e:
    print(f"Erro geral: {e}")