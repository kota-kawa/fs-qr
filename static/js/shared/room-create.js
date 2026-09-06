/* Shared create-room form behaviour for Group / Note / Task. */
(function (window, document) {
  'use strict';

  var RETENTION_PREVIEW_FALLBACK = '{time} ごろに自動削除されます';
  var DEFAULT_ERROR = 'ルーム作成に失敗しました。時間をおいて再度お試しください。';
  var INVALID_RESPONSE = 'レスポンス形式が不正です。時間をおいて再度お試しください。';

  function randomRoomId() {
    var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    var result = '';
    var bytes = new Uint8Array(6);
    if (window.crypto && typeof window.crypto.getRandomValues === 'function') {
      window.crypto.getRandomValues(bytes);
      for (var i = 0; i < bytes.length; i += 1) {
        result += chars.charAt(bytes[i] % chars.length);
      }
      return result;
    }
    for (var index = 0; index < 6; index += 1) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  }

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') || '' : '';
  }

  async function readPayload(response) {
    var body = await response.text();
    if (!body) return null;
    try {
      var payload = JSON.parse(body);
      return payload && typeof payload === 'object' ? payload : null;
    } catch (error) {
      return null;
    }
  }

  function payloadError(payload, fallback) {
    return payload && typeof payload.error === 'string' && payload.error
      ? payload.error
      : fallback;
  }

  function showError(form, message) {
    var box = form.querySelector('[data-room-create-error]');
    if (!box) return;
    box.textContent = message;
    box.classList.add('is-visible');
  }

  function clearError(form) {
    var box = form.querySelector('[data-room-create-error]');
    if (!box) return;
    box.textContent = '';
    box.classList.remove('is-visible');
  }

  function setLoading(form, active) {
    var button = form.querySelector('.room-create-submit');
    if (!button) return;
    button.disabled = active;
    button.setAttribute('aria-busy', active ? 'true' : 'false');
    if (active) {
      button.dataset.defaultLabel = button.textContent;
      button.textContent = form.dataset.processingLabel || button.textContent;
    } else if (button.dataset.defaultLabel) {
      button.textContent = button.dataset.defaultLabel;
    }
  }

  function setMode(form, mode, regenerate) {
    var manual = form.querySelector('[data-room-create-manual]');
    var automatic = form.querySelector('[data-room-create-auto]');
    var manualInput = form.querySelector('[name="id"]:not([data-room-create-hidden-id])');
    var hiddenInput = form.querySelector('[data-room-create-hidden-id]');
    var generatedInput = form.querySelector('[data-room-create-generated-id]');
    var isManual = mode === 'manual';
    if (manual) manual.hidden = !isManual;
    if (automatic) automatic.hidden = isManual;
    if (manualInput) {
      manualInput.disabled = !isManual;
      manualInput.required = isManual;
      if (!isManual) manualInput.value = '';
    }
    if (hiddenInput) {
      hiddenInput.disabled = isManual;
      hiddenInput.value = regenerate || !hiddenInput.value ? randomRoomId() : hiddenInput.value;
      if (generatedInput) generatedInput.value = hiddenInput.value;
    }
  }

  function formatDateTime(date) {
    function pad(value) { return String(value).padStart(2, '0'); }
    return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate())
      + ' ' + pad(date.getHours()) + ':' + pad(date.getMinutes());
  }

  function updatePreview(form) {
    var select = form.querySelector('[name="retention_hours"]');
    var output = form.querySelector('[data-room-create-preview]');
    if (!select || !output) return;
    var date = new Date();
    date.setHours(date.getHours() + Number(select.value || 24));
    var template = form.dataset.retentionMessage || RETENTION_PREVIEW_FALLBACK;
    output.textContent = template.replace('{time}', formatDateTime(date));
  }

  async function post(form) {
    return fetch(form.action, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-CSRF-Token': csrfToken(),
        'X-Requested-With': 'fetch',
        Accept: 'application/json'
      },
      body: new FormData(form)
    });
  }

  async function handleResponse(form, response, retryAuto) {
    var payload = await readPayload(response);
    if (response.status === 409 && retryAuto && payload && payload.data && payload.data.retry_auto === true) {
      setMode(form, 'auto', true);
      return handleResponse(form, await post(form), false);
    }
    if (!response.ok) {
      throw new Error(payloadError(payload, DEFAULT_ERROR));
    }
    var redirectUrl = payload && payload.data && payload.data.redirect_url;
    if (typeof redirectUrl === 'string' && redirectUrl) {
      window.location.href = redirectUrl;
      return;
    }
    if (response.redirected && response.url) {
      window.location.href = response.url;
      return;
    }
    throw new Error(payload ? DEFAULT_ERROR : INVALID_RESPONSE);
  }

  function bind(form) {
    if (form.dataset.roomCreateBound === 'true') return;
    form.dataset.roomCreateBound = 'true';
    var radios = form.querySelectorAll('input[name="idMode"]');
    var initial = form.querySelector('input[name="idMode"]:checked');
    setMode(form, initial ? initial.value : 'auto', false);
    updatePreview(form);

    radios.forEach(function (radio) {
      radio.addEventListener('change', function () {
        clearError(form);
        setMode(form, radio.value, radio.value === 'auto');
      });
    });
    var retention = form.querySelector('[name="retention_hours"]');
    if (retention) retention.addEventListener('change', function () { updatePreview(form); });

    form.addEventListener('submit', async function (event) {
      event.preventDefault();
      clearError(form);
      if (!form.reportValidity()) return;
      setLoading(form, true);
      try {
        await handleResponse(form, await post(form), true);
      } catch (error) {
        showError(form, error && error.message ? error.message : DEFAULT_ERROR);
        setLoading(form, false);
      }
    });
  }

  function init() {
    document.querySelectorAll('form[data-room-create]').forEach(bind);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window, document);
