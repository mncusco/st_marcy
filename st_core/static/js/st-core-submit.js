(function () {
  var API_URL = '/api/leads';
  var FORM_SELECTOR = '#lead-form';
  var SUBMIT_BTN_SELECTOR = '#lead-form button[type="submit"]';

  function getUTM() {
    var params = new URLSearchParams(window.location.search);
    return {
      utm_source: params.get('utm_source') || undefined,
      utm_medium: params.get('utm_medium') || undefined,
      utm_campaign: params.get('utm_campaign') || undefined,
      utm_content: params.get('utm_content') || undefined,
      utm_term: params.get('utm_term') || undefined,
    };
  }

  function getPageData() {
    var lang =
      document.documentElement.lang ||
      (navigator.language || '').split('-')[0] ||
      undefined;
    return {
      source_page: window.location.href,
      referrer: document.referrer || undefined,
      language: lang,
      ...getUTM(),
    };
  }

  function showError(msg) {
    var el = document.querySelector('.form-error');
    if (!el) {
      el = document.createElement('p');
      el.className = 'form-error';
      el.style.cssText =
        'color:#9a5a5a;font-size:13px;margin-top:12px;text-align:center;';
      var form = document.querySelector(FORM_SELECTOR);
      if (form) form.appendChild(el);
    }
    el.textContent = msg;
  }

  function clearError() {
    var el = document.querySelector('.form-error');
    if (el) el.remove();
  }

  var form = document.querySelector(FORM_SELECTOR);
  if (!form) return;

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    clearError();

    var btn = form.querySelector(SUBMIT_BTN_SELECTOR);
    if (btn) btn.disabled = true;

    var fd = new FormData(form);
    var payload = {
      first_name: fd.get('first_name') || fd.get('name'),
      last_name: fd.get('last_name') || '',
      email: fd.get('email'),
      country: fd.get('country') || undefined,
      ...getPageData(),
    };

    if (!payload.first_name || payload.first_name.trim().length === 0) {
      showError('Please enter your name.');
      if (btn) btn.disabled = false;
      return;
    }
    if (!payload.email || !payload.email.includes('@')) {
      showError('Please enter a valid email.');
      if (btn) btn.disabled = false;
      return;
    }

    fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(function (r) {
        return r.json().then(function (data) {
          if (!r.ok) throw new Error(data.detail || 'Submission failed');
          return data;
        });
      })
      .then(function (data) {
        if (data.download_token) {
          window.location.href = '/download/' + data.download_token;
        } else {
          showError('Unexpected response. Please try again.');
        }
      })
      .catch(function (err) {
        showError(err.message || 'Something went wrong.');
      })
      .finally(function () {
        if (btn) btn.disabled = false;
      });
  });
})();
