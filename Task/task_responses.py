from fastapi import Request
from web import render_template


def room_msg(request: Request, message: str, status_code: int = 200):
    response = render_template(request, "error.html", message=message)
    response.status_code = status_code
    return response


def task_block_response(request: Request, block_label: str):
    return room_msg(
        request, f"アクセス回数が多すぎます。{block_label}後に再試行してください。", 429
    )
