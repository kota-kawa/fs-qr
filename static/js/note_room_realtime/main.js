(function (window) {
  const appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error("App namespace is not initialized.");
  }
  const modules = appNamespace.api.getModuleNamespace("noteRoomRealtime");

  const context = modules.core.createContext();
  const config = modules.core.getConfig();
  context.logger = modules.core.createLogger(Boolean(config.debug));
  const syncHandlers = modules.sync.createSyncHandlers(context);
  const clipboardHandlers = modules.clipboard.createClipboardHandlers(context);
  const socketHandlers = modules.socket.createSocketHandlers(context, syncHandlers);

  syncHandlers.bindEditorInput();
  clipboardHandlers.bindButtons();
  modules.ui.updateCharCount(context, context.editor.value);
  socketHandlers.connectWebSocket();
})(window);
