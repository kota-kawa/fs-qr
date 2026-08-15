/**
 * Instant upload for the FS!QR landing page.
 *
 * LP上で選んだファイルを発行操作まで端末内に保持し、既存のブラウザ暗号化
 * モジュールを通して /upload へ送信する。共有URLには暗号鍵をフラグメントで
 * 付加し、クエリやパスへ鍵を出さない。
 */
(function (window, document) {
  "use strict";

  var root = document.querySelector("[data-instant-fsqr]");
  if (!root) {
    return;
  }

  var dropzone = root.querySelector("[data-instant-dropzone]");
  var fileInput = root.querySelector("[data-instant-file-input]");
  var fileList = root.querySelector("[data-instant-file-list]");
  var publishButton = root.querySelector("[data-instant-publish]");
  var clearButton = root.querySelector("[data-instant-clear]");
  var resetButton = root.querySelector("[data-instant-reset]");
  var retentionSelect = root.querySelector("[data-instant-retention]");
  var counter = root.querySelector("[data-instant-count]");
  var stateLabel = root.querySelector("[data-instant-state]");
  var errorBox = root.querySelector("[data-instant-error]");
  var hint = root.querySelector("[data-instant-hint]");
  var progress = root.querySelector("[data-instant-progress]");
  var progressPhase = root.querySelector("[data-instant-progress-phase]");
  var progressPercent = root.querySelector("[data-instant-progress-percent]");
  var progressBar = root.querySelector("[data-instant-progress-bar]");
  var progressDetail = root.querySelector("[data-instant-progress-detail]");
  var cancelButton = root.querySelector("[data-instant-cancel]");
  var sharePanel = root.querySelector("[data-instant-share-panel]");
  var qrBox = root.querySelector("[data-instant-qr]");
  var shareUrlLabel = root.querySelector("[data-instant-share-url]");
  var idLabel = root.querySelector("[data-instant-id]");
  var passwordLabel = root.querySelector("[data-instant-password]");
  var openLink = root.querySelector("[data-instant-open]");

  if (!fileInput || !fileList || !publishButton || !retentionSelect) {
    return;
  }

  var uploadUrl = root.getAttribute("data-upload-url") || "/upload";
  var limits = {
    maxFiles: Number(root.getAttribute("data-max-files")),
    maxTotalSizeBytes: Number(root.getAttribute("data-max-total-size-bytes")),
    maxTotalSizeMB: Number(root.getAttribute("data-max-total-size-mb"))
  };
  var idleStateText = stateLabel ? stateLabel.textContent : "";
  var selected = [];
  var submitting = false;
  var cancelRequested = false;
  var activeXhr = null;
  var encryptionService = null;
  var copyValues = { url: "", id: "", password: "" };
  var issuedStorageKey = "fsqr:fsqr-landing-issued";
  var issuedTtlMs = 24 * 60 * 60 * 1000;

  function getValidator() {
    var app = window.__FSQR_APP__;
    return app && app.api ? app.api.getShared("uploadValidation") : null;
  }

  function setState(text) {
    if (stateLabel) {
      stateLabel.textContent = text;
    }
  }

  function showError(message) {
    if (!errorBox) {
      return;
    }
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  function clearError() {
    if (!errorBox) {
      return;
    }
    errorBox.textContent = "";
    errorBox.hidden = true;
  }

  function formatSize(bytes) {
    if (bytes >= 1024 * 1024 * 1024) {
      return (bytes / (1024 * 1024 * 1024)).toFixed(2) + "GB";
    }
    if (bytes >= 1024 * 1024) {
      return (bytes / (1024 * 1024)).toFixed(1) + "MB";
    }
    if (bytes >= 1024) {
      return Math.round(bytes / 1024) + "KB";
    }
    return bytes + "B";
  }

  function totalSize() {
    return selected.reduce(function (total, file) {
      return total + (Number.isFinite(file.size) ? file.size : 0);
    }, 0);
  }

  function validationMessage(result) {
    if (result.reason === "max_files") {
      return "ファイルは合計" + result.maxFiles + "個までです。";
    }
    if (result.reason === "max_total_size") {
      return "ファイルは合計" + result.maxTotalSizeMB + "MBまでです。";
    }
    if (result.reason === "invalid_filename") {
      return "使用できないファイル名が含まれています。";
    }
    return "選択したファイルを追加できませんでした。";
  }

  function renderFileList() {
    fileList.textContent = "";
    selected.forEach(function (file, index) {
      var item = document.createElement("li");
      item.className = "lp-file-list__item";

      var name = document.createElement("span");
      name.className = "lp-file-list__name";
      name.textContent = file.name;

      var size = document.createElement("span");
      size.className = "lp-file-list__size";
      size.textContent = formatSize(file.size);

      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "lp-file-list__remove";
      remove.textContent = "外す";
      remove.setAttribute("aria-label", file.name + " を選択から外す");
      remove.disabled = submitting;
      remove.addEventListener("click", function () {
        if (submitting) {
          return;
        }
        selected.splice(index, 1);
        clearError();
        renderFileList();
        setState("ファイルを外しました");
      });

      item.appendChild(name);
      item.appendChild(size);
      item.appendChild(remove);
      fileList.appendChild(item);
    });

    if (counter) {
      counter.textContent = selected.length
        ? selected.length + "個 / " + formatSize(totalSize())
        : "ファイル未選択";
    }
    publishButton.disabled = selected.length === 0 || submitting;
    if (clearButton) {
      clearButton.hidden = selected.length === 0;
    }
  }

  function addFiles(files) {
    if (submitting) {
      return;
    }
    var incoming = Array.prototype.slice.call(files || []);
    if (!incoming.length) {
      return;
    }
    clearError();

    var validator = getValidator();
    if (validator) {
      var result = validator.validateSelection(incoming, limits, {
        existingFilesCount: selected.length,
        existingTotalSize: totalSize()
      });
      if (!result.ok) {
        showError(validationMessage(result));
        return;
      }
    }

    selected = selected.concat(incoming);
    renderFileList();
    setState(incoming.length + "個を追加しました");
  }

  function setProgress(value, phase, detail) {
    var safeValue = Math.max(0, Math.min(1, Number(value) || 0));
    if (progressBar) {
      progressBar.style.width = Math.round(safeValue * 100) + "%";
    }
    if (progressPercent) {
      progressPercent.textContent = Math.round(safeValue * 100) + "%";
    }
    if (progressPhase && phase) {
      progressPhase.textContent = phase;
    }
    if (progressDetail && detail) {
      progressDetail.textContent = detail;
    }
  }

  function setProgressVisible(visible) {
    if (progress) {
      progress.hidden = !visible;
    }
  }

  function setSubmitting(active) {
    submitting = active;
    publishButton.disabled = active || selected.length === 0;
    publishButton.setAttribute("aria-busy", active ? "true" : "false");
    if (dropzone) {
      dropzone.setAttribute("aria-disabled", active ? "true" : "false");
    }
    if (clearButton) {
      clearButton.disabled = active;
    }
    renderFileList();
  }

  function readCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") || "" : "";
  }

  function readPayload(responseText) {
    try {
      return JSON.parse(responseText);
    } catch (error) {
      return null;
    }
  }

  function errorMessageFor(status, payload, fallback) {
    if (status === 403) {
      return "セッションの有効期限が切れた可能性があります。ページを再読み込みしてから再度お試しください。";
    }
    if (payload && typeof payload.error === "string" && payload.error) {
      return payload.error;
    }
    return fallback;
  }

  function generateDownloadPassword() {
    var digits = "0123456789";
    var bytes = window.crypto.getRandomValues(new Uint8Array(6));
    var password = "";
    for (var i = 0; i < bytes.length; i += 1) {
      password += digits[bytes[i] % digits.length];
    }
    return password;
  }

  function getEncryptionService() {
    if (encryptionService) {
      return encryptionService;
    }
    var app = window.__FSQR_APP__;
    var modules = app && app.api ? app.api.getModuleNamespace("fsQrUpload") : null;
    if (!modules || !modules.encryption) {
      throw new Error("暗号化モジュールを読み込めませんでした。ページを再読み込みしてください。");
    }
    encryptionService = modules.encryption.createEncryptionService({
      setProgressScale: function (value) {
        setProgress(Number(value) * 0.65, "暗号化しています", "ファイルをブラウザ内で暗号化しています。");
      },
      setStatusText: function (text) {
        setProgressDetail(text);
      }
    });
    return encryptionService;
  }

  function setProgressDetail(text) {
    if (progressDetail && text) {
      progressDetail.textContent = text;
    }
  }

  function buildUploadFormData(files, encryptedBlob, downloadPassword) {
    var formData = new FormData();
    if (files.length === 1) {
      formData.append("upfile", new File([encryptedBlob], files[0].name + ".enc", {
        type: "application/octet-stream"
      }));
      formData.append("file_type", "single");
    } else {
      formData.append("upfile", new File([encryptedBlob], "encrypted_files.zip", {
        type: "application/zip"
      }));
      formData.append("file_type", "multiple");
    }
    formData.append("name", "");
    formData.append("download_password", downloadPassword);
    formData.append("original_filename", files[0].name);
    formData.append("retention_hours", retentionSelect.value);
    return formData;
  }

  function withKey(url, key) {
    if (!url || !key) {
      return url || "";
    }
    return url + "#pw=" + encodeURIComponent(key);
  }

  function renderQrCode(url) {
    if (!qrBox || !url || typeof window.QRCode !== "function") {
      return;
    }
    qrBox.textContent = "";
    new window.QRCode(qrBox, {
      text: url,
      width: 132,
      height: 132,
      correctLevel: window.QRCode.CorrectLevel.M
    });
  }

  function showSharePanel(issued) {
    if (!sharePanel) {
      return;
    }
    copyValues = {
      url: issued.share_url || "",
      id: issued.id || "",
      password: issued.password || ""
    };
    if (shareUrlLabel) {
      shareUrlLabel.textContent = copyValues.url || "共有URLを取得できませんでした";
    }
    if (idLabel) {
      idLabel.textContent = copyValues.id;
    }
    if (passwordLabel) {
      passwordLabel.textContent = copyValues.password;
    }
    if (openLink && issued.redirect_url) {
      openLink.setAttribute("href", issued.redirect_url);
    }
    renderQrCode(copyValues.url);
    sharePanel.hidden = false;
    publishButton.hidden = true;
    setProgressVisible(false);
    if (hint) {
      hint.hidden = true;
    }
    if (dropzone) {
      dropzone.hidden = true;
    }
    if (clearButton) {
      clearButton.hidden = true;
    }
    if (retentionSelect.parentElement) {
      retentionSelect.parentElement.hidden = true;
    }
    fileList.querySelectorAll(".lp-file-list__remove").forEach(function (button) {
      button.hidden = true;
    });
    setState("共有リンクを発行しました");
  }

  function rememberIssued(issued) {
    try {
      window.sessionStorage.setItem(issuedStorageKey, JSON.stringify(issued));
    } catch (error) {
      /* 保存できなくても発行自体は完了しているため無視する。 */
    }
  }

  function readIssued() {
    try {
      var raw = window.sessionStorage.getItem(issuedStorageKey);
      if (!raw) {
        return null;
      }
      var issued = JSON.parse(raw);
      if (!issued || !issued.issued_at) {
        return null;
      }
      if (Date.now() - Number(issued.issued_at) > issuedTtlMs) {
        window.sessionStorage.removeItem(issuedStorageKey);
        return null;
      }
      return issued;
    } catch (error) {
      return null;
    }
  }

  function copyToClipboard(text) {
    if (window.navigator.clipboard && window.isSecureContext) {
      return window.navigator.clipboard.writeText(text);
    }
    var helper = document.createElement("textarea");
    helper.value = text;
    helper.setAttribute("readonly", "");
    helper.style.cssText = "position:fixed;top:0;left:-9999px;opacity:0;";
    document.body.appendChild(helper);
    try {
      helper.select();
      if (!document.execCommand("copy")) {
        throw new Error("copy command failed");
      }
      return Promise.resolve();
    } finally {
      document.body.removeChild(helper);
    }
  }

  function uploadEncrypted(files, encryptedBlob, downloadPassword, shareKey) {
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      activeXhr = xhr;
      xhr.open("POST", uploadUrl, true);
      xhr.setRequestHeader("X-CSRF-Token", readCsrfToken());
      xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
      xhr.setRequestHeader("Accept", "application/json");
      xhr.upload.onprogress = function (event) {
        if (!event.lengthComputable) {
          return;
        }
        var value = 0.65 + (event.loaded / event.total) * 0.35;
        setProgress(value, "アップロードしています", "暗号化したファイルを送信しています。");
      };
      xhr.onload = function () {
        activeXhr = null;
        var payload = readPayload(xhr.responseText);
        if (xhr.status < 200 || xhr.status >= 300) {
          reject(new Error(errorMessageFor(xhr.status, payload, "アップロードに失敗しました。")));
          return;
        }
        var data = payload && payload.data;
        if (!payload || payload.status !== "ok" || !data || !data.redirect_url) {
          reject(new Error("アップロード結果を取得できませんでした。"));
          return;
        }
        resolve({
          share_url: withKey(data.share_url || "", shareKey),
          id: data.id || "",
          password: data.password || downloadPassword,
          redirect_url: withKey(data.redirect_url, shareKey),
          issued_at: Date.now()
        });
      };
      xhr.onerror = function () {
        activeXhr = null;
        reject(new Error("通信に失敗しました。接続を確認して再度お試しください。"));
      };
      xhr.onabort = function () {
        activeXhr = null;
        reject(new Error("アップロードをキャンセルしました。"));
      };
      xhr.send(buildUploadFormData(files, encryptedBlob, downloadPassword));
    });
  }

  async function publish() {
    if (submitting || !selected.length) {
      return;
    }
    clearError();
    if (!window.crypto || !window.crypto.subtle) {
      showError("このブラウザでは暗号化に対応していません。/fs-qr から別のブラウザでお試しください。");
      return;
    }

    cancelRequested = false;
    setSubmitting(true);
    setProgressVisible(true);
    setProgress(0, "暗号化の準備中", "ファイルを安全に準備しています。");
    setState("共有リンクを発行しています…");

    try {
      var files = selected.slice();
      var downloadPassword = generateDownloadPassword();
      var service = getEncryptionService();
      var encryptedBlob = await service.encryptAndZipFilesWithProgress(files, downloadPassword, "password");
      var shareKey = service.getLastEncryptionKey();
      if (cancelRequested) {
        throw new Error("アップロードをキャンセルしました。");
      }
      var issued = await uploadEncrypted(files, encryptedBlob, downloadPassword, shareKey);
      rememberIssued(issued);
      setProgress(1, "完了", "共有情報を準備しています。");
      setSubmitting(false);
      showSharePanel(issued);
    } catch (error) {
      setSubmitting(false);
      setProgressVisible(false);
      setState(idleStateText);
      showError(error && error.message ? error.message : "共有リンクの発行に失敗しました。");
    }
  }

  fileInput.addEventListener("change", function () {
    addFiles(fileInput.files);
    fileInput.value = "";
  });

  if (dropzone) {
    ["dragenter", "dragover"].forEach(function (type) {
      dropzone.addEventListener(type, function (event) {
        event.preventDefault();
        if (!submitting) {
          dropzone.classList.add("is-dragover");
        }
      });
    });
    ["dragleave", "drop"].forEach(function (type) {
      dropzone.addEventListener(type, function (event) {
        event.preventDefault();
        dropzone.classList.remove("is-dragover");
      });
    });
    dropzone.addEventListener("drop", function (event) {
      if (event.dataTransfer && event.dataTransfer.files) {
        addFiles(event.dataTransfer.files);
      }
    });
  }

  publishButton.addEventListener("click", publish);

  if (cancelButton) {
    cancelButton.addEventListener("click", function () {
      if (!submitting) {
        return;
      }
      cancelRequested = true;
      if (activeXhr) {
        activeXhr.abort();
      }
      setProgressDetail("キャンセルしています。暗号化中の場合は処理の完了後に停止します。");
    });
  }

  if (clearButton) {
    clearButton.addEventListener("click", function () {
      if (submitting) {
        return;
      }
      selected = [];
      clearError();
      renderFileList();
      setState("選択を解除しました");
    });
  }

  if (resetButton) {
    resetButton.addEventListener("click", function () {
      try {
        window.sessionStorage.removeItem(issuedStorageKey);
      } catch (error) {
        /* 保存領域へアクセスできなくても、画面は再利用できる。 */
      }
      selected = [];
      sharePanel.hidden = true;
      publishButton.hidden = false;
      if (hint) {
        hint.hidden = false;
      }
      if (dropzone) {
        dropzone.hidden = false;
      }
      if (retentionSelect.parentElement) {
        retentionSelect.parentElement.hidden = false;
      }
      clearError();
      renderFileList();
      setState(idleStateText);
    });
  }

  root.querySelectorAll("[data-instant-copy]").forEach(function (button) {
    button.addEventListener("click", function () {
      var value = copyValues[button.getAttribute("data-instant-copy")];
      if (!value) {
        return;
      }
      var label = button.textContent;
      copyToClipboard(value).then(function () {
        button.textContent = "コピー済み";
      }).catch(function () {
        button.textContent = "コピー失敗";
      }).finally(function () {
        window.setTimeout(function () {
          button.textContent = label;
        }, 1800);
      });
    });
  });

  var issued = readIssued();
  if (issued) {
    showSharePanel(issued);
  } else {
    renderFileList();
  }
})(window, document);
