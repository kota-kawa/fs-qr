/**
 * FS!QR landing-page instant upload flow.
 * 暗号化と進捗表示だけを担当し、入力・共有パネル・通信補助は共通コアを利用する。
 */
(function (window, document) {
  'use strict';

  var app = window.__FSQR_APP__;
  var root = document.querySelector('[data-instant-fsqr]');
  if (!app || !app.api || !root) {
    return;
  }

  var core = app.api.getShared('instantWidget');
  if (!core) {
    return;
  }

  var issuedKey = 'fsqr:fsqr-landing-issued';
  var widget = core.create(root, {
    // 旧実装の setState() には自動リセットが無かった（Group/Note/Task は元々タイマー
    // 付きだったため共通コアの既定値のままで問題ない）。FSQR のみ 0 を指定して、
    // 「共有リンクを発行しました」等の状態文言が数秒で消えてしまわないようにする。
    // The old setState() here had no auto-revert (Group/Note/Task already had a
    // timer, so the shared core's default is fine for them). Only FSQR needs 0,
    // so status text like "share link issued" doesn't disappear after a few seconds.
    stateResetMs: 0,
    issuedStore: { storage: window.sessionStorage, key: issuedKey }
  });
  var elements = widget.elements;
  var retentionSelect = root.querySelector('[data-instant-retention]');
  var progress = root.querySelector('[data-instant-progress]');
  var progressPhase = root.querySelector('[data-instant-progress-phase]');
  var progressPercent = root.querySelector('[data-instant-progress-percent]');
  var progressBar = root.querySelector('[data-instant-progress-bar]');
  var progressDetail = root.querySelector('[data-instant-progress-detail]');
  var cancelButton = root.querySelector('[data-instant-cancel]');
  var submitting = false;
  var cancelRequested = false;
  var activeXhr = null;
  var encryptionService = null;
  var idleStateText = widget.idleStateText;
  var tray = widget.createFileTray({
    limits: {
      maxFiles: root.getAttribute('data-max-files'),
      maxTotalSizeBytes: root.getAttribute('data-max-total-size-bytes'),
      maxTotalSizeMB: root.getAttribute('data-max-total-size-mb')
    },
    isLocked: function () { return submitting; }
  });

  if (!elements.fileInput || !elements.publishButton || !retentionSelect) {
    return;
  }

  function setProgress(value, phase, detail) {
    var safeValue = Math.max(0, Math.min(1, Number(value) || 0));
    if (progressBar) {
      progressBar.style.width = Math.round(safeValue * 100) + '%';
    }
    if (progressPercent) {
      progressPercent.textContent = Math.round(safeValue * 100) + '%';
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
    widget.setSubmitting(active, tray.count() > 0);
    if (elements.clearButton) {
      elements.clearButton.disabled = active;
    }
    tray.renderFileList();
  }

  function getEncryptionService() {
    if (encryptionService) {
      return encryptionService;
    }
    var modules = app.api.getModuleNamespace('fsQrUpload');
    if (!modules || !modules.encryption) {
      throw new Error('暗号化モジュールを読み込めませんでした。ページを再読み込みしてください。');
    }
    encryptionService = modules.encryption.createEncryptionService({
      setProgressScale: function (value) {
        setProgress(Number(value) * 0.65, '暗号化しています', 'ファイルをブラウザ内で暗号化しています。');
      },
      setStatusText: function (text) {
        if (progressDetail && text) {
          progressDetail.textContent = text;
        }
      }
    });
    return encryptionService;
  }

  function generateDownloadPassword() {
    var digits = '0123456789';
    var bytes = window.crypto.getRandomValues(new Uint8Array(6));
    var password = '';
    for (var i = 0; i < bytes.length; i += 1) {
      password += digits[bytes[i] % digits.length];
    }
    return password;
  }

  function buildUploadFormData(files, encryptedBlob, downloadPassword) {
    var formData = new FormData();
    if (files.length === 1) {
      formData.append('upfile', new File([encryptedBlob], files[0].name + '.enc', {
        type: 'application/octet-stream'
      }));
      formData.append('file_type', 'single');
    } else {
      formData.append('upfile', new File([encryptedBlob], 'encrypted_files.zip', {
        type: 'application/zip'
      }));
      formData.append('file_type', 'multiple');
    }
    formData.append('name', '');
    formData.append('download_password', downloadPassword);
    formData.append('encryption_mode', 'raw');
    formData.append('original_filename', files[0].name);
    formData.append('retention_hours', retentionSelect.value);
    return formData;
  }

  function withKey(url, key) {
    return url && key ? url + '#key=' + encodeURIComponent(key) : (url || '');
  }

  function uploadEncrypted(files, encryptedBlob, downloadPassword, shareKey) {
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      var uploadUrl = root.getAttribute('data-upload-url') || '/upload';
      activeXhr = xhr;
      xhr.open('POST', uploadUrl, true);
      xhr.setRequestHeader('X-CSRF-Token', core.readCsrfToken());
      xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
      xhr.setRequestHeader('Accept', 'application/json');
      xhr.upload.onprogress = function (event) {
        if (event.lengthComputable) {
          setProgress(0.65 + (event.loaded / event.total) * 0.35, 'アップロードしています', '暗号化したファイルを送信しています。');
        }
      };
      xhr.onload = function () {
        activeXhr = null;
        var payload = core.parseJsonText(xhr.responseText);
        if (xhr.status < 200 || xhr.status >= 300) {
          reject(new Error(core.errorMessageFor(xhr.status, payload, 'アップロードに失敗しました。', { root: root })));
          return;
        }
        var data = payload && payload.data;
        if (!payload || payload.status !== 'ok' || !data || !data.redirect_url) {
          reject(new Error('アップロード結果を取得できませんでした。'));
          return;
        }
        resolve({
          share_url: withKey(data.share_url || '', shareKey),
          id: data.id || '',
          password: data.password || downloadPassword,
          redirect_url: withKey(data.redirect_url, shareKey),
          issued_at: Date.now()
        });
      };
      xhr.onerror = function () {
        activeXhr = null;
        reject(new Error('通信に失敗しました。接続を確認して再度お試しください。'));
      };
      xhr.onabort = function () {
        activeXhr = null;
        reject(new Error('アップロードをキャンセルしました。'));
      };
      xhr.send(buildUploadFormData(files, encryptedBlob, downloadPassword));
    });
  }

  async function publish() {
    if (submitting || !tray.count()) {
      return;
    }
    widget.clearError();
    if (!window.crypto || !window.crypto.subtle) {
      widget.showError('このブラウザでは暗号化に対応していません。/fs-qr から別のブラウザでお試しください。');
      return;
    }
    cancelRequested = false;
    setSubmitting(true);
    setProgressVisible(true);
    setProgress(0, '暗号化の準備中', 'ファイルを安全に準備しています。');
    widget.setState('共有リンクを発行しています…');
    try {
      var files = tray.getFiles().slice();
      var downloadPassword = generateDownloadPassword();
      var service = getEncryptionService();
      // The six-digit password authenticates the download request. AES-GCM uses
      // a separate random key that is kept in the URL fragment only.
      // 6桁パスワードは認証専用とし、AES-GCM には URL fragment にだけ保持する乱数鍵を使う。
      var encryptedBlob = await service.encryptAndZipFilesWithProgress(files, null, 'raw');
      var shareKey = service.getLastEncryptionKey();
      if (cancelRequested) {
        throw new Error('アップロードをキャンセルしました。');
      }
      var issued = await uploadEncrypted(files, encryptedBlob, downloadPassword, shareKey);
      widget.issuedStore.remember(issued);
      setProgress(1, '完了', '共有情報を準備しています。');
      setSubmitting(false);
      widget.showSharePanel(issued, { missingUrlText: '共有URLを取得できませんでした' });
      if (elements.dropzone) {
        elements.dropzone.hidden = true;
      }
      if (retentionSelect.parentElement) {
        retentionSelect.parentElement.hidden = true;
      }
      tray.hideRemoveButtons();
      setProgressVisible(false);
      widget.setState('共有リンクを発行しました');
    } catch (error) {
      setSubmitting(false);
      setProgressVisible(false);
      widget.setState(idleStateText);
      widget.showError(error && error.message ? error.message : '共有リンクの発行に失敗しました。');
    }
  }

  tray.bindInputs();
  widget.bindCopyButtons();
  widget.bindReset(function () {
    tray.clear();
    if (elements.dropzone) {
      elements.dropzone.hidden = false;
    }
    if (retentionSelect.parentElement) {
      retentionSelect.parentElement.hidden = false;
    }
    setProgressVisible(false);
    setSubmitting(false);
    tray.renderFileList();
    widget.setState(idleStateText);
  });
  elements.publishButton.addEventListener('click', publish);
  if (cancelButton) {
    cancelButton.addEventListener('click', function () {
      if (!submitting) {
        return;
      }
      cancelRequested = true;
      if (activeXhr) {
        activeXhr.abort();
      }
      if (progressDetail) {
        progressDetail.textContent = 'キャンセルしています。暗号化中の場合は処理の完了後に停止します。';
      }
    });
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

  var issued = widget.issuedStore.read();
  if (issued) {
    widget.showSharePanel(issued);
    if (elements.dropzone) {
      elements.dropzone.hidden = true;
    }
    if (retentionSelect.parentElement) {
      retentionSelect.parentElement.hidden = true;
    }
    setProgressVisible(false);
  } else {
    tray.renderFileList();
  }
})(window, document);
