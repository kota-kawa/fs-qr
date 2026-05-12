(function () {
  const CONSENT_COOKIE_NAME = 'fsqr_cookie_consent';
  const LANGUAGE_COOKIE_NAME = 'fsqr_language';
  const CONSENT_DURATION_DAYS = 365;

  function setCookie(name, value, durationDays = CONSENT_DURATION_DAYS) {
    const expires = new Date(Date.now() + durationDays * 24 * 60 * 60 * 1000);
    document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
  }

  function getCookie(name) {
    const prefix = `${name}=`;
    const cookie = document.cookie
      .split(';')
      .map((item) => item.trim())
      .find((item) => item.startsWith(prefix));
    return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : '';
  }

  function setConsentCookie(value = 'accepted') {
    const normalizedValue =
      typeof value === 'string'
        ? value
        : JSON.stringify({ necessary: true, ...value });
    setCookie(CONSENT_COOKIE_NAME, normalizedValue);
  }

  function setLanguageCookie(value) {
    if (['ja', 'en', 'zh-CN'].includes(value)) {
      setCookie(LANGUAGE_COOKIE_NAME, value);
    }
  }

  function hasConsent() {
    return document.cookie.split(';').some((cookie) => cookie.trim().startsWith(`${CONSENT_COOKIE_NAME}=`));
  }

  function hideOverlay(overlay) {
    overlay.classList.remove('is-visible');
    overlay.setAttribute('aria-hidden', 'true');
    overlay.removeAttribute('data-cookie-consent-active-view');
    document.body.style.removeProperty('overflow');
  }

  function showOverlay(overlay) {
    overlay.classList.add('is-visible');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function switchView(overlay, viewName) {
    const views = overlay.querySelectorAll('[data-cookie-consent-view]');
    views.forEach((view) => {
      const isActive = view.getAttribute('data-cookie-consent-view') === viewName;
      view.hidden = !isActive;
      view.setAttribute('aria-hidden', String(!isActive));
    });
    overlay.setAttribute('data-cookie-consent-active-view', viewName);
  }

  function focusOnTarget(target) {
    if (target && typeof target.focus === 'function') {
      target.focus();
    }
  }

  function initLangSelect(wrapper, nativeSelect, initialLanguage) {
    const trigger = wrapper.querySelector('.lang-select-trigger');
    const list = wrapper.querySelector('.lang-select-list');
    const options = wrapper.querySelectorAll('.lang-select-option');
    const flagCurrent = wrapper.querySelector('.lang-select-flag-current');
    const labelCurrent = wrapper.querySelector('.lang-select-label-current');

    function updateDisplay(value) {
      const selected = wrapper.querySelector(`.lang-select-option[data-value="${value}"]`);
      if (!selected) return;
      if (flagCurrent) flagCurrent.textContent = selected.dataset.flag || '';
      if (labelCurrent) labelCurrent.textContent = selected.querySelector('span:last-child').textContent.trim();
      options.forEach((opt) => {
        opt.setAttribute('aria-selected', opt.dataset.value === value ? 'true' : 'false');
      });
      if (nativeSelect) nativeSelect.value = value;
    }

    function openList() {
      list.hidden = false;
      trigger.setAttribute('aria-expanded', 'true');
      const selectedOpt = list.querySelector('[aria-selected="true"]') || list.querySelector('.lang-select-option');
      if (selectedOpt) selectedOpt.focus();
    }

    function closeList() {
      list.hidden = true;
      trigger.setAttribute('aria-expanded', 'false');
      trigger.focus();
    }

    updateDisplay(initialLanguage);

    trigger.addEventListener('click', () => {
      list.hidden ? openList() : closeList();
    });

    trigger.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openList();
      }
      if (e.key === 'Escape') closeList();
    });

    options.forEach((opt) => {
      opt.addEventListener('click', () => {
        updateDisplay(opt.dataset.value);
        closeList();
      });
      opt.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          updateDisplay(opt.dataset.value);
          closeList();
        } else if (e.key === 'Escape') {
          closeList();
        } else if (e.key === 'ArrowDown') {
          e.preventDefault();
          const next = opt.nextElementSibling;
          if (next) next.focus();
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          const prev = opt.previousElementSibling;
          if (prev) prev.focus();
        }
      });
    });

    document.addEventListener('click', (e) => {
      if (!wrapper.contains(e.target)) closeList();
    });

    return { update: updateDisplay };
  }

  function initLangQuickPick(wrapper, nativeSelect, onSelect) {
    const options = wrapper.querySelectorAll('.lang-quick-option');

    function select(value) {
      options.forEach((opt) => {
        opt.dataset.selected = opt.dataset.value === value ? 'true' : '';
      });
      if (nativeSelect) nativeSelect.value = value;
      if (onSelect) onSelect(value);
    }

    options.forEach((opt) => {
      opt.addEventListener('click', () => select(opt.dataset.value));
    });

    return { update: select };
  }

  document.addEventListener('DOMContentLoaded', function () {
    const overlay = document.getElementById('cookieConsent');

    if (!overlay) {
      return;
    }

    const acceptButton = overlay.querySelector('[data-cookie-consent="accept"]');
    if (!acceptButton) {
      return;
    }

    const rejectButton = overlay.querySelector('[data-cookie-consent="reject"]');
    const customizeButton = overlay.querySelector('[data-cookie-consent="customize"]');
    const backButton = overlay.querySelector('[data-cookie-consent="back"]');
    const saveButton = overlay.querySelector('[data-cookie-consent="save"]');
    const settingsFocus = overlay.querySelector('[data-cookie-consent-settings-focus]');
    const toggles = overlay.querySelectorAll('[data-cookie-consent-toggle]');
    const languageSelect = overlay.querySelector('[data-language-select]');
    const initialLanguage =
      (window.FSQR_I18N && window.FSQR_I18N.language) ||
      getCookie(LANGUAGE_COOKIE_NAME) ||
      'ja';

    if (languageSelect) {
      languageSelect.value = initialLanguage;
    }

    const langSelectWrapper = overlay.querySelector('[data-lang-select]');
    let langSelectApi = null;
    if (langSelectWrapper) {
      langSelectApi = initLangSelect(langSelectWrapper, languageSelect, initialLanguage);
    }

    const langQuickPickWrapper = overlay.querySelector('[data-lang-quick-pick]');
    if (langQuickPickWrapper) {
      initLangQuickPick(langQuickPickWrapper, languageSelect, (value) => {
        if (langSelectApi) langSelectApi.update(value);
      });
    }

    function showSummaryView() {
      switchView(overlay, 'summary');
      const focusTarget = overlay.querySelector('[data-cookie-consent-focus]');
      focusOnTarget(focusTarget);
    }

    function showSettingsView() {
      switchView(overlay, 'settings');
      focusOnTarget(settingsFocus || toggles[0]);
    }

    window.showCookieConsentPanel = function (viewName) {
      showOverlay(overlay);
      if (viewName === 'settings') {
        showSettingsView();
      } else {
        showSummaryView();
      }
    };

    function saveLanguageAndClose(consentFn) {
      consentFn();
      const selectedLanguage = languageSelect ? languageSelect.value : initialLanguage;
      setLanguageCookie(selectedLanguage);
      hideOverlay(overlay);
      if (selectedLanguage && selectedLanguage !== initialLanguage) {
        window.location.reload();
      }
    }

    function acceptConsent() {
      saveLanguageAndClose(() => setConsentCookie('accepted'));
    }

    function rejectConsent() {
      saveLanguageAndClose(() => setConsentCookie('rejected'));
    }

    function saveCustomConsent() {
      const settings = {};
      toggles.forEach((toggle) => {
        const key = toggle.getAttribute('data-cookie-consent-toggle');
        settings[key] = toggle.checked;
      });
      setConsentCookie(settings);
      const selectedLanguage = languageSelect ? languageSelect.value : initialLanguage;
      setLanguageCookie(selectedLanguage);
      hideOverlay(overlay);
      if (selectedLanguage && selectedLanguage !== initialLanguage) {
        window.location.reload();
      }
    }

    acceptButton.addEventListener('click', acceptConsent);

    if (rejectButton) {
      rejectButton.addEventListener('click', rejectConsent);
    }

    if (customizeButton) {
      customizeButton.addEventListener('click', showSettingsView);
    }

    if (backButton) {
      backButton.addEventListener('click', showSummaryView);
    }

    if (saveButton) {
      saveButton.addEventListener('click', saveCustomConsent);
    }

    overlay.addEventListener('transitionend', function onTransitionEnd() {
      if (!overlay.classList.contains('is-visible')) {
        overlay.removeEventListener('transitionend', onTransitionEnd);
        overlay.removeAttribute('data-cookie-consent-active-view');
      }
    });

    document.querySelectorAll('[data-cookie-settings]').forEach((trigger) => {
      trigger.addEventListener('click', function () {
        window.showCookieConsentPanel('settings');
      });
    });

    if (!hasConsent()) {
      showOverlay(overlay);
      showSummaryView();
    }
  });
})();
