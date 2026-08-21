/** End-to-end smoke test for a running Compose Hocuspocus/Redis/MySQL stack. */

import assert from "node:assert/strict";
import crypto from "node:crypto";
import { HocuspocusProvider } from "@hocuspocus/provider";
import IORedis from "ioredis";
import mysql from "mysql2/promise";
import WebSocket from "ws";
import * as Y from "yjs";

const roomId = "ysmoke";
const sessionId = "0123456789abcdef0123456789abcdef";
const url = process.env.NOTE_SMOKE_URL || "ws://hocuspocus:1234";
const peerUrl = process.env.NOTE_SMOKE_PEER_URL || url;
const origin = process.env.PUBLIC_SITE_URL;
const secret = process.env.SECRET_KEY;
const redis = new IORedis(process.env.REDIS_URL);
const pool = mysql.createPool({
  host: process.env.SQL_HOST,
  user: process.env.SQL_USER,
  password: process.env.SQL_PW,
  database: process.env.SQL_DB,
});

if (!origin || !secret) throw new Error("PUBLIC_SITE_URL and SECRET_KEY are required");

function collaborationToken() {
  const body = Buffer.from(JSON.stringify({ room: roomId, exp: Math.floor(Date.now() / 1000) + 300 }))
    .toString("base64url");
  const signature = crypto.createHmac("sha256", secret).update(body).digest("base64url");
  return `${body}.${signature}`;
}

class SessionWebSocket extends WebSocket {
  constructor(address) {
    super(address, [], {
      headers: { Cookie: `session=${sessionId}`, Origin: origin },
    });
  }
}

class NoSessionWebSocket extends WebSocket {
  constructor(address) {
    super(address, [], { headers: { Origin: origin } });
  }
}

async function waitFor(predicate, message, timeoutMs = 10000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error(message);
}

await pool.execute("DELETE FROM note_content WHERE room_id = ?", [roomId]);
await pool.execute("DELETE FROM note_room WHERE room_id = ?", [roomId]);
await pool.execute(
  "INSERT INTO note_room (time, id, password, room_id, retention_hours, status, expires_at) VALUES (NOW(), ?, ?, ?, 24, 'active', DATE_ADD(NOW(), INTERVAL 1 HOUR))",
  [roomId, "smoke-password", roomId],
);
await pool.execute(
  "INSERT INTO note_content (room_id, content, updated_at, version, yjs_state) VALUES (?, 'legacy-', NOW(6), 0, NULL)",
  [roomId],
);
await redis.set(
  `starsessions.${sessionId}`,
  JSON.stringify({ note_room_access: { [roomId]: {} } }),
  "EX",
  300,
);

const firstDocument = new Y.Doc();
const secondDocument = new Y.Doc();
let unauthorizedRejected = false;
const first = new HocuspocusProvider({
  url,
  name: roomId,
  token: collaborationToken(),
  document: firstDocument,
  WebSocketPolyfill: SessionWebSocket,
});
const second = new HocuspocusProvider({
  url: peerUrl,
  name: roomId,
  token: collaborationToken(),
  document: secondDocument,
  WebSocketPolyfill: SessionWebSocket,
});
const unauthorizedDocument = new Y.Doc();
const unauthorized = new HocuspocusProvider({
  url,
  name: roomId,
  token: collaborationToken(),
  document: unauthorizedDocument,
  WebSocketPolyfill: NoSessionWebSocket,
  onAuthenticationFailed: () => { unauthorizedRejected = true; },
});

try {
  await waitFor(() => first.synced && second.synced, "authorized clients did not sync");
  assert.equal(firstDocument.getText("content").toString(), "legacy-");
  await waitFor(() => unauthorizedRejected, "missing session was not rejected");

  firstDocument.getText("content").insert(7, "A");
  secondDocument.getText("content").insert(7, "B");
  await waitFor(
    () => firstDocument.getText("content").toString().length === 9
      && firstDocument.getText("content").toString() === secondDocument.getText("content").toString(),
    "authorized clients did not converge",
  );
  await waitFor(async () => {
    const [rows] = await pool.execute(
      "SELECT content, yjs_state, version FROM note_content WHERE room_id = ?",
      [roomId],
    );
    return rows[0]?.content?.length === 9 && rows[0]?.yjs_state && rows[0]?.version > 0;
  }, "merged state was not persisted");

  await pool.execute("UPDATE note_room SET status = 'expired' WHERE room_id = ?", [roomId]);
  await redis.publish(
    `note:room:${roomId}`,
    JSON.stringify({ room_id: roomId, payload: { type: "room_expired" } }),
  );
  await waitFor(() => !first.synced, "expiration event did not close the room");

  let expiredRejected = false;
  const expiredDocument = new Y.Doc();
  const expired = new HocuspocusProvider({
    url,
    name: roomId,
    token: collaborationToken(),
    document: expiredDocument,
    WebSocketPolyfill: SessionWebSocket,
    onAuthenticationFailed: () => { expiredRejected = true; },
  });
  try {
    await waitFor(() => expiredRejected, "expired room accepted a new connection");
  } finally {
    expired.destroy();
    expiredDocument.destroy();
  }
} finally {
  first.destroy();
  second.destroy();
  unauthorized.destroy();
  firstDocument.destroy();
  secondDocument.destroy();
  unauthorizedDocument.destroy();
  await redis.del(`starsessions.${sessionId}`);
  await pool.execute("DELETE FROM note_content WHERE room_id = ?", [roomId]);
  await pool.execute("DELETE FROM note_room WHERE room_id = ?", [roomId]);
  await redis.quit();
  await pool.end();
}

console.log("Hocuspocus Docker smoke test passed");
