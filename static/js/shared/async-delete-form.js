/**
 * 削除フォームの非同期送信モジュール
 *
 * data-confirm-submit 属性を持つ .owner-delete-form に対して:
 * 1. 確認ダイアログ表示後、fetch API で非同期POSTを行う
 * 2. 送信中はボタンをローディング状態にし、即座にUIフィードバックを返す
 * 3. レスポンスに応じてリダイレクトまたはエラー表示を行う
 */
(function () {
  "use strict";

  function initAsyncDeleteForms() {
    document
      .querySelectorAll(".owner-delete-form[data-confirm-submit]")
      .forEach(function (form) {
        form.addEventListener("submit", async function (event) {
          event.preventDefault();

          var confirmed = await window.showConfirmModal(
            form.dataset.confirmSubmit,
            {
              title: form.dataset.confirmTitle || undefined,
              confirmLabel: form.dataset.confirmLabel || undefined,
            }
          );
          if (!confirmed) {
            return;
          }

          var submitBtn = form.querySelector('button[type="submit"]');
          var originalContent = "";
          if (submitBtn) {
            originalContent = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML =
              '<span class="async-delete-spinner"></span>' +
              (form.dataset.deletingLabel || "削除中...");
          }

          try {
            var formData = new FormData(form);
            var response = await fetch(form.action, {
              method: "POST",
              headers: {
                Accept: "application/json",
                "X-Requested-With": "XMLHttpRequest",
              },
              body: formData,
            });

            if (response.ok) {
              var contentType = response.headers.get("content-type") || "";
              if (contentType.includes("application/json")) {
                var data = await response.json();
                if (data.redirect_url) {
                  window.location.href = data.redirect_url;
                  return;
                }
              }
              // JSON以外の成功レスポンスやリダイレクト
              if (response.redirected) {
                window.location.href = response.url;
                return;
              }
              // デフォルトのリダイレクト先
              window.location.href = "/remove-succes";
              return;
            }

            // エラーレスポンス処理
            var errorMessage =
              "削除に失敗しました。時間をおいて再度お試しください。";
            try {
              var contentType = response.headers.get("content-type") || "";
              if (contentType.includes("application/json")) {
                var errorData = await response.json();
                if (errorData.message) {
                  errorMessage = errorData.message;
                }
              }
            } catch (_) {
              // JSONパース失敗は無視
            }
            window.showAlertModal(errorMessage);
          } catch (networkError) {
            window.showAlertModal(
              "通信エラーが発生しました。ネットワーク接続を確認してください。"
            );
          } finally {
            if (submitBtn) {
              submitBtn.disabled = false;
              submitBtn.innerHTML = originalContent;
            }
          }
        });
      });
  }

  // スピナーのスタイルを動的に追加
  if (!document.getElementById("asyncDeleteSpinnerStyle")) {
    var style = document.createElement("style");
    style.id = "asyncDeleteSpinnerStyle";
    style.textContent =
      ".async-delete-spinner{display:inline-block;width:1em;height:1em;" +
      "border:2px solid currentColor;border-right-color:transparent;" +
      "border-radius:50%;animation:asyncDeleteSpin .6s linear infinite;" +
      "margin-right:.4em;vertical-align:middle}" +
      "@keyframes asyncDeleteSpin{to{transform:rotate(360deg)}}";
    document.head.appendChild(style);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAsyncDeleteForms);
  } else {
    initAsyncDeleteForms();
  }
})();
