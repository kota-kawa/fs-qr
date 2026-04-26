(function () {
  if (window.__fsqrAlertModalInitialized) {
    return;
  }
  window.__fsqrAlertModalInitialized = true;

  let showModalImpl = null;
  let showConfirmModalImpl = null;

  window.showAlertModal = function (text) {
    if (typeof showModalImpl === "function") {
      showModalImpl(text);
      return;
    }
    window.alert(String(text ?? ""));
  };

  window.showConfirmModal = function (text, options) {
    if (typeof showConfirmModalImpl === "function") {
      return showConfirmModalImpl(text, options);
    }
    return Promise.resolve(window.confirm(String(text ?? "")));
  };

  function setupAlertModal() {
    const overlay = document.getElementById("fsqrAlertModalOverlay");
    const title = document.getElementById("fsqrAlertModalTitle");
    const message = document.getElementById("fsqrAlertModalMessage");
    const closeButton = document.getElementById("fsqrAlertModalClose");
    const cancelButton = document.getElementById("fsqrAlertModalCancel");

    if (!overlay || !title || !message || !closeButton || !cancelButton) {
      return;
    }

    const openClass = "fsqr-alert-open";
    let previousActiveElement = null;
    let activeResolver = null;
    let closeValue = false;

    function closeModal() {
      overlay.classList.remove("is-visible");
      overlay.setAttribute("aria-hidden", "true");
      document.body.classList.remove(openClass);
      if (previousActiveElement && typeof previousActiveElement.focus === "function") {
        previousActiveElement.focus();
      }
      if (typeof activeResolver === "function") {
        const resolver = activeResolver;
        activeResolver = null;
        resolver(closeValue);
      }
    }

    function openModal(text, options) {
      const normalizedOptions = options || {};
      previousActiveElement = document.activeElement;
      closeValue = false;
      title.textContent = normalizedOptions.title || "お知らせ";
      message.textContent = String(text ?? "");
      closeButton.textContent = normalizedOptions.confirmLabel || "OK";
      cancelButton.textContent = normalizedOptions.cancelLabel || "キャンセル";
      cancelButton.hidden = normalizedOptions.showCancel !== true;
      overlay.classList.add("is-visible");
      overlay.setAttribute("aria-hidden", "false");
      document.body.classList.add(openClass);
      (normalizedOptions.showCancel === true ? cancelButton : closeButton).focus();
    }

    function showModal(text) {
      activeResolver = null;
      openModal(text);
    }

    function showConfirmModal(text, options) {
      return new Promise(function (resolve) {
        activeResolver = resolve;
        openModal(text, Object.assign({
          title: "確認",
          confirmLabel: "削除する",
          cancelLabel: "キャンセル",
          showCancel: true
        }, options || {}));
      });
    }

    closeButton.addEventListener("click", function () {
      closeValue = true;
      closeModal();
    });
    cancelButton.addEventListener("click", function () {
      closeValue = false;
      closeModal();
    });
    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) {
        closeValue = false;
        closeModal();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && overlay.classList.contains("is-visible")) {
        closeValue = false;
        closeModal();
      }
    });
    showModalImpl = showModal;
    showConfirmModalImpl = showConfirmModal;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupAlertModal);
  } else {
    setupAlertModal();
  }
})();
