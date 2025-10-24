const socket = io();

const early = [];
let follow = true; // only auto-follow when you're at the bottom
const MAX_CHARS = 200000;
const KEEP_CHARS = 150000;

function appendLine(el, line){
  if (!line) return;

  // Keep pre content as plain text (no HTML injection / no colorizing)
  if (el.textContent && !el.textContent.endsWith('\n')) el.textContent += '\n';
  el.textContent += line + '\n';

  // Trim very long buffers to keep the page snappy
  if (el.textContent.length > MAX_CHARS) {
    el.textContent = el.textContent.slice(-KEEP_CHARS);
  }

  if (follow) el.scrollTop = el.scrollHeight;
}

// ---------- JSON viewer (for config mode) ----------
function renderJsonTree(container, data, label = 'root', open = true) {
  container.innerHTML = '';
  container.appendChild(buildNode(label, data, open));

  function buildNode(key, value, open) {
    const isObj = value && typeof value === 'object';
    const isArr = Array.isArray(value);
    const node = document.createElement('div');
    node.style.marginLeft = '8px';
    node.style.fontFamily = 'Consolas, "Courier New", monospace';
    node.style.lineHeight = '1.45';

    if (!isObj) {
      const line = document.createElement('div');
      line.textContent = `${key}: ${formatPrimitive(value)}`;
      node.appendChild(line);
      return node;
    }

    const details = document.createElement('details');
    if (open) details.setAttribute('open', 'open');

    const summary = document.createElement('summary');
    const typeLabel = isArr ? `Array(${value.length})` : 'Object';
    summary.textContent = `${key}: ${typeLabel}`;
    details.appendChild(summary);

    const childWrap = document.createElement('div');
    childWrap.style.marginLeft = '14px';

    if (isArr) {
      value.forEach((v, i) => childWrap.appendChild(buildNode(`[${i}]`, v, false)));
    } else {
      Object.keys(value).sort().forEach(k => {
        childWrap.appendChild(buildNode(k, value[k], false));
      });
    }

    details.appendChild(childWrap);
    node.appendChild(details);
    return node;
  }

  function formatPrimitive(v) {
    if (typeof v === 'string') return JSON.stringify(v);
    if (v === null) return 'null';
    return String(v);
  }
}

function updateCfgViews(rawEl, treeEl, text) {
  // Raw
  rawEl.textContent = text || '';
  rawEl.scrollTop = rawEl.scrollHeight;

  // Tree
  try {
    const obj = JSON.parse(text || '{}');
    renderJsonTree(treeEl, obj);
  } catch (e) {
    treeEl.innerHTML = '';
    const warn = document.createElement('div');
    warn.textContent = 'Invalid JSON';
    treeEl.appendChild(warn);
  }
}

// --- socket stream (logs only) ---
socket.on('log_line', ({ line }) => {
  const el = document.getElementById('log');
  if (!el) { early.push(line); return; }
  const mode = el.dataset.mode || 'logs';
  if (mode !== 'logs') return;                 // only for logs
  const isLive = el.dataset.live === 'true';
  if (!isLive) return;                         // do not append when viewing old files
  appendLine(el, line);
});

document.addEventListener('DOMContentLoaded', () => {
  const logEl = document.getElementById('log');
  if (!logEl) return;

  const mode = logEl.dataset.mode || 'logs';
  const dlUrl = logEl.dataset.download || '';
  const jsonTreeEl = document.getElementById('jsonTree');
  const toggleBtn = document.getElementById('toggleViewBtn');

  // Initial scroll to bottom for raw view
  logEl.scrollTop = logEl.scrollHeight;

  // Drain any early lines collected before DOM was ready (logs only + live)
  if (early.length && mode === 'logs' && logEl.dataset.live === 'true') {
    for (const l of early) appendLine(logEl, l);
    early.length = 0;
  }

  // --- smart autoscroll ---
  const BOTTOM_EPS = 4; // px tolerance for "at the bottom"
  const atBottom = () => (logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight) <= BOTTOM_EPS;
  const updateFollow = () => { follow = atBottom(); };

  logEl.addEventListener('scroll', updateFollow, { passive: true });
  logEl.addEventListener('wheel', updateFollow, { passive: true });
  logEl.addEventListener('touchmove', updateFollow, { passive: true });
  logEl.addEventListener('keydown', updateFollow);

  window.addEventListener('beforeunload', () => socket.off('log_line'));

  // --- dropup picker ("Select") ---
  const pickerBtn = document.getElementById('pickerBtn');
  const pickerMenu = document.getElementById('pickerMenu');
  if (pickerBtn && pickerMenu) {
    const close = () => { pickerMenu.classList.remove('open'); pickerBtn.setAttribute('aria-expanded','false'); };
    pickerBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const open = pickerMenu.classList.toggle('open');
      pickerBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    document.addEventListener('click', (e) => {
      if (!pickerMenu.contains(e.target) && e.target !== pickerBtn) close();
    });
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') close();
    });
  }

  // --- Config mode: one-time display (no live updates) ---
  if (mode === 'cfg') {
    // 1) Render tree once from the server-provided initial text
    if (jsonTreeEl) updateCfgViews(logEl, jsonTreeEl, logEl.textContent);

    // 2) Optionally do a single fetch of the latest file if a download URL is provided
    if (dlUrl && jsonTreeEl) {
      fetch(dlUrl, { cache: 'no-store' })
        .then(r => r.ok ? r.text() : Promise.reject())
        .then(t => updateCfgViews(logEl, jsonTreeEl, t))
        .catch(() => {/* ignore */});
    }

    // 3) Raw/Tree toggle
    if (toggleBtn && jsonTreeEl) {
      toggleBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const state = toggleBtn.getAttribute('data-view') || 'raw';
        if (state === 'raw') {
          // switch to tree
          logEl.style.display = 'none';
          jsonTreeEl.style.display = '';
          toggleBtn.textContent = 'Raw view';
          toggleBtn.setAttribute('data-view', 'tree');
        } else {
          // switch to raw
          jsonTreeEl.style.display = 'none';
          logEl.style.display = '';
          toggleBtn.textContent = 'Tree view';
          toggleBtn.setAttribute('data-view', 'raw');
        }
      });
    }
  }
});
