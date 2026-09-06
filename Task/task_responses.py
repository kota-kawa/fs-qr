from __future__ import annotations

from typing import Any, Mapping

from fastapi import Request

from api_response import api_error_response, error_page_or_json
from i18n import current_language_ctx, get_frontend_messages
from rate_limit import get_block_message


def task_message(key: str, fallback: str, **params: Any) -> str:
    """Return a manually translated Task message with optional placeholders."""

    message = get_frontend_messages(current_language_ctx.get()).get(key, fallback)
    if not params:
        return message
    try:
        return message.format(**params)
    except (KeyError, IndexError, ValueError):
        # Keep the translated template visible if a future caller omits a value.
        return message


def task_validation_message(error: str | BaseException) -> str:
    """Translate Task validation errors without matching Japanese source text.

    ``RoomInputError.message_key`` is the stable contract from ``models.py``.
    The string map remains as a compatibility fallback for older validators and
    unrelated ``ValueError`` instances.
    """

    message = str(error)
    message_key = getattr(error, "message_key", None)
    if message_key:
        return task_message(
            message_key
            if str(message_key).startswith("task.")
            else f"task.{message_key}",
            message,
        )

    key_by_message = {
        "IDが指定されていません。": "task.id_missing",
        "IDに無効な文字が含まれています。半角英数字のみ使用してください。": "task.id_invalid_chars",
        "IDは6文字の半角英数字で入力してください。": "task.id_invalid_length",
        "IDまたはパスワードが不正です。": "task.invalid_credentials",
        "IDまたはパスワードが違います。": "task.invalid_credentials",
        "パスワードは6桁の数字で入力してください。": "task.invalid_credentials",
    }
    key = key_by_message.get(message)
    if key is None:
        return task_message("task.request_error", "入力内容が不正です。")
    return task_message(key, message)


def task_rate_limit_message(label: str | None) -> str:
    """Keep the historical Task import while using the shared rate-limit text."""

    return get_block_message(label)


def task_api_error(
    key: str,
    fallback: str,
    *,
    status_code: int = 400,
    data: Mapping[str, Any] | None = None,
    **params: Any,
):
    """Build a localized JSON error response for a Task API route."""

    return api_error_response(
        task_message(key, fallback, **params), status_code=status_code, data=data
    )


def room_msg(request: Request, message: str, status_code: int = 200):
    return error_page_or_json(request, message, status_code=status_code)


def task_block_response(request: Request, block_label: str):
    return room_msg(
        request,
        task_message(
            "task.block_retry",
            "アクセス回数が多すぎます。{label}後に再試行してください。",
            label=block_label,
        ),
        429,
    )
