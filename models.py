"""
共通入力バリデーションモデル。
各モジュールのルートハンドラからインポートして使用する。
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from settings import (
    NOTE_MAX_CONTENT_LENGTH,
    TASK_MAX_CATEGORY_LENGTH,
    TASK_MAX_NOTE_LENGTH,
    TASK_MAX_TITLE_LENGTH,
)

_ROOM_ID_RE = re.compile(r"^[a-zA-Z0-9]{6}$")
_ALNUM_RE = re.compile(r"^[a-zA-Z0-9]+$")
_PASSWORD_RE = re.compile(r"^[0-9]{6}$")
_TASK_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# 共有データは長期保管用途ではないため、保存期間を24時間以内に制限する。
_RETENTION_HOUR_CHOICES = frozenset({1, 6, 12, 24})
# Note/Task は共同編集やタスク管理など、より長期の運用でも使われるため、
# 保存期間を1日・1週間・1か月から選べるようにする。
_LONG_RETENTION_HOUR_CHOICES = frozenset({24, 24 * 7, 24 * 30})


def _normalize_task_date(value: object) -> str | None:
    """日付入力を ISO 形式にそろえ、不正な暦日を拒否する。"""
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        raise ValueError("日付は YYYY-MM-DD 形式で指定してください。")
    normalized = value.strip()
    if not normalized:
        return None
    if not _TASK_DATE_RE.fullmatch(normalized):
        raise ValueError("日付は YYYY-MM-DD 形式で指定してください。")
    try:
        date.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("存在しない日付は指定できません。") from exc
    return normalized


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
        if not _ROOM_ID_RE.match(v):
            raise ValueError("IDは6文字の半角英数字で入力してください。")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        v = v.strip()
        if not _PASSWORD_RE.match(v):
            raise ValueError("パスワードは6桁の数字で入力してください。")
        return v


class RoomCreateInput(BaseModel):
    """ルーム作成フォームの入力バリデーション。

    使用箇所: Group /create_group_room
    id は auto モードでは空可。manual モードでは 6文字英数字必須。
    """

    id: str = ""
    id_mode: str = "auto"
    retention_hours: int = 24

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return v.strip()

    @field_validator("retention_hours", mode="before")
    @classmethod
    def coerce_retention_hours(cls, v) -> int:
        try:
            v = int(v)
        except (TypeError, ValueError):
            return 24
        return v if v in _RETENTION_HOUR_CHOICES else 24

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


class NoteTaskRoomCreateInput(RoomCreateInput):
    """Note / Task のルーム作成フォームの入力バリデーション。

    使用箇所: Note /create_note_room、Task /create_task_room
    保存期間は1日・1週間・1か月から選択する（RoomCreateInputより長期に対応）。
    """

    retention_hours: int = 24

    @field_validator("retention_hours", mode="before")
    @classmethod
    def coerce_retention_hours(cls, v) -> int:
        try:
            v = int(v)
        except (TypeError, ValueError):
            return 24
        return v if v in _LONG_RETENTION_HOUR_CHOICES else 24


class FsqrUploadInput(BaseModel):
    """FSQR ファイルアップロードフォームの入力バリデーション。

    使用箇所: FSQR /upload
    name (id) は空の場合は自動生成するので省略可。
    """

    name: str = ""
    retention_hours: int = 24

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("retention_hours", mode="before")
    @classmethod
    def coerce_retention_hours(cls, v) -> int:
        try:
            v = int(v)
        except (TypeError, ValueError):
            return 24
        return v if v in _RETENTION_HOUR_CHOICES else 24

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

    使用箇所: Note /ws/note/{room_id}
    """

    type: Literal["save"]
    request_id: Optional[str] = Field(default=None, max_length=64)
    content: str = Field(default="", max_length=NOTE_MAX_CONTENT_LENGTH)
    base_version: int = Field(ge=0)
    original_content: str = Field(max_length=NOTE_MAX_CONTENT_LENGTH)


class NoteSyncInput(BaseModel):
    """ノート同期 API の POST ボディのバリデーション。

    使用箇所: Note /api/note/{room_id} (POST)
    """

    content: str = Field(default="", max_length=NOTE_MAX_CONTENT_LENGTH)
    base_version: int = Field(ge=0)
    original_content: str = Field(max_length=NOTE_MAX_CONTENT_LENGTH)


class NoteExportInput(BaseModel):
    """ノートの TXT / PDF 出力 API の POST ボディ。"""

    content: str = Field(default="", max_length=NOTE_MAX_CONTENT_LENGTH)


class TaskItemInput(BaseModel):
    """タスク作成 API の入力。カテゴリは短命なルームのため文字列で保持する。"""

    title: str = Field(min_length=1, max_length=TASK_MAX_TITLE_LENGTH)
    note: str = Field(default="", max_length=TASK_MAX_NOTE_LENGTH)
    board_status: Literal["todo", "doing", "done"] = "todo"
    priority: Literal["high", "normal", "low"] = "normal"
    category: str = Field(default="", max_length=TASK_MAX_CATEGORY_LENGTH)
    start_date: Optional[str] = None
    due_date: Optional[str] = None

    @field_validator("title", "note", "category", mode="before")
    @classmethod
    def strip_task_text(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("start_date", "due_date", mode="before")
    @classmethod
    def normalize_task_date(cls, value: object) -> str | None:
        return _normalize_task_date(value)

    @model_validator(mode="after")
    def validate_dates(self) -> TaskItemInput:
        if self.start_date and self.due_date:
            if self.start_date > self.due_date:
                raise ValueError("開始日は期限日以前の日付を指定してください。")
        return self


class TaskItemUpdateInput(BaseModel):
    """変更された項目だけを受け取る、楽観ロック用のタスク更新入力。"""

    version: int = Field(ge=0)
    title: Optional[str] = Field(
        default=None, min_length=1, max_length=TASK_MAX_TITLE_LENGTH
    )
    note: Optional[str] = Field(default=None, max_length=TASK_MAX_NOTE_LENGTH)
    board_status: Optional[Literal["todo", "doing", "done"]] = None
    priority: Optional[Literal["high", "normal", "low"]] = None
    category: Optional[str] = Field(default=None, max_length=TASK_MAX_CATEGORY_LENGTH)
    start_date: Optional[str] = None
    due_date: Optional[str] = None
    position: Optional[int] = Field(default=None, ge=0)

    @field_validator("title", "note", "category", mode="before")
    @classmethod
    def strip_optional_task_text(cls, value: object) -> object:
        return str(value or "").strip() if value is not None else value

    @field_validator("start_date", "due_date", mode="before")
    @classmethod
    def normalize_task_date(cls, value: object) -> str | None:
        return _normalize_task_date(value)

    @model_validator(mode="after")
    def validate_dates(self) -> TaskItemUpdateInput:
        if self.start_date and self.due_date:
            if self.start_date > self.due_date:
                raise ValueError("開始日は期限日以前の日付を指定してください。")
        return self


class TaskReorderInput(BaseModel):
    board_status: Literal["todo", "doing", "done"]
    ordered_item_ids: list[int] = Field(min_length=0, max_length=200)
