(function (window) {
  window.NoteRoomRealtimeModules = window.NoteRoomRealtimeModules || {};
  const modules = window.NoteRoomRealtimeModules;

  function getConfig() {
    return window.NoteRoomRealtimeConfig || {};
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
    createContext: createContext
  };
})(window);
