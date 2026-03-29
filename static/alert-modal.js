(function () {
  if (window.__fsqrAlertModalInitialized) {
    return;
  }
  window.__fsqrAlertModalInitialized = true;

  let showModalImpl = null;

  window.showAlertModal = function (text) {
    if (typeof showModalImpl === "function") {
      showModalImpl(text);
      return;
    }
    window.alert(String(text ?? ""));
  };

  function setupAlertModal() {
    const overlay = document.getElementById("fsqrAlertModalOverlay");
    const message = document.getElementById("fsqrAlertModalMessage");
    const closeButton = document.getElementById("fsqrAlertModalClose");

    if (!overlay || !message || !closeButton) {
      return;
    }

    const openClass = "fsqr-alert-open";
    let previousActiveElement = null;

    function closeModal() {
      overlay.classList.remove("is-visible");
      overlay.setAttribute("aria-hidden", "true");
      document.body.classList.remove(openClass);
      if (previousActiveElement && typeof previousActiveElement.focus === "function") {
        previousActiveElement.focus();
      }
    }

    function showModal(text) {
      previousActiveElement = document.activeElement;
      message.textContent = String(text ?? "");
      overlay.classList.add("is-visible");
      overlay.setAttribute("aria-hidden", "false");
      document.body.classList.add(openClass);
      closeButton.focus();
    }

    closeButton.addEventListener("click", closeModal);
    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) {
        closeModal();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && overlay.classList.contains("is-visible")) {
        closeModal();
      }
    });
    showModalImpl = showModal;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupAlertModal);
  } else {
    setupAlertModal();
  }
})();
