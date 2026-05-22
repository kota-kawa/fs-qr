(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('fsQrUpload');

  function translate(key, fallback) {
    if (window.FSQR_I18N && typeof window.FSQR_I18N.t === 'function') {
      return window.FSQR_I18N.t(key, fallback);
    }
    return fallback || key;
  }

  function createEncryptionService(options) {
    var setProgressScale = options.setProgressScale;
    var setStatusText = typeof options.setStatusText === 'function'
      ? options.setStatusText
      : function () {};
    var lastEncryptionKey = '';

    function base64UrlEncode(bytes) {
      var binary = '';
      for (var i = 0; i < bytes.length; i += 1) {
        binary += String.fromCharCode(bytes[i]);
      }
      return btoa(binary)
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=+$/g, '');
    }

    function base64UrlDecode(value) {
      var normalized = String(value || '').replace(/-/g, '+').replace(/_/g, '/');
      while (normalized.length % 4) {
        normalized += '=';
      }
      var binary = atob(normalized);
      var bytes = new Uint8Array(binary.length);
      for (var i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i);
      }
      return bytes;
    }

    function generateEncryptionKey() {
      var bytes = crypto.getRandomValues(new Uint8Array(32));
      return base64UrlEncode(bytes);
    }

    async function importEncryptionKey(key, mode) {
      if (mode === 'password') {
        var keyBuffer = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(key));
        return crypto.subtle.importKey('raw', keyBuffer, { name: 'AES-GCM' }, false, ['encrypt']);
      }
      var rawKey = base64UrlDecode(key);
      if (rawKey.length !== 32) {
        throw new Error(translate('upload.error_processing', 'Encryption key is invalid.'));
      }
      return crypto.subtle.importKey('raw', rawKey, { name: 'AES-GCM' }, false, ['encrypt']);
    }

    async function encryptAndZipFilesWithProgress(files, key, mode) {
      lastEncryptionKey = key || generateEncryptionKey();
      var keyMode = mode || (key ? 'password' : 'raw');
      var cryptoKey = await importEncryptionKey(lastEncryptionKey, keyMode);

      if (files.length === 1) {
        var singleFile = files[0];
        setStatusText(translate('upload.encrypting_step', 'Encrypting: {name} ({current}/{total})').replace('{name}', singleFile.name).replace('{current}', '1').replace('{total}', '1'));
        var singleIv = crypto.getRandomValues(new Uint8Array(12));
        var singleFileBuffer = await singleFile.arrayBuffer();

        setStatusText(translate('upload.encrypting_step_pct', 'Encrypting: {name} ({current}/{total}, {pct}%)').replace('{name}', singleFile.name).replace('{current}', '1').replace('{total}', '1').replace('{pct}', '25'));
        setProgressScale(0.25);

        var singleEncryptedBuffer = await crypto.subtle.encrypt({ name: 'AES-GCM', iv: singleIv }, cryptoKey, singleFileBuffer);

        setStatusText(translate('upload.encrypted_done', 'Encrypted: {name} ({current}/{total})').replace('{name}', singleFile.name).replace('{current}', '1').replace('{total}', '1'));
        setProgressScale(1);
        return new Blob([singleIv, singleEncryptedBuffer]);
      }

      var zip = new JSZip();

      for (var i = 0; i < files.length; i += 1) {
        var file = files[i];
        var iv = crypto.getRandomValues(new Uint8Array(12));
        var fileBuffer = await file.arrayBuffer();
        var encryptedBuffer = await crypto.subtle.encrypt({ name: 'AES-GCM', iv: iv }, cryptoKey, fileBuffer);
        zip.file(`${file.name}.enc`, new Blob([iv, encryptedBuffer]));

        var encryptProgress = (i + 1) / files.length;
        setStatusText(translate('upload.encrypting_step', 'Encrypting: {name} ({current}/{total})').replace('{name}', file.name).replace('{current}', String(i + 1)).replace('{total}', String(files.length)));
        setProgressScale(encryptProgress);
      }

      return zip.generateAsync({ type: 'blob' }, function (metadata) {
        setStatusText(translate('upload.compressing', 'Compressing... {percent}%').replace('{percent}', String(Math.round(metadata.percent))));
        setProgressScale(1);
      });
    }

    return {
      encryptAndZipFilesWithProgress: encryptAndZipFilesWithProgress,
      getLastEncryptionKey: function () {
        return lastEncryptionKey;
      }
    };
  }

  modules.encryption = {
    createEncryptionService: createEncryptionService
  };
})(window);
