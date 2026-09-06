/**
 * Shared progress spinner / transfer card controller.
 * FSQR のアップロード・ダウンロード、Group のアップロード・ダウンロードで
 * それぞれ書かれていた「進捗カードの表示・非表示・フェーズ切替・進捗バー更新」を一本化する。
 *
 * createProgressSpinner({
 *   root,                 // element shown/hidden as a whole / 全体の表示・非表示対象
 *   displayValue,         // 'grid' | 'flex' | '' (removeProperty) used when showing
 *   hiddenClass,          // optional class toggled together with display (e.g. 'spinner-container--hidden')
 *   animationContainer,   // element receiving phase classes / フェーズ用クラスを付ける要素
 *   phases,               // { phaseName: { className, eyebrow } }
 *   eyebrow, text, detail,// text nodes / 見出し・本文・補足
 *   bars                  // { primary: element, secondary: element } progress bars (scaleX)
 * })
 */
(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var helpers = appNamespace.api.getShared('runtimeHelpers');
  if (!helpers) {
    throw new Error('Shared runtime helpers are not initialized.');
  }

  function createProgressSpinner(options) {
    var opts = options || {};
    var root = opts.root || null;
    var displayValue = typeof opts.displayValue === 'string' ? opts.displayValue : '';
    var hiddenClass = opts.hiddenClass || '';
    var animationContainer = opts.animationContainer || null;
    var phases = opts.phases || {};
    var eyebrow = opts.eyebrow || null;
    var text = opts.text || null;
    var detail = opts.detail || null;
    var bars = opts.bars || {};

    var phaseClassNames = Object.keys(phases).map(function (name) {
      return phases[name].className;
    }).filter(Boolean);

    /** Switch the visual phase (e.g. encrypting → uploading). / 表示フェーズを切り替える。 */
    function setPhase(phaseName) {
      var phase = phases[phaseName];
      if (animationContainer && phaseClassNames.length) {
        phaseClassNames.forEach(function (className) {
          animationContainer.classList.remove(className);
        });
        if (phase && phase.className) {
          animationContainer.classList.add(phase.className);
        }
      }
      if (phase && typeof phase.eyebrow === 'string') {
        helpers.setElementText(eyebrow, phase.eyebrow);
      }
    }

    function show() {
      if (!root) {
        return;
      }
      if (displayValue) {
        root.style.display = displayValue;
      } else {
        helpers.showElement(root);
      }
      if (hiddenClass) {
        root.classList.remove(hiddenClass);
      }
    }

    function hide() {
      if (!root) {
        return;
      }
      helpers.hideElement(root);
      if (hiddenClass) {
        root.classList.add(hiddenClass);
      }
    }

    function setEyebrow(value) {
      helpers.setElementText(eyebrow, value);
    }

    function setText(value) {
      helpers.setElementText(text, value);
    }

    function setDetail(value) {
      helpers.setElementText(detail, value);
    }

    /** Update one progress bar (0..1). / 指定した進捗バーを更新する（0〜1）。 */
    function setProgress(scale, barName) {
      helpers.setProgressScale(bars[barName || 'primary'], scale);
    }

    function resetProgress() {
      Object.keys(bars).forEach(function (barName) {
        helpers.setProgressScale(bars[barName], 0);
      });
    }

    /** Bring the card into view on long pages. / 長いページでもカードが見えるようにスクロールする。 */
    function scrollIntoCenter() {
      if (!root || typeof root.scrollIntoView !== 'function') {
        return;
      }
      window.requestAnimationFrame(function () {
        try {
          root.scrollIntoView({ behavior: 'smooth', block: 'center' });
        } catch (error) {
          root.scrollIntoView(true);
        }
      });
    }

    return {
      show: show,
      hide: hide,
      setPhase: setPhase,
      setEyebrow: setEyebrow,
      setText: setText,
      setDetail: setDetail,
      setProgress: setProgress,
      resetProgress: resetProgress,
      scrollIntoCenter: scrollIntoCenter
    };
  }

  appNamespace.api.setShared('progressSpinner', Object.freeze({
    createProgressSpinner: createProgressSpinner
  }));
})(window);
