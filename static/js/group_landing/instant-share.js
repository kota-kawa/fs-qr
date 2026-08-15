/**
 * Instant share box for the FS!QR Group landing page.
 *
 * LPに置いた「その場で使える共有ボックス」。ルームを作らずにファイルを選べ、
 * 発行ボタンを押した時点で初めてルーム作成とアップロードをまとめて実行する。
 * 発行後は共有URL・QRコード・ルームID・パスワードをその場で提示する。
 */
(function (window, document) {
  "use strict";

  var STATE_RESET_MS = 2400;

  var root = document.querySelector("[data-instant-share-box]");
  if (!root) {
    return;
  }

  var dropzone = root.querySelector("[data-instant-dropzone]");
  var fileInput = root.querySelector("[data-instant-file-input]");
  var fileList = root.querySelector("[data-instant-file-list]");
  var publishButton = root.querySelector("[data-instant-publish]");
  var clearButton = root.querySelector("[data-instant-clear]");
  var counter = root.querySelector("[data-instant-count]");
  var stateLabel = root.querySelector("[data-instant-state]");
  var errorBox = root.querySelector("[data-instant-error]");
  var hint = root.querySelector("[data-instant-hint]");
  var sharePanel = root.querySelector("[data-instant-share-panel]");
  var qrBox = root.querySelector("[data-instant-qr]");
  var shareUrlLabel = root.querySelector("[data-instant-share-url]");
  var roomIdLabel = root.querySelector("[data-instant-room-id]");
  var passwordLabel = root.querySelector("[data-instant-password]");
  var openLink = root.querySelector("[data-instant-open]");
  var resetButton = root.querySelector("[data-instant-reset]");
  if (!fileInput || !publishButton || !fileList) {
    return;
  }

  var createUrl = root.getAttribute("data-create-url") || "/create_group_room";
  var uploadUrl = root.getAttribute("data-upload-url") || "/group_upload";
  var limits = {
    maxFiles: Number(root.getAttribute("data-max-files")),
    maxTotalSizeBytes: Number(root.getAttribute("data-max-total-size-bytes")),
    maxTotalSizeMB: Number(root.getAttribute("data-max-total-size-mb"))
  };
  var idleStateText = stateLabel ? stateLabel.textContent : "";

  var selected = [];
  var stateTimer = null;
  var submitting = false;
  var copyValues = { url: "", room: "", password: "" };

  /** ファイル選択の検証は他画面と同じ共有モジュールを使う。 */
  function getValidator() {
    var app = window.__FSQR_APP__;
    return app && app.api ? app.api.getShared("uploadValidation") : null;
  }

  function setState(text) {
    if (!stateLabel) {
      return;
    }
    stateLabel.textContent = text;
    if (stateTimer) {
      window.clearTimeout(stateTimer);
    }
    if (text !== idleStateText) {
      stateTimer = window.setTimeout(function () {
        stateLabel.textContent = idleStateText;
      }, STATE_RESET_MS);
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
    if (bytes >= 1024 * 1024) {
      return (bytes / (1024 * 1024)).toFixed(1) + "MB";
    }
    if (bytes >= 1024) {
      return Math.round(bytes / 1024) + "KB";
    }
    return bytes + "B";
  }

  function totalSize() {
    return selected.reduce(function (acc, file) {
      return acc + (Number.isFinite(file.size) ? file.size : 0);
    }, 0);
  }

  function describeValidationError(result) {
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
      remove.addEventListener("click", function () {
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
        showError(describeValidationError(result));
        return;
      }
    }

    selected = selected.concat(incoming);
    renderFileList();
    setState(incoming.length + "個を追加しました");
  }

  function renderQrCode(shareUrl) {
    if (!qrBox || typeof window.QRCode !== "function") {
      return;
    }
    qrBox.innerHTML = "";
    new window.QRCode(qrBox, {
      text: shareUrl,
      width: 132,
      height: 132,
      correctLevel: window.QRCode.CorrectLevel.M
    });
  }

  /** 発行結果を画面に反映し、選択欄は操作できない状態へ切り替える。 */
  function showSharePanel(issued) {
    if (!sharePanel) {
      return;
    }
    copyValues = {
      url: issued.share_url || "",
      room: issued.room_id || "",
      password: issued.password || ""
    };
    if (shareUrlLabel) {
      shareUrlLabel.textContent = copyValues.url;
    }
    if (roomIdLabel) {
      roomIdLabel.textContent = copyValues.room;
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
    if (hint) {
      hint.hidden = true;
    }
    if (dropzone) {
      dropzone.hidden = true;
    }
    if (clearButton) {
      clearButton.hidden = true;
    }
    fileList.querySelectorAll(".lp-file-list__remove").forEach(function (button) {
      button.hidden = true;
    });
    setState("ルームへアップロードしました");
  }

  async function copyToClipboard(text) {
    if (window.navigator.clipboard && window.isSecureContext) {
      await window.navigator.clipboard.writeText(text);
      return;
    }
    // 非セキュアコンテキスト向けのフォールバック
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
    } finally {
      document.body.removeChild(helper);
    }
  }

  function readCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") || "" : "";
  }

  async function readPayload(response) {
    try {
      return await response.json();
    } catch (error) {
      return null;
    }
  }

  function errorMessageFor(response, payload, fallback) {
    // CSRF 失敗はサーバー側メッセージが英語のため、先に案内文へ差し替える。
    if (response.status === 403) {
      return "セッションの有効期限が切れた可能性があります。ページを再読み込みしてから再度お試しください。";
    }
    if (payload && typeof payload.error === "string" && payload.error) {
      return payload.error;
    }
    return fallback;
  }

  function setSubmitting(active) {
    submitting = active;
    publishButton.disabled = active || selected.length === 0;
    publishButton.setAttribute("aria-busy", active ? "true" : "false");
  }

  async function createRoom() {
    var response = await window.fetch(createUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": readCsrfToken(),
        "X-Requested-With": "fetch",
        Accept: "application/json"
      },
      body: JSON.stringify({ id: "", idMode: "auto", retention_hours: 24 })
    });
    var payload = await readPayload(response);
    if (!response.ok) {
      throw new Error(
        errorMessageFor(
          response,
          payload,
          "ルームの作成に失敗しました。時間をおいて再度お試しください。"
        )
      );
    }
    var data = (payload && payload.data) || {};
    if (!data.redirect_url || !data.room_id) {
      throw new Error("作成したルームの情報が取得できませんでした。");
    }
    return data;
  }

  async function uploadFiles(roomId) {
    var body = new FormData();
    selected.forEach(function (file) {
      body.append("upfile", file);
    });
    var response = await window.fetch(uploadUrl + "/" + encodeURIComponent(roomId), {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-CSRF-Token": readCsrfToken(),
        "X-Requested-With": "fetch",
        Accept: "application/json"
      },
      body: body
    });
    var payload = await readPayload(response);
    if (!response.ok) {
      throw new Error(
        errorMessageFor(
          response,
          payload,
          "ファイルのアップロードに失敗しました。ルーム画面から再度お試しください。"
        )
      );
    }
  }

  async function publish() {
    if (submitting || !selected.length) {
      return;
    }
    clearError();
    setSubmitting(true);
    setState("ルームを作成しています…");

    var created = null;
    try {
      created = await createRoom();
      setState("ファイルをアップロードしています…");
      await uploadFiles(created.room_id);
      setSubmitting(false);
      showSharePanel(created);
    } catch (error) {
      setSubmitting(false);
      setState(idleStateText);
      var message =
        error && error.message
          ? error.message
          : "共有リンクの発行に失敗しました。時間をおいて再度お試しください。";
      if (created) {
        // ルームは作成済みなので、共有情報だけは渡して手動アップロードへ誘導する。
        showSharePanel(created);
        showError(message + "（ルームは作成済みです。ルーム画面から追加してください）");
      } else {
        showError(message);
      }
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
        dropzone.classList.add("is-dragover");
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

  if (clearButton) {
    clearButton.addEventListener("click", function () {
      selected = [];
      clearError();
      renderFileList();
      setState("選択を解除しました");
    });
  }

  if (resetButton) {
    resetButton.addEventListener("click", function () {
      selected = [];
      if (sharePanel) {
        sharePanel.hidden = true;
      }
      publishButton.hidden = false;
      if (hint) {
        hint.hidden = false;
      }
      if (dropzone) {
        dropzone.hidden = false;
      }
      clearError();
      renderFileList();
      setState(idleStateText);
    });
  }

  root.querySelectorAll("[data-instant-copy]").forEach(function (button) {
    button.addEventListener("click", async function () {
      var value = copyValues[button.getAttribute("data-instant-copy")];
      if (!value) {
        return;
      }
      var label = button.textContent;
      try {
        await copyToClipboard(value);
        button.textContent = "コピー済み";
      } catch (error) {
        button.textContent = "コピー失敗";
      }
      window.setTimeout(function () {
        button.textContent = label;
      }, 1800);
    });
  });

  renderFileList();
})(window, document);
