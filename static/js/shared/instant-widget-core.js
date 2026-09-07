/**
 * Shared core for the landing-page "instant" widgets.
 * 4 つのプロダクト LP に置いた「その場で使える」ボックス（FSQR / Group / Note / Task）で
 * 重複していた共通処理（状態表示・エラー表示・共有パネル・コピー・保存・通信）をまとめる。
 *
 * Usage:
 *   var widget = __FSQR_APP__.api.getShared('instantWidget').create(root, options);
 * Each instant-*.js keeps only its service-specific flow.
 */
(function (window, document) {
  'use strict';

  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }

  var STATE_RESET_MS = 2400;
  var COPY_LABEL_RESET_MS = 1800;
  var ISSUED_TTL_MS = 24 * 60 * 60 * 1000;
  var QR_SIZE = 132;
  var SESSION_EXPIRED_MESSAGE = 'セッションの有効期限が切れた可能性があります。ページを再読み込みしてから再度お試しください。';

  // --- Stateless helpers / 状態を持たない補助関数 ---

  function readCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') || '' : '';
  }

  /** Parse a JSON text without throwing. / 例外を出さずに JSON 文字列を読む。 */
  function parseJsonText(text) {
    try {
      return JSON.parse(text);
    } catch (error) {
      return null;
    }
  }

  /** Read a fetch Response body as JSON without throwing. / fetch の Response を JSON として読む。 */
  async function readJsonResponse(response) {
    try {
      return await response.json();
    } catch (error) {
      return null;
    }
  }

  /**
   * Pick the error text for a failed request.
   * CSRF 失敗はサーバー側メッセージが英語のため、先に案内文へ差し替える。
   */
  function errorMessageFor(status, payload, fallback, context) {
    if (status === 403) {
      var translated = window.FSQR_I18N && typeof window.FSQR_I18N.t === 'function'
        ? window.FSQR_I18N.t('task.create_session_expired', SESSION_EXPIRED_MESSAGE)
        : SESSION_EXPIRED_MESSAGE;
      if (context && context.root) {
        translated = context.root.getAttribute('data-session-expired-message') || translated;
      }
      return translated;
    }
    if (payload && typeof payload.error === 'string' && payload.error) {
      return payload.error;
    }
    return fallback;
  }

  function requestHeaders(extra) {
    return Object.assign({
      'X-CSRF-Token': readCsrfToken(),
      'X-Requested-With': 'fetch',
      Accept: 'application/json'
    }, extra || {});
  }

  /** POST a JSON body; resolves to { response, payload }. / JSON を POST し、レスポンスと本文を返す。 */
  async function postJson(url, body) {
    var response = await window.fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: requestHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(body)
    });
    return { response: response, payload: await readJsonResponse(response) };
  }

  /** POST multipart form data; resolves to { response, payload }. / FormData を POST する。 */
  async function postFormData(url, formData) {
    var response = await window.fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: requestHeaders(),
      body: formData
    });
    return { response: response, payload: await readJsonResponse(response) };
  }

  function formatSize(bytes) {
    if (bytes >= 1024 * 1024 * 1024) {
      return (bytes / (1024 * 1024 * 1024)).toFixed(2) + 'GB';
    }
    if (bytes >= 1024 * 1024) {
      return (bytes / (1024 * 1024)).toFixed(1) + 'MB';
    }
    if (bytes >= 1024) {
      return Math.round(bytes / 1024) + 'KB';
    }
    return bytes + 'B';
  }

  // 呼び出し側は Promise チェーン（.then/.catch）で結果を扱うため、
  // async 関数にして例外を必ず reject へ変換する。素の function のままだと
  // execCommand('copy') が失敗したときの throw が .catch() 登録前に
  // 同期的に飛び出し、「コピー失敗」表示が出せなくなる。
  // Callers consume this via a Promise chain (.then/.catch), so this must be
  // async to guarantee thrown errors become rejections. As a plain function,
  // the throw on a failed execCommand('copy') would escape synchronously
  // before .catch() is even attached, silently skipping the "copy failed" UI.
  async function copyToClipboard(text) {
    if (window.navigator.clipboard && window.isSecureContext) {
      return window.navigator.clipboard.writeText(text);
    }
    // 非セキュアコンテキスト向けのフォールバック
    var helper = document.createElement('textarea');
    helper.value = text;
    helper.setAttribute('readonly', '');
    helper.style.cssText = 'position:fixed;top:0;left:-9999px;opacity:0;';
    document.body.appendChild(helper);
    try {
      helper.select();
      if (!document.execCommand('copy')) {
        throw new Error('copy command failed');
      }
    } finally {
      document.body.removeChild(helper);
    }
  }

  /**
   * Remember the last issued room/share so a reload can show the panel again.
   * 発行済み情報を一定時間だけ保存し、リロード後も共有情報へ戻れるようにする。
   */
  function createIssuedStore(config) {
    var storage = config.storage;
    var key = config.key;
    var ttlMs = config.ttlMs || ISSUED_TTL_MS;
    var requireShareUrl = config.requireShareUrl !== false;

    function remember(issued) {
      try {
        storage.setItem(key, JSON.stringify(issued));
      } catch (error) {
        /* 保存できなくても発行自体は完了しているため無視する。 */
      }
    }

    function read() {
      try {
        var raw = storage.getItem(key);
        if (!raw) {
          return null;
        }
        var parsed = JSON.parse(raw);
        if (!parsed || !parsed.issued_at || (requireShareUrl && !parsed.share_url)) {
          return null;
        }
        if (Date.now() - Number(parsed.issued_at) > ttlMs) {
          storage.removeItem(key);
          return null;
        }
        return parsed;
      } catch (error) {
        return null;
      }
    }

    function clear() {
      try {
        storage.removeItem(key);
      } catch (error) {
        /* 削除できなくても入力欄は使える状態へ戻す。 */
      }
    }

    return { remember: remember, read: read, clear: clear };
  }

  /**
   * Create the widget controller bound to one root element.
   * options.stateResetMs   … auto-revert delay for the state label (0 = keep until next change)
   * options.issuedStore    … { storage, key, ttlMs, requireShareUrl } or null
   * options.publishSelector… selector of the publish/share button (default [data-instant-publish])
   */
  function create(root, options) {
    var opts = options || {};
    var stateResetMs = typeof opts.stateResetMs === 'number' ? opts.stateResetMs : STATE_RESET_MS;

    var elements = {
      dropzone: root.querySelector('[data-instant-dropzone]'),
      fileInput: root.querySelector('[data-instant-file-input]'),
      fileList: root.querySelector('[data-instant-file-list]'),
      publishButton: root.querySelector(opts.publishSelector || '[data-instant-publish]'),
      clearButton: root.querySelector('[data-instant-clear]'),
      resetButton: root.querySelector('[data-instant-reset]'),
      counter: root.querySelector('[data-instant-count]'),
      stateLabel: root.querySelector('[data-instant-state]'),
      errorBox: root.querySelector('[data-instant-error]'),
      hint: root.querySelector('[data-instant-hint]'),
      sharePanel: root.querySelector('[data-instant-share-panel]'),
      qrBox: root.querySelector('[data-instant-qr]'),
      shareUrlLabel: root.querySelector('[data-instant-share-url]'),
      // FSQR LP uses data-instant-id, the other LPs data-instant-room-id / 両方の属性名を受け付ける
      roomIdLabel: root.querySelector('[data-instant-room-id], [data-instant-id]'),
      passwordLabel: root.querySelector('[data-instant-password]'),
      openLink: root.querySelector('[data-instant-open]')
    };

    var idleStateText = elements.stateLabel ? elements.stateLabel.textContent : '';
    var stateTimer = null;
    var copyValues = { url: '', room: '', id: '', password: '' };
    var issuedStore = opts.issuedStore ? createIssuedStore(opts.issuedStore) : null;

    function setState(text) {
      if (!elements.stateLabel) {
        return;
      }
      elements.stateLabel.textContent = text;
      if (stateTimer) {
        window.clearTimeout(stateTimer);
        stateTimer = null;
      }
      if (stateResetMs > 0 && text !== idleStateText) {
        stateTimer = window.setTimeout(function () {
          elements.stateLabel.textContent = idleStateText;
        }, stateResetMs);
      }
    }

    function showError(message) {
      if (!elements.errorBox) {
        return;
      }
      elements.errorBox.textContent = message;
      elements.errorBox.hidden = false;
    }

    function clearError() {
      if (!elements.errorBox) {
        return;
      }
      elements.errorBox.textContent = '';
      elements.errorBox.hidden = true;
    }

    /** Toggle the busy state of the publish button. / 発行ボタンの busy 状態を切り替える。 */
    function setSubmitting(active, hasContent) {
      if (!elements.publishButton) {
        return;
      }
      elements.publishButton.disabled = active || hasContent === false;
      elements.publishButton.setAttribute('aria-busy', active ? 'true' : 'false');
    }

    function renderQrCode(url) {
      if (!elements.qrBox || !url || typeof window.QRCode !== 'function') {
        return;
      }
      elements.qrBox.textContent = '';
      new window.QRCode(elements.qrBox, {
        text: url,
        width: QR_SIZE,
        height: QR_SIZE,
        correctLevel: window.QRCode.CorrectLevel.M
      });
    }

    /**
     * Fill and reveal the share panel; the caller hides its own input controls afterwards.
     * 共有パネルへ発行結果を反映して表示する。入力欄の無効化は呼び出し元が続けて行う。
     */
    function showSharePanel(issued, panelOptions) {
      if (!elements.sharePanel) {
        return false;
      }
      var panelOpts = panelOptions || {};
      var identifier = issued.room_id || issued.id || '';
      copyValues = {
        url: issued.share_url || '',
        room: identifier,
        id: identifier,
        password: issued.password || ''
      };
      if (elements.shareUrlLabel) {
        elements.shareUrlLabel.textContent = copyValues.url || (panelOpts.missingUrlText || '');
      }
      if (elements.roomIdLabel) {
        elements.roomIdLabel.textContent = identifier;
      }
      if (elements.passwordLabel) {
        elements.passwordLabel.textContent = copyValues.password;
      }
      if (elements.openLink && issued.redirect_url) {
        elements.openLink.setAttribute('href', issued.redirect_url);
      }
      renderQrCode(copyValues.url);

      elements.sharePanel.hidden = false;
      if (elements.publishButton) {
        elements.publishButton.hidden = true;
      }
      if (elements.hint) {
        elements.hint.hidden = true;
      }
      if (elements.clearButton) {
        elements.clearButton.hidden = true;
      }
      return true;
    }

    /** Return to the editing state (reset button). / 共有パネルを閉じて入力状態へ戻す。 */
    function restoreEditing() {
      if (issuedStore) {
        issuedStore.clear();
      }
      if (elements.sharePanel) {
        elements.sharePanel.hidden = true;
      }
      if (elements.publishButton) {
        elements.publishButton.hidden = false;
      }
      if (elements.hint) {
        elements.hint.hidden = false;
      }
      clearError();
      setState(idleStateText);
    }

    /** [data-instant-copy] buttons copy the issued values. / 発行結果のコピーボタン。 */
    function bindCopyButtons() {
      root.querySelectorAll('[data-instant-copy]').forEach(function (button) {
        button.addEventListener('click', function () {
          var value = copyValues[button.getAttribute('data-instant-copy')];
          if (!value) {
            return;
          }
          var label = button.textContent;
          copyToClipboard(value).then(function () {
            button.textContent = 'コピー済み';
          }).catch(function () {
            button.textContent = 'コピー失敗';
          }).finally(function () {
            window.setTimeout(function () {
              button.textContent = label;
            }, COPY_LABEL_RESET_MS);
          });
        });
      });
    }

    function bindReset(afterReset) {
      if (!elements.resetButton) {
        return;
      }
      elements.resetButton.addEventListener('click', function () {
        restoreEditing();
        if (typeof afterReset === 'function') {
          afterReset();
        }
      });
    }

    /**
     * Drag & drop onto the dropzone. `isLocked()` suppresses the hover state while submitting.
     * ドロップゾーンの D&D。送信中は isLocked() でホバー表示を抑制する。
     */
    function bindDropzone(onFiles, isLocked) {
      var dropzone = elements.dropzone;
      if (!dropzone) {
        return;
      }
      var locked = typeof isLocked === 'function' ? isLocked : function () { return false; };
      ['dragenter', 'dragover'].forEach(function (type) {
        dropzone.addEventListener(type, function (event) {
          event.preventDefault();
          if (!locked()) {
            dropzone.classList.add('is-dragover');
          }
        });
      });
      ['dragleave', 'drop'].forEach(function (type) {
        dropzone.addEventListener(type, function (event) {
          event.preventDefault();
          dropzone.classList.remove('is-dragover');
        });
      });
      dropzone.addEventListener('drop', function (event) {
        if (event.dataTransfer && event.dataTransfer.files) {
          onFiles(event.dataTransfer.files);
        }
      });
    }

    /**
     * Selected-file list for the FSQR / Group LPs.
     * FSQR・Group の LP で使うファイル一覧。検証は共有モジュール（uploadValidation）に委ねる。
     */
    function createFileTray(trayOptions) {
      var trayOpts = trayOptions || {};
      var limits = trayOpts.limits || {};
      var isLocked = typeof trayOpts.isLocked === 'function' ? trayOpts.isLocked : function () { return false; };
      var selected = [];

      function getValidator() {
        return appNamespace.api.getShared('uploadValidation') || null;
      }

      function totalSize() {
        return selected.reduce(function (total, file) {
          return total + (Number.isFinite(file.size) ? file.size : 0);
        }, 0);
      }

      function renderFileList() {
        if (!elements.fileList) {
          return;
        }
        var locked = isLocked();
        elements.fileList.textContent = '';
        selected.forEach(function (file, index) {
          var item = document.createElement('li');
          item.className = 'lp-file-list__item';

          var name = document.createElement('span');
          name.className = 'lp-file-list__name';
          name.textContent = file.name;

          var size = document.createElement('span');
          size.className = 'lp-file-list__size';
          size.textContent = formatSize(file.size);

          var remove = document.createElement('button');
          remove.type = 'button';
          remove.className = 'lp-file-list__remove';
          remove.textContent = '外す';
          remove.setAttribute('aria-label', file.name + ' を選択から外す');
          remove.disabled = locked;
          remove.addEventListener('click', function () {
            if (isLocked()) {
              return;
            }
            selected.splice(index, 1);
            clearError();
            renderFileList();
            setState('ファイルを外しました');
          });

          item.appendChild(name);
          item.appendChild(size);
          item.appendChild(remove);
          elements.fileList.appendChild(item);
        });

        if (elements.counter) {
          elements.counter.textContent = selected.length
            ? selected.length + '個 / ' + formatSize(totalSize())
            : 'ファイル未選択';
        }
        if (elements.publishButton) {
          elements.publishButton.disabled = selected.length === 0 || locked;
        }
        if (elements.clearButton) {
          elements.clearButton.hidden = selected.length === 0;
        }
      }

      function addFiles(files) {
        if (isLocked()) {
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
            showError(validator.describeFailure(result, { scope: 'landing' }));
            return;
          }
        }

        selected = selected.concat(incoming);
        renderFileList();
        setState(incoming.length + '個を追加しました');
      }

      function clear() {
        selected = [];
      }

      function hideRemoveButtons() {
        if (!elements.fileList) {
          return;
        }
        elements.fileList.querySelectorAll('.lp-file-list__remove').forEach(function (button) {
          button.hidden = true;
        });
      }

      function bindInputs() {
        if (elements.fileInput) {
          elements.fileInput.addEventListener('change', function () {
            addFiles(elements.fileInput.files);
            elements.fileInput.value = '';
          });
        }
        bindDropzone(addFiles, isLocked);
      }

      return {
        getFiles: function () { return selected; },
        count: function () { return selected.length; },
        totalSize: totalSize,
        renderFileList: renderFileList,
        addFiles: addFiles,
        clear: clear,
        hideRemoveButtons: hideRemoveButtons,
        bindInputs: bindInputs
      };
    }

    return {
      root: root,
      elements: elements,
      idleStateText: idleStateText,
      issuedStore: issuedStore,
      setState: setState,
      showError: showError,
      clearError: clearError,
      setSubmitting: setSubmitting,
      renderQrCode: renderQrCode,
      showSharePanel: showSharePanel,
      restoreEditing: restoreEditing,
      bindCopyButtons: bindCopyButtons,
      bindReset: bindReset,
      bindDropzone: bindDropzone,
      createFileTray: createFileTray
    };
  }

  appNamespace.api.setShared('instantWidget', Object.freeze({
    create: create,
    createIssuedStore: createIssuedStore,
    readCsrfToken: readCsrfToken,
    parseJsonText: parseJsonText,
    readJsonResponse: readJsonResponse,
    errorMessageFor: errorMessageFor,
    postJson: postJson,
    postFormData: postFormData,
    formatSize: formatSize,
    copyToClipboard: copyToClipboard
  }));
})(window, document);
