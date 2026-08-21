import crypto from "node:crypto";

export function verifyCollaborationToken(token, roomId, secret, now = Date.now() / 1000) {
  if (!secret || typeof token !== "string" || token.length > 2048) return false;
  const [body, signature, extra] = token.split(".");
  if (!body || !signature || extra) return false;
  const expected = crypto.createHmac("sha256", secret).update(body).digest();
  let actual;
  try { actual = Buffer.from(signature, "base64url"); } catch { return false; }
  if (actual.length !== expected.length || !crypto.timingSafeEqual(actual, expected)) return false;
  try {
    const payload = JSON.parse(Buffer.from(body, "base64url").toString("utf8"));
    return payload.room === roomId && Number(payload.exp) > now;
  } catch { return false; }
}
