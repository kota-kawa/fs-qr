"""期限切れルーム掃除を scheduler から呼ぶ共通ラッパー。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from database import reset_db_connection


async def run_cleanup(
    cleaner: Callable[[], Awaitable[Any]],
    *,
    after: Callable[[Any], Awaitable[None]] | None = None,
    reset: Callable[[], Awaitable[None]] = reset_db_connection,
) -> Any:
    """DB 接続を必ず解放し、必要ならサービス固有の後処理を実行する。"""

    try:
        result = await cleaner()
        if after is not None:
            await after(result)
        return result
    finally:
        await reset()


def expired_room_ids(result: Any) -> list[str]:
    """各データ層の旧戻り値を scheduler 用の一覧へ正規化する。"""

    if isinstance(result, dict):
        values = result.get("expired_room_ids", [])
    elif isinstance(result, (list, tuple, set)):
        values = result
    else:
        values = []
    return [str(value) for value in values if value]


__all__ = ["expired_room_ids", "run_cleanup"]
