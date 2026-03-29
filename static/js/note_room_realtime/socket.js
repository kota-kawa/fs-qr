(function (window) {
  window.NoteRoomRealtimeModules = window.NoteRoomRealtimeModules || {};
  const modules = window.NoteRoomRealtimeModules;
  const ui = modules.ui;

  function createSocketHandlers(context, syncHandlers) {
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
      context.ws = new WebSocket(`${proto}://${window.location.host}/ws/note/${context.room}/${context.roomPassword}`);

      context.ws.addEventListener("open", () => {
        context.reconnectAttempt = 0;
        ui.setStatus(context, "badge bg-info", "Connected");
        if (context.pendingContent !== null) {
          const content = context.pendingContent;
          context.pendingContent = null;
          syncHandlers.sendSave(content);
        }
      });

      context.ws.addEventListener("message", (event) => {
        let payload = null;
        try {
          payload = JSON.parse(event.data);
        } catch (err) {
          return;
        }
        if (!payload || !payload.type) {
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
        console.warn("WebSocket closed:", event.code, event.reason);
        if (event.code === 1006) {
          console.error("WebSocket connection failed abruptly. Check server logs or network.");
        }
        scheduleReconnect();
      });

      context.ws.addEventListener("error", () => {
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
