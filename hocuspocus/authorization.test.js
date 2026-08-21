import assert from "node:assert/strict";
import test from "node:test";
import {
  originIsAllowed,
  sessionHasRoomAccess,
  sessionIdFromCookie,
} from "./authorization.js";

test("requires the configured same origin and a valid session identifier", () => {
  assert.equal(originIsAllowed("https://fs-qr.net", "https://fs-qr.net/path"), true);
  assert.equal(originIsAllowed("https://evil.example", "https://fs-qr.net"), false);
  assert.equal(
    sessionIdFromCookie("other=x; session=0123456789abcdef0123456789abcdef"),
    "0123456789abcdef0123456789abcdef",
  );
  assert.equal(sessionIdFromCookie("session=../../unsafe"), null);
});

test("checks Note room access in the StarSessions Redis record", async () => {
  const redis = {
    async get(key) {
      assert.equal(key, "starsessions.0123456789abcdef0123456789abcdef");
      return JSON.stringify({ note_room_access: { room42: { share_token: "x" } } });
    },
  };
  assert.equal(
    await sessionHasRoomAccess(
      redis,
      "0123456789abcdef0123456789abcdef",
      "room42",
    ),
    true,
  );
  assert.equal(
    await sessionHasRoomAccess(
      redis,
      "0123456789abcdef0123456789abcdef",
      "other",
    ),
    false,
  );
});
