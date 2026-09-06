(function (window) {
  const appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error("App namespace is not initialized.");
  }
  const modules = appNamespace.api.getModuleNamespace("noteRoomRealtime");
  const core = modules.core;
  const sharePanel = appNamespace.api.getShared("sharePanel");

  function showEditorFeedback(message, kind) {
    if (sharePanel && typeof sharePanel.setShareFeedback === "function") {
      sharePanel.setShareFeedback(message, kind);
    }
  }

  function updateCharCount(context, content) {
    if (!context.charCount) return;
    context.charCount.textContent = core.formatMessage(
      "note.char_count",
      "{length} / {max_length} characters",
      { length: (content || "").length, max_length: context.MAX_LENGTH }
    );
  }

  modules.ui = {
    showEditorFeedback: showEditorFeedback,
    updateCharCount: updateCharCount
  };
})(window);
