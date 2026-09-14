/**
 * Apps Script — Web App genérico para a planilha de Metas.
 * Segue o mesmo contrato já usado nos outros módulos do sistema
 * (gv_enviar / cu_enviar / enviar_auth): POST com JSON no body.
 *
 * Ações suportadas:
 *   { "aba": "metas", "acao": "inserir", "linha": [ ... valores na ordem das colunas ... ] }
 *   { "aba": "metas", "acao": "atualizar_linha", "linha_num": N,
 *     "valores": [ {"col": 1, "valor": "..."}, {"col": 5, "valor": "..."} ] }
 *   { "aba": "metas", "acao": "deletar_linha", "linha_num": N }
 *
 * "linha_num" é 1-based contando a linha 1 como cabeçalho (ou seja, a
 * primeira linha de dados é linha_num = 2).
 * "col" em "valores" é 1-based (coluna A = 1, B = 2, ...).
 */
function doPost(e) {
  var payload = JSON.parse(e.postData.contents);
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(payload.aba);

  if (!sheet) {
    return ContentService.createTextOutput(
      JSON.stringify({ ok: false, erro: "Aba não encontrada: " + payload.aba })
    ).setMimeType(ContentService.MimeType.JSON);
  }

  try {
    if (payload.acao === "inserir") {
      sheet.appendRow(payload.linha);

    } else if (payload.acao === "atualizar_linha") {
      var linhaNum = payload.linha_num;
      payload.valores.forEach(function (v) {
        sheet.getRange(linhaNum, v.col).setValue(v.valor);
      });

    } else if (payload.acao === "deletar_linha") {
      sheet.deleteRow(payload.linha_num);

    } else {
      return ContentService.createTextOutput(
        JSON.stringify({ ok: false, erro: "Ação desconhecida: " + payload.acao })
      ).setMimeType(ContentService.MimeType.JSON);
    }

    return ContentService.createTextOutput(
      JSON.stringify({ ok: true })
    ).setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(
      JSON.stringify({ ok: false, erro: err.toString() })
    ).setMimeType(ContentService.MimeType.JSON);
  }
}
