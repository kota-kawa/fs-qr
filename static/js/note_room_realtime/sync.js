(function (window) {
  window.NoteRoomRealtimeModules = window.NoteRoomRealtimeModules || {};
  const modules = window.NoteRoomRealtimeModules;
  const ui = modules.ui;
  const selfEditModule = modules.selfEdit;

  function createSyncHandlers(context) {
    function sendSave(currentContent) {
      if (currentContent.length > context.MAX_LENGTH) {
        alert(`文字数は最大 ${context.MAX_LENGTH} 文字までです。現在 ${currentContent.length} 文字です。`);
        selfEditModule.setSelfEdit(context, false);
        return;
      }

      if (currentContent === context.contentAtLastSync) {
        selfEditModule.setSelfEdit(context, false);
        return;
      }

      context.pendingContent = currentContent;
      if (!context.ws || context.ws.readyState !== WebSocket.OPEN) {
        ui.setStatus(context, "badge bg-warning text-dark", "Offline (reconnecting...)");
        return;
      }

      context.pendingContent = null;
      selfEditModule.setSelfEdit(context, true, context.selfEditTimeoutMs);
      ui.setStatus(context, "badge bg-secondary", "Saving...");

      context.ws.send(JSON.stringify({
        type: "save",
        content: currentContent,
        last_known_updated_at: context.lastStamp,
        original_content: context.contentAtLastSync
      }));
    }

    function handleAck(payload) {
      if (payload.status && (payload.status.startsWith("ok") || payload.status.startsWith("conflict"))) {
        if (payload.content !== undefined && payload.updated_at) {
          selfEditModule.applyServerContent(context, payload.content, payload.updated_at);
        }

        if (payload.status === "ok_merged") {
          ui.setStatus(context, "badge bg-info", "Saved (Merged)");
        } else if (payload.status.startsWith("conflict")) {
          ui.setStatus(context, "badge bg-warning text-dark", "Conflict resolved");
        } else {
          ui.setStatus(context, "badge bg-success", "Saved");
        }
      } else if (payload.error) {
        ui.setStatus(context, "badge bg-danger", payload.error);
      }
      selfEditModule.setSelfEdit(context, false);
    }

    function handleUpdate(payload) {
      if (context.selfEdit) {
        return;
      }
      if (payload.updated_at && payload.updated_at !== context.lastStamp) {
        selfEditModule.applyServerContent(context, payload.content, payload.updated_at, "Updated by others");
      }
    }

    function handleInit(payload) {
      context.editor.value = payload.content || "";
      ui.updateCharCount(context, context.editor.value);
      context.contentAtLastSync = context.editor.value;
      context.lastStamp = payload.updated_at || "";
      ui.setStatus(context, "badge bg-success", "Up-to-date");
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

    return {
      sendSave: sendSave,
      handleAck: handleAck,
      handleUpdate: handleUpdate,
      handleInit: handleInit,
      bindEditorInput: bindEditorInput
    };
  }

  modules.sync = {
    createSyncHandlers: createSyncHandlers
  };
})(window);
