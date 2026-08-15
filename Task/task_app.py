from fastapi import APIRouter

from .task_routes_pages import (
    register_task_create_room_page_route,
    register_task_main_pages_routes,
    register_task_search_page_route,
)
from .task_routes_room import (
    register_task_create_room_route,
    register_task_delete_own_room_route,
    register_task_room_access_routes,
    register_task_search_process_route,
)

router = APIRouter()
register_task_main_pages_routes(router)
register_task_create_room_page_route(router)
register_task_create_room_route(router)
register_task_search_page_route(router)
register_task_search_process_route(router)
register_task_room_access_routes(router)
register_task_delete_own_room_route(router)
