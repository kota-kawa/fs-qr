(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('fsQrUpload');

  function createEncryptionService(options) {
    var setProgressScale = options.setProgressScale;

    async function encryptAndZipFilesWithProgress(files, key) {
      var keyBuffer = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(key));
      var cryptoKey = await crypto.subtle.importKey('raw', keyBuffer, { name: 'AES-GCM' }, false, ['encrypt']);

      if (files.length === 1) {
        var singleFile = files[0];
        var singleIv = crypto.getRandomValues(new Uint8Array(12));
        var singleFileBuffer = await singleFile.arrayBuffer();

        setProgressScale(0.25);

        var singleEncryptedBuffer = await crypto.subtle.encrypt({ name: 'AES-GCM', iv: singleIv }, cryptoKey, singleFileBuffer);

        setProgressScale(0.5);
        return new Blob([singleIv, singleEncryptedBuffer]);
      }

      var zip = new JSZip();

      for (var i = 0; i < files.length; i += 1) {
        var file = files[i];
        var iv = crypto.getRandomValues(new Uint8Array(12));
        var fileBuffer = await file.arrayBuffer();
        var encryptedBuffer = await crypto.subtle.encrypt({ name: 'AES-GCM', iv: iv }, cryptoKey, fileBuffer);
        zip.file(`${file.name}.enc`, new Blob([iv, encryptedBuffer]));

        var encryptProgress = ((i + 1) / files.length) * 25;
        setProgressScale(encryptProgress / 100);
      }

      return zip.generateAsync({ type: 'blob' }, function (metadata) {
        var zipProgress = 25 + (metadata.percent / 4);
        setProgressScale(zipProgress / 100);
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
