(function (window) {
  window.NoteRoomRealtimeModules = window.NoteRoomRealtimeModules || {};
  const modules = window.NoteRoomRealtimeModules;
  const ui = modules.ui;

  function createClipboardHandlers(context) {
    async function handlePasteFromClipboard() {
      if (!navigator.clipboard || !navigator.clipboard.readText) {
        ui.showEditorFeedback("この環境ではペースト機能を利用できません。", "error");
        return;
      }

      try {
        const clipText = await navigator.clipboard.readText();
        if (!clipText) {
          ui.showEditorFeedback("クリップボードに貼り付けるテキストがありません。", "error");
          return;
        }

        const selectionStart = context.editor.selectionStart ?? context.editor.value.length;
        const selectionEnd = context.editor.selectionEnd ?? context.editor.value.length;
        const before = context.editor.value.slice(0, selectionStart);
        const after = context.editor.value.slice(selectionEnd);
        const remain = context.MAX_LENGTH - (before.length + after.length);

        if (remain <= 0) {
          ui.showEditorFeedback(`文字数上限（${context.MAX_LENGTH}文字）に達しています。`, "error");
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
          ui.showEditorFeedback(`上限のため${insertText.length}文字のみ貼り付けました。`, "error");
        } else {
          ui.showEditorFeedback("ペーストしました。", "success");
        }
      } catch (error) {
        ui.showEditorFeedback("ペーストに失敗しました。ブラウザの権限設定を確認してください。", "error");
      }
    }

    async function handleCopyAllText() {
      const text = context.editor.value || "";
      if (!text) {
        ui.showEditorFeedback("コピーするテキストがありません。", "error");
        return;
      }

      try {
        if (typeof copyTextToClipboard !== "function") {
          throw new Error("Clipboard helper unavailable");
        }
        await copyTextToClipboard(text);
        ui.showEditorFeedback("ノート全文をコピーしました。", "success");
      } catch (error) {
        ui.showEditorFeedback("全文コピーに失敗しました。手動でコピーしてください。", "error");
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
