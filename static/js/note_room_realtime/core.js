(function (window) {
  const appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error("App namespace is not initialized.");
  }
  const modules = appNamespace.api.getModuleNamespace("noteRoomRealtime");

  function translate(key, fallback) {
    if (window.FSQR_I18N && typeof window.FSQR_I18N.t === "function") {
      return window.FSQR_I18N.t(key, fallback);
    }
    return fallback || key;
  }

  function formatMessage(key, fallback, replacements) {
    let message = translate(key, fallback);
    Object.keys(replacements || {}).forEach(function (name) {
      message = message.replace(new RegExp(`\\{${name}\\}`, "g"), String(replacements[name]));
    });
    return message;
  }

  function createLogger(enabled) {
    return {
      error: function () {
        if (enabled && window.console && typeof window.console.error === "function") {
          window.console.error.apply(window.console, arguments);
        }
      }
    };
  }

  function createContext() {
    const config = appNamespace.api.getConfig("noteRoomRealtime");
    const parsedLimit = Number(config.limits?.maxContentLength);
    return {
      room: config.room,
      editor: document.getElementById("editor"),
      status: document.getElementById("status"),
      charCount: document.getElementById("charCount"),
      pasteButton: document.getElementById("pasteButton"),
      copyAllButton: document.getElementById("copyAllButton"),
      txtDownloadButton: document.getElementById("txtDownloadButton"),
      pdfDownloadButton: document.getElementById("pdfDownloadButton"),
      MAX_LENGTH: Number.isFinite(parsedLimit) && parsedLimit > 0 ? parsedLimit : 10000,
      logger: createLogger(Boolean(config.debug))
    };
  }

  modules.core = {
    translate: translate,
    formatMessage: formatMessage,
    createContext: createContext
  };
})(window);
