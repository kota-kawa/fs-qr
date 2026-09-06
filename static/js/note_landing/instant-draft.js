/**
 * Note landing-page instant draft flow.
 * 下書きの保存だけを担当し、共有・通信・共有パネルは共通コアを利用する。
 */
(function (window, document) {
  'use strict';

  var app = window.__FSQR_APP__;
  var root = document.querySelector('[data-instant-note]');
  if (!app || !app.api || !root) {
    return;
  }

  var core = app.api.getShared('instantWidget');
  if (!core) {
    return;
  }

  var storageKey = root.getAttribute('data-storage-key') || 'fsqr:note-draft';
  var widget = core.create(root, {
    publishSelector: '[data-instant-share]',
    issuedStore: { storage: window.localStorage, key: storageKey + ':issued' }
  });
  var elements = widget.elements;
  var editor = root.querySelector('[data-instant-editor]');
  var shareButton = root.querySelector('[data-instant-share]');
  var maxLength = parseInt(root.getAttribute('data-max-length'), 10) || 10000;
  var saveTimer = null;
  var submitting = false;
  var idleStateText = widget.idleStateText;
  var savedStateText = root.getAttribute('data-saved-label') || idleStateText;
  var store = widget.issuedStore;

  if (!editor || !shareButton) {
    return;
  }

  function readDraft() {
    try {
      return window.localStorage.getItem(storageKey) || '';
    } catch (error) {
      return '';
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

  function updateCounter() {
    if (elements.counter) {
      elements.counter.textContent = editor.value.length + ' / ' + maxLength + '文字';
    }
  }

  function scheduleSave() {
    if (saveTimer) {
      window.clearTimeout(saveTimer);
    }
    saveTimer = window.setTimeout(function () {
      if (writeDraft(editor.value)) {
        widget.setState(savedStateText);
      }
    }, 400);
  }

  function setSubmitting(active) {
    submitting = active;
    widget.setSubmitting(active, true);
  }

  function showIssued(issued) {
    editor.value = '';
    editor.readOnly = true;
    widget.showSharePanel(issued);
    widget.setState('ノートルームへ引き継ぎました');
  }

  async function publish() {
    if (submitting) {
      return;
    }
    widget.clearError();
    if (saveTimer) {
      window.clearTimeout(saveTimer);
      saveTimer = null;
    }
    writeDraft(editor.value);
    setSubmitting(true);
    widget.setState('共有リンクを発行しています…');
    try {
      var result = await core.postJson(root.getAttribute('data-create-url') || '/create_note_room', {
        id: '',
        idMode: 'auto',
        retention_hours: 24,
        content: editor.value
      });
      if (!result.response.ok) {
        throw new Error(core.errorMessageFor(
          result.response.status,
          result.payload,
          'ノートの作成に失敗しました。時間をおいて再度お試しください。',
          { root: root }
        ));
      }
      var data = (result.payload && result.payload.data) || {};
      if (!data.redirect_url) {
        throw new Error('作成したノートへの移動先が取得できませんでした。');
      }
      var issued = {
        share_url: data.share_url || '',
        room_id: data.room_id || '',
        password: data.password || '',
        redirect_url: data.redirect_url,
        issued_at: Date.now()
      };
      writeDraft('');
      store.remember(issued);
      setSubmitting(false);
      showIssued(issued);
    } catch (error) {
      setSubmitting(false);
      widget.setState(idleStateText);
      widget.showError(error && error.message
        ? error.message
        : 'ノートの作成に失敗しました。時間をおいて再度お試しください。');
    }
  }

  widget.bindCopyButtons();
  widget.bindReset(function () {
    editor.readOnly = false;
    editor.value = '';
    if (elements.clearButton) {
      elements.clearButton.hidden = false;
    }
    updateCounter();
    writeDraft('');
    widget.setState(idleStateText);
    editor.focus();
  });
  editor.addEventListener('input', function () {
    widget.clearError();
    updateCounter();
    scheduleSave();
  });
  shareButton.addEventListener('click', publish);

  if (elements.clearButton) {
    elements.clearButton.addEventListener('click', function () {
      editor.value = '';
      writeDraft('');
      widget.clearError();
      updateCounter();
      widget.setState('下書きを削除しました');
      editor.focus();
    });
  }

  var issued = store.read();
  if (issued) {
    showIssued(issued);
  } else {
    editor.value = readDraft().slice(0, maxLength);
  }
  updateCounter();
})(window, document);
