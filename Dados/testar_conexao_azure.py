"""
testar_conexao_azure.py — Carrera Signature

Diagnóstico isolado (sem Streamlit) da conexão com o Azure SQL Server.
Roda cada camada separadamente para identificar exatamente onde a
conexão está falhando: rede/porta, TLS/FreeTDS, ou login.

Uso:
    python Dados/testar_conexao_azure.py

Preencha SERVIDOR / BANCO / USUARIO / SENHA abaixo (ou exporte como
variáveis de ambiente AZURE_SQL_SERVER, AZURE_SQL_DATABASE,
AZURE_SQL_USER, AZURE_SQL_PASSWORD antes de rodar).
"""

import os
import socket
import sys

SERVIDOR = os.environ.get("AZURE_SQL_SERVER",   "sql-agil.database.windows.net")
BANCO    = os.environ.get("AZURE_SQL_DATABASE", "SEU_BANCO")
USUARIO  = os.environ.get("AZURE_SQL_USER",     "SEU_USUARIO")
SENHA    = os.environ.get("AZURE_SQL_PASSWORD", "SUA_SENHA")
PORTA    = 1433


def linha(txt=""):
    print("─" * 70) if not txt else print(f"\n▶ {txt}")


def etapa_1_dns_e_porta():
    linha("ETAPA 1 — Resolução DNS + porta 1433 (TCP puro, sem TLS)")
    try:
        ip = socket.gethostbyname(SERVIDOR)
        print(f"  ✅ DNS OK — {SERVIDOR} resolve para {ip}")
    except Exception as e:
        print(f"  ❌ Falha ao resolver DNS: {e}")
        print("     → Verifique se o nome do servidor está correto.")
        return False

    try:
        sock = socket.create_connection((SERVIDOR, PORTA), timeout=8)
        sock.close()
        print(f"  ✅ Porta {PORTA} aberta — TCP conectou normalmente.")
        return True
    except Exception as e:
        print(f"  ❌ Não foi possível abrir TCP na porta {PORTA}: {e}")
        print("     → Provável bloqueio de firewall LOCAL/rede corporativa/antivírus,")
        print("       não do Azure. Tente outra rede (ex.: hotspot do celular) para confirmar.")
        return False


def etapa_2_pymssql():
    linha("ETAPA 2 — pymssql.connect() direto (sem SQLAlchemy)")

    eh_azure_ad = "@" in USUARIO and not USUARIO.lower().endswith(f"@{SERVIDOR.split('.')[0].lower()}")
    if eh_azure_ad:
        print(f"  ⚠️  Usuário '{USUARIO}' parece ser conta Azure AD (e-mail corporativo).")
        print("     pymssql/FreeTDS NÃO suporta autenticação Azure AD (ActiveDirectoryPassword).")
        print("     Esta etapa vai falhar por design — pule direto para a Etapa 3 (pyodbc).")
        return False

    try:
        import pymssql
        print(f"  ℹ️  pymssql versão: {pymssql.__version__}")
    except ImportError:
        print("  ❌ pymssql não instalado. Rode: pip install pymssql --upgrade")
        return False

    usuario_fmt = USUARIO if "@" in USUARIO else f"{USUARIO}@{SERVIDOR.split('.')[0]}"

    for tds in ["7.4", "7.3", "8.0", None]:
        try:
            kwargs = dict(
                server=SERVIDOR, user=usuario_fmt, password=SENHA,
                database=BANCO, login_timeout=15, timeout=15,
            )
            if tds:
                kwargs["tds_version"] = tds
            print(f"  → Tentando com tds_version={tds!r} ...")
            conn = pymssql.connect(**kwargs)
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            conn.close()
            print(f"  ✅ Conectou com sucesso usando tds_version={tds!r}!")
            return True
        except Exception as e:
            print(f"     ❌ Falhou: {e}")

    print("  ⚠️ Nenhuma combinação de tds_version funcionou via pymssql.")
    return False


def etapa_3_pyodbc():
    linha("ETAPA 3 — pyodbc com ODBC Driver 18 (alternativa mais robusta / obrigatória p/ Azure AD)")
    try:
        import pyodbc
    except ImportError:
        print("  ℹ️ pyodbc não instalado. Para testar esta alternativa:")
        print("     pip install pyodbc")
        print("     E instale o 'ODBC Driver 18 for SQL Server' da Microsoft:")
        print("     https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server")
        return False

    drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
    print(f"  ℹ️ Drivers ODBC disponíveis: {drivers or 'nenhum encontrado'}")
    if not drivers:
        print("  ❌ Nenhum driver ODBC SQL Server instalado no sistema.")
        return False

    driver = next((d for d in drivers if "18" in d), drivers[0])

    eh_azure_ad = "@" in USUARIO and not USUARIO.lower().endswith(f"@{SERVIDOR.split('.')[0].lower()}")
    auth_clause = "Authentication=ActiveDirectoryPassword;" if eh_azure_ad else ""
    if eh_azure_ad:
        print(f"  ℹ️  Usuário Azure AD detectado — usando Authentication=ActiveDirectoryPassword")

    conn_str = (
        f"DRIVER={{{driver}}};SERVER=tcp:{SERVIDOR},1433;DATABASE={BANCO};"
        f"UID={USUARIO};PWD={SENHA};Encrypt=yes;TrustServerCertificate=no;"
        f"Connection Timeout=15;{auth_clause}"
    )
    try:
        conn = pyodbc.connect(conn_str, timeout=15)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        conn.close()
        print(f"  ✅ Conectou com sucesso via pyodbc usando driver '{driver}'"
              f"{' + Azure AD' if eh_azure_ad else ''}!")
        return True
    except Exception as e:
        print(f"  ❌ Falhou: {e}")
        return False


if __name__ == "__main__":
    print("═" * 70)
    print("  DIAGNÓSTICO DE CONEXÃO — AZURE SQL — Carrera Signature")
    print("═" * 70)
    print(f"  Servidor: {SERVIDOR}")
    print(f"  Banco:    {BANCO}")
    print(f"  Usuário:  {USUARIO}")

    rede_ok = etapa_1_dns_e_porta()
    if not rede_ok:
        print("\n🛑 Pare aqui: resolva o problema de rede/porta antes de prosseguir.")
        sys.exit(1)

    pymssql_ok = etapa_2_pymssql()
    if pymssql_ok:
        print("\n🎉 pymssql funciona neste ambiente — use-o normalmente no app.")
        sys.exit(0)

    print("\n⚠️ pymssql falhou mesmo com a rede OK — provável problema de TLS/FreeTDS.")
    pyodbc_ok = etapa_3_pyodbc()

    linha("RESUMO")
    if pyodbc_ok:
        print("  ✅ pyodbc funcionou — recomendo trocar o driver da app para pyodbc.")
        print("     No secrets.toml, adicione: driver = \"pyodbc\" na seção [azure_sql]")
    else:
        print("  ❌ Nenhum driver conectou. Causas prováveis restantes:")
        print("     • Senha com caractere especial mal escapado")
        print("     • Nome de usuário deveria ser 'usuario@nome-curto-do-servidor'")
        print("     • VPN/proxy corporativo interceptando TLS na porta 1433")
