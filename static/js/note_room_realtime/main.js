(function (window) {
  window.NoteRoomRealtimeModules = window.NoteRoomRealtimeModules || {};
  const modules = window.NoteRoomRealtimeModules;

  const context = modules.core.createContext();
  const syncHandlers = modules.sync.createSyncHandlers(context);
  const clipboardHandlers = modules.clipboard.createClipboardHandlers(context);
  const socketHandlers = modules.socket.createSocketHandlers(context, syncHandlers);

  syncHandlers.bindEditorInput();
  clipboardHandlers.bindButtons();
  modules.ui.updateCharCount(context, context.editor.value);
  socketHandlers.connectWebSocket();
})(window);
