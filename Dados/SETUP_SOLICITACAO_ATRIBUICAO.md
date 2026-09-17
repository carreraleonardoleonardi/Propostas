# Setup — Solicitação de Atribuição (LM Frotas)

Essa funcionalidade tem 2 partes que dependem de configuração sua:
1. Uma aba nova na planilha do estoque, pra guardar o histórico de solicitações.
2. Um trecho de código novo no Apps Script que **já existe** e atende o
   `GV_WEBHOOK` — não precisa criar um script novo, só adicionar uma ação nele.

## 1. Criar a aba "solicitacoes"

1. Na MESMA planilha onde já está a aba `veiculos` e `historico`, crie uma
   aba nova chamada `solicitacoes` (tudo minúsculo).
2. Cole este cabeçalho exato na linha 1:

```
id	data_solicitacao	pedido	cliente	vendedor	chassi	modelo	cor	placa	locadora	solicitado_por	email_enviado	data_envio_email
```

3. Abra essa aba e pegue o `gid` na URL do navegador (termina em
   `...#gid=123456789`).
4. A URL de leitura (CSV) fica assim, trocando pelo ID real da planilha
   (mesmo ID que já está em `GV_SHEET_URL`) e pelo gid do passo 3:

```
https://docs.google.com/spreadsheets/d/SEU_ID_DA_PLANILHA/export?format=csv&gid=SEU_GID
```

5. Cole essa URL em `pages/gestao_veiculos.py`, na constante:
```python
SOLIC_SHEET_URL = "..."
```

## 2. Adicionar a ação "solicitar_atribuicao" no Apps Script existente

Abra o Apps Script que já atende o `GV_WEBHOOK` (Extensões → Apps Script,
na planilha do estoque). Ele já deve ter uma função `doPost(e)` com um
`if/else if` tratando `payload.acao` (`"inserir"`, `"atualizar_linha"`,
`"deletar_linha"`, etc.).

**Adicione um novo `else if`** nessa cadeia, chamando uma função nova:

```javascript
} else if (payload.acao === "solicitar_atribuicao") {
  processarSolicitacaoAtribuicao(payload);

}
```

**E adicione esta função nova** em qualquer lugar do script (fora do `doPost`):

```javascript
/**
 * Registra a solicitação na aba "solicitacoes" e envia o e-mail pra LM.
 * payload.dados = {
 *   id, data_solicitacao, pedido, cliente, vendedor, chassi, modelo, cor,
 *   placa, locadora, solicitado_por, destinatarios (array), assunto, corpo
 * }
 */
function processarSolicitacaoAtribuicao(payload) {
  var d = payload.dados;
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("solicitacoes");

  // 1) Grava a linha já como "Não enviado" (garante registro mesmo se o
  //    envio de e-mail falhar por algum motivo)
  var linha = [
    d.id, d.data_solicitacao, d.pedido, d.cliente, d.vendedor,
    d.chassi, d.modelo, d.cor, d.placa, d.locadora,
    d.solicitado_por, "Não", "",
  ];
  sheet.appendRow(linha);
  var linhaNum = sheet.getLastRow();

  // 2) Tenta enviar o e-mail
  try {
    MailApp.sendEmail({
      to: d.destinatarios.join(","),
      subject: d.assunto,
      body: d.corpo,
    });

    // 3) Marca como enviado
    var agora = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "dd/MM/yyyy HH:mm");
    sheet.getRange(linhaNum, 12).setValue("Sim");   // coluna "email_enviado"
    sheet.getRange(linhaNum, 13).setValue(agora);   // coluna "data_envio_email"

  } catch (err) {
    // Se o envio falhar, a linha já está gravada como "Não" — dá pra
    // reenviar manualmente depois, sem perder o registro da solicitação.
    sheet.getRange(linhaNum, 12).setValue("Erro: " + err.toString());
  }
}
```

Depois de colar, clique em **Implantar → Gerenciar implantações → editar
(ícone de lápis) → Nova versão → Implantar**. Isso é necessário sempre que
o código do script muda — só salvar não atualiza a versão publicada que o
`GV_WEBHOOK` está usando.

## 3. Preencher o "DN" no template do e-mail

No corpo do e-mail enviado, o campo **"DN (nome e nº da concessionária)"**
usa a constante `DN_CARRERA` em `pages/gestao_veiculos.py`. Troque:

```python
DN_CARRERA = "PREENCHER: nome e nº da concessionária Carrera"
```

pelo valor real (ex.: `"Carrera Signature — DN 1234"`).

## Pronto

Depois desses 3 passos, a aba **Atribuição** (só aparece pra veículos da
locadora **LM FROTAS**) já vai: atualizar Pedido/Cliente/Vendedor do
veículo, registrar a solicitação na aba `solicitacoes`, disparar o e-mail
pra `thalita.gardim@lm-mobilidade.com` e `flavia.andrade@lm-mobilidade.com`,
e tudo isso aparece listado na aba **Solicitações** (com o status do
e-mail: enviado ou não).
