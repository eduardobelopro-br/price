UI_HTML = """<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>Price</title>
<link rel="stylesheet" href="/static/ui.css">
</head>
<body>

<header class="nexo-header">
  <div class="nexo-header-brand">
    <strong>NEXO</strong>
    <span>Price — monitor de preços</span>
  </div>
  <div class="nexo-theme-switch" id="themeSwitch" role="group" aria-label="Tema">
    <button type="button" data-theme-choice="light" title="Claro">☀ Claro</button>
    <button type="button" data-theme-choice="dark" title="Escuro">🌙 Escuro</button>
    <button type="button" data-theme-choice="system" title="Sistema">⚙ Sistema</button>
  </div>
</header>

<main>

<section class="nexo-card-solid nexo-section">
  <form id="configForm">
    <div class="nexo-form-row">
      <div class="nexo-field">
        <label class="nexo-label" for="apiBase">URL da API</label>
        <input class="nexo-input" id="apiBase" value="">
      </div>
      <div class="nexo-field">
        <label class="nexo-label" for="apiKey">X-API-Key</label>
        <input class="nexo-input" id="apiKey" type="password" value="" autocomplete="off">
      </div>
      <button class="btn-primary" type="submit">Salvar</button>
      <span id="configStatus" class="muted"></span>
    </div>
  </form>
</section>

<section class="nexo-card-solid nexo-section">
  <div class="nexo-section-header"><h2>Novo produto</h2></div>
  <form id="newProductForm">
    <div class="nexo-form-row">
      <div class="nexo-field">
        <label class="nexo-label" for="newUrl">URL do produto</label>
        <input class="nexo-input" id="newUrl" placeholder="https://loja.exemplo/produto" required>
      </div>
      <div class="nexo-field-narrow">
        <label class="nexo-label" for="newInterval">Intervalo (s)</label>
        <input class="nexo-input" id="newInterval" type="number" min="1">
      </div>
      <button class="btn-primary" type="submit">Cadastrar</button>
    </div>
  </form>
  <p id="createError" class="nexo-alert nexo-alert-danger" hidden></p>
</section>

<section class="nexo-card-solid nexo-section">
  <div class="nexo-section-header">
    <h2>Produtos</h2>
    <button class="btn-outline" id="reloadProducts" type="button">Recarregar</button>
  </div>
  <div class="nexo-table-wrap">
    <table class="nexo-table" id="productsTable">
      <thead>
        <tr>
          <th>URL</th><th>Status</th><th>Último preço</th><th>Próxima verificação</th>
          <th>Falhas seguidas</th><th>Ações</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>
</section>

<div id="detail"></div>

<section class="nexo-card-solid nexo-section">
  <div class="nexo-section-header">
    <h2>Alertas recentes</h2>
    <button class="btn-outline" id="reloadAlerts" type="button">Recarregar</button>
  </div>
  <div class="nexo-table-wrap">
    <table class="nexo-table" id="alertsTable">
      <thead><tr><th>Produto</th><th>Regra</th><th>Preço anterior</th><th>Preço atual</th><th>Quando</th><th>Entrega</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>
</section>

</main>

<script src="/static/ui.js"></script>
</body>
</html>
"""
