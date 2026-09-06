/**
 * Browser-side AES-GCM decryption for the FSQR download page.
 * ブラウザ内で AES-GCM 復号を行う処理。鍵の扱いと復号手順は変更しないこと。
 * 判断の背景は docs/decisions/0004-browser-side-fsqr-encryption.md を参照。
 */
(function (window) {
  'use strict';

  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('fsQrDownload');

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

  function createDecryptionService(context) {
    /**
     * Raw 32-byte keys come from the fragment; passwords are stretched with SHA-256.
     * フラグメント経由の鍵は 32 バイトの生鍵、パスワードは SHA-256 で鍵長へ伸ばす。
     */
    async function importDecryptionKey(key) {
      if (context.decryptionKeyMode === 'raw-base64url') {
        var rawKey = base64UrlDecode(key);
        if (rawKey.length !== 32) {
          throw new Error(context.translate('download.decrypt_failed', 'Decryption failed.'));
        }
        return crypto.subtle.importKey('raw', rawKey, { name: 'AES-GCM' }, false, ['decrypt']);
      }
      var keyBuffer = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(key));
      return crypto.subtle.importKey('raw', keyBuffer, { name: 'AES-GCM' }, false, ['decrypt']);
    }

    async function decryptFile(encryptedBuffer, key, iv) {
      var cryptoKey = await importDecryptionKey(key);

      try {
        return await crypto.subtle.decrypt({ name: 'AES-GCM', iv: iv }, cryptoKey, encryptedBuffer);
      } catch (error) {
        console.error('Decryption error:', error);
        return null;
      }
    }

    /** Single file: the first 12 bytes are the IV. / 単一ファイルは先頭 12 バイトが IV。 */
    async function decryptSingleFile(encryptedBlob, key) {
      try {
        var arrayBuffer = await encryptedBlob.arrayBuffer();
        var iv = arrayBuffer.slice(0, 12);
        var encryptedContent = arrayBuffer.slice(12);
        context.setStatusText(
          context.formatMessage('download.decrypting_progress', 'Decrypting... {percent}%', { percent: 35 })
        );
        context.setProgress(0.35);
        var decryptedContent = await decryptFile(encryptedContent, key, iv);

        if (!decryptedContent) {
          return null;
        }

        context.setStatusText(
          context.formatMessage('download.decrypting_progress', 'Decrypting... {percent}%', { percent: 100 })
        );
        context.setProgress(1);
        return new Blob([decryptedContent]);
      } catch (error) {
        console.error('Single-file decryption error:', error);
        return null;
      }
    }

    /** Multiple files: each ZIP entry is decrypted individually. / 複数ファイルは ZIP の各要素を個別に復号する。 */
    async function decryptAndBuildZip(encryptedBlob, key) {
      var zip = await JSZip.loadAsync(encryptedBlob);
      var decryptedZip = new JSZip();
      var fileNames = Object.keys(zip.files);
      var totalFiles = fileNames.length;
      var processedFiles = 0;

      for (var i = 0; i < fileNames.length; i += 1) {
        var fileName = fileNames[i];
        var fileEntry = zip.file(fileName);
        if (!fileEntry) {
          continue;
        }

        var fileData = await fileEntry.async('arraybuffer');
        var iv = fileData.slice(0, 12);
        var encryptedContent = fileData.slice(12);
        var decryptedContent = await decryptFile(encryptedContent, key, iv);

        if (!decryptedContent) {
          return null;
        }

        decryptedZip.file(fileName.replace(/\.enc$/i, ''), decryptedContent);
        processedFiles += 1;
        context.setStatusText(
          context.formatMessage(
            'download.decrypting_progress',
            'Decrypting... {percent}%',
            { percent: Math.round((processedFiles / totalFiles) * 100) }
          )
        );
        context.setProgress(totalFiles ? processedFiles / totalFiles : 1);
      }

      return decryptedZip.generateAsync({ type: 'blob' });
    }

    return {
      decryptSingleFile: decryptSingleFile,
      decryptAndBuildZip: decryptAndBuildZip
    };
  }

  modules.decrypt = {
    base64UrlDecode: base64UrlDecode,
    createDecryptionService: createDecryptionService
  };
})(window);
