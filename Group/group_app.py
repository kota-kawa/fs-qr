from fastapi import APIRouter, Request

from .group_common import (
    canonical_redirect,
    get_room_if_valid,
    is_safe_path as _is_safe_path,
)
from .group_routes_file import (
    register_group_delete_file_route,
    register_group_download_all_route,
    register_group_download_file_route,
    register_group_list_files_route,
    register_group_upload_route,
)
from .group_routes_manage import (
    register_group_delete_all_rooms_route,
    register_group_delete_room_route,
    register_group_logout_management_route,
    register_group_manage_page_routes,
)
from .group_routes_pages import (
    register_group_create_room_page_route,
    register_group_main_pages_routes,
    register_group_search_page_route,
)
from .group_routes_room import (
    register_group_create_room_route,
    register_group_direct_route,
    register_group_room_access_route,
    register_group_search_process_route,
)
from .group_responses import group_block_response, room_msg as _room_msg

router = APIRouter()

register_group_main_pages_routes(router)
register_group_room_access_route(router)
register_group_create_room_page_route(router)
register_group_create_room_route(router)
register_group_upload_route(router)
register_group_list_files_route(router)
register_group_download_all_route(router)
register_group_download_file_route(router)
register_group_delete_file_route(router)
register_group_search_page_route(router)
register_group_search_process_route(router)
register_group_direct_route(router)
register_group_manage_page_routes(router)
register_group_logout_management_route(router)
register_group_delete_room_route(router)
register_group_delete_all_rooms_route(router)


async def _get_room_if_valid(room_id, password):
    return await get_room_if_valid(room_id, password)


def is_safe_path(base_path, target_path):
    return _is_safe_path(base_path, target_path)


def _canonical_redirect(request: Request):
    return canonical_redirect(request)


def _group_block_response(request: Request, block_label):
    return group_block_response(request, block_label)


def room_msg(request: Request, message: str, status_code: int = 200):
    return _room_msg(request, message, status_code=status_code)
