# =========================================================
# utils.py
# Funções utilitárias reutilizadas em todo o projeto
# =========================================================

import datetime
import calendar
import pandas as pd


# =========================================================
# TEXTO
# =========================================================

def limpar_texto(txt) -> str:
    """
    Limpa texto para uso no PDF (compatibilidade latin-1).
    Usado pelo pdf_generator.py.
    """
    if pd.isna(txt):
        return ""
    return str(txt).encode("latin-1", "replace").decode("latin-1")


# =========================================================
# VALORES MONETÁRIOS
# =========================================================

def valor_para_float(valor) -> float | None:
    """
    Converte texto monetário em float.
    Ex.: 'R$ 2.139,00' -> 2139.0
    """
    try:
        valor_limpo = (
            str(valor)
            .replace("R$", "")
            .replace(".", "")
            .replace(",", ".")
            .strip()
        )
        return float(valor_limpo)
    except Exception:
        return None


def formatar_valor_brl(valor) -> str:
    """
    Formata um valor numérico ou string para exibição em reais.
    Ex.: 2139.0 -> 'R$ 2.139'
    """
    try:
        numero = valor_para_float(valor)
        if numero is None:
            return str(valor)
        inteiro = int(round(numero))
        return f"R$ {inteiro:,}".replace(",", ".")
    except Exception:
        return str(valor)


# =========================================================
# DATAS
# =========================================================

def data_validade_mes_atual() -> str:
    """
    Retorna o último dia do mês atual no formato DD/MM/AAAA.
    Usado nos cards de plano.
    """
    hoje = datetime.date.today()
    ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
    data_final = datetime.date(hoje.year, hoje.month, ultimo_dia)
    return data_final.strftime("%d/%m/%Y")
