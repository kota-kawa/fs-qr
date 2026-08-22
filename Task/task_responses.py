from __future__ import annotations

from typing import Any, Mapping

from fastapi import Request

from api_response import api_error_response
from i18n import current_language_ctx, get_frontend_messages
from web import render_template


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


def task_validation_message(message: str) -> str:
    """Translate the small set of validation messages exposed by Task forms."""

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
    """Translate the rate-limit variants without exposing Redis's Japanese label."""

    if label == "1日":
        return task_message(
            "task.rate_limit_day",
            "一定回数以上の失敗があったため、この機能へのアクセスを1日間ブロックしています。時間をおいて再度お試しください。",
        )
    if label == "30分":
        return task_message(
            "task.rate_limit_30min",
            "一定回数以上の失敗があったため、この機能へのアクセスを30分間ブロックしています。時間をおいて再度お試しください。",
        )
    return task_message(
        "task.rate_limit_generic",
        "一定回数以上の失敗があったため、この機能へのアクセスを制限しています。時間をおいて再度お試しください。",
    )


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
    response = render_template(request, "error.html", message=message)
    response.status_code = status_code
    return response


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
