import assert from "node:assert/strict";
import crypto from "node:crypto";
import test from "node:test";

import { verifyCollaborationToken } from "./token.js";

function token(payload, secret = "test-secret") {
  const body = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const signature = crypto.createHmac("sha256", secret).update(body).digest("base64url");
  return `${body}.${signature}`;
}

test("accepts a valid room-scoped token", () => {
  assert.equal(verifyCollaborationToken(token({ room: "room1", exp: 200 }), "room1", "test-secret", 100), true);
});

test("rejects wrong room, expiry, and malformed signatures", () => {
  assert.equal(verifyCollaborationToken(token({ room: "room1", exp: 200 }), "room2", "test-secret", 100), false);
  assert.equal(verifyCollaborationToken(token({ room: "room1", exp: 100 }), "room1", "test-secret", 100), false);
  assert.equal(verifyCollaborationToken("bad.token", "room1", "test-secret", 100), false);
});
