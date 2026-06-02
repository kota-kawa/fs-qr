"""ページ単位の「現在の閲覧者数」を管理するモジュール。

各ページ（FSQR 共有/アップロード完了、Group/Note ルーム）に対して、
閲覧者がハートビートを送り続けている間だけ「閲覧中」とみなし、その人数を返す。

実装方針:
- Redis の Sorted Set を利用し、member=viewer_id / score=最終ハートビート時刻 で保持する。
  読み取り時に ``PRESENCE_WINDOW_SECONDS`` より古いメンバーを掃除してから件数を数えるため、
  ブラウザを閉じてハートビートが途切れた閲覧者は自動的に除外される。
- Redis が利用できない環境（テストや単一プロセス運用）では、プロセス内の
  メモリ辞書へフォールバックする。
"""

import logging
import re
import time

from cache_utils import redis_client

logger = logging.getLogger(__name__)

# ハートビートが途切れてからこの秒数で閲覧者を「離脱」とみなす。
# フロント側は 4 秒間隔で送るため、1 回失敗しても継続閲覧者を残しつつ、
# 離脱通知が届かなかった場合の表示遅延を 10 秒以内に抑える。
PRESENCE_WINDOW_SECONDS = 10
# Redis キー自体の TTL。全員が離脱すればキーを残さず自動消滅させる。
PRESENCE_KEY_TTL_SECONDS = 60

# 不特定多数のページから呼ばれる公開 API のため、scope は許可リストで限定する。
ALLOWED_SCOPES = frozenset(
    {
        "fsqr-share",  # /fs-qr/s/{token}
        "fsqr-upload",  # /upload_complete/{secure_id}
        "group",  # /group/r/{room_id}
        "note",  # /note/r/{room_id}
    }
)

_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_VIEWER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Redis 不在時のプロセス内フォールバック: {(scope, key): {viewer_id: last_seen}}
_local_store: dict[tuple[str, str], dict[str, float]] = {}


def is_valid_scope(scope: str) -> bool:
    return scope in ALLOWED_SCOPES


def is_valid_key(key: str) -> bool:
    return bool(key) and bool(_KEY_RE.match(key))


def is_valid_viewer_id(viewer_id: str) -> bool:
    return bool(viewer_id) and bool(_VIEWER_ID_RE.match(viewer_id))


def _redis_key(scope: str, key: str) -> str:
    return f"presence:{scope}:{key}"


# --- メモリ内フォールバック ---------------------------------------------------


def _local_prune(viewers: dict[str, float], now: float) -> None:
    threshold = now - PRESENCE_WINDOW_SECONDS
    for viewer_id in [vid for vid, seen in viewers.items() if seen <= threshold]:
        viewers.pop(viewer_id, None)


def _local_touch(scope: str, key: str, viewer_id: str, now: float) -> int:
    viewers = _local_store.setdefault((scope, key), {})
    viewers[viewer_id] = now
    _local_prune(viewers, now)
    if not viewers:
        _local_store.pop((scope, key), None)
        return 0
    return len(viewers)


def _local_count(scope: str, key: str, now: float) -> int:
    viewers = _local_store.get((scope, key))
    if not viewers:
        return 0
    _local_prune(viewers, now)
    if not viewers:
        _local_store.pop((scope, key), None)
        return 0
    return len(viewers)


def _local_leave(scope: str, key: str, viewer_id: str, now: float) -> int:
    viewers = _local_store.get((scope, key))
    if not viewers:
        return 0
    viewers.pop(viewer_id, None)
    _local_prune(viewers, now)
    if not viewers:
        _local_store.pop((scope, key), None)
        return 0
    return len(viewers)


# --- Redis 実装 ---------------------------------------------------------------


async def _redis_touch(scope: str, key: str, viewer_id: str, now: float) -> int:
    rk = _redis_key(scope, key)
    pipe = redis_client.pipeline(transaction=True)
    pipe.zadd(rk, {viewer_id: now})
    pipe.zremrangebyscore(rk, "-inf", now - PRESENCE_WINDOW_SECONDS)
    pipe.zcard(rk)
    pipe.expire(rk, PRESENCE_KEY_TTL_SECONDS)
    results = await pipe.execute()
    return int(results[2])


async def _redis_count(scope: str, key: str, now: float) -> int:
    rk = _redis_key(scope, key)
    pipe = redis_client.pipeline(transaction=True)
    pipe.zremrangebyscore(rk, "-inf", now - PRESENCE_WINDOW_SECONDS)
    pipe.zcard(rk)
    results = await pipe.execute()
    return int(results[1])


async def _redis_leave(scope: str, key: str, viewer_id: str, now: float) -> int:
    rk = _redis_key(scope, key)
    pipe = redis_client.pipeline(transaction=True)
    pipe.zrem(rk, viewer_id)
    pipe.zremrangebyscore(rk, "-inf", now - PRESENCE_WINDOW_SECONDS)
    pipe.zcard(rk)
    results = await pipe.execute()
    return int(results[2])


# --- 公開 API -----------------------------------------------------------------


async def heartbeat(scope: str, key: str, viewer_id: str) -> int:
    """閲覧者の生存を記録し、現在の閲覧者数を返す。"""
    now = time.time()
    try:
        return await _redis_touch(scope, key, viewer_id, now)
    except Exception as exc:  # Redis 不在/障害時はメモリにフォールバック
        logger.debug("presence heartbeat fell back to local store: %s", exc)
        return _local_touch(scope, key, viewer_id, now)


async def count(scope: str, key: str) -> int:
    """現在の閲覧者数を返す（記録は行わない）。"""
    now = time.time()
    try:
        return await _redis_count(scope, key, now)
    except Exception as exc:
        logger.debug("presence count fell back to local store: %s", exc)
        return _local_count(scope, key, now)


async def leave(scope: str, key: str, viewer_id: str) -> int:
    """閲覧者を明示的に離脱させ、残りの閲覧者数を返す。"""
    now = time.time()
    try:
        return await _redis_leave(scope, key, viewer_id, now)
    except Exception as exc:
        logger.debug("presence leave fell back to local store: %s", exc)
        return _local_leave(scope, key, viewer_id, now)
