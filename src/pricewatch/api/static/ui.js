// All remote/dynamic values (product titles, sellers, error messages, URLs
// scraped from monitored pages, etc.) are rendered through DOM APIs
// (textContent, createElement, setAttribute), never through raw HTML string
// building. This file intentionally avoids that assignment pattern entirely.

let runtimeApiKey = '';
let openDetailProductId = null;

// ---- Tema (NEXO Design System §6): claro / escuro / sistema ----

const THEME_STORAGE_KEY = 'nexo-theme';

function applyTheme(choice) {
  if (choice === 'light' || choice === 'dark') {
    document.documentElement.setAttribute('data-theme', choice);
  } else {
    document.documentElement.removeAttribute('data-theme');
  }
  for (const btn of document.querySelectorAll('#themeSwitch button')) {
    btn.classList.toggle('active', btn.dataset.themeChoice === choice);
  }
}

function setTheme(choice) {
  localStorage.setItem(THEME_STORAGE_KEY, choice);
  applyTheme(choice);
}

function initTheme() {
  const stored = localStorage.getItem(THEME_STORAGE_KEY) || 'system';
  applyTheme(stored);
  for (const btn of document.querySelectorAll('#themeSwitch button')) {
    btn.addEventListener('click', () => setTheme(btn.dataset.themeChoice));
  }
}

// ---- API ----

function apiBaseInput() {
  return document.getElementById('apiBase');
}

function apiBase() {
  return apiBaseInput().value.replace(/\/$/, '');
}

function apiKey() {
  return runtimeApiKey;
}

function saveConfig() {
  runtimeApiKey = document.getElementById('apiKey').value;
  localStorage.setItem('price_api_base', apiBase());
  document.getElementById('configStatus').textContent = 'salvo (a chave não é persistida)';
}

function loadConfig() {
  apiBaseInput().value = localStorage.getItem('price_api_base') || window.location.origin;
  // Cleanup for browsers that still have the key from before it stopped
  // being persisted (Fase 6.1) — never leave it sitting in storage.
  localStorage.removeItem('price_api_key');
}

async function api(path, options) {
  options = options || {};
  options.headers = Object.assign(
    { 'X-API-Key': apiKey(), 'Content-Type': 'application/json' },
    options.headers || {}
  );
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

// Validates a URL before it is ever assigned to an href, allowing only
// http/https so a monitored page's data cannot smuggle in an executable scheme.
function safeExternalUrl(raw) {
  const url = new URL(raw, window.location.origin);
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new Error('URL externa inválida');
  }
  return url.href;
}

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    node.setAttribute(key, value);
  }
  for (const child of children || []) {
    node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
  }
  return node;
}

function td(value) {
  const cell = document.createElement('td');
  cell.textContent = value == null || value === '' ? '-' : String(value);
  return cell;
}

// NEXO Design System §8: estados oficiais de badge são success/warning/danger/
// info/neutral — nunca uma cor de status inventada.
const STATUS_BADGE = {
  active: ['badge-success', 'ativo'],
  paused: ['badge-warning', 'pausado'],
  error: ['badge-danger', 'erro'],
  unsupported: ['badge-danger', 'não suportado'],
  archived: ['badge-neutral', 'arquivado'],
};

function statusBadge(status) {
  const [badgeClass, label] = STATUS_BADGE[status] || ['badge-neutral', status];
  const span = document.createElement('span');
  span.className = `badge ${badgeClass}`;
  span.textContent = label;
  return span;
}

function button(label, onClick, variant) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = variant || 'btn-outline';
  btn.textContent = label;
  btn.addEventListener('click', onClick);
  return btn;
}

function linkTo(rawUrl, text) {
  const link = document.createElement('a');
  try {
    link.href = safeExternalUrl(rawUrl);
    link.target = '_blank';
    link.rel = 'noopener';
  } catch {
    // Leave the anchor without an href rather than risk an unsafe scheme.
  }
  link.textContent = text;
  return link;
}

function buildTable(headers, rows, emptyMessage) {
  const table = document.createElement('table');
  table.className = 'nexo-table';
  const thead = document.createElement('thead');
  const headRow = document.createElement('tr');
  for (const header of headers) {
    headRow.appendChild(el('th', {}, [header]));
  }
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  if (rows.length === 0) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = headers.length;
    cell.className = 'muted';
    cell.textContent = emptyMessage;
    row.appendChild(cell);
    tbody.appendChild(row);
  } else {
    for (const rowCells of rows) {
      const row = document.createElement('tr');
      for (const cell of rowCells) {
        row.appendChild(cell instanceof HTMLElement ? cell : td(cell));
      }
      tbody.appendChild(row);
    }
  }
  table.appendChild(tbody);

  const wrap = document.createElement('div');
  wrap.className = 'nexo-table-wrap';
  wrap.appendChild(table);
  return wrap;
}

