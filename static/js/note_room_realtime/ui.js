(function (window) {
  const appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error("App namespace is not initialized.");
  }
  const modules = appNamespace.api.getModuleNamespace("noteRoomRealtime");

  function translate(key, fallback) {
    if (window.FSQR_I18N && typeof window.FSQR_I18N.t === "function") {
      return window.FSQR_I18N.t(key, fallback);
    }
    return fallback || key;
  }

  const STATUS_LABELS = {
    "Connected": translate("note.connected", "接続済み"),
    "Connection error": translate("note.connection_error", "接続エラー"),
    "Conflict resolved": translate("note.conflict_resolved", "競合を解消しました"),
    "Offline (reconnecting...)": translate("note.offline_reconnecting", "オフライン（再接続中）"),
    "Remote update queued": translate("note.remote_update_queued", "他の編集を反映待ち"),
    "Reconnecting...": translate("note.reconnecting", "再接続中…"),
    "Saved": translate("note.saved", "保存済み"),
    "Saved (Merged)": translate("note.saved_merged", "保存済み（変更を統合）"),
    "Saving...": translate("note.saving", "保存中…"),
    "Sync timeout (retrying)": translate("note.sync_timeout", "同期がタイムアウトしました（再試行中）"),
    "Up-to-date": translate("note.up_to_date", "最新です")
  };

  function formatLastSync(date) {
    if (!date) {
      return "";
    }
    const diffMs = Date.now() - date.getTime();
    const diffMinutes = Math.max(0, Math.floor(diffMs / 60000));
    if (diffMinutes === 0) {
      return translate("note.last_sync_just_now", "最終同期: たった今");
    }
    return translate("note.last_sync_minutes_ago", "最終同期: {n}分前").replace("{n}", diffMinutes);
  }

  function setStatus(context, className, text) {
    const label = STATUS_LABELS[text] || text;
    if (text === "Saved" || text === "Saved (Merged)" || text === "Up-to-date") {
      context.lastSyncedAt = new Date();
    }
    context.status.className = className;
    const syncText = formatLastSync(context.lastSyncedAt);
    context.status.textContent = syncText ? `${label}（${syncText}）` : label;
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
