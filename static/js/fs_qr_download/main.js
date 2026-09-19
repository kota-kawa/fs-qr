/**
 * Entry point for the FSQR download page: download → decrypt → save.
 * ダウンロード画面の入口。取得・復号・保存の流れをつなぐ。
 */
(function (window, document) {
  'use strict';

  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('fsQrDownload');

  document.addEventListener('DOMContentLoaded', function () {
    var context = modules.core.createContext();
    if (!context.downloadForm) {
      return;
    }

    var decryption = modules.decrypt.createDecryptionService(context);
    var transfer = modules.transfer.createTransferService(context);

    context.downloadForm.addEventListener('submit', async function (event) {
      event.preventDefault();
      if (context.requiresFragmentKey && !context.decryptionKey) {
        context.setStatusText(
          context.translate(
            'download.key_required',
            'Open the complete share URL to download this file.'
          )
        );
        return;
      }
      context.showSpinner(
        context.formatMessage('download.downloading_progress', 'Downloading... {percent}%', { percent: 0 }),
        'receiving'
      );
      context.setProgress(0);

      try {
        var downloadResult = await transfer.downloadEncryptedBlob();
        var encryptedBlob = downloadResult.blob;
        var fileType = downloadResult.fileType;
        var originalFilename = downloadResult.originalFilename;

        context.showSpinner(
          context.formatMessage('download.decrypting_progress', 'Decrypting... {percent}%', { percent: 0 }),
          'decrypting'
        );
        context.setProgress(0);

        var decryptedBlob;
        var downloadFilename;

        if (fileType === 'single') {
          decryptedBlob = await decryption.decryptSingleFile(encryptedBlob, context.decryptionKey);
          downloadFilename = originalFilename || (context.secureId + '_decrypted');
        } else {
          decryptedBlob = await decryption.decryptAndBuildZip(encryptedBlob, context.decryptionKey);
          downloadFilename = context.secureId + '.zip';
        }

        if (!decryptedBlob) {
          throw new Error(context.translate('download.decrypt_failed', 'Decryption failed.'));
        }

        transfer.saveBlob(decryptedBlob, downloadFilename);
        context.setStatusText(context.translate('download.complete', 'Download complete!'));
        context.setProgress(1);
      } catch (error) {
        window.showAlertModal(
          error instanceof Error ? error.message : context.translate('download.decrypt_failed', 'Decryption failed.')
        );
      } finally {
        context.hideSpinner();
      }
    });
  });
})(window, document);
