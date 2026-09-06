"""セッションに保持する「ルームへのアクセス許可」を扱う共通クラス。

Group / Note / Task / FSQR はそれぞれ別のセッション名前空間を使うが、
「覚える・確認する・共有トークンやパスワードを読む・忘れる」という操作は
同じ形をしている。ここでは :mod:`room_access` の低レベル関数を、名前空間を
束ねた小さなクラスとして提供する。

Each service instantiates :class:`RoomSessionAccess` with its existing session
key so stored session data stays compatible with previous deployments.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Optional

from fastapi import Request

import room_access


class RoomSessionAccess:
    """1 つのセッション名前空間に対するルームアクセスの記録・参照。"""

    def __init__(self, namespace: str) -> None:
        self.namespace = namespace

    # --- 記録 / recording -------------------------------------------------

    def grant(
        self, request: Request, key: str, payload: Optional[Mapping[str, Any]] = None
    ) -> None:
        """任意のペイロードでアクセスを記録する（空文字も保存したい FSQR 用）。"""
        room_access.grant_access(request.session, self.namespace, key, payload=payload)

    def remember(
        self,
        request: Request,
        key: str,
        *,
        share_token: str | None = None,
        password: str | None = None,
        can_delete: bool = False,
    ) -> None:
        """空でない値だけをペイロードに載せてアクセスを記録する。

        再度呼ばれたときは既存の値を保ちつつ上書きするため、共有 URL 経由で
        入ったあとに検索で入り直しても share_token は失われない。
        """
        payload: dict[str, str] = {}
        if share_token:
            payload["share_token"] = share_token
        if password:
            payload["password"] = password
        if can_delete:
            payload["can_delete"] = "1"
        room_access.grant_access(
            request.session, self.namespace, key, payload=payload or None
        )

    # --- 参照 / lookups ---------------------------------------------------

    def has_session(self, session: Mapping[str, Any], key: str) -> bool:
        """WebSocket など Request を持たない経路向けのアクセス確認。"""
        return room_access.has_access(session, self.namespace, key)

    def has(self, request: Request, key: str) -> bool:
        return self.has_session(request.session, key)

    def get(self, request: Request, key: str) -> Optional[dict[str, Any]]:
        return room_access.get_access(request.session, self.namespace, key)

    def field(self, request: Request, key: str, name: str, default: str = "") -> str:
        return room_access.get_access_field(
            request.session, self.namespace, key, name, default
        )

    def share_token(self, request: Request, key: str) -> str:
        return self.field(request, key, "share_token", "")

    def password(self, request: Request, key: str) -> str:
        return self.field(request, key, "password", "")

    def can_delete(self, request: Request, key: str) -> bool:
        return self.field(request, key, "can_delete", "") == "1"

    # --- 取り消し / revocation -------------------------------------------

    def forget(self, request: Request, key: str) -> None:
        room_access.revoke_access(request.session, self.namespace, key)

    def forget_session(self, session: MutableMapping[str, Any], key: str) -> None:
        room_access.revoke_access(session, self.namespace, key)


# 既存のセッションキー文字列をそのまま使い、デプロイ後もログイン状態を保つ。
# Namespaces are the historical session keys so existing sessions stay valid.
NOTE_ACCESS = RoomSessionAccess("note_room_access")
TASK_ACCESS = RoomSessionAccess("task_room_access")
GROUP_ACCESS = RoomSessionAccess("group_room_access")
FSQR_ACCESS = RoomSessionAccess("fsqr_upload_access")