function showError(box, message) {
  box.textContent = message;
  box.hidden = !message;
}

async function createProduct(event) {
  event.preventDefault();
  const url = document.getElementById('newUrl').value;
  const interval = document.getElementById('newInterval').value;
  const errorBox = document.getElementById('createError');
  showError(errorBox, '');
  try {
    const payload = { url: url };
    if (interval) payload.check_interval_seconds = parseInt(interval, 10);
    await api('/api/v1/products', { method: 'POST', body: JSON.stringify(payload) });
    document.getElementById('newUrl').value = '';
    document.getElementById('newInterval').value = '';
    await loadProducts();
  } catch (err) {
    showError(errorBox, err.message);
  }
}

async function loadProducts() {
  const products = await api('/api/v1/products');
  const tbody = document.querySelector('#productsTable tbody');
  tbody.replaceChildren();

  for (const p of products) {
    const tr = document.createElement('tr');

    const urlCell = document.createElement('td');
    urlCell.appendChild(linkTo(p.url, p.title || p.url));
    tr.appendChild(urlCell);

    const statusCell = document.createElement('td');
    statusCell.appendChild(statusBadge(p.status));
    tr.appendChild(statusCell);

    const price = p.last_price_amount ? `${p.last_price_amount} ${p.last_price_currency}` : null;
    tr.appendChild(td(price));
    tr.appendChild(td(fmtDate(p.next_check_at)));
    tr.appendChild(td(p.consecutive_failures));

    const actions = document.createElement('td');
    actions.className = 'nexo-actions';
    actions.appendChild(button('Detalhes', () => showDetail(p.id), 'btn-outline'));
    actions.appendChild(button('Verificar agora', () => checkNow(p.id), 'btn-secondary'));
    actions.appendChild(
      button(
        p.status === 'paused' ? 'Retomar' : 'Pausar',
        () => toggleStatus(p.id, p.status),
        'btn-secondary'
      )
    );
    actions.appendChild(button('Arquivar', () => archiveProduct(p.id), 'btn-danger'));
    tr.appendChild(actions);

    tbody.appendChild(tr);
  }
}

async function refreshOpenDetail(id) {
  if (openDetailProductId === id) await showDetail(id);
}

async function checkNow(id) {
  try {
    await api(`/api/v1/products/${id}/check`, { method: 'POST' });
    await loadProducts();
    await refreshOpenDetail(id);
  } catch (err) {
    alert(err.message);
  }
}

