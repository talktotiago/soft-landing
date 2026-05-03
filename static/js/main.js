/* ─── Market Calculator ────────────────────────────────────────────────────── */

function initMarketCalculator() {
  const dataEl = document.getElementById('reportData');
  const savedEl = document.getElementById('savedMarketItems');
  const currEl  = document.getElementById('reportCurrency');

  if (!dataEl) return;

  const reportData   = JSON.parse(dataEl.textContent);
  const savedItems   = savedEl ? JSON.parse(savedEl.textContent) : [];
  const currency     = currEl ? JSON.parse(currEl.textContent) : '$';

  // Build a flat list of all items from all categories
  const allItems = [];
  Object.entries(reportData.categories || {}).forEach(([cat, items]) => {
    items.forEach(item => allItems.push({ ...item, cat }));
  });

  // State: item selections {itemName: quantity}
  const state = {};
  savedItems.forEach(si => {
    if (si.item_name) state[si.item_name] = si.quantity || 1;
  });

  const container = document.getElementById('marketItems');
  const searchInput = document.getElementById('marketSearch');
  const totalBadge  = document.getElementById('marketTotal');

  function render(filter) {
    filter = (filter || '').toLowerCase();
    container.innerHTML = '';

    allItems
      .filter(item => !filter || item.name.toLowerCase().includes(filter))
      .forEach(item => {
        const qty = state[item.name] || 0;
        const checked = qty > 0;

        const row = document.createElement('div');
        row.className = 'market-item-row';
        row.innerHTML = `
          <input type="checkbox" class="form-check-input flex-shrink-0"
                 id="mi-${encodeURIComponent(item.name)}"
                 ${checked ? 'checked' : ''}>
          <label for="mi-${encodeURIComponent(item.name)}" class="text-truncate" title="${item.name}">
            ${item.name}
          </label>
          <input type="number" class="form-control form-control-sm qty-input"
                 min="0" step="0.5" value="${qty || 1}"
                 ${!checked ? 'disabled' : ''}>
          <span class="item-subtotal">
            ${checked ? currency + ' ' + (item.price * qty).toFixed(2) : '—'}
          </span>
        `;

        const checkbox = row.querySelector('input[type="checkbox"]');
        const qtyInput = row.querySelector('.qty-input');
        const subtotal = row.querySelector('.item-subtotal');

        function update() {
          const isChecked = checkbox.checked;
          const q = isChecked ? (parseFloat(qtyInput.value) || 1) : 0;
          qtyInput.disabled = !isChecked;
          state[item.name] = q;
          subtotal.textContent = q > 0
            ? `${currency} ${(item.price * q).toFixed(2)}`
            : '—';
          recalcTotal();
        }

        checkbox.addEventListener('change', update);
        qtyInput.addEventListener('input', update);

        container.appendChild(row);
      });

    recalcTotal();
  }

  function recalcTotal() {
    let total = 0;
    allItems.forEach(item => {
      const qty = state[item.name] || 0;
      if (qty > 0) total += item.price * qty;
    });
    if (totalBadge) {
      totalBadge.textContent = `${currency} ${total.toFixed(2)}`;
    }
  }

  searchInput?.addEventListener('input', function () {
    render(this.value);
  });

  document.getElementById('clearMarketBtn')?.addEventListener('click', () => {
    Object.keys(state).forEach(k => delete state[k]);
    render(searchInput?.value || '');
  });

  document.getElementById('saveMarketBtn')?.addEventListener('click', () => {
    const items = Object.entries(state)
      .filter(([, qty]) => qty > 0)
      .map(([name, quantity]) => {
        const found = allItems.find(i => i.name === name);
        return { name, quantity, price: found ? found.price : 0, unit: 'unit' };
      });

    fetch('/api/market', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.ok) showToast('Shopping list saved!', 'success');
      })
      .catch(() => showToast('Could not save list.', 'danger'));
  });

  render();
}

/* ─── Profile Market Calculator ────────────────────────────────────────────── */

