/**
 * Instant draft editor for the FS!QR Note landing page.
 *
 * LPに置いた「その場で書けるノート」。ルームを作らずに書き始められ、
 * 下書きはこの端末のlocalStorageにだけ保存する。共有ボタンを押した時点で
 * 初めてサーバー側にルームを作成し、下書き本文ごと引き継ぐ。
 */
(function (window, document) {
  "use strict";

  var SAVE_DEBOUNCE_MS = 400;
  var STATE_RESET_MS = 2400;

  var root = document.querySelector("[data-instant-note]");
  if (!root) {
    return;
  }

  var editor = root.querySelector("[data-instant-editor]");
  var shareButton = root.querySelector("[data-instant-share]");
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
  if (!editor || !shareButton) {
    return;
  }

  var createUrl = root.getAttribute("data-create-url") || "/create_note_room";
  var storageKey = root.getAttribute("data-storage-key") || "fsqr:note-draft";
  var maxLength = parseInt(root.getAttribute("data-max-length"), 10);
  if (!maxLength || maxLength < 1) {
    maxLength = 10000;
  }
  var idleStateText = stateLabel ? stateLabel.textContent : "";
  var savedStateText = root.getAttribute("data-saved-label") || idleStateText;
  var issuedKey = storageKey + ":issued";
  var ISSUED_TTL_MS = 24 * 60 * 60 * 1000;

  var saveTimer = null;
  var stateTimer = null;
  var submitting = false;
  var copyValues = { url: "", room: "", password: "" };

  /** localStorage は Safari のプライベートモードなどで例外を投げるため常に保護する。 */
  function readDraft() {
    try {
      return window.localStorage.getItem(storageKey) || "";
    } catch (error) {
      return "";
    }
  }

  function writeDraft(value) {
    try {
      if (value) {
        window.localStorage.setItem(storageKey, value);
      } else {
        window.localStorage.removeItem(storageKey);
      }
      return true;
    } catch (error) {
      return false;
    }
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

  function updateCounter() {
    if (!counter) {
      return;
    }
    counter.textContent = editor.value.length + " / " + maxLength + "文字";
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

  function scheduleSave() {
    if (saveTimer) {
      window.clearTimeout(saveTimer);
    }
    saveTimer = window.setTimeout(function () {
      if (writeDraft(editor.value)) {
        setState(savedStateText);
      }
    }, SAVE_DEBOUNCE_MS);
  }

  /** 発行済みノートを一時的に覚えておき、再訪時にも共有情報へ戻れるようにする。 */
  function rememberIssued(issued) {
    try {
      window.localStorage.setItem(issuedKey, JSON.stringify(issued));
    } catch (error) {
      /* 保存できなくても発行自体は完了しているため無視する */
    }
  }

  function readIssued() {
    try {
      var raw = window.localStorage.getItem(issuedKey);
      if (!raw) {
        return null;
      }
      var parsed = JSON.parse(raw);
      if (!parsed || !parsed.share_url || !parsed.issued_at) {
        return null;
      }
      if (Date.now() - Number(parsed.issued_at) > ISSUED_TTL_MS) {
        window.localStorage.removeItem(issuedKey);
        return null;
      }
      return parsed;
    } catch (error) {
      return null;
    }
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

  /** 発行結果を画面に反映し、下書き欄は読み取り専用へ切り替える。 */
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
    shareButton.hidden = true;
    if (hint) {
      hint.hidden = true;
    }
    if (clearButton) {
      clearButton.hidden = true;
    }
    editor.readOnly = true;
    setState("ノートルームへ引き継ぎました");
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

  function errorMessageFor(response, payload) {
    // CSRF 失敗はサーバー側メッセージが英語のため、先に案内文へ差し替える。
    if (response.status === 403) {
      return "セッションの有効期限が切れた可能性があります。ページを再読み込みしてから再度お試しください。";
    }
    if (payload && typeof payload.error === "string" && payload.error) {
      return payload.error;
    }
    return "ノートの作成に失敗しました。時間をおいて再度お試しください。";
  }

  function setSubmitting(active) {
    submitting = active;
    shareButton.disabled = active;
    shareButton.setAttribute("aria-busy", active ? "true" : "false");
  }

  async function createRoomFromDraft() {
    if (submitting) {
      return;
    }
    clearError();
    // 送信直前の入力も取りこぼさないよう、デバウンス待ちの保存を先に確定させる。
    if (saveTimer) {
      window.clearTimeout(saveTimer);
      saveTimer = null;
    }
    writeDraft(editor.value);

    setSubmitting(true);
    setState("共有リンクを発行しています…");

    try {
      var response = await window.fetch(createUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": readCsrfToken(),
          "X-Requested-With": "fetch",
          Accept: "application/json"
        },
        body: JSON.stringify({
          id: "",
          idMode: "auto",
          retention_hours: 24,
          content: editor.value
        })
      });

      var payload = null;
      try {
        payload = await response.json();
      } catch (error) {
        payload = null;
      }

      if (!response.ok) {
        throw new Error(errorMessageFor(response, payload));
      }

      var data = (payload && payload.data) || {};
      if (typeof data.redirect_url !== "string" || !data.redirect_url) {
        throw new Error("作成したノートへの移動先が取得できませんでした。");
      }

      var issued = {
        share_url: data.share_url || "",
        room_id: data.room_id || "",
        password: data.password || "",
        redirect_url: data.redirect_url,
        issued_at: Date.now()
      };
      // ルーム側へ本文を引き継げたので、端末に残した下書きは破棄する。
      writeDraft("");
      rememberIssued(issued);
      setSubmitting(false);
      showSharePanel(issued);
    } catch (error) {
      setSubmitting(false);
      setState(idleStateText);
      showError(
        error && error.message
          ? error.message
          : "ノートの作成に失敗しました。時間をおいて再度お試しください。"
      );
    }
  }

  var issuedNote = readIssued();
  if (issuedNote) {
    // 直前に発行したノートがあれば、リロード後も共有情報へ戻れるようにする。
    editor.value = "";
    showSharePanel(issuedNote);
  } else {
    var restored = readDraft();
    if (restored) {
      editor.value = restored.slice(0, maxLength);
    }
  }
  updateCounter();

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

  editor.addEventListener("input", function () {
    clearError();
    updateCounter();
    scheduleSave();
  });

  shareButton.addEventListener("click", createRoomFromDraft);

  var resetButton = root.querySelector("[data-instant-reset]");
  if (resetButton) {
    resetButton.addEventListener("click", function () {
      try {
        window.localStorage.removeItem(issuedKey);
      } catch (error) {
        /* 削除できなくても入力欄は使える状態へ戻す */
      }
      if (sharePanel) {
        sharePanel.hidden = true;
      }
      shareButton.hidden = false;
      if (hint) {
        hint.hidden = false;
      }
      if (clearButton) {
        clearButton.hidden = false;
      }
      editor.readOnly = false;
      editor.value = "";
      updateCounter();
      setState(idleStateText);
      editor.focus();
    });
  }

  if (clearButton) {
    clearButton.addEventListener("click", function () {
      editor.value = "";
      writeDraft("");
      clearError();
      updateCounter();
      setState("下書きを削除しました");
      editor.focus();
    });
  }
})(window, document);
