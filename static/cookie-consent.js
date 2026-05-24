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

  function getSupportedLanguageValues() {
    const configuredLanguages = window.FSQR_I18N && window.FSQR_I18N.supportedLanguages;
    if (Array.isArray(configuredLanguages) && configuredLanguages.length) {
      return configuredLanguages;
    }
    return Array.from(document.querySelectorAll('[data-language-select] option'))
      .map((option) => option.value)
      .filter(Boolean);
  }

  function getSupportedLanguageValue(value, fallback = '') {
    const supportedLanguages = getSupportedLanguageValues();
    return supportedLanguages.includes(value) ? value : fallback;
  }

  function setLanguageCookie(value) {
    if (getSupportedLanguageValue(value)) {
      setCookie(LANGUAGE_COOKIE_NAME, value);
    }
  }

  function hasConsent() {
    return document.cookie.split(';').some((cookie) => cookie.trim().startsWith(`${CONSENT_COOKIE_NAME}=`));
  }

  function getStoredConsentSettings() {
    const storedValue = getCookie(CONSENT_COOKIE_NAME);

    if (storedValue === 'accepted') {
      return { analytics: true, marketing: true };
    }

    if (storedValue === 'rejected' || !storedValue) {
      return { analytics: false, marketing: false };
    }

    try {
      const parsed = JSON.parse(storedValue);
      return {
        analytics: Boolean(parsed.analytics),
        marketing: Boolean(parsed.marketing)
      };
    } catch (error) {
      return { analytics: false, marketing: false };
    }
  }

  function getFocusableElements(container) {
    return Array.from(
      container.querySelectorAll(
        'a[href], button:not([disabled]):not([hidden]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    ).filter((element) => {
      return !element.hidden && element.offsetParent !== null && element.getAttribute('aria-hidden') !== 'true';
    });
  }

  let lastFocusedElement = null;
  let scrollLockY = 0;
  const langSelectClosers = [];

  function closeOpenLangSelects() {
    langSelectClosers.forEach((close) => close({ restoreFocus: false }));
  }

  function lockBodyScroll() {
    scrollLockY = window.scrollY;
    document.body.style.position = 'fixed';
    document.body.style.top = `-${scrollLockY}px`;
    document.body.style.left = '0';
    document.body.style.right = '0';
    document.body.style.overflow = 'hidden';
  }

  function unlockBodyScroll() {
    document.body.style.removeProperty('position');
    document.body.style.removeProperty('top');
    document.body.style.removeProperty('left');
    document.body.style.removeProperty('right');
    document.body.style.removeProperty('overflow');
    window.scrollTo(0, scrollLockY);
  }

  function hideOverlay(overlay, options = {}) {
    closeOpenLangSelects();
    overlay.classList.remove('is-visible');
    overlay.setAttribute('aria-hidden', 'true');
    overlay.removeAttribute('data-cookie-consent-active-view');
    overlay.removeAttribute('data-cookie-consent-closeable');
    unlockBodyScroll();

    if (options.restoreFocus !== false && lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
      lastFocusedElement.focus();
    }
  }

  function setCloseable(overlay, closeable) {
    const closeButton = overlay.querySelector('[data-cookie-consent="close"]');
    overlay.setAttribute('data-cookie-consent-closeable', closeable ? 'true' : 'false');
    if (closeButton) {
      closeButton.hidden = !closeable;
    }
  }

  function showOverlay(overlay, options = {}) {
    lastFocusedElement = document.activeElement;
    setCloseable(overlay, Boolean(options.closeable));
    overlay.classList.add('is-visible');
    overlay.setAttribute('aria-hidden', 'false');
    lockBodyScroll();
  }

  function switchView(overlay, viewName) {
    closeOpenLangSelects();
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

  function initLangSelect(wrapper, nativeSelect, initialLanguage, onSelect) {
    const trigger = wrapper.querySelector('.lang-select-trigger');
    const list = wrapper.querySelector('.lang-select-list');
    const options = wrapper.querySelectorAll('.lang-select-option');
    const flagCurrent = wrapper.querySelector('.lang-select-flag-current');
    const labelCurrent = wrapper.querySelector('.lang-select-label-current');

    // Portal the list to <body> so its position:fixed is relative to the
    // viewport, not to a transformed ancestor (the dialog animation creates
    // a containing block that would otherwise mis-position the list).
    if (list && list.parentNode !== document.body) {
      document.body.appendChild(list);
    }

    function updateDisplay(value, displayOptions = {}) {
      const selected = list.querySelector(`.lang-select-option[data-value="${value}"]`);
      if (!selected) return;
      if (flagCurrent) flagCurrent.textContent = selected.dataset.flag || '';
      if (labelCurrent) labelCurrent.textContent = selected.querySelector('span:last-child').textContent.trim();
      options.forEach((opt) => {
        opt.setAttribute('aria-selected', opt.dataset.value === value ? 'true' : 'false');
      });
      if (nativeSelect) nativeSelect.value = value;
      if (!displayOptions.silent && onSelect) onSelect(value);
    }

    function positionList() {
      const tRect = trigger.getBoundingClientRect();
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const gap = 6;
      const margin = 12;
      const spaceBelow = vh - tRect.bottom - gap - margin;
      const spaceAbove = tRect.top - gap - margin;
      const openDown = spaceBelow >= spaceAbove || spaceBelow >= 200;
      const availableH = Math.max(openDown ? spaceBelow : spaceAbove, 120);
      const listH = Math.min(360, availableH);

      list.style.maxHeight = listH + 'px';
      list.style.minWidth = Math.min(tRect.width, vw - 2 * margin) + 'px';
      list.style.maxWidth = (vw - 2 * margin) + 'px';

      if (openDown) {
        list.style.top = (tRect.bottom + gap) + 'px';
        list.style.bottom = 'auto';
      } else {
        list.style.bottom = (vh - tRect.top + gap) + 'px';
        list.style.top = 'auto';
      }

      // Horizontal: align list's right edge to trigger's right edge by default;
      // if that pushes the list off-screen on the left, clamp to viewport margin.
      const rightGap = Math.max(margin, vw - tRect.right);
      const leftIfRight = vw - rightGap - Math.min(tRect.width, vw - 2 * margin);
      if (leftIfRight >= margin) {
        list.style.right = rightGap + 'px';
        list.style.left = 'auto';
      } else {
        list.style.left = margin + 'px';
        list.style.right = margin + 'px';
      }
    }

    let repositionScheduled = false;
    function scheduleReposition() {
      if (list.hidden || repositionScheduled) return;
      repositionScheduled = true;
      requestAnimationFrame(() => {
        repositionScheduled = false;
        if (!list.hidden) positionList();
      });
    }

    function openList() {
      list.hidden = false;
      trigger.setAttribute('aria-expanded', 'true');
      positionList();
      const selectedOpt = list.querySelector('[aria-selected="true"]') || list.querySelector('.lang-select-option');
      if (selectedOpt) {
        selectedOpt.scrollIntoView({ block: 'nearest' });
        selectedOpt.focus();
      }
    }

    function closeList(opts = {}) {
      if (list.hidden) return;
      list.hidden = true;
      list.style.cssText = '';
      trigger.setAttribute('aria-expanded', 'false');
      if (opts.restoreFocus !== false) trigger.focus();
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
      if (list.hidden) return;
      if (wrapper.contains(e.target) || list.contains(e.target)) return;
      closeList({ restoreFocus: false });
    });

    window.addEventListener('resize', scheduleReposition);
    window.addEventListener('scroll', scheduleReposition, true);
    langSelectClosers.push(closeList);

    return { update: updateDisplay };
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
    const closeButton = overlay.querySelector('[data-cookie-consent="close"]');
    const saveButton = overlay.querySelector('[data-cookie-consent="save"]');
    const settingsFocus = overlay.querySelector('[data-cookie-consent-settings-focus]');
    const toggles = overlay.querySelectorAll('[data-cookie-consent-toggle]');
    const languageSelect = overlay.querySelector('[data-language-select]');
    const initialLanguage = getSupportedLanguageValue(
      (window.FSQR_I18N && window.FSQR_I18N.language) ||
      getCookie(LANGUAGE_COOKIE_NAME),
      'ja'
    );

    if (languageSelect) {
      languageSelect.value = initialLanguage;
    }

    const langSelectWrappers = Array.from(overlay.querySelectorAll('[data-lang-select]'));
    const langSelectApis = [];
    let settingsBackAction = 'summary';

    langSelectWrappers.forEach((wrapper, i) => {
      const api = initLangSelect(wrapper, languageSelect, initialLanguage, (value) => {
        langSelectApis.forEach((otherApi, j) => {
          if (j !== i) otherApi.update(value, { silent: true });
        });
        if (value && value !== initialLanguage) {
          setLanguageCookie(value);
          window.location.reload();
        }
      });
      langSelectApis.push(api);
    });

    function syncTogglesFromStoredConsent() {
      const storedSettings = getStoredConsentSettings();
      toggles.forEach((toggle) => {
        const key = toggle.getAttribute('data-cookie-consent-toggle');
        toggle.checked = Boolean(storedSettings[key]);
      });
    }

    function showSummaryView() {
      switchView(overlay, 'summary');
      const focusTarget = overlay.querySelector('[data-cookie-consent-focus]');
      focusOnTarget(focusTarget);
    }

    function showSettingsView(options = {}) {
      syncTogglesFromStoredConsent();
      settingsBackAction = options.backAction || 'summary';
      switchView(overlay, 'settings');
      focusOnTarget(settingsFocus || toggles[0]);
    }

    window.showCookieConsentPanel = function (viewName) {
      showOverlay(overlay, { closeable: true });
      if (viewName === 'settings') {
        showSettingsView({ backAction: 'close' });
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
      backButton.addEventListener('click', () => {
        if (
          settingsBackAction === 'close'
          && overlay.getAttribute('data-cookie-consent-closeable') === 'true'
        ) {
          hideOverlay(overlay);
          return;
        }
        showSummaryView();
      });
    }

    if (saveButton) {
      saveButton.addEventListener('click', saveCustomConsent);
    }

    if (closeButton) {
      closeButton.addEventListener('click', () => {
        if (overlay.getAttribute('data-cookie-consent-closeable') === 'true') {
          hideOverlay(overlay);
        }
      });
    }

    overlay.addEventListener('click', (event) => {
      if (
        event.target === overlay
        && overlay.getAttribute('data-cookie-consent-closeable') === 'true'
      ) {
        hideOverlay(overlay);
      }
    });

    overlay.addEventListener('keydown', (event) => {
      if (!overlay.classList.contains('is-visible')) return;

      if (event.key === 'Escape' && overlay.getAttribute('data-cookie-consent-closeable') === 'true') {
        hideOverlay(overlay);
        return;
      }

      if (event.key !== 'Tab') return;

      const focusableElements = getFocusableElements(overlay);
      if (!focusableElements.length) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
      } else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    });

    overlay.addEventListener('transitionend', function onTransitionEnd(e) {
      if (e.target !== overlay) return;
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
      showOverlay(overlay, { closeable: false });
      showSummaryView();
    }
  });
})();