async function toggleStatus(id, currentStatus) {
  const nextStatus = currentStatus === 'paused' ? 'active' : 'paused';
  await api(`/api/v1/products/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ status: nextStatus }),
  });
  await loadProducts();
  await refreshOpenDetail(id);
}

async function archiveProduct(id) {
  if (!confirm('Arquivar este produto?')) return;
  await api(`/api/v1/products/${id}`, { method: 'DELETE' });
  await loadProducts();
}

async function showDetail(id) {
  openDetailProductId = id;
  const [product, history, rules] = await Promise.all([
    api(`/api/v1/products/${id}`),
    api(`/api/v1/products/${id}/history?limit=20`),
    api(`/api/v1/products/${id}/rules`),
  ]);

  const detail = document.getElementById('detail');
  detail.replaceChildren();

  const section = el('section', { class: 'nexo-card-solid nexo-section' }, []);
  section.appendChild(el('h2', {}, [`Detalhes: ${product.title || product.url}`]));
  section.appendChild(el('p', { class: 'muted' }, [product.url]));

  section.appendChild(el('h3', {}, ['Erros recentes']));
  const errorsList = document.createElement('ul');
  if (product.recent_errors.length) {
    for (const e of product.recent_errors) {
      const li = document.createElement('li');
      li.textContent = `${fmtDate(e.observed_at)} — ${e.collector}: ${e.error_code} (${e.error_message || ''})`;
      errorsList.appendChild(li);
    }
  } else {
    errorsList.appendChild(el('li', { class: 'muted' }, ['nenhum erro recente']));
  }
  section.appendChild(errorsList);

  section.appendChild(el('h3', {}, ['Histórico (últimas 20 observações)']));
  section.appendChild(
    buildTable(
      ['Quando', 'Preço', 'Fonte', 'Disponibilidade'],
      history.map((h) => [
        fmtDate(h.observed_at),
        `${h.price_amount} ${h.price_currency}`,
        h.source,
        h.availability || '-',
      ]),
      'sem histórico'
    )
  );

  section.appendChild(el('h3', {}, ['Regras']));
  section.appendChild(
    buildTable(
      ['Tipo', 'Limite', 'Ativa', ''],
      rules.map((r) => [
        r.kind,
        r.threshold == null ? '-' : r.threshold,
        String(r.active),
        button('Remover', () => deleteRule(r.id, id), 'btn-danger'),
      ]),
      'sem regras'
    )
  );

  const form = el('form', { class: 'inline nexo-form-row' }, []);
  form.addEventListener('submit', (event) => createRule(event, id));

  const kindField = el('div', { class: 'nexo-field-narrow' }, []);
  kindField.appendChild(el('label', { class: 'nexo-label', for: 'ruleKind' }, ['Tipo']));
  const kindSelect = document.createElement('select');
  kindSelect.id = 'ruleKind';
  kindSelect.className = 'nexo-select';
  const options = [
    ['target_price', 'Preço-alvo'],
    ['absolute_drop', 'Queda absoluta'],
    ['percentage_drop', 'Queda percentual'],
    ['new_low', 'Novo menor preço'],
  ];
  for (const [value, label] of options) {
    kindSelect.appendChild(el('option', { value }, [label]));
  }
  kindField.appendChild(kindSelect);
  form.appendChild(kindField);

  const thresholdField = el('div', { class: 'nexo-field-narrow' }, []);
  thresholdField.appendChild(el('label', { class: 'nexo-label', for: 'ruleThreshold' }, ['Limite']));
  const thresholdInput = document.createElement('input');
  thresholdInput.id = 'ruleThreshold';
  thresholdInput.className = 'nexo-input';
  thresholdInput.type = 'number';
  thresholdInput.step = '0.01';
  thresholdInput.required = true;
  thresholdField.appendChild(thresholdInput);
  form.appendChild(thresholdField);

  const submitButton = document.createElement('button');
  submitButton.type = 'submit';
  submitButton.className = 'btn-primary';
  submitButton.textContent = 'Adicionar regra';
  form.appendChild(submitButton);

  section.appendChild(form);
  detail.appendChild(section);
}

async function createRule(event, productId) {
  event.preventDefault();
  const kind = document.getElementById('ruleKind').value;
  const threshold = document.getElementById('ruleThreshold').value;
  try {
    await api(`/api/v1/products/${productId}/rules`, {
      method: 'POST',
      body: JSON.stringify({ kind: kind, threshold: threshold }),
    });
    await showDetail(productId);
  } catch (err) {
    alert(err.message);
  }
}

async function deleteRule(ruleId, productId) {
  await api(`/api/v1/rules/${ruleId}`, { method: 'DELETE' });
  await showDetail(productId);
}

async function loadAlerts() {
  const alerts = await api('/api/v1/alerts?limit=50');
  const tbody = document.querySelector('#alertsTable tbody');
  tbody.replaceChildren();

  if (alerts.length === 0) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 6;
    cell.className = 'muted';
    cell.textContent = 'sem alertas';
    row.appendChild(cell);
    tbody.appendChild(row);
    return;
  }

  for (const a of alerts) {
    const tr = document.createElement('tr');
    tr.appendChild(td(`#${a.product_id}`));
    tr.appendChild(td(`#${a.rule_id}`));
    tr.appendChild(td(`${a.reference_price} ${a.currency}`));
    tr.appendChild(td(`${a.current_price} ${a.currency}`));
    tr.appendChild(td(fmtDate(a.created_at)));
    const delivery = a.deliveries.map((d) => `${d.channel}:${d.status}`).join(', ');
    tr.appendChild(td(delivery || 'pendente'));
    tbody.appendChild(tr);
  }
}

document.getElementById('configForm').addEventListener('submit', (event) => {
  event.preventDefault();
  saveConfig();
});
document.getElementById('newProductForm').addEventListener('submit', createProduct);
document.getElementById('reloadProducts').addEventListener('click', loadProducts);
document.getElementById('reloadAlerts').addEventListener('click', loadAlerts);

initTheme();
loadConfig();
loadProducts().catch((err) => console.error(err));
