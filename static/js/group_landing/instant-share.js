/**
 * Group landing-page instant share flow.
 * 共通の入力・共有パネル・通信処理は instant-widget-core.js に委譲する。
 */
(function (window, document) {
  'use strict';

  var app = window.__FSQR_APP__;
  var root = document.querySelector('[data-instant-share-box]');
  if (!app || !app.api || !root) {
    return;
  }

  var core = app.api.getShared('instantWidget');
  if (!core) {
    return;
  }

  var widget = core.create(root);
  var elements = widget.elements;
  var uploadUrl = root.getAttribute('data-upload-url') || '/group_upload';
  var limits = {
    maxFiles: root.getAttribute('data-max-files'),
    maxTotalSizeBytes: root.getAttribute('data-max-total-size-bytes'),
    maxTotalSizeMB: root.getAttribute('data-max-total-size-mb')
  };
  var submitting = false;
  var idleStateText = widget.idleStateText;
  var tray = widget.createFileTray({
    limits: limits,
    isLocked: function () { return submitting; }
  });

  function requestError(response, payload, fallback) {
    return core.errorMessageFor(response.status, payload, fallback, { root: root });
  }

  function setSubmitting(active) {
    submitting = active;
    widget.setSubmitting(active, tray.count() > 0);
    if (elements.dropzone) {
      elements.dropzone.setAttribute('aria-disabled', active ? 'true' : 'false');
    }
    tray.renderFileList();
  }

  async function createRoom() {
    var result = await core.postJson(root.getAttribute('data-create-url') || '/create_group_room', {
      id: '',
      idMode: 'auto',
      retention_hours: 24
    });
    if (!result.response.ok) {
      throw new Error(requestError(result.response, result.payload, 'ルームの作成に失敗しました。時間をおいて再度お試しください。'));
    }
    var data = (result.payload && result.payload.data) || {};
    if (!data.redirect_url || !data.room_id) {
      throw new Error('作成したルームの情報が取得できませんでした。');
    }
    return data;
  }

  async function uploadFiles(roomId) {
    var formData = new FormData();
    tray.getFiles().forEach(function (file) {
      formData.append('upfile', file);
    });
    var result = await core.postFormData(uploadUrl + '/' + encodeURIComponent(roomId), formData);
    if (!result.response.ok) {
      throw new Error(requestError(result.response, result.payload, 'ファイルのアップロードに失敗しました。ルーム画面から再度お試しください。'));
    }
  }

  async function publish() {
    if (submitting || !tray.count()) {
      return;
    }
    widget.clearError();
    setSubmitting(true);
    widget.setState('ルームを作成しています…');
    var created = null;
    try {
      created = await createRoom();
      widget.setState('ファイルをアップロードしています…');
      await uploadFiles(created.room_id);
      setSubmitting(false);
      widget.showSharePanel(created);
      if (elements.dropzone) {
        elements.dropzone.hidden = true;
      }
      tray.hideRemoveButtons();
      widget.setState('ルームへアップロードしました');
    } catch (error) {
      setSubmitting(false);
      widget.setState(idleStateText);
      var message = error && error.message
        ? error.message
        : '共有リンクの発行に失敗しました。時間をおいて再度お試しください。';
      if (created) {
        widget.showSharePanel(created);
        if (elements.dropzone) {
          elements.dropzone.hidden = true;
        }
        tray.hideRemoveButtons();
        widget.showError(message + '（ルームは作成済みです。ルーム画面から追加してください）');
      } else {
        widget.showError(message);
      }
    }
  }

  tray.bindInputs();
  widget.bindCopyButtons();
  widget.bindReset(function () {
    tray.clear();
    if (elements.dropzone) {
      elements.dropzone.hidden = false;
    }
    tray.renderFileList();
    setSubmitting(false);
    widget.setState(idleStateText);
  });

  if (elements.publishButton) {
    elements.publishButton.addEventListener('click', publish);
  }
  if (elements.clearButton) {
    elements.clearButton.addEventListener('click', function () {
      if (submitting) {
        return;
      }
      tray.clear();
      widget.clearError();
      tray.renderFileList();
      widget.setState('選択を解除しました');
    });
  }
  tray.renderFileList();
})(window, document);
