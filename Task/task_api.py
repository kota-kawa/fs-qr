from fastapi import APIRouter

from .task_routes_io import register_task_io_routes
from .task_routes_items import register_task_item_routes

router = APIRouter(prefix="/api")
register_task_io_routes(router)
register_task_item_routes(router)
