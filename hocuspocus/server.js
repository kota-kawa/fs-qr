import { Redis } from "@hocuspocus/extension-redis";
import { Server } from "@hocuspocus/server";
import IORedis from "ioredis";
import mysql from "mysql2/promise";
import * as Y from "yjs";
import {
  originIsAllowed,
  sessionHasRoomAccess,
  sessionIdFromCookie,
} from "./authorization.js";
import { verifyCollaborationToken } from "./token.js";

const port = Number(process.env.HOCUSPOCUS_PORT || 1234);
const secret = process.env.NOTE_YJS_SECRET || process.env.SECRET_KEY;
const redisUrl = process.env.REDIS_URL || "redis://redis:6379/0";
const maxContentLength = Number(process.env.NOTE_MAX_CONTENT_LENGTH || 10000);
const maxUpdateBytes = maxContentLength * 8 + 65536;
const publicSiteUrl = process.env.PUBLIC_SITE_URL || "https://fs-qr.net";

if (!secret) throw new Error("NOTE_YJS_SECRET or SECRET_KEY is required");

const pool = mysql.createPool({
  host: process.env.SQL_HOST || "db",
  user: process.env.SQL_USER,
  password: process.env.SQL_PW,
  database: process.env.SQL_DB,
  waitForConnections: true,
  connectionLimit: 10,
  charset: "utf8mb4",
});
const sessionRedis = new IORedis(redisUrl);
sessionRedis.on("error", (error) => {
  console.warn("Note authorization Redis error", error.message);
});

async function roomIsActive(roomId) {
  const [rows] = await pool.execute(
    "SELECT 1 FROM note_room WHERE room_id = ? AND status = 'active' AND expires_at > NOW() LIMIT 1",
    [roomId],
  );
  return rows.length === 1;
}

async function loadDocument(roomId) {
  const connection = await pool.getConnection();
  try {
    await connection.beginTransaction();
    const [rows] = await connection.execute(
      "SELECT content, yjs_state FROM note_content WHERE room_id = ? FOR UPDATE",
      [roomId],
    );
    if (!rows.length) throw new Error("Note room content does not exist");
    let document = new Y.Doc();
    let shouldPersistState = false;
    if (rows[0].yjs_state) {
      Y.applyUpdate(document, new Uint8Array(rows[0].yjs_state));
      // An old-version rollback can update LONGTEXT without knowing yjs_state.
      // 旧版への rollback 後に本文が変わった場合は、本文を正として再移行する。
      if (document.getText("content").toString() !== (rows[0].content || "")) {
        document.destroy();
        document = new Y.Doc();
        if (rows[0].content) document.getText("content").insert(0, rows[0].content);
        shouldPersistState = true;
      }
    } else {
      shouldPersistState = true;
      if (rows[0].content) {
        document.getText("content").insert(0, rows[0].content);
      }
    }
    if (shouldPersistState) {
      await connection.execute(
        "UPDATE note_content SET yjs_state = ? WHERE room_id = ?",
        [Buffer.from(Y.encodeStateAsUpdate(document)), roomId],
      );
    }
    await connection.commit();
    return document;
  } catch (error) {
    await connection.rollback();
    throw error;
  } finally {
    connection.release();
  }
}

const server = new Server({
  port,
  stopOnSignals: false,
  debounce: 500,
  maxDebounce: 2000,
  websocketOptions: { maxPayload: maxUpdateBytes },
  extensions: [
    new Redis({
      // A URL-based client preserves Redis authentication, TLS and DB selection.
      // URL形式ならRedisの認証・TLS・DB番号を欠落させない。
      createClient: () => new IORedis(redisUrl),
      prefix: "fsqr:note:yjs",
    }),
  ],
  async onAuthenticate({ token, documentName, requestHeaders }) {
    const sessionId = sessionIdFromCookie(requestHeaders.get("cookie"));
    const authorized = verifyCollaborationToken(token, documentName, secret)
      && originIsAllowed(requestHeaders.get("origin"), publicSiteUrl)
      && await sessionHasRoomAccess(sessionRedis, sessionId, documentName)
      && await roomIsActive(documentName);
    if (!authorized) {
      throw new Error("Unauthorized");
    }
    return { roomId: documentName };
  },
  async onLoadDocument({ documentName }) {
    return loadDocument(documentName);
  },
  async onStoreDocument({ documentName, document }) {
    const content = document.getText("content").toString();
    if (content.length > maxContentLength) {
      server.hocuspocus.closeConnections(documentName);
      throw new Error("Note content exceeds configured limit");
    }
    const state = Buffer.from(Y.encodeStateAsUpdate(document));
    const [result] = await pool.execute(
      "UPDATE note_content nc JOIN note_room nr ON nr.room_id = nc.room_id SET nc.content = ?, nc.yjs_state = ?, nc.updated_at = NOW(6), nc.version = nc.version + 1 WHERE nc.room_id = ? AND nr.status = 'active' AND nr.expires_at > NOW()",
      [content, state, documentName],
    );
    if (result.affectedRows !== 1) {
      server.hocuspocus.closeConnections(documentName);
      throw new Error("Note room expired before the document could be stored");
    }
  },
});

const expirationSubscriber = new IORedis(redisUrl);
expirationSubscriber.on("error", (error) => {
  console.warn("Note expiration subscriber Redis error", error.message);
});
await expirationSubscriber.psubscribe("note:room:*");
expirationSubscriber.on("pmessage", (_pattern, channel, raw) => {
  try {
    const event = JSON.parse(raw);
    if (event.payload?.type === "room_expired") {
      const roomId = String(channel).slice("note:room:".length);
      console.info("Closing expired Note collaboration room", roomId);
      server.hocuspocus.closeConnections(roomId);
    }
  } catch (error) {
    console.warn("Ignoring invalid Note expiration event", error.message);
  }
});

let shuttingDown = false;
const shutdown = async () => {
  if (shuttingDown) return;
  shuttingDown = true;
  await server.destroy();
  await expirationSubscriber.quit();
  await sessionRedis.quit();
  await pool.end();
};
process.once("SIGTERM", shutdown);
process.once("SIGINT", shutdown);
await server.listen();
