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
  let select = document.getElementById('lang-switcher');
  
  if (!select) {
    const nav = document.querySelector('.nav-links');
    if (nav) {
      const li = document.createElement('li');
      li.innerHTML = `
        <label for="lang-switcher" class="sr-only">Language</label>
        <select id="lang-switcher" style="background:transparent;border:1px solid currentColor;color:inherit;font-size:10px;letter-spacing:0.2em;text-transform:uppercase;padding:4px 8px;cursor:pointer;">
          <option value="en">EN</option>
          <option value="it">IT</option>
          <option value="es">ES</option>
          <option value="sr">SR</option>
          <option value="ru">RU</option>
        </select>`;
      nav.appendChild(li);
      select = document.getElementById('lang-switcher');
    }
  }
  
  if (!select) {
    console.warn('i18n: #lang-switcher non trovato e nav non trovata');
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
    initCookieConsent();
  }

  return { init, get, switchLang, getCurrent: () => currentLang };

})();

/* ── COOKIE CONSENT ── */
function initCookieConsent() {
  if (window.__stCookieConsentInitialized) return;
  window.__stCookieConsentInitialized = true;

  const css = document.createElement('link');
  css.rel = 'stylesheet';
  css.href = '/cookie-consent.css?v=1';
  document.head.appendChild(css);

  const saved = localStorage.getItem('st_cookie_consent');
  if (saved) return;

  const lang = (document.documentElement.lang || 'en').slice(0, 2);
  const copy = {
    en: { title: 'Your privacy', text: 'We use essential cookies for the site to function. Optional analytics and advertising cookies are used only with your consent. See our Privacy Policy for details.', accept: 'Accept all', reject: 'Essential only', settings: 'Preferences', privacy: 'Privacy Policy' },
    it: { title: 'La tua privacy', text: 'Utilizziamo cookie essenziali per il funzionamento del sito. I cookie opzionali di analisi e pubblicità vengono utilizzati solo con il tuo consenso. Consulta la Privacy Policy per i dettagli.', accept: 'Accetta tutti', reject: 'Solo essenziali', settings: 'Preferenze', privacy: 'Privacy Policy' },
    es: { title: 'Tu privacidad', text: 'Utilizamos cookies esenciales para el funcionamiento del sitio. Las cookies opcionales de análisis y publicidad se utilizan solo con tu consentimiento. Consulta la Política de Privacidad para más información.', accept: 'Aceptar todas', reject: 'Solo esenciales', settings: 'Preferencias', privacy: 'Política de Privacidad' },
    sr: { title: 'Vaša privatnost', text: 'Koristimo neophodne kolačiće za rad sajta. Opcioni analitički i reklamni kolačići koriste se samo uz vašu saglasnost. Više informacija nalazi se u Politici privatnosti.', accept: 'Prihvati sve', reject: 'Samo neophodni', settings: 'Podešavanja', privacy: 'Politika privatnosti' },
    ru: { title: 'Ваша конфиденциальность', text: 'Мы используем необходимые файлы cookie для работы сайта. Необязательные аналитические и рекламные cookie используются только с вашего согласия. Подробнее — в Политике конфиденциальности.', accept: 'Принять все', reject: 'Только необходимые', settings: 'Настройки', privacy: 'Политика конфиденциальности' }
  }[lang] || null;
  if (!copy) return;

  const root = document.createElement('div');
  root.className = 'st-cc-root';
  root.innerHTML = `
    <div class="st-cc-overlay" data-cc-overlay></div>
    <section class="st-cc-banner" role="dialog" aria-label="${copy.title}">
      <div class="st-cc-content">
        <h2 class="st-cc-title">${copy.title}</h2>
        <p class="st-cc-text">${copy.text} <a href="/privacy.html">${copy.privacy}</a></p>
      </div>
      <div class="st-cc-actions">
        <button class="st-cc-btn st-cc-btn-secondary" type="button" data-cc-reject>${copy.reject}</button>
        <button class="st-cc-btn st-cc-btn-secondary" type="button" data-cc-settings>${copy.settings}</button>
        <button class="st-cc-btn st-cc-btn-primary" type="button" data-cc-accept>${copy.accept}</button>
      </div>
    </section>
    <section class="st-cc-settings" role="dialog" aria-modal="true" aria-label="${copy.settings}" data-cc-panel>
      <div class="st-cc-settings-header"><h2 class="st-cc-settings-title">${copy.settings}</h2><button class="st-cc-close" type="button" data-cc-close aria-label="Close">×</button></div>
      <div class="st-cc-settings-body">
        <div class="st-cc-option"><div><h3 class="st-cc-option-title">Essential</h3><p class="st-cc-option-description">Required for basic site functionality.</p></div><div class="st-cc-toggle"><input type="checkbox" checked disabled><span class="st-cc-toggle-track"></span></div></div>
        <div class="st-cc-option"><div><h3 class="st-cc-option-title">Analytics</h3><p class="st-cc-option-description">Helps us understand how visitors use the site.</p></div><label class="st-cc-toggle"><input type="checkbox" data-cc-analytics><span class="st-cc-toggle-track"></span></label></div>
        <div class="st-cc-option"><div><h3 class="st-cc-option-title">Advertising</h3><p class="st-cc-option-description">Used for measuring and improving advertising.</p></div><label class="st-cc-toggle"><input type="checkbox" data-cc-advertising><span class="st-cc-toggle-track"></span></label></div>
      </div>
      <div class="st-cc-settings-footer"><button class="st-cc-btn st-cc-btn-secondary" type="button" data-cc-close>${copy.reject}</button><button class="st-cc-btn st-cc-btn-primary" type="button" data-cc-save>${copy.accept}</button></div>
    </section>`;
  document.body.appendChild(root);

  const banner = root.querySelector('.st-cc-banner');
  const panel = root.querySelector('[data-cc-panel]');
  const overlay = root.querySelector('[data-cc-overlay]');

  function closePanel() { panel.classList.remove('is-open'); overlay.classList.remove('is-open'); }
  function save(analytics, advertising) {
    localStorage.setItem('st_cookie_consent', JSON.stringify({ analytics: !!analytics, advertising: !!advertising, at: new Date().toISOString() }));
    banner.remove(); closePanel(); overlay.remove();
  }

  root.querySelector('[data-cc-accept]').addEventListener('click', () => save(true, true));
  root.querySelector('[data-cc-reject]').addEventListener('click', () => save(false, false));
  root.querySelector('[data-cc-settings]').addEventListener('click', () => { panel.classList.add('is-open'); overlay.classList.add('is-open'); });
  root.querySelectorAll('[data-cc-close]').forEach(btn => btn.addEventListener('click', closePanel));
  root.querySelector('[data-cc-save]').addEventListener('click', () => save(root.querySelector('[data-cc-analytics]').checked, root.querySelector('[data-cc-advertising]').checked));
  overlay.addEventListener('click', closePanel);
}
