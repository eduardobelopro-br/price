UI_HTML = """<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>Price</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }
  h1 { font-size: 1.4rem; }
  h2 { font-size: 1.1rem; margin-top: 2rem; }
  table { border-collapse: collapse; width: 100%; margin-top: 0.5rem; }
  th, td { border: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.9rem; }
  th { background: #f5f5f5; }
  tr.selected { background: #eef6ff; }
  .status-active { color: #147a2f; }
  .status-paused { color: #8a6d00; }
  .status-error, .status-unsupported { color: #b3261e; }
  .status-archived { color: #777; }
  button { cursor: pointer; }
  input, select { padding: 0.3rem; }
  form.inline { display: inline; }
  #config { background: #f5f5f5; padding: 0.75rem; border-radius: 6px; margin-bottom: 1rem; }
  #config input { width: 20rem; }
  .error { color: #b3261e; }
  .muted { color: #777; font-size: 0.85rem; }
</style>
</head>
<body>
<h1>Price — monitor de preços</h1>

<div id="config">
  <label>URL da API: <input id="apiBase" value=""></label>
  <label>X-API-Key: <input id="apiKey" type="password" value=""></label>
  <button onclick="saveConfig()">Salvar</button>
  <span id="configStatus" class="muted"></span>
</div>

<h2>Novo produto</h2>
<form onsubmit="createProduct(event)">
  <input id="newUrl" placeholder="https://loja.exemplo/produto" size="40" required>
  <input id="newInterval" type="number" placeholder="intervalo (s)" min="1">
  <button type="submit">Cadastrar</button>
</form>
<p id="createError" class="error"></p>

<h2>Produtos</h2>
<button onclick="loadProducts()">Recarregar</button>
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
<button onclick="loadAlerts()">Recarregar</button>
<table id="alertsTable">
  <thead><tr><th>Produto</th><th>Regra</th><th>Preço anterior</th><th>Preço atual</th><th>Quando</th><th>Entrega</th></tr></thead>
  <tbody></tbody>
</table>

<script>
function apiBase() { return document.getElementById('apiBase').value.replace(/\\/$/, ''); }
function apiKey() { return document.getElementById('apiKey').value; }

function saveConfig() {
  localStorage.setItem('price_api_base', apiBase());
  localStorage.setItem('price_api_key', apiKey());
  document.getElementById('configStatus').textContent = 'salvo';
}

function loadConfig() {
  document.getElementById('apiBase').value = localStorage.getItem('price_api_base') || window.location.origin;
  document.getElementById('apiKey').value = localStorage.getItem('price_api_key') || '';
}

async function api(path, options) {
  options = options || {};
  options.headers = Object.assign({'X-API-Key': apiKey(), 'Content-Type': 'application/json'}, options.headers || {});
  const response = await fetch(apiBase() + path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message = (body.error && body.error.message) || response.statusText;
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

function fmtDate(value) {
  if (!value) return '-';
  return new Date(value).toLocaleString('pt-BR');
}

async function createProduct(event) {
  event.preventDefault();
  const url = document.getElementById('newUrl').value;
  const interval = document.getElementById('newInterval').value;
  document.getElementById('createError').textContent = '';
  try {
    const payload = {url: url};
    if (interval) payload.check_interval_seconds = parseInt(interval, 10);
    await api('/api/v1/products', {method: 'POST', body: JSON.stringify(payload)});
    document.getElementById('newUrl').value = '';
    document.getElementById('newInterval').value = '';
    await loadProducts();
  } catch (err) {
    document.getElementById('createError').textContent = err.message;
  }
}

async function loadProducts() {
  const products = await api('/api/v1/products');
  const tbody = document.querySelector('#productsTable tbody');
  tbody.innerHTML = '';
  for (const p of products) {
    const tr = document.createElement('tr');
    const price = p.last_price_amount ? (p.last_price_amount + ' ' + p.last_price_currency) : '-';
    tr.innerHTML = `
      <td><a href="${p.url}" target="_blank" rel="noopener">${p.title || p.url}</a></td>
      <td class="status-${p.status}">${p.status}</td>
      <td>${price}</td>
      <td>${fmtDate(p.next_check_at)}</td>
      <td>${p.consecutive_failures}</td>
      <td>
        <button onclick="showDetail(${p.id})">Detalhes</button>
        <button onclick="checkNow(${p.id})">Verificar agora</button>
        <button onclick="toggleStatus(${p.id}, '${p.status}')">${p.status === 'paused' ? 'Retomar' : 'Pausar'}</button>
        <button onclick="archiveProduct(${p.id})">Arquivar</button>
      </td>`;
    tbody.appendChild(tr);
  }
}

let openDetailProductId = null;

async function refreshOpenDetail(id) {
  if (openDetailProductId === id) await showDetail(id);
}

async function checkNow(id) {
  try {
    await api(`/api/v1/products/${id}/check`, {method: 'POST'});
    await loadProducts();
    await refreshOpenDetail(id);
  } catch (err) {
    alert(err.message);
  }
}

async function toggleStatus(id, currentStatus) {
  const nextStatus = currentStatus === 'paused' ? 'active' : 'paused';
  await api(`/api/v1/products/${id}`, {method: 'PATCH', body: JSON.stringify({status: nextStatus})});
  await loadProducts();
  await refreshOpenDetail(id);
}

async function archiveProduct(id) {
  if (!confirm('Arquivar este produto?')) return;
  await api(`/api/v1/products/${id}`, {method: 'DELETE'});
  await loadProducts();
}

async function showDetail(id) {
  openDetailProductId = id;
  const [product, history, rules] = await Promise.all([
    api(`/api/v1/products/${id}`),
    api(`/api/v1/products/${id}/history?limit=20`),
    api(`/api/v1/products/${id}/rules`),
  ]);

  const errorsHtml = product.recent_errors.length
    ? product.recent_errors.map(e => `<li>${fmtDate(e.observed_at)} — ${e.collector}: ${e.error_code} (${e.error_message || ''})</li>`).join('')
    : '<li class="muted">nenhum erro recente</li>';

  const historyHtml = history.length
    ? history.map(h => `<tr><td>${fmtDate(h.observed_at)}</td><td>${h.price_amount} ${h.price_currency}</td><td>${h.source}</td><td>${h.availability || '-'}</td></tr>`).join('')
    : '<tr><td colspan="4" class="muted">sem histórico</td></tr>';

  const rulesHtml = rules.length
    ? rules.map(r => `<tr><td>${r.kind}</td><td>${r.threshold}</td><td>${r.active}</td><td><button onclick="deleteRule(${r.id}, ${id})">Remover</button></td></tr>`).join('')
    : '<tr><td colspan="4" class="muted">sem regras</td></tr>';

  document.getElementById('detail').innerHTML = `
    <h2>Detalhes: ${product.title || product.url}</h2>
    <p class="muted">${product.url}</p>
    <h3>Erros recentes</h3>
    <ul>${errorsHtml}</ul>
    <h3>Histórico (últimas 20 observações)</h3>
    <table><thead><tr><th>Quando</th><th>Preço</th><th>Fonte</th><th>Disponibilidade</th></tr></thead>
    <tbody>${historyHtml}</tbody></table>
    <h3>Regras</h3>
    <table><thead><tr><th>Tipo</th><th>Limite</th><th>Ativa</th><th></th></tr></thead>
    <tbody>${rulesHtml}</tbody></table>
    <form class="inline" onsubmit="createRule(event, ${id})">
      <select id="ruleKind">
        <option value="target_price">Preço-alvo</option>
        <option value="absolute_drop">Queda absoluta</option>
        <option value="percentage_drop">Queda percentual</option>
        <option value="new_low">Novo menor preço</option>
      </select>
      <input id="ruleThreshold" type="number" step="0.01" placeholder="limite" required>
      <button type="submit">Adicionar regra</button>
    </form>
  `;
}

async function createRule(event, productId) {
  event.preventDefault();
  const kind = document.getElementById('ruleKind').value;
  const threshold = document.getElementById('ruleThreshold').value;
  await api(`/api/v1/products/${productId}/rules`, {
    method: 'POST',
    body: JSON.stringify({kind: kind, threshold: threshold}),
  });
  await showDetail(productId);
}

async function deleteRule(ruleId, productId) {
  await api(`/api/v1/rules/${ruleId}`, {method: 'DELETE'});
  await showDetail(productId);
}

async function loadAlerts() {
  const alerts = await api('/api/v1/alerts?limit=50');
  const tbody = document.querySelector('#alertsTable tbody');
  tbody.innerHTML = alerts.length
    ? alerts.map(a => `
        <tr>
          <td>#${a.product_id}</td>
          <td>#${a.rule_id}</td>
          <td>${a.reference_price} ${a.currency}</td>
          <td>${a.current_price} ${a.currency}</td>
          <td>${fmtDate(a.created_at)}</td>
          <td>${a.deliveries.map(d => `${d.channel}:${d.status}`).join(', ') || 'pendente'}</td>
        </tr>`).join('')
    : '<tr><td colspan="6" class="muted">sem alertas</td></tr>';
}

loadConfig();
loadProducts().catch(err => console.error(err));
</script>
</body>
</html>
"""
