(function () {
  const CONSENT_COOKIE_NAME = 'fsqr_cookie_consent';
  const CONSENT_DURATION_DAYS = 365;

  function setConsentCookie() {
    const expires = new Date(Date.now() + CONSENT_DURATION_DAYS * 24 * 60 * 60 * 1000);
    const cookieValue = `${CONSENT_COOKIE_NAME}=1; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
    document.cookie = cookieValue;
  }

  function hasConsent() {
    return document.cookie.split(';').some((cookie) => cookie.trim().startsWith(`${CONSENT_COOKIE_NAME}=`));
  }

  function hideOverlay(overlay) {
    overlay.classList.remove('is-visible');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.style.removeProperty('overflow');
  }

  function showOverlay(overlay) {
    overlay.classList.add('is-visible');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    const focusTarget = overlay.querySelector('[data-cookie-consent-focus]');
    if (focusTarget) {
      focusTarget.focus();
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

    function acceptConsent() {
      setConsentCookie();
      hideOverlay(overlay);
    }

    acceptButton.addEventListener('click', acceptConsent);

    showOverlay(overlay);
  });
})();
