"""
共通入力バリデーションモデル。
各モジュールのルートハンドラからインポートして使用する。
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator
from settings import NOTE_MAX_CONTENT_LENGTH

_ROOM_ID_RE = re.compile(r"^[a-zA-Z0-9]{6}$")
_ALNUM_RE = re.compile(r"^[a-zA-Z0-9]+$")
_PASSWORD_RE = re.compile(r"^(?:[0-9]{6}|[a-zA-Z0-9_-]{8,64})$")
_RETENTION_CHOICES = frozenset({1, 7, 30})


class RoomSearchInput(BaseModel):
    """ルーム検索・ログインフォームの入力バリデーション。

    使用箇所: FSQR /try_login、Note /search_note_process、Group /search_group_process
    """

    room_id: str
    password: str

    @field_validator("room_id")
    @classmethod
    def validate_room_id(cls, v: str) -> str:
        v = v.strip()
        if not _ALNUM_RE.match(v):
            raise ValueError(
                "IDに無効な文字が含まれています。半角英数字のみ使用してください。"
            )
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        v = v.strip()
        if not _PASSWORD_RE.match(v):
            raise ValueError(
                "パスワードは6桁数字、または8〜64文字の半角英数字・-_で入力してください。"
            )
        return v


class RoomCreateInput(BaseModel):
    """ルーム作成フォームの入力バリデーション。

    使用箇所: Note /create_note_room、Group /create_group_room
    id は auto モードでは空可。manual モードでは 6文字英数字必須。
    """

    id: str = ""
    id_mode: str = "auto"
    retention_days: int = 7

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return v.strip()

    @field_validator("retention_days", mode="before")
    @classmethod
    def coerce_retention_days(cls, v) -> int:
        try:
            v = int(v)
        except (TypeError, ValueError):
            return 7
        return v if v in _RETENTION_CHOICES else 7

    def validate_manual_id(self) -> str:
        """manual モード用：6文字英数字チェック。エラー時は ValueError を送出。"""
        v = self.id
        if not v:
            raise ValueError("IDが指定されていません。")
        if not _ALNUM_RE.match(v):
            raise ValueError(
                "IDに無効な文字が含まれています。半角英数字のみ使用してください。"
            )
        if len(v) != 6:
            raise ValueError("IDは6文字の半角英数字で入力してください。")
        return v


class FsqrUploadInput(BaseModel):
    """FSQR ファイルアップロードフォームの入力バリデーション。

    使用箇所: FSQR /upload
    name (id) は空の場合は自動生成するので省略可。
    """

    name: str = ""
    retention_days: int = 7

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("retention_days", mode="before")
    @classmethod
    def coerce_retention_days(cls, v) -> int:
        try:
            v = int(v)
        except (TypeError, ValueError):
            return 7
        return v if v in _RETENTION_CHOICES else 7

    def validate_manual_id(self) -> str:
        """name が指定された場合の 6文字英数字チェック。エラー時は ValueError を送出。"""
        v = self.name
        if not _ALNUM_RE.match(v):
            raise ValueError(
                "IDに無効な文字が含まれています。半角英数字のみ使用してください。"
            )
        if len(v) != 6:
            raise ValueError("IDは6文字の半角英数字で入力してください。")
        return v


class NoteWsMessage(BaseModel):
    """WebSocket から受信するノート保存メッセージのバリデーション。

    使用箇所: Note /ws/note/{room_id}/{password}
    """

    type: Literal["save"]
    request_id: Optional[str] = Field(default=None, max_length=64)
    content: str = Field(default="", max_length=NOTE_MAX_CONTENT_LENGTH)
    last_known_updated_at: Optional[str] = None
    original_content: Optional[str] = None


class NoteSyncInput(BaseModel):
    """ノート同期 API の POST ボディのバリデーション。

    使用箇所: Note /api/note/{room_id}/{password} (POST)
    """

    content: str = Field(default="", max_length=NOTE_MAX_CONTENT_LENGTH)
    last_known_updated_at: Optional[str] = None
    original_content: Optional[str] = None
