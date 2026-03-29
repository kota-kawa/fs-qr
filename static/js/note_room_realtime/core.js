(function (window) {
  const appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error("App namespace is not initialized.");
  }
  const modules = appNamespace.api.getModuleNamespace("noteRoomRealtime");
  const SYNC_STATES = Object.freeze({
    // Local state machine for note sync lifecycle.
    BOOTSTRAPPING: "bootstrapping",
    IDLE: "idle",
    DIRTY: "dirty",
    SAVING: "saving",
    SAVING_DIRTY: "saving_dirty",
    OFFLINE_DIRTY: "offline_dirty"
  });

  function getConfig() {
    return appNamespace.api.getConfig("noteRoomRealtime");
  }

  function createLogger(enabled) {
    function callConsole(method, args) {
      if (!enabled || typeof window.console === "undefined") {
        return;
      }
      if (typeof window.console[method] === "function") {
        window.console[method].apply(window.console, args);
        return;
      }
      if (typeof window.console.log === "function") {
        window.console.log.apply(window.console, args);
      }
    }

    return {
      log: function () {
        callConsole("log", arguments);
      },
      warn: function () {
        callConsole("warn", arguments);
      },
      error: function () {
        callConsole("error", arguments);
      }
    };
  }

  function isPlainObject(value) {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
  }

  function safeParseJson(rawText, logger, label) {
    if (typeof rawText !== "string") {
      if (logger && typeof logger.warn === "function") {
        logger.warn(`${label || "JSON payload"} is not a string.`);
      }
      return null;
    }

    try {
      return JSON.parse(rawText);
    } catch (error) {
      if (logger && typeof logger.warn === "function") {
        logger.warn(`${label || "JSON payload"} parse failed.`, error);
      }
      return null;
    }
  }

  function createContext() {
    const config = getConfig();
    const limits = config.limits || {};
    const parsedMaxContentLength = Number(limits.maxContentLength);
    const parsedSelfEditTimeoutMs = Number(limits.selfEditTimeoutMs);
    const maxLength = Number.isFinite(parsedMaxContentLength) && parsedMaxContentLength > 0
      ? parsedMaxContentLength
      : 1;
    const selfEditTimeoutMs = Number.isFinite(parsedSelfEditTimeoutMs) && parsedSelfEditTimeoutMs > 0
      ? parsedSelfEditTimeoutMs
      : 1000;

    return {
      room: config.room,
      roomPassword: config.roomPassword,
      websocketCsrfToken: config.websocketCsrfToken,
      editor: document.getElementById("editor"),
      status: document.getElementById("status"),
      mergeStatus: document.getElementById("mergeStatus"),
      charCount: document.getElementById("charCount"),
      pasteButton: document.getElementById("pasteButton"),
      copyAllButton: document.getElementById("copyAllButton"),
      MAX_LENGTH: maxLength,
      selfEditTimeoutMs: selfEditTimeoutMs,
      lastStamp: "",
      syncState: SYNC_STATES.BOOTSTRAPPING,
      contentAtLastSync: "",
      ws: null,
      reconnectAttempt: 0,
      reconnectTimer: null,
      pendingContent: null,
      pendingBaseContent: null,
      inFlightSave: null,
      pendingRemoteUpdate: null,
      saveSequence: 0,
      ackRttMs: null,
      typTimer: null
    };
  }

  modules.core = {
    getConfig: getConfig,
    createLogger: createLogger,
    isPlainObject: isPlainObject,
    safeParseJson: safeParseJson,
    createContext: createContext,
    SYNC_STATES: SYNC_STATES
  };
})(window);
