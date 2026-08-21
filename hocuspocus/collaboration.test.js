import assert from "node:assert/strict";
import test from "node:test";
import { HocuspocusProvider } from "@hocuspocus/provider";
import { Server } from "@hocuspocus/server";
import WebSocket from "ws";
import * as Y from "yjs";

async function waitFor(predicate, message, timeoutMs = 5000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  throw new Error(message);
}

test("two clients converge and the merged Yjs state is persisted", async () => {
  const persisted = new Map();
  const server = new Server({
    port: 0,
    address: "127.0.0.1",
    quiet: true,
    stopOnSignals: false,
    debounce: 10,
    maxDebounce: 30,
    async onAuthenticate({ token }) {
      if (token !== "test-token") throw new Error("Unauthorized");
    },
    async onLoadDocument({ documentName }) {
      const document = new Y.Doc();
      const state = persisted.get(documentName);
      if (state) Y.applyUpdate(document, state);
      return document;
    },
    async onStoreDocument({ documentName, document }) {
      persisted.set(documentName, Y.encodeStateAsUpdate(document));
    },
  });

  await server.listen();
  const url = `ws://127.0.0.1:${server.address.port}`;
  const firstDocument = new Y.Doc();
  const secondDocument = new Y.Doc();
  const first = new HocuspocusProvider({
    url,
    name: "room42",
    token: "test-token",
    document: firstDocument,
    WebSocketPolyfill: WebSocket,
  });
  const second = new HocuspocusProvider({
    url,
    name: "room42",
    token: "test-token",
    document: secondDocument,
    WebSocketPolyfill: WebSocket,
  });

  try {
    await waitFor(() => first.synced && second.synced, "providers did not sync");
    firstDocument.getText("content").insert(0, "A");
    secondDocument.getText("content").insert(0, "B");
    await waitFor(
      () => {
        const firstText = firstDocument.getText("content").toString();
        return firstText.length === 2
          && firstText === secondDocument.getText("content").toString();
      },
      "clients did not converge",
    );
    await waitFor(() => persisted.has("room42"), "document was not persisted");

    const restored = new Y.Doc();
    Y.applyUpdate(restored, persisted.get("room42"));
    assert.equal(restored.getText("content").toString(), firstDocument.getText("content").toString());
    assert.deepEqual([...restored.getText("content").toString()].sort(), ["A", "B"]);
    restored.destroy();
  } finally {
    first.destroy();
    second.destroy();
    firstDocument.destroy();
    secondDocument.destroy();
    await server.destroy();
  }
});
