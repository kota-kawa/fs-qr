(function (window) {
  window.NoteRoomRealtimeModules = window.NoteRoomRealtimeModules || {};
  const modules = window.NoteRoomRealtimeModules;
  const ui = modules.ui;

  function setSelfEdit(context, value, timeoutMs = 8000) {
    context.selfEdit = value;

    if (context.selfEditTimeout) {
      clearTimeout(context.selfEditTimeout);
      context.selfEditTimeout = null;
    }

    if (value && timeoutMs > 0) {
      context.selfEditTimeout = setTimeout(() => {
        if (context.selfEdit) {
          const logger = context.logger || { log: function () {}, warn: function () {}, error: function () {} };
          logger.warn("selfEdit flag was stuck, resetting");
          context.selfEdit = false;
          context.status.className = "badge bg-warning";
          context.status.textContent = "Connection timeout";
        }
      }, timeoutMs);
    }
  }

  function isCursorSafeToRestore(oldContent, newContent, cursorStart, cursorEnd) {
    if (cursorStart < 0 || cursorEnd < 0 || cursorStart > cursorEnd) {
      return false;
    }

    const lengthDiff = Math.abs(newContent.length - oldContent.length);
    const relativeDiff = lengthDiff / Math.max(oldContent.length, 1);
    if (relativeDiff > 0.3) {
      return false;
    }

    const contextRange = 50;
    const contextStart = Math.max(0, cursorStart - contextRange);
    const contextEnd = Math.min(oldContent.length, cursorEnd + contextRange);

    const oldContext = oldContent.substring(contextStart, contextEnd);
    const newContextEnd = Math.min(newContent.length, contextEnd);
    const newContext = newContent.substring(contextStart, newContextEnd);

    return oldContext === newContext || lengthDiff < 10;
  }

  function applyServerContent(context, newContent, updatedAt, message) {
    if (newContent === undefined || updatedAt === undefined) {
      return;
    }

    const isEditorFocused = document.activeElement === context.editor;
    const oldContent = context.editor.value;
    let cursorStart = 0;
    let cursorEnd = 0;

    if (isEditorFocused) {
      cursorStart = context.editor.selectionStart;
      cursorEnd = context.editor.selectionEnd;
    }

    context.editor.value = newContent;
    ui.updateCharCount(context, newContent);

    if (isEditorFocused && isCursorSafeToRestore(oldContent, newContent, cursorStart, cursorEnd)) {
      const newLength = newContent.length;
      context.editor.setSelectionRange(Math.min(cursorStart, newLength), Math.min(cursorEnd, newLength));
      context.editor.focus();
    }

    context.lastStamp = updatedAt;
    context.contentAtLastSync = newContent;

    if (message) {
      ui.setStatus(context, "badge bg-warning text-dark", message);
    }
  }

  modules.selfEdit = {
    setSelfEdit: setSelfEdit,
    applyServerContent: applyServerContent
  };
})(window);
