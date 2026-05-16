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

    async function encryptAndZipFilesWithProgress(files, key) {
      var keyBuffer = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(key));
      var cryptoKey = await crypto.subtle.importKey('raw', keyBuffer, { name: 'AES-GCM' }, false, ['encrypt']);

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
      encryptAndZipFilesWithProgress: encryptAndZipFilesWithProgress
    };
  }

  modules.encryption = {
    createEncryptionService: createEncryptionService
  };
})(window);
