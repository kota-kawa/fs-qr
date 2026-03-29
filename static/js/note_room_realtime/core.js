(function (window) {
  window.NoteRoomRealtimeModules = window.NoteRoomRealtimeModules || {};
  const modules = window.NoteRoomRealtimeModules;

  function getConfig() {
    return window.NoteRoomRealtimeConfig || {};
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

  function createContext() {
    const config = getConfig();

    return {
      room: config.room,
      roomPassword: config.roomPassword,
      editor: document.getElementById("editor"),
      status: document.getElementById("status"),
      charCount: document.getElementById("charCount"),
      pasteButton: document.getElementById("pasteButton"),
      copyAllButton: document.getElementById("copyAllButton"),
      MAX_LENGTH: 10000,
      lastStamp: "",
      selfEdit: false,
      contentAtLastSync: "",
      selfEditTimeout: null,
      ws: null,
      reconnectAttempt: 0,
      reconnectTimer: null,
      pendingContent: null,
      typTimer: null
    };
  }

  modules.core = {
    getConfig: getConfig,
    createLogger: createLogger,
    createContext: createContext
  };
})(window);
