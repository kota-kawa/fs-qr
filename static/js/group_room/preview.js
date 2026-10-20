(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('groupRoom');
  var core = modules.core || {};

  function createPreviewManager(options) {
    var roomId = options.roomId;
    var overlay = options.overlay;
    var dialog = options.dialog;
    var title = options.title;
    var body = options.body;
    var closeButton = options.closeButton;
    var downloadLink = options.downloadLink;
    var logger = options.logger || { warn: function () {} };
    var previousActiveElement = null;
    var previewToken = 0;
    var htmlPreview = null;
    var htmlVersion = 0;

    function translate(key, fallback) {
      return core.translate ? core.translate(key, fallback) : fallback;
    }

    function notify(message) {
      if (typeof window.showAlertModal === 'function') {
        window.showAlertModal(message);
        return;
      }
      window.alert(message);
    }

    function encodeFilename(filename) {
      return encodeURIComponent(filename);
    }

    function getPreviewUrl(file) {
      return `/preview/${roomId}/${encodeFilename(file.name)}`;
    }

    function getDownloadUrl(file) {
      return `/download/${roomId}/${encodeFilename(file.name)}`;
    }

    function clearPreviewBody() {
      htmlPreview = null;
      while (body.firstChild) {
        body.removeChild(body.firstChild);
      }
      body.className = 'group-preview-body';
    }

    function setMessage(message) {
      clearPreviewBody();
      body.classList.add('is-centered');
      var messageElement = document.createElement('p');
      messageElement.className = 'group-preview-message';
      messageElement.textContent = message;
      body.appendChild(messageElement);
    }

    function openModal(file) {
      previousActiveElement = document.activeElement;
      title.textContent = file.name;
      downloadLink.href = getDownloadUrl(file);
      downloadLink.setAttribute('download', file.name);
      overlay.classList.add('is-visible');
      overlay.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
      closeButton.focus();
    }

    function closePreview() {
      previewToken += 1;
      overlay.classList.remove('is-visible');
      overlay.setAttribute('aria-hidden', 'true');
      document.body.style.removeProperty('overflow');
      clearPreviewBody();
      if (previousActiveElement && typeof previousActiveElement.focus === 'function') {
        previousActiveElement.focus();
      }
    }

    function renderImagePreview(file) {
      clearPreviewBody();
      body.classList.add('is-centered');
      var image = document.createElement('img');
      image.className = 'group-preview-image';
      image.src = getPreviewUrl(file);
      image.alt = core.formatMessage ? core.formatMessage('group.preview_alt', '{name} preview', { name: file.name }) : `${file.name} preview`;
      image.onerror = function () {
        setMessage(core.translate ? core.translate('group.preview_load_error', 'Could not load the preview.') : 'Could not load the preview.');
      };
      body.appendChild(image);
    }

    function renderFramePreview(file) {
      clearPreviewBody();
      var frame = document.createElement('iframe');
      frame.className = 'group-preview-frame';
      frame.title = core.formatMessage ? core.formatMessage('group.preview_alt', '{name} preview', { name: file.name }) : `${file.name} preview`;
      frame.src = getPreviewUrl(file);
      body.appendChild(frame);
    }

    function renderTextPreview(file, token) {
      clearPreviewBody();
      body.classList.add('is-centered');
      setMessage(core.translate ? core.translate('common.loading', 'Loading...') : 'Loading...');
      window.fetch(getPreviewUrl(file), { credentials: 'same-origin' })
        .then(function (response) {
          if (!response.ok) {
            throw new Error(`Preview request failed: ${response.status}`);
          }
          return response.text();
        })
        .then(function (text) {
          if (token !== previewToken) {
            return;
          }
          clearPreviewBody();
          var pre = document.createElement('pre');
          pre.className = 'group-preview-text';
          pre.textContent = text;
          body.appendChild(pre);
        })
        .catch(function (error) {
          if (token !== previewToken) {
            return;
          }
          logger.warn('Preview request failed.', error);
          setMessage(core.translate ? core.translate('group.preview_load_error', 'Could not load the preview.') : 'Could not load the preview.');
        });
    }

    function showHtmlStatus(message) {
      htmlPreview.status.textContent = message;
      htmlPreview.status.hidden = false;
    }

    // Uploaded HTML always opens without scripts. Running them is a per-open
    // choice; stopping replaces the viewer so the script document is discarded.
    // The viewer page renders it one frame deeper under a frame-src 'none' CSP.
    function renderHtmlFrame(scriptsEnabled) {
      var state = htmlPreview;
      var version = ++htmlVersion;
      state.notice.textContent = scriptsEnabled
        ? translate('group.html_preview_scripts_running', 'JavaScript is running in an isolated frame. Network access and page navigation are restricted.')
        : translate('group.html_preview_scripts_off', 'JavaScript is not running. Run it only if you trust the person who uploaded this file.');
      state.toggle.textContent = scriptsEnabled
        ? translate('group.html_preview_stop_scripts', 'Stop')
        : translate('group.html_preview_run_scripts', 'Run JavaScript');
      state.toggle.setAttribute('aria-pressed', String(scriptsEnabled));
      state.scriptsEnabled = scriptsEnabled;
      state.status.hidden = true;
      if (state.frame) {
        state.frame.remove();
      }
      var frame = document.createElement('iframe');
      frame.className = 'group-preview-frame group-html-preview-frame';
      frame.title = core.formatMessage ? core.formatMessage('group.preview_alt', '{name} preview', { name: state.file.name }) : `${state.file.name} preview`;
      frame.setAttribute('referrerpolicy', 'no-referrer');
      frame.src = '/group-html-viewer';
      state.frame = frame;
      state.version = version;
      state.viewerReady = false;
      state.container.appendChild(frame);
      // A viewer blocked by CSP or a failed load never reports back.
      window.setTimeout(function () {
        if (state === htmlPreview && version === state.version && !state.viewerReady) {
          showHtmlStatus(translate('group.preview_load_error', 'Could not load the preview.'));
        }
      }, 10000);
    }

    function showHtmlPreview(file, source) {
      clearPreviewBody();
      var container = document.createElement('div');
      container.className = 'group-html-preview';
      var toolbar = document.createElement('div');
      toolbar.className = 'group-html-preview-toolbar';
      var notice = document.createElement('p');
      notice.className = 'group-html-preview-notice';
      var toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'group-html-preview-toggle';
      var status = document.createElement('p');
      status.className = 'group-html-preview-status';
      status.setAttribute('role', 'status');
      status.hidden = true;
      toolbar.appendChild(notice);
      toolbar.appendChild(toggle);
      container.appendChild(toolbar);
      container.appendChild(status);
      body.appendChild(container);
      htmlPreview = {
        file: file,
        source: source,
        container: container,
        notice: notice,
        toggle: toggle,
        status: status,
        frame: null,
        scriptsEnabled: false,
        version: 0
      };
      toggle.addEventListener('click', function () {
        renderHtmlFrame(!htmlPreview.scriptsEnabled);
      });
      renderHtmlFrame(false);
    }

    function renderHtmlPreview(file, token) {
      setMessage(translate('common.loading', 'Loading...'));
      window.fetch(getPreviewUrl(file), { credentials: 'same-origin' })
        .then(function (response) {
          if (response.status === 413) {
            return { tooLarge: true };
          }
          if (!response.ok) {
            throw new Error(`Preview request failed: ${response.status}`);
          }
          return response.text().then(function (source) {
            return { source: source };
          });
        })
        .then(function (result) {
          if (token !== previewToken) {
            return;
          }
          if (result.tooLarge) {
            setMessage(translate('group.html_preview_too_large', 'This HTML file is too large to preview. Download it to view it.'));
            return;
          }
          showHtmlPreview(file, result.source);
        })
        .catch(function (error) {
          if (token !== previewToken) {
            return;
          }
          logger.warn('Preview request failed.', error);
          setMessage(translate('group.preview_load_error', 'Could not load the preview.'));
        });
    }

    function previewFile(file) {
      if (!file || file.previewable !== true) {
        notify(core.translate ? core.translate('group.preview_unsupported', 'This file type cannot be previewed.') : 'This file type cannot be previewed.');
        return;
      }

      previewToken += 1;
      openModal(file);

      if (file.previewType === 'html') {
        renderHtmlPreview(file, previewToken);
        return;
      }

      if (file.previewType === 'image') {
        renderImagePreview(file);
        return;
      }

      if (file.previewType === 'pdf') {
        renderFramePreview(file);
        return;
      }

      if (file.previewType === 'text') {
        renderTextPreview(file, previewToken);
        return;
      }

      setMessage(core.translate ? core.translate('group.preview_unsupported', 'This file type cannot be previewed.') : 'This file type cannot be previewed.');
    }

    window.addEventListener('message', function (event) {
      var data = event.data;
      if (!htmlPreview || !htmlPreview.frame || event.source !== htmlPreview.frame.contentWindow ||
          event.origin !== window.location.origin || !data || data.type !== 'html-preview') {
        return;
      }
      if (data.state === 'viewer-ready') {
        htmlPreview.viewerReady = true;
        htmlPreview.frame.contentWindow.postMessage({
          type: 'group-html-render',
          source: htmlPreview.source,
          scriptsEnabled: htmlPreview.scriptsEnabled,
          version: htmlPreview.version
        }, window.location.origin);
        return;
      }
      if (data.version !== htmlPreview.version) {
        return;
      }
      if (data.state === 'cdn-error') {
        showHtmlStatus(translate('group.html_preview_cdn_error', 'Some supported CDN resources could not be loaded, so the layout may differ.'));
      } else if (data.state === 'error') {
        showHtmlStatus(translate('group.preview_load_error', 'Could not load the preview.'));
      }
    });

    closeButton.addEventListener('click', closePreview);
    overlay.addEventListener('click', function (event) {
      if (event.target === overlay) {
        closePreview();
      }
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && overlay.classList.contains('is-visible')) {
        closePreview();
      }
    });
    if (dialog) {
      dialog.addEventListener('click', function (event) {
        event.stopPropagation();
      });
    }

    return {
      previewFile: previewFile
    };
  }

  modules.preview = {
    createPreviewManager: createPreviewManager
  };
})(window);
