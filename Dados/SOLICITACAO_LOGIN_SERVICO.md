# Solicitação: login de serviço para o Dashboard de Performance

**Para:** administrador do Azure SQL Server `sql-agil.database.windows.net`
**De:** equipe Carrera Signature — Dashboard de Performance (Streamlit)

## Contexto

O dashboard de Performance precisa se conectar ao banco `SQL-AGIL` de forma
automática (sem tela, sem MFA, sem depender do login pessoal de ninguém),
já que várias pessoas vão abrir o relatório. Autenticação Azure AD pessoal
(a que uso hoje) não serve pra isso — exige MFA interativo a cada execução.

## O que precisamos

Um **login SQL Server tradicional** (não Azure AD), somente leitura,
com acesso apenas às tabelas usadas pelo relatório:

```sql
-- Executar conectado como admin no banco SQL-AGIL

CREATE LOGIN carrera_dashboard_reader WITH PASSWORD = 'DEFINA_UMA_SENHA_FORTE_AQUI';

CREATE USER carrera_dashboard_reader FOR LOGIN carrera_dashboard_reader;

GRANT SELECT ON dbo.tbConsolidaSalesforce   TO carrera_dashboard_reader;
GRANT SELECT ON mkt.ConsolidadoCampanhas    TO carrera_dashboard_reader;
GRANT SELECT ON dbo.tbColaboradores         TO carrera_dashboard_reader;
```

Se preferir dar acesso de leitura ao banco inteiro em vez de tabela por
tabela, a alternativa mais simples é:

```sql
ALTER ROLE db_datareader ADD MEMBER carrera_dashboard_reader;
```

## Por que isso resolve

- Não depende de MFA nem de sessão interativa — o login e senha ficam
  guardados só no `secrets.toml` do servidor onde o app roda.
- Qualquer pessoa que abrir o dashboard usa essa mesma credencial de
  serviço, sem precisar da própria conta Azure AD.
- Acesso restrito a **somente leitura** nas tabelas necessárias — não
  consegue alterar nada no banco.

## Depois de criado

Só precisamos que nos repassem (de forma segura, não por chat/e-mail
aberto): o **nome do login** (`carrera_dashboard_reader` ou o nome que
preferirem) e a **senha**. O restante da configuração já está pronto no
app, é só trocar as credenciais no `secrets.toml`.
