(function (window) {
  const appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error("App namespace is not initialized.");
  }
  const modules = appNamespace.api.getModuleNamespace("noteRoomRealtime");
  const ui = modules.ui;

  function createSocketHandlers(context, syncHandlers) {
    const logger = context.logger || { log: function () {}, warn: function () {}, error: function () {} };
    const core = modules.core;

    function scheduleReconnect() {
      if (context.reconnectTimer) {
        return;
      }
      const delay = Math.min(500 * Math.pow(2, context.reconnectAttempt), 5000);
      context.reconnectAttempt += 1;
      ui.setStatus(context, "badge bg-warning text-dark", "Reconnecting...");
      context.reconnectTimer = setTimeout(() => {
        context.reconnectTimer = null;
        connectWebSocket();
      }, delay);
    }

    function connectWebSocket() {
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      const wsUrl = new URL(
        `${proto}://${window.location.host}/ws/note/${context.room}/${context.roomPassword}`
      );
      if (context.websocketCsrfToken) {
        wsUrl.searchParams.set("csrf_token", context.websocketCsrfToken);
      }
      context.ws = new WebSocket(wsUrl.toString());

      context.ws.addEventListener("open", () => {
        context.reconnectAttempt = 0;
        ui.setStatus(context, "badge bg-info", "Connected");
        syncHandlers.handleSocketOnline();
      });

      context.ws.addEventListener("message", (event) => {
        const payload = core.safeParseJson
          ? core.safeParseJson(event && event.data, logger, "note websocket message")
          : null;
        if (!payload) {
          return;
        }
        if (!core.isPlainObject(payload)) {
          logger.warn("Invalid websocket payload shape:", payload);
          return;
        }
        if (typeof payload.type !== "string") {
          logger.warn("WebSocket payload type is missing or invalid:", payload);
          return;
        }
        if (payload.type === "init") {
          syncHandlers.handleInit(payload);
          return;
        }
        if (payload.type === "ack") {
          syncHandlers.handleAck(payload);
          return;
        }
        if (payload.type === "update") {
          syncHandlers.handleUpdate(payload);
          return;
        }
        if (payload.type === "error") {
          ui.setStatus(context, "badge bg-danger", payload.error || "Connection error");
        }
      });

      context.ws.addEventListener("close", (event) => {
        logger.warn("WebSocket closed:", event.code, event.reason);
        if (event.code === 1006) {
          logger.error("WebSocket connection failed abruptly. Check server logs or network.");
        }
        syncHandlers.handleSocketOffline();
        scheduleReconnect();
      });

      context.ws.addEventListener("error", () => {
        syncHandlers.handleSocketOffline();
        ui.setStatus(context, "badge bg-danger", "Connection error");
      });
    }

    return {
      connectWebSocket: connectWebSocket
    };
  }

  modules.socket = {
    createSocketHandlers: createSocketHandlers
  };
})(window);
