from fastapi import Request

from api_response import api_error_response
from rate_limit import get_block_message
from web import render_template


def room_msg(request: Request, message: str, status_code: int = 200):
    response = render_template(request, "error.html", message=message)
    response.status_code = status_code
    return response


def group_block_response(request: Request, block_label):
    message = get_block_message(block_label)
    content_type = request.headers.get("content-type", "")
    if (
        content_type.startswith("application/json")
        or request.headers.get("x-requested-with") == "XMLHttpRequest"
    ):
        return api_error_response(message, status_code=429)
    return room_msg(request, message, status_code=429)
