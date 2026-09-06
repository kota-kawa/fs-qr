from fastapi import Request

from api_response import error_page_or_json
from rate_limit import get_block_message


def room_msg(request: Request, message: str, status_code: int = 200):
    return error_page_or_json(request, message, status_code=status_code)


def group_block_response(request: Request, block_label):
    message = get_block_message(block_label)
    return error_page_or_json(request, message, status_code=429)
