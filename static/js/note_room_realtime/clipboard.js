(function (window) {
  const appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error("App namespace is not initialized.");
  }
  const modules = appNamespace.api.getModuleNamespace("noteRoomRealtime");
  const ui = modules.ui;
  const core = modules.core || {};

  function translate(key, fallback) {
    if (window.FSQR_I18N && typeof window.FSQR_I18N.t === "function") {
      return window.FSQR_I18N.t(key, fallback);
    }
    return fallback || key;
  }

  function createClipboardHandlers(context) {
    async function handlePasteFromClipboard() {
      if (!navigator.clipboard || !navigator.clipboard.readText) {
        ui.showEditorFeedback(translate("note.clipboard_paste_unavailable", "Paste is not available in this environment."), "error");
        return;
      }

      try {
        const clipText = await navigator.clipboard.readText();
        if (!clipText) {
          ui.showEditorFeedback(translate("note.clipboard_empty", "There is no text to paste from the clipboard."), "error");
          return;
        }

        const selectionStart = context.editor.selectionStart ?? context.editor.value.length;
        const selectionEnd = context.editor.selectionEnd ?? context.editor.value.length;
        const before = context.editor.value.slice(0, selectionStart);
        const after = context.editor.value.slice(selectionEnd);
        const remain = context.MAX_LENGTH - (before.length + after.length);

        if (remain <= 0) {
          ui.showEditorFeedback(core.formatMessage
            ? core.formatMessage("note.char_limit_reached", "The character limit ({max_length}) has been reached.", { max_length: context.MAX_LENGTH })
            : `The character limit (${context.MAX_LENGTH}) has been reached.`, "error");
          return;
        }

        const insertText = clipText.slice(0, remain);
        context.editor.value = before + insertText + after;
        const nextCursor = selectionStart + insertText.length;
        context.editor.setSelectionRange(nextCursor, nextCursor);
        ui.updateCharCount(context, context.editor.value);
        context.editor.dispatchEvent(new Event("input", { bubbles: true }));
        context.editor.focus();

        if (insertText.length < clipText.length) {
          ui.showEditorFeedback(core.formatMessage
            ? core.formatMessage("note.paste_truncated", "Only {count} characters were pasted because of the limit.", { count: insertText.length })
            : `Only ${insertText.length} characters were pasted because of the limit.`, "error");
        } else {
          ui.showEditorFeedback(translate("note.paste_success", "Pasted."), "success");
        }
      } catch (error) {
        ui.showEditorFeedback(translate("note.paste_error", "Paste failed. Check your browser permission settings."), "error");
      }
    }

    async function handleCopyAllText() {
      const text = context.editor.value || "";
      if (!text) {
        ui.showEditorFeedback(translate("note.copy_empty", "There is no text to copy."), "error");
        return;
      }

      try {
        if (typeof copyTextToClipboard !== "function") {
          throw new Error("Clipboard helper unavailable");
        }
        await copyTextToClipboard(text);
        ui.showEditorFeedback(translate("note.copy_success", "Copied the full note."), "success");
      } catch (error) {
        ui.showEditorFeedback(translate("note.copy_error", "Copy failed. Please copy manually."), "error");
      }
    }

    function bindButtons() {
      if (context.pasteButton) {
        context.pasteButton.addEventListener("click", handlePasteFromClipboard);
      }

      if (context.copyAllButton) {
        context.copyAllButton.addEventListener("click", handleCopyAllText);
      }
    }

    return {
      bindButtons: bindButtons
    };
  }

  modules.clipboard = {
    createClipboardHandlers: createClipboardHandlers
  };
})(window);
