(() => {
  const INTERACTIVE_SELECTOR = [
    'a[href]',
    'button',
    'input:not([type="hidden"])',
    'select',
    'textarea',
    'summary',
    '[role="button"]',
  ].join(',');

  const MAX_LABEL_LENGTH = 80;

  function normalizeText(value) {
    return (value || '').replace(/\s+/g, ' ').trim();
  }

  function toSafeLabel(value) {
    const normalized = normalizeText(value);
    if (!normalized) {
      return '';
    }
    if (normalized.length <= MAX_LABEL_LENGTH) {
      return normalized;
    }
    return `${normalized.slice(0, MAX_LABEL_LENGTH - 3)}...`;
  }

  function getAssociatedLabel(element) {
    if (element.labels && element.labels.length) {
      return toSafeLabel(
        Array.from(element.labels)
          .map((label) => label.textContent)
          .join(' ')
      );
    }

    const wrappingLabel = element.closest('label');
    if (wrappingLabel) {
      return toSafeLabel(wrappingLabel.textContent);
    }

    return '';
  }

  function getCandidateLabel(element) {
    const type = (element.getAttribute('type') || '').toLowerCase();

    const fromData = toSafeLabel(element.getAttribute('data-default-label'));
    if (fromData) {
      return fromData;
    }

    const fromTitle = toSafeLabel(element.getAttribute('title'));
    if (fromTitle) {
      return fromTitle;
    }

    const fromLabel = getAssociatedLabel(element);
    if (fromLabel) {
      return fromLabel;
    }

    if (type === 'file') {
      return 'ファイルを選択';
    }

    if (type === 'submit' || type === 'button' || type === 'reset') {
      const fromValue = toSafeLabel(element.value);
      if (fromValue) {
        return fromValue;
      }
    }

    const fromPlaceholder = toSafeLabel(element.getAttribute('placeholder'));
    if (fromPlaceholder) {
      return fromPlaceholder;
    }

    const imageWithAlt = element.querySelector('img[alt]');
    if (imageWithAlt) {
      const fromAlt = toSafeLabel(imageWithAlt.getAttribute('alt'));
      if (fromAlt) {
        return fromAlt;
      }
    }

    const fromText = toSafeLabel(element.textContent);
    if (fromText) {
      return fromText;
    }

    if (element.tagName.toLowerCase() === 'a') {
      return 'リンクを開く';
    }

    if (element.tagName.toLowerCase() === 'button') {
      return 'ボタン';
    }

    return '';
  }

  function ensureAriaLabel(element) {
    if (!(element instanceof HTMLElement)) {
      return;
    }

    if (!element.matches(INTERACTIVE_SELECTOR)) {
      return;
    }

    if (element.hasAttribute('aria-label') || element.hasAttribute('aria-labelledby')) {
      return;
    }

    if (element.getAttribute('aria-hidden') === 'true' || element.closest('[aria-hidden="true"]')) {
      return;
    }

    const candidate = getCandidateLabel(element);
    if (!candidate) {
      return;
    }

    element.setAttribute('aria-label', candidate);
  }

  function processInteractiveElements(root = document) {
    if (!(root instanceof Element || root instanceof Document)) {
      return;
    }

    if (root instanceof Element) {
      ensureAriaLabel(root);
    }

    root.querySelectorAll(INTERACTIVE_SELECTOR).forEach(ensureAriaLabel);
  }

  function setupObserver() {
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type !== 'childList') {
          continue;
        }

        mutation.addedNodes.forEach((node) => {
          if (!(node instanceof Element)) {
            return;
          }
          processInteractiveElements(node);
        });
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });
  }

  function init() {
    processInteractiveElements(document);
    setupObserver();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
