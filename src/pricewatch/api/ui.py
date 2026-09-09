UI_HTML = """<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>Price</title>
<link rel="stylesheet" href="/static/ui.css">
</head>
<body>
<h1>Price — monitor de preços</h1>

<form id="configForm">
  <div id="config">
    <label>URL da API: <input id="apiBase" value=""></label>
    <label>X-API-Key: <input id="apiKey" type="password" value="" autocomplete="off"></label>
    <button type="submit">Salvar</button>
    <span id="configStatus" class="muted"></span>
  </div>
</form>

<h2>Novo produto</h2>
<form id="newProductForm">
  <input id="newUrl" placeholder="https://loja.exemplo/produto" size="40" required>
  <input id="newInterval" type="number" placeholder="intervalo (s)" min="1">
  <button type="submit">Cadastrar</button>
</form>
<p id="createError" class="error"></p>

<h2>Produtos</h2>
<button id="reloadProducts" type="button">Recarregar</button>
<table id="productsTable">
  <thead>
    <tr>
      <th>URL</th><th>Status</th><th>Último preço</th><th>Próxima verificação</th>
      <th>Falhas seguidas</th><th>Ações</th>
    </tr>
  </thead>
  <tbody></tbody>
</table>

<div id="detail"></div>

<h2>Alertas recentes</h2>
<button id="reloadAlerts" type="button">Recarregar</button>
<table id="alertsTable">
  <thead><tr><th>Produto</th><th>Regra</th><th>Preço anterior</th><th>Preço atual</th><th>Quando</th><th>Entrega</th></tr></thead>
  <tbody></tbody>
</table>

<script src="/static/ui.js"></script>
</body>
</html>
"""
