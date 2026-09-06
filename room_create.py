"""共通のルーム ID 選択ロジック。

ルーム作成の HTTP ハンドラーはサービスごとに異なるデータ層とレスポンスを
持つ一方、手動 ID の検証と自動 ID の衝突回避は同じ処理です。このモジュール
はその骨格だけを共有し、呼び出し側がサービス固有のエラー応答を選べるように
します。

The service routers still own persistence and response rendering. This module only
selects a validated, available six-character room id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from room_credentials import allocate_unique_room_id, generate_room_id
from models import RoomInputError, validate_manual_room_id


RoomExists = Callable[[str], Awaitable[bool]]


@dataclass(frozen=True)
class RoomIdSelection:
    """選択結果。auto の候補衝突はクライアント再試行へ通知する。"""

    room_id: str | None
    retry_auto: bool = False


class RoomIdConflict(ValueError):
    """手動指定 ID が既存ルームと衝突した。"""


async def select_room_id(
    requested_id: str,
    id_mode: str,
    exists: RoomExists,
    *,
    attempts: int = 10,
    generator: Callable[[], str] = generate_room_id,
) -> RoomIdSelection:
    """利用可能な ID を選択する。

    ``requested_id`` は auto モードでブラウザが先に表示した候補にも使えます。
    その候補が衝突した場合は ``retry_auto=True`` を返し、manual の衝突とは別に
    409 応答を組み立てられるようにします。
    """

    requested = str(requested_id or "").strip()
    if id_mode != "auto":
        room_id = validate_manual_room_id(requested)
        if await exists(room_id):
            raise RoomIdConflict(room_id)
        return RoomIdSelection(room_id)

    if requested:
        try:
            candidate = validate_manual_room_id(requested)
        except RoomInputError:
            candidate = ""
        if candidate:
            if await exists(candidate):
                return RoomIdSelection(None, retry_auto=True)
            return RoomIdSelection(candidate)

    # The optional generator parameter keeps deterministic route tests possible;
    # production callers use the cryptographically secure room_credentials helper.
    async def candidate_exists(value: str) -> bool:
        return await exists(value)

    if generator is generate_room_id:
        room_id = await allocate_unique_room_id(candidate_exists, attempts=attempts)
    else:
        room_id = None
        for _ in range(attempts):
            candidate = generator()
            if not await candidate_exists(candidate):
                room_id = candidate
                break
    return RoomIdSelection(room_id)


__all__ = ["RoomIdConflict", "RoomIdSelection", "select_room_id"]
