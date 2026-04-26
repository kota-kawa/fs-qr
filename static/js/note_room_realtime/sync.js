(function (window) {
  const appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error("App namespace is not initialized.");
  }
  const modules = appNamespace.api.getModuleNamespace("noteRoomRealtime");
  const ui = modules.ui;
  const selfEditModule = modules.selfEdit;
  const SYNC_STATES = modules.core.SYNC_STATES;

  function createSyncHandlers(context) {
    const logger = context.logger || { log: function () {}, warn: function () {}, error: function () {} };
    const core = modules.core;

    function isPlainObject(value) {
      if (core && typeof core.isPlainObject === "function") {
        return core.isPlainObject(value);
      }
      return Boolean(value) && typeof value === "object" && !Array.isArray(value);
    }

    function normalizeAckPayload(payload) {
      if (!isPlainObject(payload)) {
        return null;
      }
      if (payload.status !== undefined && typeof payload.status !== "string") {
        return null;
      }
      if (payload.data !== undefined && !isPlainObject(payload.data)) {
        return null;
      }
      if (payload.error !== undefined && payload.error !== null && typeof payload.error !== "string") {
        return null;
      }
      if (payload.request_id !== undefined && typeof payload.request_id !== "string") {
        return null;
      }
      if (payload.requestId !== undefined && typeof payload.requestId !== "string") {
        return null;
      }
      if (payload.data && payload.data.content !== undefined && typeof payload.data.content !== "string") {
        return null;
      }
      if (payload.data && payload.data.updated_at !== undefined && typeof payload.data.updated_at !== "string") {
        return null;
      }
      if (payload.data && payload.data.note_status !== undefined && typeof payload.data.note_status !== "string") {
        return null;
      }
      return payload;
    }

    function normalizeUpdatePayload(payload) {
      if (!isPlainObject(payload)) {
        return null;
      }
      if (payload.status !== undefined && typeof payload.status !== "string") {
        return null;
      }
      if (payload.data !== undefined && !isPlainObject(payload.data)) {
        return null;
      }
      if (!payload.data || typeof payload.data.content !== "string" || typeof payload.data.updated_at !== "string") {
        return null;
      }
      if (payload.data.note_status !== undefined && typeof payload.data.note_status !== "string") {
        return null;
      }
      return payload;
    }

    function normalizeInitPayload(payload) {
      if (!isPlainObject(payload)) {
        return null;
      }
      if (typeof payload.content !== "string" || typeof payload.updated_at !== "string") {
        return null;
      }
      return payload;
    }

    function setSyncState(nextState) {
      context.syncState = nextState;
    }

    function markDirty(content) {
      context.pendingContent = content;
      context.pendingBaseContent = context.contentAtLastSync;
      if (
        context.syncState === SYNC_STATES.BOOTSTRAPPING
        || context.syncState === SYNC_STATES.IDLE
      ) {
        setSyncState(SYNC_STATES.DIRTY);
      } else if (context.syncState === SYNC_STATES.SAVING) {
        setSyncState(SYNC_STATES.SAVING_DIRTY);
      }
    }

    function canSendNow() {
      return Boolean(context.ws && context.ws.readyState === WebSocket.OPEN);
    }

    function createSaveEnvelope(currentContent) {
      context.saveSequence += 1;
      const requestId = `save-${context.saveSequence}`;
      const envelope = {
        type: "save",
        request_id: requestId,
        content: currentContent,
        last_known_updated_at: context.lastStamp,
        original_content: context.pendingBaseContent || context.contentAtLastSync
      };
      context.inFlightSave = {
        requestId: requestId,
        content: currentContent,
        startedAt: Date.now(),
        timeoutHandle: null
      };
      return envelope;
    }

    function scheduleAckTimeout(requestId) {
      const timeoutMs = selfEditModule.getAdaptiveAckTimeoutMs(context);
      if (!timeoutMs || timeoutMs <= 0) {
        return;
      }
      context.inFlightSave.timeoutHandle = setTimeout(() => {
        if (!context.inFlightSave || context.inFlightSave.requestId !== requestId) {
          return;
        }
        logger.warn("Ack timeout for request", requestId);
        setSyncState(SYNC_STATES.OFFLINE_DIRTY);
        context.pendingContent = context.editor.value;
        context.pendingBaseContent = context.contentAtLastSync;
        context.inFlightSave = null;
        ui.setStatus(context, "badge bg-warning text-dark", "Sync timeout (retrying)");
      }, timeoutMs);
    }

    function clearInFlightTimeout() {
      if (context.inFlightSave && context.inFlightSave.timeoutHandle) {
        clearTimeout(context.inFlightSave.timeoutHandle);
        context.inFlightSave.timeoutHandle = null;
      }
    }

    function parseAckRequestId(payload) {
      if (!payload) {
        return "";
      }
      if (typeof payload.request_id === "string") {
        return payload.request_id;
      }
      if (typeof payload.requestId === "string") {
        return payload.requestId;
      }
      return "";
    }

    function finalizeInFlightFromAck(payload) {
      const ackRequestId = parseAckRequestId(payload);
      if (!context.inFlightSave) {
        return false;
      }
      if (ackRequestId && ackRequestId !== context.inFlightSave.requestId) {
        logger.warn("Ignoring stale ack", ackRequestId, context.inFlightSave.requestId);
        return false;
      }
      clearInFlightTimeout();
      selfEditModule.finalizeAckRtt(context, context.inFlightSave.requestId);
      context.inFlightSave = null;
      return true;
    }

    function startNextPendingIfReady() {
      if (context.pendingContent === null || context.pendingContent === undefined) {
        return;
      }
      if (context.pendingContent === context.contentAtLastSync) {
        context.pendingContent = null;
        context.pendingBaseContent = null;
        setSyncState(SYNC_STATES.IDLE);
        return;
      }
      sendSave(context.pendingContent);
    }

    function sendSave(currentContent) {
      if (currentContent.length > context.MAX_LENGTH) {
        if (typeof window.showAlertModal === 'function') {
          window.showAlertModal(`文字数は最大 ${context.MAX_LENGTH} 文字までです。現在 ${currentContent.length} 文字です。`);
        } else {
          window.alert(`文字数は最大 ${context.MAX_LENGTH} 文字までです。現在 ${currentContent.length} 文字です。`);
        }
        setSyncState(SYNC_STATES.IDLE);
        return;
      }

      if (currentContent === context.contentAtLastSync) {
        context.pendingContent = null;
        context.pendingBaseContent = null;
        if (context.syncState !== SYNC_STATES.BOOTSTRAPPING) {
          setSyncState(SYNC_STATES.IDLE);
        }
        return;
      }

      markDirty(currentContent);
      if (!canSendNow()) {
        setSyncState(SYNC_STATES.OFFLINE_DIRTY);
        ui.setStatus(context, "badge bg-warning text-dark", "Offline (reconnecting...)");
        return;
      }

      if (context.inFlightSave) {
        setSyncState(SYNC_STATES.SAVING_DIRTY);
        return;
      }

      context.pendingContent = null;
      setSyncState(SYNC_STATES.SAVING);
      ui.setStatus(context, "badge bg-secondary", "Saving...");
      ui.setMergeStatus(context, "", "");

      const envelope = createSaveEnvelope(currentContent);
      scheduleAckTimeout(envelope.request_id);
      context.ws.send(JSON.stringify(envelope));
    }

    function handleAck(payload) {
      const normalizedPayload = normalizeAckPayload(payload);
      if (!normalizedPayload) {
        logger.warn("Invalid ack payload:", payload);
        return;
      }

      const appliedAck = finalizeInFlightFromAck(normalizedPayload);
      if (!appliedAck) {
        return;
      }

      var ackData = normalizedPayload.data || {};
      var noteStatus = typeof ackData.note_status === "string" ? ackData.note_status : "";
      var hasServerContent = ackData.content !== undefined && ackData.updated_at;
      if (hasServerContent && (normalizedPayload.status === "ok" || noteStatus.startsWith("conflict"))) {
        selfEditModule.applyServerContent(context, ackData.content, ackData.updated_at);
      }

      if (
        normalizedPayload.status === "ok"
      ) {
        if (noteStatus === "ok_merged") {
          ui.setStatus(context, "badge bg-info", "Saved (Merged)");
          ui.setMergeStatus(context, "競合を自動マージして保存しました。", "success");
        } else {
          ui.setStatus(context, "badge bg-success", "Saved");
          ui.setMergeStatus(context, "", "");
        }
      } else if (normalizedPayload.status === "error" && noteStatus.startsWith("conflict")) {
        ui.setStatus(context, "badge bg-warning text-dark", "Conflict resolved");
        ui.setMergeStatus(context, "最新内容との競合が発生し、サーバー版を反映しました。", "warning");
      } else if (normalizedPayload.status === "error" && normalizedPayload.error) {
        ui.setStatus(context, "badge bg-danger", normalizedPayload.error);
        ui.setMergeStatus(context, "", "");
      }

      selfEditModule.flushPendingRemoteUpdate(context, "Updated by others");

      if (context.pendingContent !== null && context.pendingContent !== undefined) {
        setSyncState(SYNC_STATES.SAVING_DIRTY);
        startNextPendingIfReady();
        return;
      }

      setSyncState(SYNC_STATES.IDLE);
    }

    function handleUpdate(payload) {
      const normalizedPayload = normalizeUpdatePayload(payload);
      if (!normalizedPayload) {
        logger.warn("Invalid update payload:", payload);
        return;
      }

      if (context.inFlightSave || context.syncState === SYNC_STATES.SAVING || context.syncState === SYNC_STATES.SAVING_DIRTY) {
        selfEditModule.queuePendingRemoteUpdate(context, normalizedPayload);
        return;
      }

      var updateData = normalizedPayload.data || {};
      if (updateData.updated_at && updateData.updated_at !== context.lastStamp) {
        const hasLocalDraft = context.pendingContent !== null && context.pendingContent !== undefined;
        const hasUnsyncedEditor = context.editor.value !== context.contentAtLastSync;
        if (hasLocalDraft || hasUnsyncedEditor) {
          selfEditModule.queuePendingRemoteUpdate(context, {
            content: updateData.content,
            updated_at: updateData.updated_at,
            status: updateData.note_status || ""
          });
          ui.setStatus(context, "badge bg-warning text-dark", "Remote update queued");
          ui.setMergeStatus(context, "他ユーザーの更新を待機中です（ローカル保存後に反映）。", "warning");
          return;
        }
        selfEditModule.applyServerContent(
          context,
          updateData.content,
          updateData.updated_at,
          "Updated by others"
        );
        ui.setMergeStatus(context, "", "");
      }
    }

    function handleInit(payload) {
      const normalizedPayload = normalizeInitPayload(payload);
      if (!normalizedPayload) {
        logger.warn("Invalid init payload:", payload);
        return;
      }

      context.editor.value = normalizedPayload.content;
      ui.updateCharCount(context, context.editor.value);
      context.contentAtLastSync = context.editor.value;
      context.lastStamp = normalizedPayload.updated_at;
      context.pendingContent = null;
      context.pendingBaseContent = null;
      context.pendingRemoteUpdate = null;
      context.inFlightSave = null;
      setSyncState(SYNC_STATES.IDLE);
      ui.setStatus(context, "badge bg-success", "Up-to-date");
      ui.setMergeStatus(context, "", "");
    }

    function bindEditorInput() {
      context.editor.addEventListener("input", () => {
        clearTimeout(context.typTimer);
        ui.updateCharCount(context, context.editor.value);

        context.typTimer = setTimeout(() => {
          const currentContent = context.editor.value;
          sendSave(currentContent);
        }, 800);
      });
    }

    function handleSocketOnline() {
      if (context.syncState === SYNC_STATES.OFFLINE_DIRTY || context.pendingContent !== null) {
        setSyncState(SYNC_STATES.DIRTY);
      } else if (!context.inFlightSave) {
        setSyncState(SYNC_STATES.IDLE);
      }
      if (context.pendingContent !== null) {
        startNextPendingIfReady();
      }
    }

    function handleSocketOffline() {
      if (context.inFlightSave) {
        clearInFlightTimeout();
        context.pendingContent = context.editor.value;
        context.pendingBaseContent = context.contentAtLastSync;
        context.inFlightSave = null;
      }
      if (context.pendingContent !== null || context.editor.value !== context.contentAtLastSync) {
        setSyncState(SYNC_STATES.OFFLINE_DIRTY);
        ui.setStatus(context, "badge bg-warning text-dark", "Offline (reconnecting...)");
      }
    }

    return {
      sendSave: sendSave,
      handleAck: handleAck,
      handleUpdate: handleUpdate,
      handleInit: handleInit,
      bindEditorInput: bindEditorInput,
      handleSocketOnline: handleSocketOnline,
      handleSocketOffline: handleSocketOffline
    };
  }

  modules.sync = {
    createSyncHandlers: createSyncHandlers
  };
})(window);
