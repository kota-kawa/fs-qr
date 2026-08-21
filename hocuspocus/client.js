import * as Y from "yjs";
import { HocuspocusProvider } from "@hocuspocus/provider";

const config = window.__FSQR_APP__?.api?.getConfig("noteRoomRealtime") || {};
const modules = window.__FSQR_APP__?.api?.getModuleNamespace("noteRoomRealtime");
const context = modules?.core?.createContext();
const editor = context?.editor;
const status = context?.status;
const charCount = document.getElementById("charCount");
const maxLength = Number(config.limits?.maxContentLength || 10000);

if (editor && config.room && config.collaborationToken) {
  const doc = new Y.Doc();
  const text = doc.getText("content");
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const provider = new HocuspocusProvider({
    url: `${protocol}://${window.location.host}/yjs`,
    name: config.room,
    document: doc,
    token: config.collaborationToken,
  });
  const localOrigin = Symbol("local-editor-input");

  const updateCount = () => {
    if (charCount) charCount.textContent = `${editor.value.length} / ${maxLength}文字`;
  };

  text.observe((event, transaction) => {
    if (transaction.origin === localOrigin) return;
    const start = editor.selectionStart;
    const end = editor.selectionEnd;
    editor.value = text.toString();
    editor.setSelectionRange(Math.min(start, editor.value.length), Math.min(end, editor.value.length));
    updateCount();
  });

  editor.addEventListener("input", () => {
    const next = editor.value.slice(0, maxLength);
    if (next !== editor.value) editor.value = next;
    const current = text.toString();
    let prefix = 0;
    while (prefix < current.length && prefix < next.length && current[prefix] === next[prefix]) prefix += 1;
    let suffix = 0;
    while (suffix < current.length - prefix && suffix < next.length - prefix && current[current.length - 1 - suffix] === next[next.length - 1 - suffix]) suffix += 1;
    doc.transact(() => {
      const removeCount = current.length - prefix - suffix;
      if (removeCount) text.delete(prefix, removeCount);
      const inserted = next.slice(prefix, next.length - suffix);
      if (inserted) text.insert(prefix, inserted);
    }, localOrigin);
    updateCount();
  });

  provider.on("status", ({ status: connectionStatus }) => {
    if (!status) return;
    status.className = connectionStatus === "connected" ? "badge bg-success" : "badge bg-secondary";
    status.textContent = connectionStatus === "connected" ? "共同編集中" : "再接続中…";
  });
  provider.on("synced", () => {
    if (status) status.textContent = "同期済み";
  });
  provider.on("authenticationFailed", () => {
    if (status) {
      status.className = "badge bg-danger";
      status.textContent = "認証期限切れ（再読み込みしてください）";
    }
  });
  window.addEventListener("beforeunload", () => {
    provider.destroy();
    doc.destroy();
  }, { once: true });
  modules.clipboard?.createClipboardHandlers(context).bindButtons();
  modules.export?.createExportHandlers(context).bindButtons();
  updateCount();
}
