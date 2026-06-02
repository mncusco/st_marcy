/**
 * i18n.js — Shamanic Travels
 * Motore multilingua leggero. Nessuna dipendenza esterna.
 *
 * USO NEGLI HTML:
 *   <script src="i18n.js"></script>
 *   Poi chiama: i18n.init('en')  oppure  i18n.init()  (autodetect)
 *   Marca gli elementi con data-i18n="chiave.sottochiave"
 */

const i18n = (() => {

  const STORAGE_KEY = 'st_lang';
  const SUPPORTED   = ['en', 'it', 'es', 'sr', 'ru'];
  const FALLBACK    = 'en';

  const LABELS = {
    en: 'EN', it: 'IT', es: 'ES', sr: 'SR', ru: 'RU'
  };

  let currentLang = FALLBACK;
  let strings     = {};

  /* ── rileva lingua browser ── */
  function detectBrowserLang() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && SUPPORTED.includes(saved)) return saved;
    const nav = (navigator.language || navigator.userLanguage || 'en').slice(0, 2).toLowerCase();
    const map = { hr: 'sr', bs: 'sr', me: 'sr' }; // varianti serbo-croate
    const lang = map[nav] || nav;
    return SUPPORTED.includes(lang) ? lang : FALLBACK;
  }

  /* ── carica JSON lingua ── */
  async function loadLang(lang) {
    try {
      const res = await fetch(`lang/${lang}.json?v=1`);
      if (!res.ok) throw new Error();
      return await res.json();
    } catch {
      if (lang !== FALLBACK) return loadLang(FALLBACK);
      return {};
    }
  }

  /* ── legge chiave nested tipo "nav.ethos" ── */
  function get(key) {
    return key.split('.').reduce((obj, k) => (obj && obj[k] !== undefined ? obj[k] : null), strings);
  }

  /* ── applica traduzioni al DOM ── */
  function applyStrings() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      const val = get(key);
      if (val !== null) {
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
          el.placeholder = val;
        } else {
          el.textContent = val;
        }
      }
    });

    /* attributi: data-i18n-attr="placeholder:chiave" */
    document.querySelectorAll('[data-i18n-attr]').forEach(el => {
      const parts = el.getAttribute('data-i18n-attr').split(':');
      if (parts.length === 2) {
        const val = get(parts[1]);
        if (val !== null) el.setAttribute(parts[0], val);
      }
    });

    /* HTML: data-i18n-html="chiave" (per tag interni tipo <em>) */
    document.querySelectorAll('[data-i18n-html]').forEach(el => {
      const key = el.getAttribute('data-i18n-html');
      const val = get(key);
      if (val !== null) el.innerHTML = val;
    });
  }

  /* ── aggiorna <html lang=""> ── */
  function setHtmlLang(lang) {
    document.documentElement.setAttribute('lang', lang);
  }

  /* ── costruisce il selettore lingua nella nav ── */
  function buildSelector() {
    const existing = document.getElementById('langSelector');
    if (existing) existing.remove();

    const wrap = document.createElement('div');
    wrap.id = 'langSelector';
    wrap.setAttribute('role', 'navigation');
    wrap.setAttribute('aria-label', 'Language selector');
    wrap.style.cssText = `
      display: flex;
      align-items: center;
      gap: 6px;
      margin-left: 24px;
    `;

    SUPPORTED.forEach(lang => {
      const btn = document.createElement('button');
      btn.textContent   = LABELS[lang];
      btn.dataset.lang  = lang;
      btn.setAttribute('aria-label', `Switch to ${lang.toUpperCase()}`);
      btn.style.cssText = `
        background: none;
        border: none;
        cursor: pointer;
        font-family: 'Inter', sans-serif;
        font-size: 10px;
        font-weight: 400;
        letter-spacing: 0.15em;
        padding: 4px 6px;
        color: inherit;
        opacity: ${lang === currentLang ? '1' : '0.4'};
        transition: opacity 0.2s;
      `;
      btn.addEventListener('mouseenter', () => { if (lang !== currentLang) btn.style.opacity = '0.75'; });
      btn.addEventListener('mouseleave', () => { if (lang !== currentLang) btn.style.opacity = '0.4'; });
      btn.addEventListener('click', () => switchLang(lang));
      wrap.appendChild(btn);

      /* separatore */
      if (lang !== SUPPORTED[SUPPORTED.length - 1]) {
        const sep = document.createElement('span');
        sep.textContent  = '·';
        sep.style.cssText = 'opacity:0.2; font-size:10px; pointer-events:none;';
        wrap.appendChild(sep);
      }
    });

    /* inserisce dopo .nav-links */
    const navLinks = document.querySelector('.nav-links');
    if (navLinks) navLinks.after(wrap);
    else {
      const navInner = document.querySelector('.nav-inner');
      if (navInner) navInner.appendChild(wrap);
    }
  }

  /* ── cambia lingua ── */
  async function switchLang(lang) {
    if (!SUPPORTED.includes(lang)) return;
    currentLang = lang;
    localStorage.setItem(STORAGE_KEY, lang);
    strings = await loadLang(lang);
    applyStrings();
    setHtmlLang(lang);
    buildSelector(); /* ricostruisce per aggiornare gli stati attivi */
    document.dispatchEvent(new CustomEvent('langChanged', { detail: { lang } }));
  }

  /* ── init pubblico ── */
  async function init(forceLang) {
    currentLang = forceLang || detectBrowserLang();
    strings     = await loadLang(currentLang);
    applyStrings();
    setHtmlLang(currentLang);
    buildSelector();
  }

  return { init, get, switchLang, getCurrent: () => currentLang };

})();
