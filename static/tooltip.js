(() => {
  const TOOLTIP_CLASS = "fsqr-tooltip";
  const TOOLTIP_ATTR = "data-tooltip";
  const ORIGINAL_TITLE_ATTR = "data-tooltip-title";
  const SKIP_ATTR = "data-tooltip-skip";
  const IGNORE_SELECTOR = "input, textarea, select, option";
  const VIEWPORT_MARGIN = 10;
  const GAP = 10;
  const MAX_TOOLTIP_WIDTH = 320;

  let tooltip = null;
  let currentTarget = null;
  let showTimer = null;
  let hideTimer = null;
  let initialized = false;

  function clearTimers() {
    if (showTimer) {
      clearTimeout(showTimer);
      showTimer = null;
    }
    if (hideTimer) {
      clearTimeout(hideTimer);
      hideTimer = null;
    }
  }

  function getTooltipElement() {
    if (tooltip && document.body.contains(tooltip)) {
      return tooltip;
    }

    tooltip = document.createElement("div");
    tooltip.className = TOOLTIP_CLASS;
    tooltip.setAttribute("role", "tooltip");
    tooltip.setAttribute("hidden", "");
    tooltip.setAttribute("aria-hidden", "true");
    document.body.appendChild(tooltip);
    return tooltip;
  }

  function isElementDisabled(element) {
    return element.disabled || element.getAttribute("aria-disabled") === "true";
  }

  function shouldSkipElement(element) {
    if (!element || !element.matches) {
      return true;
    }
    if (element.hasAttribute(SKIP_ATTR)) {
      return true;
    }
    if (element.closest(`[${SKIP_ATTR}]`)) {
      return true;
    }
    if (element.matches(IGNORE_SELECTOR) || element.closest(IGNORE_SELECTOR)) {
      return true;
    }
    return false;
  }

  function extractText(element) {
    const custom = element.getAttribute(TOOLTIP_ATTR);
    if (custom) {
      return custom.trim();
    }

    const migratedTitle = element.getAttribute(ORIGINAL_TITLE_ATTR);
    if (migratedTitle) {
      return migratedTitle.trim();
    }

    const title = element.getAttribute("title");
    if (title) {
      return title.trim();
    }

    const ariaLabel = element.getAttribute("aria-label");
    if (ariaLabel) {
      return ariaLabel.trim();
    }

    return "";
  }

  function ensureTooltipAttributes(element) {
    if (!element || !element.matches) {
      return;
    }
    if (shouldSkipElement(element)) {
      return;
    }
    if (element.hasAttribute(ORIGINAL_TITLE_ATTR)) {
      return;
    }
    const title = element.getAttribute("title");
    if (!title || !title.trim()) {
      return;
    }
    element.setAttribute(ORIGINAL_TITLE_ATTR, title);
    element.removeAttribute("title");
  }

  function discoverTargets(root = document) {
    if (!root || !root.querySelectorAll) {
      return;
    }
    root.querySelectorAll("[title]").forEach((element) => {
      ensureTooltipAttributes(element);
    });
  }

  function findTarget(eventTarget) {
    if (!eventTarget || !eventTarget.closest) {
      return null;
    }
    const candidate = eventTarget.closest(
      `[${TOOLTIP_ATTR}], [${ORIGINAL_TITLE_ATTR}], [title], [aria-label]`
    );
    if (!candidate || shouldSkipElement(candidate) || isElementDisabled(candidate)) {
      return null;
    }
    const text = extractText(candidate);
    if (!text) {
      return null;
    }
    return candidate;
  }

  function updatePosition(element, tip) {
    const rect = element.getBoundingClientRect();
    const viewportWidth = document.documentElement.clientWidth;
    const viewportHeight = document.documentElement.clientHeight;
    const maxWidth = Math.min(MAX_TOOLTIP_WIDTH, viewportWidth - VIEWPORT_MARGIN * 2);

    tip.style.maxWidth = `${Math.max(120, maxWidth)}px`;
    tip.style.left = "0px";
    tip.style.top = "0px";

    const tipRect = tip.getBoundingClientRect();
    const centeredLeft = rect.left + rect.width / 2 - tipRect.width / 2;
    let left = Math.min(
      viewportWidth - tipRect.width - VIEWPORT_MARGIN,
      Math.max(VIEWPORT_MARGIN, centeredLeft)
    );

    const placeTop = rect.top >= tipRect.height + GAP + VIEWPORT_MARGIN;
    const placement = placeTop ? "top" : "bottom";
    let top = placeTop ? rect.top - tipRect.height - GAP : rect.bottom + GAP;
    if (placement === "bottom") {
      top = Math.min(
        viewportHeight - tipRect.height - VIEWPORT_MARGIN,
        Math.max(VIEWPORT_MARGIN, top)
      );
    }

    const anchorCenter = rect.left + rect.width / 2;
    const arrowLeft = Math.min(
      tipRect.width - 12,
      Math.max(12, anchorCenter - left)
    );

    tip.dataset.placement = placement;
    tip.style.setProperty("--fsqr-tooltip-arrow-left", `${arrowLeft}px`);
    tip.style.left = `${Math.round(left)}px`;
    tip.style.top = `${Math.round(top)}px`;
  }

  function showTooltip(target) {
    if (!target) {
      return;
    }
    const text = extractText(target);
    if (!text) {
      return;
    }

    const tip = getTooltipElement();
    tip.textContent = text;
    tip.removeAttribute("hidden");
    tip.setAttribute("aria-hidden", "false");
    tip.setAttribute("id", "fsqr-global-tooltip");
    updatePosition(target, tip);
    tip.classList.add("is-visible");

    currentTarget = target;
    const describedBy = (target.getAttribute("aria-describedby") || "").trim();
    const ids = describedBy ? describedBy.split(/\s+/) : [];
    if (!ids.includes("fsqr-global-tooltip")) {
      ids.push("fsqr-global-tooltip");
      target.setAttribute("aria-describedby", ids.join(" ").trim());
    }
  }

  function hideTooltip(immediate = false) {
    if (!tooltip) {
      return;
    }

    if (currentTarget) {
      const describedBy = (currentTarget.getAttribute("aria-describedby") || "").trim();
      if (describedBy) {
        const remainingIds = describedBy
          .split(/\s+/)
          .filter((value) => value && value !== "fsqr-global-tooltip");
        if (remainingIds.length) {
          currentTarget.setAttribute("aria-describedby", remainingIds.join(" "));
        } else {
          currentTarget.removeAttribute("aria-describedby");
        }
      }
      currentTarget = null;
    }

    const doHide = () => {
      if (!tooltip) {
        return;
      }
      tooltip.classList.remove("is-visible");
      tooltip.setAttribute("aria-hidden", "true");
      tooltip.setAttribute("hidden", "");
    };

    if (immediate) {
      clearTimers();
      doHide();
      return;
    }

    if (hideTimer) {
      clearTimeout(hideTimer);
    }
    hideTimer = setTimeout(() => {
      doHide();
      hideTimer = null;
    }, 40);
  }

  function onPointerEnter(event) {
    const target = findTarget(event.target);
    if (!target) {
      return;
    }
    clearTimers();
    showTimer = setTimeout(() => {
      showTooltip(target);
      showTimer = null;
    }, 140);
  }

  function onPointerLeave(event) {
    const target = event.target;
    if (!target || !currentTarget) {
      return;
    }
    if (target !== currentTarget && !target.contains(currentTarget)) {
      return;
    }
    clearTimers();
    hideTooltip();
  }

  function onFocusIn(event) {
    const target = findTarget(event.target);
    if (!target) {
      return;
    }
    clearTimers();
    showTooltip(target);
  }

  function onFocusOut(event) {
    if (!currentTarget) {
      return;
    }
    const next = event.relatedTarget;
    if (next && currentTarget.contains(next)) {
      return;
    }
    hideTooltip(true);
  }

  function onGlobalInteraction(event) {
    if (!currentTarget) {
      return;
    }
    const activeTarget = findTarget(event.target);
    if (activeTarget !== currentTarget) {
      hideTooltip(true);
    }
  }

  function onEscape(event) {
    if (event.key === "Escape") {
      hideTooltip(true);
    }
  }

  function onScrollOrResize() {
    if (!currentTarget || !tooltip || tooltip.hasAttribute("hidden")) {
      return;
    }
    updatePosition(currentTarget, tooltip);
  }

  function initTooltip() {
    if (initialized) {
      discoverTargets(document);
      return;
    }
    initialized = true;

    discoverTargets(document);

    document.addEventListener("pointerenter", onPointerEnter, true);
    document.addEventListener("pointerleave", onPointerLeave, true);
    document.addEventListener("focusin", onFocusIn, true);
    document.addEventListener("focusout", onFocusOut, true);
    document.addEventListener("pointerdown", onGlobalInteraction, true);
    document.addEventListener("keydown", onEscape, true);
    window.addEventListener("scroll", onScrollOrResize, true);
    window.addEventListener("resize", onScrollOrResize, { passive: true });

    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        mutation.addedNodes.forEach((node) => {
          if (!(node instanceof Element)) {
            return;
          }
          if (node.matches && node.matches("[title]")) {
            ensureTooltipAttributes(node);
          }
          discoverTargets(node);
        });
      }
      if (currentTarget) {
        onScrollOrResize();
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initTooltip, { once: true });
  } else {
    initTooltip();
  }
})();
