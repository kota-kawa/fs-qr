(function () {
  const CONSENT_COOKIE_NAME = 'fsqr_cookie_consent';
  const CONSENT_DURATION_DAYS = 365;

  function setConsentCookie(value = 'accepted') {
    const normalizedValue =
      typeof value === 'string'
        ? value
        : JSON.stringify({ necessary: true, ...value });
    const expires = new Date(Date.now() + CONSENT_DURATION_DAYS * 24 * 60 * 60 * 1000);
    const cookieValue = `${CONSENT_COOKIE_NAME}=${encodeURIComponent(normalizedValue)}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
    document.cookie = cookieValue;
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

  document.addEventListener('DOMContentLoaded', function () {
    const overlay = document.getElementById('cookieConsent');

    if (!overlay || hasConsent()) {
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

    function showSummaryView() {
      switchView(overlay, 'summary');
      const focusTarget = overlay.querySelector('[data-cookie-consent-focus]');
      focusOnTarget(focusTarget);
    }

    function showSettingsView() {
      switchView(overlay, 'settings');
      focusOnTarget(settingsFocus || toggles[0]);
    }

    function acceptConsent() {
      setConsentCookie('accepted');
      hideOverlay(overlay);
    }

    function rejectConsent() {
      setConsentCookie('rejected');
      hideOverlay(overlay);
    }

    function saveCustomConsent() {
      const settings = {};
      toggles.forEach((toggle) => {
        const key = toggle.getAttribute('data-cookie-consent-toggle');
        settings[key] = toggle.checked;
      });
      setConsentCookie(settings);
      hideOverlay(overlay);
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

    showOverlay(overlay);
    showSummaryView();
  });
})();
