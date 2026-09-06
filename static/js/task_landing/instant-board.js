/**
 * Task landing-page instant board flow.
 * 下書きの編集を担当し、ルーム作成・共有・通信は共通コアへ集約する。
 */
(function (window, document) {
  'use strict';

  var app = window.__FSQR_APP__;
  var root = document.querySelector('[data-instant-board]');
  if (!app || !app.api || !root) {
    return;
  }

  var core = app.api.getShared('instantWidget');
  if (!core) {
    return;
  }

  var storageKey = root.getAttribute('data-storage-key') || 'fsqr:task-draft';
  var widget = core.create(root, {
    issuedStore: { storage: window.localStorage, key: storageKey + ':issued' }
  });
  var elements = widget.elements;
  var addForm = root.querySelector('[data-instant-add-form]');
  var titleInput = root.querySelector('[data-instant-title-input]');
  var taskList = root.querySelector('[data-instant-task-list]');
  var maxItems = parseInt(root.getAttribute('data-max-items'), 10) || 200;
  var maxTitleLength = parseInt(root.getAttribute('data-max-title-length'), 10) || 200;
  var itemUrlTemplate = root.getAttribute('data-item-url-template') || '/api/task/{room_id}/items';
  var tasks = [];
  var saveTimer = null;
  var submitting = false;
  var idleStateText = widget.idleStateText;

  if (!addForm || !titleInput || !taskList || !elements.publishButton) {
    return;
  }

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
        widget.setState('この端末に保存しました');
      }
    }, 300);
  }

  function renderTaskList() {
    taskList.textContent = '';
    tasks.forEach(function (task, index) {
      var item = document.createElement('li');
      item.className = 'lp-task-list__item';
      var title = document.createElement('span');
      title.className = 'lp-task-list__title';
      title.textContent = task.title;
      var remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'lp-task-list__remove';
      remove.textContent = '削除';
      remove.setAttribute('aria-label', task.title + ' を下書きから削除');
      remove.disabled = submitting;
      remove.addEventListener('click', function () {
        if (submitting) {
          return;
        }
        tasks.splice(index, 1);
        renderTaskList();
        scheduleSave();
        widget.setState('タスクを削除しました');
      });
      item.appendChild(title);
      item.appendChild(remove);
      taskList.appendChild(item);
    });
    if (elements.counter) {
      elements.counter.textContent = tasks.length ? tasks.length + '件のタスク' : 'タスク未追加';
    }
    widget.setSubmitting(submitting, tasks.length > 0);
    if (elements.clearButton) {
      elements.clearButton.hidden = tasks.length === 0;
    }
  }

  function addTask(rawTitle) {
    var title = (rawTitle || '').trim().slice(0, maxTitleLength);
    if (!title) {
      return;
    }
    widget.clearError();
    if (tasks.length >= maxItems) {
      widget.showError('タスクは' + maxItems + '件までです。');
      return;
    }
    tasks.push({ title: title });
    renderTaskList();
    scheduleSave();
    widget.setState('タスクを追加しました');
  }

  function setSubmitting(active) {
    submitting = active;
    widget.setSubmitting(active, tasks.length > 0);
    renderTaskList();
  }

  function showIssued(issued) {
    addForm.hidden = true;
    tasks = [];
    renderTaskList();
    widget.showSharePanel(issued);
    widget.setState('ボードへ登録しました');
  }

  async function createBoard() {
    var result = await core.postJson(root.getAttribute('data-create-url') || '/create_task_room', {
      id: '',
      idMode: 'auto',
      retention_hours: 24
    });
    if (!result.response.ok) {
      throw new Error(core.errorMessageFor(
        result.response.status,
        result.payload,
        'ボードの作成に失敗しました。時間をおいて再度お試しください。',
        { root: root }
      ));
    }
    var data = (result.payload && result.payload.data) || {};
    if (!data.redirect_url || !data.room_id) {
      throw new Error('作成したボードの情報が取得できませんでした。');
    }
    return data;
  }

  async function createTaskItem(roomId, title) {
    var url = itemUrlTemplate.replace('{room_id}', encodeURIComponent(roomId));
    var result = await core.postJson(url, { title: title, board_status: 'todo' });
    if (!result.response.ok) {
      throw new Error(core.errorMessageFor(
        result.response.status,
        result.payload,
        'タスクの登録に失敗しました。ボード画面から追加してください。',
        { root: root }
      ));
    }
  }

  async function publish() {
    if (submitting || !tasks.length) {
      return;
    }
    widget.clearError();
    var pendingTasks = tasks.slice();
    setSubmitting(true);
    widget.setState('ボードを作成しています…');
    var created = null;
    try {
      created = await createBoard();
      for (var i = 0; i < pendingTasks.length; i += 1) {
        widget.setState('タスクを登録しています…（' + (i + 1) + '/' + pendingTasks.length + '）');
        await createTaskItem(created.room_id, pendingTasks[i].title);
      }
      writeDraft([]);
      var issued = {
        share_url: created.share_url || '',
        room_id: created.room_id || '',
        password: created.password || '',
        redirect_url: created.redirect_url,
        issued_at: Date.now()
      };
      widget.issuedStore.remember(issued);
      setSubmitting(false);
      showIssued(issued);
    } catch (error) {
      setSubmitting(false);
      widget.setState(idleStateText);
      var message = error && error.message
        ? error.message
        : '共有リンクの発行に失敗しました。時間をおいて再度お試しください。';
      if (created) {
        var issuedAfterFailure = {
          share_url: created.share_url || '',
          room_id: created.room_id || '',
          password: created.password || '',
          redirect_url: created.redirect_url,
          issued_at: Date.now()
        };
        widget.issuedStore.remember(issuedAfterFailure);
        showIssued(issuedAfterFailure);
        widget.showError(message + '（ボードは作成済みです。ボード画面から追加してください）');
      } else {
        widget.showError(message);
      }
    }
  }

  widget.bindCopyButtons();
  widget.bindReset(function () {
    tasks = [];
    addForm.hidden = false;
    renderTaskList();
    writeDraft([]);
    widget.setState(idleStateText);
    titleInput.focus();
  });
  addForm.addEventListener('submit', function (event) {
    event.preventDefault();
    addTask(titleInput.value);
    titleInput.value = '';
    titleInput.focus();
  });
  elements.publishButton.addEventListener('click', publish);
  if (elements.clearButton) {
    elements.clearButton.addEventListener('click', function () {
      if (submitting) {
        return;
      }
      tasks = [];
      widget.clearError();
      renderTaskList();
      scheduleSave();
      widget.setState('下書きを削除しました');
    });
  }

  var issued = widget.issuedStore.read();
  if (issued) {
    showIssued(issued);
  } else {
    tasks = readDraft();
    renderTaskList();
  }
})(window, document);
