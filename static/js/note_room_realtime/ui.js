(function (window) {
  const appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error("App namespace is not initialized.");
  }
  const modules = appNamespace.api.getModuleNamespace("noteRoomRealtime");
  const core = modules.core || {};

  function translate(key, fallback) {
    if (window.FSQR_I18N && typeof window.FSQR_I18N.t === "function") {
      return window.FSQR_I18N.t(key, fallback);
    }
    return fallback || key;
  }

  const STATUS_LABELS = {
    "Connected": translate("note.connected", "Connected"),
    "Connection error": translate("note.connection_error", "Connection error"),
    "Conflict resolved": translate("note.conflict_resolved", "Conflict resolved"),
    "Offline (reconnecting...)": translate("note.offline_reconnecting", "Offline (reconnecting...)"),
    "Remote update queued": translate("note.remote_update_queued", "Remote update queued"),
    "Reconnecting...": translate("note.reconnecting", "Reconnecting..."),
    "Saved": translate("note.saved", "Saved"),
    "Saved (Merged)": translate("note.saved_merged", "Saved (merged)"),
    "Saving...": translate("note.saving", "Saving..."),
    "Sync timeout (retrying)": translate("note.sync_timeout", "Sync timeout (retrying)"),
    "Up-to-date": translate("note.up_to_date", "Up to date")
  };

  function formatLastSync(date) {
    if (!date) {
      return "";
    }
    const diffMs = Date.now() - date.getTime();
    const diffMinutes = Math.max(0, Math.floor(diffMs / 60000));
    if (diffMinutes === 0) {
      return translate("note.last_sync_just_now", "Last synced: just now");
    }
    return translate("note.last_sync_minutes_ago", "Last synced: {n} min ago").replace("{n}", diffMinutes);
  }

  function setStatus(context, className, text) {
    const label = STATUS_LABELS[text] || text;
    if (text === "Saved" || text === "Saved (Merged)" || text === "Up-to-date") {
      context.lastSyncedAt = new Date();
    }
    context.status.className = className;
    const syncText = formatLastSync(context.lastSyncedAt);
    context.status.textContent = syncText ? `${label} (${syncText})` : label;
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
    context.charCount.textContent = core.formatMessage
      ? core.formatMessage("note.char_count", "{length} / {max_length} characters", { length: length, max_length: context.MAX_LENGTH })
      : `${length} / ${context.MAX_LENGTH} characters`;
  }

  function setMergeStatus(context, text, kind) {
    if (!context.mergeStatus) {
      return;
    }
    context.mergeStatus.textContent = text || "";
    context.mergeStatus.classList.toggle("note-conflict-banner", Boolean(text));
    context.mergeStatus.classList.toggle("is-success", kind === "success");
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
