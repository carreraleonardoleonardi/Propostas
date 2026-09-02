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

SERVIDOR = os.environ.get("AZURE_SQL_SERVER",   "")
BANCO    = os.environ.get("AZURE_SQL_DATABASE", "")
USUARIO  = os.environ.get("AZURE_SQL_USER",     "r")
SENHA    = os.environ.get("AZURE_SQL_PASSWORD", "")
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


def etapa_3_pyodbc(modo_auth="ActiveDirectoryPassword"):
    linha(f"ETAPA 3 — pyodbc com ODBC Driver 18 (Authentication={modo_auth or 'nenhuma'})")
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

    sem_senha = modo_auth in ("ActiveDirectoryInteractive", "ActiveDirectoryIntegrated",
                               "ActiveDirectoryDeviceCodeFlow", "ActiveDirectoryMsi")
    partes = [f"DRIVER={{{driver}}}", f"SERVER=tcp:{SERVIDOR},1433", f"DATABASE={BANCO}"]
    if modo_auth != "ActiveDirectoryIntegrated":
        partes.append(f"UID={USUARIO}")
    if not sem_senha:
        partes.append(f"PWD={SENHA}")
    partes += ["Encrypt=yes", "TrustServerCertificate=no", "Connection Timeout=15"]
    if modo_auth:
        partes.append(f"Authentication={modo_auth}")
    conn_str = ";".join(partes) + ";"

    if modo_auth == "ActiveDirectoryInteractive":
        print("  ⏳ Modo interativo — uma janela de login/MFA deve abrir agora...")

    try:
        conn = pyodbc.connect(conn_str, timeout=15)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        conn.close()
        print(f"  ✅ Conectou com sucesso via pyodbc usando driver '{driver}' "
              f"(Authentication={modo_auth or 'nenhuma'})!")
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

    eh_azure_ad = "@" in USUARIO and not USUARIO.lower().endswith(f"@{SERVIDOR.split('.')[0].lower()}")

    pymssql_ok = etapa_2_pymssql()
    if pymssql_ok:
        print("\n🎉 pymssql funciona neste ambiente — use-o normalmente no app.")
        sys.exit(0)

    if not eh_azure_ad:
        print("\n⚠️ pymssql falhou mesmo com a rede OK — provável problema de TLS/FreeTDS.")
        pyodbc_ok = etapa_3_pyodbc(modo_auth=None)
    else:
        print("\n⚠️ Tentando via pyodbc com Authentication=ActiveDirectoryPassword...")
        pyodbc_ok = etapa_3_pyodbc(modo_auth="ActiveDirectoryPassword")
        if not pyodbc_ok:
            print("\n⚠️ ActiveDirectoryPassword falhou — se sua conta exige MFA, isso é esperado.")
            print("   Tentando modo interativo (uma janela de login/MFA vai abrir)...")
            pyodbc_ok = etapa_3_pyodbc(modo_auth="ActiveDirectoryInteractive")

    linha("RESUMO")
    if pyodbc_ok:
        print("  ✅ pyodbc funcionou.")
        print('     No secrets.toml, confirme: driver = "ODBC Driver 18 for SQL Server"')
        if eh_azure_ad:
            print('     E, se foi o modo interativo que funcionou, adicione:')
            print('     authentication = "ActiveDirectoryInteractive"')
    else:
        print("  ❌ Nenhum driver/modo conectou. Causas prováveis restantes:")
        print("     • Senha com caractere especial mal escapado")
        print("     • Conta Azure AD sem acesso ao banco (nem CREATE USER foi feito)")
        print("     • VPN/proxy corporativo interceptando TLS na porta 1433")

