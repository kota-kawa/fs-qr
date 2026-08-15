/**
 * Instant draft board for the FS!QR Task landing page.
 *
 * LPに置いた「その場で書けるタスクボード」。ボードを作らずにタスクを
 * 書き出せ、下書きはこの端末のlocalStorageにだけ保存する。共有ボタンを
 * 押した時点で初めてボードを作成し、書き出したタスクを順番に登録する。
 */
(function (window, document) {
  "use strict";

  var SAVE_DEBOUNCE_MS = 300;
  var STATE_RESET_MS = 2400;

  var root = document.querySelector("[data-instant-board]");
  if (!root) {
    return;
  }

  var addForm = root.querySelector("[data-instant-add-form]");
  var titleInput = root.querySelector("[data-instant-title-input]");
  var taskList = root.querySelector("[data-instant-task-list]");
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
  if (!addForm || !titleInput || !taskList || !publishButton) {
    return;
  }

  var createUrl = root.getAttribute("data-create-url") || "/create_task_room";
  var itemUrlTemplate =
    root.getAttribute("data-item-url-template") || "/task/{room_id}/items";
  var storageKey = root.getAttribute("data-storage-key") || "fsqr:task-draft";
  var maxItems = parseInt(root.getAttribute("data-max-items"), 10) || 200;
  var maxTitleLength = parseInt(root.getAttribute("data-max-title-length"), 10) || 200;
  var idleStateText = stateLabel ? stateLabel.textContent : "";
  var issuedKey = storageKey + ":issued";
  var ISSUED_TTL_MS = 24 * 60 * 60 * 1000;

  var tasks = [];
  var saveTimer = null;
  var stateTimer = null;
  var submitting = false;
  var copyValues = { url: "", room: "", password: "" };

  function readDraft() {
    try {
      var raw = window.localStorage.getItem(storageKey);
      var parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return [];
    }
  }

  function writeDraft(list) {
    try {
      if (list.length) {
        window.localStorage.setItem(storageKey, JSON.stringify(list));
      } else {
        window.localStorage.removeItem(storageKey);
      }
      return true;
    } catch (error) {
      return false;
    }
  }

  function scheduleSave() {
    if (saveTimer) {
      window.clearTimeout(saveTimer);
    }
    saveTimer = window.setTimeout(function () {
      if (writeDraft(tasks)) {
        setState("この端末に保存しました");
      }
    }, SAVE_DEBOUNCE_MS);
  }

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

  function renderTaskList() {
    taskList.textContent = "";
    tasks.forEach(function (task, index) {
      var item = document.createElement("li");
      item.className = "lp-task-list__item";

      var title = document.createElement("span");
      title.className = "lp-task-list__title";
      title.textContent = task.title;

      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "lp-task-list__remove";
      remove.textContent = "削除";
      remove.setAttribute("aria-label", task.title + " を下書きから削除");
      remove.addEventListener("click", function () {
        tasks.splice(index, 1);
        renderTaskList();
        scheduleSave();
        setState("タスクを削除しました");
      });

      item.appendChild(title);
      item.appendChild(remove);
      taskList.appendChild(item);
    });

    if (counter) {
      counter.textContent = tasks.length ? tasks.length + "件のタスク" : "タスク未追加";
    }
    publishButton.disabled = tasks.length === 0 || submitting;
    if (clearButton) {
      clearButton.hidden = tasks.length === 0;
    }
  }

  function addTask(rawTitle) {
    var title = (rawTitle || "").trim().slice(0, maxTitleLength);
    if (!title) {
      return;
    }
    clearError();
    if (tasks.length >= maxItems) {
      showError("タスクは" + maxItems + "件までです。");
      return;
    }
    tasks.push({ title: title });
    renderTaskList();
    scheduleSave();
    setState("タスクを追加しました");
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

  /** 発行結果を画面に反映し、下書き入力は操作できない状態へ切り替える。 */
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
    if (addForm) {
      addForm.hidden = true;
    }
    if (clearButton) {
      clearButton.hidden = true;
    }
    taskList.querySelectorAll(".lp-task-list__remove").forEach(function (button) {
      button.hidden = true;
    });
    setState("ボードへ登録しました");
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
    publishButton.disabled = active || tasks.length === 0;
    publishButton.setAttribute("aria-busy", active ? "true" : "false");
  }

  async function createBoard() {
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
          "ボードの作成に失敗しました。時間をおいて再度お試しください。"
        )
      );
    }
    var data = (payload && payload.data) || {};
    if (!data.redirect_url || !data.room_id) {
      throw new Error("作成したボードの情報が取得できませんでした。");
    }
    return data;
  }

  async function createTaskItem(roomId, title) {
    var url = itemUrlTemplate.replace("{room_id}", encodeURIComponent(roomId));
    var response = await window.fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": readCsrfToken(),
        "X-Requested-With": "fetch",
        Accept: "application/json"
      },
      body: JSON.stringify({ title: title, board_status: "todo" })
    });
    if (!response.ok) {
      var payload = await readPayload(response);
      throw new Error(
        errorMessageFor(
          response,
          payload,
          "タスクの登録に失敗しました。ボード画面から追加してください。"
        )
      );
    }
  }

  async function publish() {
    if (submitting || !tasks.length) {
      return;
    }
    clearError();
    setSubmitting(true);
    setState("ボードを作成しています…");

    var created = null;
    try {
      created = await createBoard();
      // 順序を保つため直列に登録する（並列だと position の採番順が崩れる）
      for (var i = 0; i < tasks.length; i += 1) {
        setState("タスクを登録しています…（" + (i + 1) + "/" + tasks.length + "）");
        await createTaskItem(created.room_id, tasks[i].title);
      }
      writeDraft([]);
      rememberIssued({
        share_url: created.share_url || "",
        room_id: created.room_id || "",
        password: created.password || "",
        redirect_url: created.redirect_url,
        issued_at: Date.now()
      });
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
        // ボードは作成済みなので、共有情報だけは渡して手動登録へ誘導する。
        writeDraft([]);
        rememberIssued({
          share_url: created.share_url || "",
          room_id: created.room_id || "",
          password: created.password || "",
          redirect_url: created.redirect_url,
          issued_at: Date.now()
        });
        showSharePanel(created);
        showError(message + "（ボードは作成済みです。ボード画面から追加してください）");
      } else {
        showError(message);
      }
    }
  }

  addForm.addEventListener("submit", function (event) {
    event.preventDefault();
    addTask(titleInput.value);
    titleInput.value = "";
    titleInput.focus();
  });

  publishButton.addEventListener("click", publish);

  if (clearButton) {
    clearButton.addEventListener("click", function () {
      tasks = [];
      clearError();
      renderTaskList();
      scheduleSave();
      setState("下書きを削除しました");
    });
  }

  if (resetButton) {
    resetButton.addEventListener("click", function () {
      try {
        window.localStorage.removeItem(issuedKey);
      } catch (error) {
        /* 削除できなくても入力欄は使える状態へ戻す */
      }
      tasks = [];
      if (sharePanel) {
        sharePanel.hidden = true;
      }
      publishButton.hidden = false;
      if (hint) {
        hint.hidden = false;
      }
      if (addForm) {
        addForm.hidden = false;
      }
      clearError();
      renderTaskList();
      setState(idleStateText);
      titleInput.focus();
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

  var issuedBoard = readIssued();
  if (issuedBoard) {
    // 直前に発行したボードがあれば、リロード後も共有情報へ戻れるようにする。
    tasks = [];
    showSharePanel(issuedBoard);
  } else {
    tasks = readDraft();
  }
  renderTaskList();
})(window, document);
