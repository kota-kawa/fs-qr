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

  function setMergeStatus(context, text, kind) {
    if (!context.mergeStatus) {
      return;
    }
    context.mergeStatus.textContent = text || "";
    if (!text) {
      context.mergeStatus.style.color = "var(--text-medium)";
      return;
    }
    if (kind === "warning") {
      context.mergeStatus.style.color = "#92400e";
      return;
    }
    if (kind === "success") {
      context.mergeStatus.style.color = "#166534";
      return;
    }
    context.mergeStatus.style.color = "var(--text-medium)";
  }

  modules.ui = {
    setStatus: setStatus,
    showEditorFeedback: showEditorFeedback,
    updateCharCount: updateCharCount,
    setMergeStatus: setMergeStatus
  };
})(window);
