/**
 * MITCHÔ — Chargeur automatique de prix vivriers
 * Mode backend  : GET /prices (FastAPI — données WFP pré-parsées)
 * Mode fallback : HDX API directe + CORS proxy
 *
 * Logique :
 *  1. Essaie le backend MITCHÔ (plus fiable, pas de CORS)
 *  2. Fallback : interroge l'API HDX directement via CORS proxy
 *  3. En cas d'échec total, conserve les valeurs statiques HTML
 */

const BACKEND_PRICES_URL = 'http://localhost:8000/prices';
const HDX_DATASET_ID     = 'wfp-food-prices-for-benin';
const HDX_API_BASE       = 'https://data.humdata.org/api/3/action';
const CORS_PROXY         = 'https://corsproxy.io/?';

const PRODUCT_MAP = {
  'Maize (white)'  : 'maiz',
  'Rice (imported)': 'riz',
  'Gari'           : 'gari',
  'Beans (white)'  : 'niebe',
};

const PRODUCT_LABELS = {
  maiz  : 'Maïs blanc',
  riz   : 'Riz importé',
  gari  : 'Gari blanc',
  niebe : 'Niébé blanc',
};

const MARKETS_PRIORITY = ['Cotonou', 'Dantokpa', 'Malanville', 'Parakou'];

let _lastUpdate = null;

async function loadLivePrices() {
  const btn = document.getElementById('btn-refresh-prices');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="material-symbols-outlined text-[14px] animate-spin">sync</span> Chargement...';
  }
  try {
    // Try backend first
    let prices = null;
    try {
      const res = await fetch(BACKEND_PRICES_URL, { signal: AbortSignal.timeout(5000) });
      if (res.ok) {
        const data = await res.json();
        if (data.prices && data.prices.length > 0) {
          prices = _backendPricesToDomMap(data.prices, data.updated_at);
        }
      }
    } catch (_) { /* backend not running, fallback to HDX */ }

    if (!prices) {
      const pkgUrl = `${HDX_API_BASE}/package_show?id=${HDX_DATASET_ID}`;
      const pkgRes = await fetch(pkgUrl, { signal: AbortSignal.timeout(8000) });
      if (!pkgRes.ok) throw new Error('HDX API unavailable');

      const pkg = await pkgRes.json();
      const resources = pkg.result?.resources || [];
      const csvResource = resources.find(r =>
        r.format?.toUpperCase() === 'CSV' &&
        (r.name?.toLowerCase().includes('benin') || r.name?.toLowerCase().includes('ben'))
      ) || resources.find(r => r.format?.toUpperCase() === 'CSV');

      if (!csvResource?.url) throw new Error('No CSV resource found');

      const csvUrl = CORS_PROXY + encodeURIComponent(csvResource.url);
      const csvRes = await fetch(csvUrl, { signal: AbortSignal.timeout(15000) });
      if (!csvRes.ok) throw new Error('CSV download failed');

      const csvText = await csvRes.text();
      prices = parseWFPCsv(csvText);
    }

    if (!prices || Object.keys(prices).length === 0) throw new Error('No Benin data');

    applyPricesToDOM(prices);
    showUpdateBadge(prices._date);
    _lastUpdate = prices._date;

  } catch (err) {
    console.info('[MITCHÔ] Prices: using static values.', err.message);
    showUpdateBadge(null);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<span class="material-symbols-outlined text-[14px]">sync</span> Actualiser';
    }
  }
}

