/**
 * i18n.js — Shamanic Travels
 * Versione per <select> esistente. Carica da /lang/*.json
 * USO: <script src="i18n.js"></script> poi i18n.init();
 */

const i18n = (() => {

  const STORAGE_KEY = 'st_lang';
  const SUPPORTED = ['en', 'it', 'es', 'sr', 'ru'];
  const FALLBACK = 'en';

  let currentLang = FALLBACK;
  let strings = {};

  function detectBrowserLang() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && SUPPORTED.includes(saved)) return saved;
    const nav = (navigator.language || navigator.userLanguage || 'en').slice(0, 2).toLowerCase();
    const map = { hr: 'sr', bs: 'sr', me: 'sr' };
    const lang = map[nav] || nav;
    return SUPPORTED.includes(lang)? lang : FALLBACK;
  }

  async function loadLang(lang) {
    try {
      const res = await fetch(`/lang/${lang}.json?v=${Date.now()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (e) {
      console.error(`i18n: fallito caricamento ${lang}.json`, e);
      if (lang!== FALLBACK) return loadLang(FALLBACK);
      return {};
    }
  }

  function get(key) {
    return key.split('.').reduce((obj, k) => (obj && obj[k]!== undefined? obj[k] : null), strings);
  }

  function applyStrings() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      const val = get(key);
      if (val!== null) {
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
          el.placeholder = val;
        } else {
          el.textContent = val;
        }
      }
    });

    document.querySelectorAll('[data-i18n-attr]').forEach(el => {
      const parts = el.getAttribute('data-i18n-attr').split(':');
      if (parts.length === 2) {
        const val = get(parts[1]);
        if (val!== null) el.setAttribute(parts[0], val);
      }
    });

    document.querySelectorAll('[data-i18n-html]').forEach(el => {
      const key = el.getAttribute('data-i18n-html');
      const val = get(key);
      if (val!== null) el.innerHTML = val;
    });
  }

  function setHtmlLang(lang) {
    document.documentElement.setAttribute('lang', lang);
  }

  /* ── USA IL SELECT ESISTENTE ── */
  function bindSelector() {
    const select = document.getElementById('lang-switcher');
    if (!select) {
      console.warn('i18n: #lang-switcher non trovato');
      return;
    }
    select.value = currentLang;
    if (!select.dataset.i18nBound) {
      select.addEventListener('change', (e) => switchLang(e.target.value));
      select.dataset.i18nBound = 'true';
    }
  }

  async function switchLang(lang) {
    if (!SUPPORTED.includes(lang)) return;
    currentLang = lang;
    localStorage.setItem(STORAGE_KEY, lang);
    strings = await loadLang(lang);
    applyStrings();
    setHtmlLang(lang);
    bindSelector();
    document.dispatchEvent(new CustomEvent('langChanged', { detail: { lang } }));
  }

  async function init(forceLang) {
    currentLang = forceLang || detectBrowserLang();
    strings = await loadLang(currentLang);
    applyStrings();
    setHtmlLang(currentLang);
    bindSelector();
  }

  return { init, get, switchLang, getCurrent: () => currentLang };

})();
