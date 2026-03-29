(function (window) {
  window.NoteRoomRealtimeModules = window.NoteRoomRealtimeModules || {};
  const modules = window.NoteRoomRealtimeModules;
  const ui = modules.ui;

  function toStampValue(value) {
    if (typeof value !== "string") {
      return "";
    }
    return value;
  }

  function isStampNewer(candidate, baseline) {
    const candidateStamp = toStampValue(candidate);
    const baselineStamp = toStampValue(baseline);
    if (!candidateStamp) {
      return false;
    }
    if (!baselineStamp) {
      return true;
    }
    return candidateStamp > baselineStamp;
  }

  function getAdaptiveAckTimeoutMs(context) {
    const floorMs = Number(context.selfEditTimeoutMs || 0);
    const rttMs = Number(context.ackRttMs || 0);
    if (Number.isFinite(rttMs) && rttMs > 0) {
      return Math.max(floorMs, Math.ceil(rttMs * 4));
    }
    return floorMs;
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
    if (!isStampNewer(updatedAt, context.lastStamp) && updatedAt !== context.lastStamp) {
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

  function queuePendingRemoteUpdate(context, payload) {
    if (!payload || payload.content === undefined || payload.updated_at === undefined) {
      return;
    }
    if (
      context.pendingRemoteUpdate
      && !isStampNewer(payload.updated_at, context.pendingRemoteUpdate.updatedAt)
      && payload.updated_at !== context.pendingRemoteUpdate.updatedAt
    ) {
      return;
    }
    context.pendingRemoteUpdate = {
      content: payload.content,
      updatedAt: payload.updated_at,
      status: payload.status || ""
    };
  }

  function flushPendingRemoteUpdate(context, defaultMessage) {
    if (!context.pendingRemoteUpdate) {
      return false;
    }
    const queued = context.pendingRemoteUpdate;
    context.pendingRemoteUpdate = null;
    if (isStampNewer(queued.updatedAt, context.lastStamp)) {
      applyServerContent(context, queued.content, queued.updatedAt, defaultMessage || "Updated by others");
      return true;
    }
    return false;
  }

  function finalizeAckRtt(context, ackForRequestId) {
    const inFlight = context.inFlightSave;
    if (!inFlight || inFlight.requestId !== ackForRequestId) {
      return;
    }
    const elapsed = Date.now() - inFlight.startedAt;
    if (!Number.isFinite(elapsed) || elapsed <= 0) {
      return;
    }
    if (!Number.isFinite(context.ackRttMs) || context.ackRttMs <= 0) {
      context.ackRttMs = elapsed;
      return;
    }
    context.ackRttMs = Math.round((context.ackRttMs * 0.7) + (elapsed * 0.3));
  }

  modules.selfEdit = {
    getAdaptiveAckTimeoutMs: getAdaptiveAckTimeoutMs,
    applyServerContent: applyServerContent,
    queuePendingRemoteUpdate: queuePendingRemoteUpdate,
    flushPendingRemoteUpdate: flushPendingRemoteUpdate,
    finalizeAckRtt: finalizeAckRtt,
    isStampNewer: isStampNewer
  };
})(window);
