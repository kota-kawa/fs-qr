(function (window) {
  const appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error("App namespace is not initialized.");
  }
  const modules = appNamespace.api.getModuleNamespace("noteRoomRealtime");

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? (meta.getAttribute("content") || "") : "";
  }

  function showFeedback(message, kind) {
    if (typeof window.setShareFeedback === "function") {
      window.setShareFeedback(message, kind);
      return;
    }
    if (kind === "error") {
      window.alert(message);
    }
  }

  function saveBlob(blob, filename) {
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    link.hidden = true;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(function () {
      URL.revokeObjectURL(objectUrl);
    }, 0);
  }

  function createExportHandlers(context) {
    const core = modules.core;

    async function download(format, button) {
      if (!button || button.disabled) {
        return;
      }
      button.disabled = true;
      try {
        const response = await fetch(
          `/api/note/${encodeURIComponent(context.room)}/export/${format}`,
          {
            method: "POST",
            credentials: "same-origin",
            headers: {
              "Content-Type": "application/json",
              "X-CSRF-Token": getCsrfToken()
            },
            body: JSON.stringify({ content: context.editor.value })
          }
        );
        if (!response.ok) {
          throw new Error(`Export failed with status ${response.status}`);
        }
        saveBlob(await response.blob(), `note-${context.room}.${format}`);
        showFeedback(core.translate("download.complete", "Download complete!"), "success");
      } catch (error) {
        context.logger.error("Note export failed.", error);
        showFeedback(core.translate("download.error", "An error occurred during the download."), "error");
      } finally {
        button.disabled = false;
      }
    }

    function bindButtons() {
      if (context.txtDownloadButton) {
        context.txtDownloadButton.addEventListener("click", function () {
          download("txt", context.txtDownloadButton);
        });
      }
      if (context.pdfDownloadButton) {
        context.pdfDownloadButton.addEventListener("click", function () {
          download("pdf", context.pdfDownloadButton);
        });
      }
    }

    return { bindButtons: bindButtons };
  }

  modules.export = { createExportHandlers: createExportHandlers };
})(window);
