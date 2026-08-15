from fastapi import APIRouter

from .task_routes_items import register_task_item_routes

router = APIRouter(prefix="/api")
register_task_item_routes(router)
