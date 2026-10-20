from fastapi import APIRouter
from room_settings import register_room_settings_route
from room_session import TASK_ACCESS
from . import task_data

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
register_room_settings_route(
    router,
    service="task",
    access=TASK_ACCESS,
    update=lambda key, hours: task_data.update_room_retention(key, hours),
)
register_task_search_page_route(router)
register_task_search_process_route(router)
register_task_room_access_routes(router)
register_task_delete_own_room_route(router)
