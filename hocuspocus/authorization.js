/** Session and Origin checks shared by the Hocuspocus authentication hook. */

const SESSION_ID_PATTERN = /^[a-f0-9]{32}$/;

export function originIsAllowed(origin, publicSiteUrl) {
  if (!origin || !publicSiteUrl) return false;
  try {
    return new URL(origin).origin === new URL(publicSiteUrl).origin;
  } catch {
    return false;
  }
}

export function sessionIdFromCookie(cookieHeader) {
  if (typeof cookieHeader !== "string") return null;
  for (const part of cookieHeader.split(";")) {
    const separator = part.indexOf("=");
    if (separator === -1) continue;
    const name = part.slice(0, separator).trim();
    const value = part.slice(separator + 1).trim();
    if (name === "session" && SESSION_ID_PATTERN.test(value)) return value;
  }
  return null;
}

export async function sessionHasRoomAccess(redisClient, sessionId, roomId) {
  if (!sessionId || !roomId) return false;
  const raw = await redisClient.get(`starsessions.${sessionId}`);
  if (!raw) return false;
  try {
    const session = JSON.parse(raw);
    const rooms = session?.note_room_access;
    return rooms !== null
      && typeof rooms === "object"
      && !Array.isArray(rooms)
      && Object.prototype.hasOwnProperty.call(rooms, roomId);
  } catch {
    return false;
  }
}
