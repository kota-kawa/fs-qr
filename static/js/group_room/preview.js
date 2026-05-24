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

    function renderTextPreview(file) {
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
          clearPreviewBody();
          var pre = document.createElement('pre');
          pre.className = 'group-preview-text';
          pre.textContent = text;
          body.appendChild(pre);
        })
        .catch(function (error) {
          logger.warn('Preview request failed.', error);
          setMessage(core.translate ? core.translate('group.preview_load_error', 'Could not load the preview.') : 'Could not load the preview.');
        });
    }

    function previewFile(file) {
      if (!file || file.previewable !== true) {
        notify(core.translate ? core.translate('group.preview_unsupported', 'This file type cannot be previewed.') : 'This file type cannot be previewed.');
        return;
      }

      openModal(file);

      if (file.previewType === 'image') {
        renderImagePreview(file);
        return;
      }

      if (file.previewType === 'pdf') {
        renderFramePreview(file);
        return;
      }

      if (file.previewType === 'text') {
        renderTextPreview(file);
        return;
      }

      setMessage(core.translate ? core.translate('group.preview_unsupported', 'This file type cannot be previewed.') : 'This file type cannot be previewed.');
    }

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