function initProfileCalculator() {
  const savedEl = document.getElementById('savedMarketItems');
  const currEl  = document.getElementById('profileCurrency');
  if (!savedEl) return;

  const savedItems = JSON.parse(savedEl.textContent) || [];
  const currency   = currEl ? JSON.parse(currEl.textContent) : '$';

  const allItems = savedItems.map(si => ({
    name:  si.item_name,
    price: si.price || 0,
  }));

  const state = {};
  savedItems.forEach(si => {
    if (si.item_name) state[si.item_name] = si.quantity || 1;
  });

  const container  = document.getElementById('marketItems');
  const searchInput = document.getElementById('marketSearch');
  const totalBadge  = document.getElementById('marketTotal');

  if (allItems.length === 0) {
    container.innerHTML = '<p class="text-muted small text-center py-3">No saved items yet.<br>Visit a city report to build your basket.</p>';
    return;
  }

  function render(filter) {
    filter = (filter || '').toLowerCase();
    container.innerHTML = '';
    allItems
      .filter(item => !filter || item.name.toLowerCase().includes(filter))
      .forEach(item => {
        const qty     = state[item.name] || 0;
        const checked = qty > 0;
        const row     = document.createElement('div');
        row.className = 'market-item-row';
        row.innerHTML = `
          <input type="checkbox" class="form-check-input flex-shrink-0"
                 id="mi-${encodeURIComponent(item.name)}" ${checked ? 'checked' : ''}>
          <label for="mi-${encodeURIComponent(item.name)}" class="text-truncate" title="${item.name}">
            ${item.name}
          </label>
          <input type="number" class="form-control form-control-sm qty-input"
                 min="0" step="0.5" value="${qty || 1}" ${!checked ? 'disabled' : ''}>
          <span class="item-subtotal">
            ${checked ? currency + ' ' + (item.price * qty).toFixed(2) : '—'}
          </span>
        `;
        const checkbox = row.querySelector('input[type="checkbox"]');
        const qtyInput = row.querySelector('.qty-input');
        const subtotal = row.querySelector('.item-subtotal');
        function update() {
          const isChecked = checkbox.checked;
          const q = isChecked ? (parseFloat(qtyInput.value) || 1) : 0;
          qtyInput.disabled = !isChecked;
          state[item.name] = q;
          subtotal.textContent = q > 0 ? `${currency} ${(item.price * q).toFixed(2)}` : '—';
          recalcTotal();
        }
        checkbox.addEventListener('change', update);
        qtyInput.addEventListener('input', update);
        container.appendChild(row);
      });
    recalcTotal();
  }

  function recalcTotal() {
    let total = 0;
    allItems.forEach(item => {
      const qty = state[item.name] || 0;
      if (qty > 0) total += item.price * qty;
    });
    if (totalBadge) totalBadge.textContent = `${currency} ${total.toFixed(2)}`;
  }

  searchInput?.addEventListener('input', function () { render(this.value); });

  document.getElementById('clearMarketBtn')?.addEventListener('click', () => {
    Object.keys(state).forEach(k => delete state[k]);
    render(searchInput?.value || '');
  });

  document.getElementById('saveMarketBtn')?.addEventListener('click', () => {
    const items = Object.entries(state)
      .filter(([, qty]) => qty > 0)
      .map(([name, quantity]) => {
        const found = allItems.find(i => i.name === name);
        return { name, quantity, price: found ? found.price : 0, unit: 'unit' };
      });
    fetch('/api/market', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items }),
    })
      .then(r => r.json())
      .then(d => { if (d.ok) showToast('Basket saved!', 'success'); })
      .catch(() => showToast('Could not save basket.', 'danger'));
  });

  render();
}

/* ─── Toast helper ──────────────────────────────────────────────────────────── */
function showToast(message, type = 'info') {
  const container = getToastContainer();
  const id = 'toast-' + Date.now();
  const el = document.createElement('div');
  el.className = `toast align-items-center text-bg-${type} border-0 show`;
  el.id = id;
  el.setAttribute('role', 'alert');
  el.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">${message}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto"
              data-bs-dismiss="toast"></button>
    </div>
  `;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function getToastContainer() {
  let c = document.getElementById('toastContainer');
  if (!c) {
    c = document.createElement('div');
    c.id = 'toastContainer';
    c.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    c.style.zIndex = 9999;
    document.body.appendChild(c);
  }
  return c;
}
