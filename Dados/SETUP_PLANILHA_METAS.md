# Setup da planilha de Metas

## 1. Criar a planilha

1. Crie uma nova planilha no Google Sheets (arquivo novo, não uma aba dentro de
   uma planilha existente).
2. Renomeie a primeira aba para `metas` (tudo minúsculo, sem acento).
3. Na linha 1, cole exatamente estes cabeçalhos, um por coluna, nesta ordem:

```
ID	Ano	Tipo_Periodo	Periodo	Responsavel	Frente	Tipo_Meta	Programa	Valor	Criado_Por	Data_Criacao	Data_Atualizacao
```

Não precisa preencher mais nada — o app grava as linhas sozinho.

## 2. Publicar o Apps Script (Web App)

1. Na planilha, vá em **Extensões → Apps Script**.
2. Apague o conteúdo padrão e cole o código abaixo (arquivo
   `Dados/apps_script_metas.gs` nesta mesma pasta — é o mesmo conteúdo).
3. Clique em **Implantar → Nova implantação**.
4. Tipo: **App da Web**.
   - Executar como: **Eu** (sua conta)
   - Quem pode acessar: **Qualquer pessoa**
5. Clique em **Implantar**, autorize as permissões pedidas, e copie a **URL do
   app da Web** gerada (termina em `/exec`).

## 3. Pegar a URL de leitura (CSV) da aba "metas"

1. Com a aba `metas` selecionada, olhe a URL do navegador — ela termina em
   algo tipo `...#gid=123456789`. Anote esse número.
2. A URL de leitura (CSV) fica assim, trocando `SEU_ID_DA_PLANILHA` e
   `SEU_GID` pelos valores reais:

```
https://docs.google.com/spreadsheets/d/SEU_ID_DA_PLANILHA/export?format=csv&gid=SEU_GID
```

(O ID da planilha é o trecho entre `/d/` e `/edit` na URL normal do Sheets.)

## 4. Preencher no código

Abra `pages/metas.py` e troque as duas linhas no topo:

```python
METAS_SHEET_URL = "COLE_AQUI_A_URL_CSV_DA_ABA_METAS"
METAS_WEBHOOK   = "COLE_AQUI_A_URL_DO_APPS_SCRIPT_WEB_APP"
```

pela URL CSV (passo 3) e pela URL do Web App (passo 2), respectivamente.

Pronto — depois disso o módulo Metas fica 100% funcional (criar, editar,
excluir, listar).