function parseWFPCsv(raw) {
  const lines  = raw.trim().split('\n');
  const header = lines[0].split(',').map(h => h.trim().replace(/"/g, '').toLowerCase());

  const idxDate   = header.findIndex(h => h === 'date' || h === 'mp_year' || h === 'year');
  const idxMarket = header.findIndex(h => h.includes('market'));
  const idxCommod = header.findIndex(h => h.includes('commodity') || h.includes('cm_name'));
  const idxPrice  = header.findIndex(h => h === 'price' || h === 'mp_price');
  const idxCurr   = header.findIndex(h => h.includes('currency') || h.includes('cur_name'));
  const idxCountry= header.findIndex(h => h.includes('country') || h.includes('adm0_name'));

  if (idxPrice < 0 || idxCommod < 0) return {};

  const rows = lines.slice(1)
    .map(l => l.split(',').map(v => v.trim().replace(/"/g, '')))
    .filter(r => r.length > idxPrice);

  const beninRows = idxCountry >= 0
    ? rows.filter(r => r[idxCountry]?.toLowerCase().includes('benin') || r[idxCountry]?.toLowerCase() === 'ben')
    : rows;

  if (beninRows.length === 0) return {};

  const latestDate = beninRows
    .map(r => r[idxDate] || '')
    .sort()
    .reverse()[0];

  const recentRows = beninRows.filter(r => (r[idxDate] || '').startsWith(latestDate.substring(0, 7)));

  const result = { _date: latestDate };

  for (const [wfpName, key] of Object.entries(PRODUCT_MAP)) {
    const matches = recentRows.filter(r => {
      const commodity = r[idxCommod] || '';
      return commodity.toLowerCase().includes(wfpName.toLowerCase().split(' ')[0]);
    });

    if (matches.length === 0) continue;

    const sorted = matches.sort((a, b) => {
      const ma = r => MARKETS_PRIORITY.findIndex(m => (r[idxMarket] || '').includes(m));
      return ma(a) - ma(b);
    });

    const prices = sorted.map(r => parseFloat(r[idxPrice])).filter(p => !isNaN(p) && p > 0);
    if (prices.length === 0) continue;

    const avg = Math.round(prices.reduce((s, p) => s + p, 0) / prices.length);
    const currency = idxCurr >= 0 ? (sorted[0][idxCurr] || 'FCFA') : 'FCFA';

    result[key] = { price: avg, currency };
  }

  return result;
}

function applyPricesToDOM(prices) {
  const cards = document.querySelectorAll('[data-product]');

  cards.forEach(card => {
    const nameEl  = card.querySelector('p.font-semibold, p[class*="font-semibold"]');
    const priceEl = card.querySelector('.text-right p.font-semibold');
    const badgeEl = card.querySelector('.text-right span');

    if (!nameEl || !priceEl) return;
    const label = nameEl.textContent.trim();

    let key = null;
    for (const [k, lbl] of Object.entries(PRODUCT_LABELS)) {
      if (label.toLowerCase().includes(lbl.toLowerCase().split(' ')[0].toLowerCase())) {
        key = k; break;
      }
    }
    if (!key || !prices[key]) return;

    const { price, currency } = prices[key];
    const oldPrice = parseInt(priceEl.textContent) || price;
    const diff = price - oldPrice;
    const pct  = oldPrice ? Math.round((diff / oldPrice) * 100) : 0;

    priceEl.textContent = `${price} ${currency}/kg`;

    if (badgeEl) {
      const sign = pct > 0 ? '+' : '';
      badgeEl.textContent = pct === 0 ? 'stable' : `${sign}${pct}% vs mois préc.`;
      badgeEl.className = badgeEl.className
        .replace(/text-\w+\s/g, '')
        .replace(/bg-\w+\/\d+/g, '');
      if (pct > 0) {
        badgeEl.classList.add('text-tertiary', 'bg-tertiary/10');
      } else if (pct < 0) {
        badgeEl.classList.add('text-primary', 'bg-primary/10');
      } else {
        badgeEl.classList.add('text-on-surface-variant', 'bg-surface-container');
      }
    }
  });
}

function showUpdateBadge(date) {
  const existing = document.getElementById('prices-update-badge');
  if (existing) existing.remove();

  const section = document.querySelector('[data-product]')?.closest('section');
  const header  = section?.querySelector('.flex.items-end');
  if (!header) return;

  const badge = document.createElement('p');
  badge.id = 'prices-update-badge';
  badge.className = 'font-caption text-caption mt-1';

  if (date) {
    const d = new Date(date);
    const label = d.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
    badge.textContent = `Données WFP · ${label}`;
    badge.classList.add('text-primary');
  } else {
    badge.textContent = 'Données statiques · avril 2026';
    badge.classList.add('text-on-surface-variant');
  }

  header.appendChild(badge);
}

/* ── Convertir la réponse du backend en format DOM map ── */
function _backendPricesToDomMap(backendPrices, updatedAt) {
  const RAW_TO_KEY = {
    'Maïs blanc':   'maiz',
    'Riz importé':  'riz',
    'Gari blanc':   'gari',
    'Niébé blanc':  'niebe',
    'Sorgho':       'sorgho',
    'Mil':          'mil',
  };
  const map = { _date: updatedAt ? `${updatedAt}-01` : null };
  for (const p of backendPrices) {
    const key = RAW_TO_KEY[p.product];
    if (key) map[key] = p.price;
  }
  return map;
}

document.addEventListener('DOMContentLoaded', loadLivePrices);
