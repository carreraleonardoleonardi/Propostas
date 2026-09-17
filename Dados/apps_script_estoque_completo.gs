function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName(data.aba) || ss.getSheets()[0];
    
    if (data.acao === "inserir") {
      sheet.appendRow(data.linha);
    } else if (data.acao === "atualizar") {
      var col = data.coluna;
      var row = data.linha_num;
      sheet.getRange(row, col).setValue(data.valor);
    } else if (data.acao === "atualizar_linha") {
      var row = data.linha_num;
      data.valores.forEach(function(item) {
        sheet.getRange(row, item.col).setValue(item.valor);
      });
    } else if (data.acao === "deletar_linha") {
      sheet.deleteRow(data.linha_num);
    } else if (data.acao === "solicitar_atribuicao") {
      processarSolicitacaoAtribuicao(data);
    }
    
    return ContentService
      .createTextOutput(JSON.stringify({status: "ok"}))
      .setMimeType(ContentService.MimeType.JSON);
  } catch(err) {
    return ContentService
      .createTextOutput(JSON.stringify({status: "erro", msg: err.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  }
  
}

function doGet(e) {
  return ContentService
    .createTextOutput(JSON.stringify({status: "online"}))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * Registra a solicitação na aba "solicitacoes" e envia o e-mail pra LM.
 * data.dados = {
 *   id, data_solicitacao, pedido, cliente, vendedor, chassi, modelo, cor,
 *   placa, locadora, solicitado_por, destinatarios (array), assunto, corpo
 * }
 */
function processarSolicitacaoAtribuicao(data) {
  var d = data.dados;
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
