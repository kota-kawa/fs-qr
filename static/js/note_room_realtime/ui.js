(function (window) {
  window.NoteRoomRealtimeModules = window.NoteRoomRealtimeModules || {};
  const modules = window.NoteRoomRealtimeModules;

  function setStatus(context, className, text) {
    context.status.className = className;
    context.status.textContent = text;
  }

  function showEditorFeedback(message, kind) {
    if (typeof setShareFeedback === "function") {
      setShareFeedback(message, kind);
    }
  }

  function updateCharCount(context, content) {
    if (!context.charCount) {
      return;
    }
    const length = (content || "").length;
    context.charCount.textContent = `${length} / ${context.MAX_LENGTH}文字`;
  }

  modules.ui = {
    setStatus: setStatus,
    showEditorFeedback: showEditorFeedback,
    updateCharCount: updateCharCount
  };
})(window);
