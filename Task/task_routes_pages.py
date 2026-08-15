from fastapi import APIRouter, Request

from web import render_template
from .task_common import canonical_redirect


def register_task_main_pages_routes(router: APIRouter) -> None:
    @router.get("/task_menu", name="task.task_menu")
    async def task_menu(request: Request):
        return canonical_redirect(request) or render_template(request, "task_menu.html")

    @router.get("/shared-task", name="task.landing")
    async def task_landing(request: Request):
        return canonical_redirect(request) or render_template(
            request, "task_landing.html"
        )

    @router.get("/task", name="task.task_room_access")
    async def task_room_access(request: Request):
        return canonical_redirect(request) or render_template(
            request, "task_room_access.html"
        )


def register_task_create_room_page_route(router: APIRouter) -> None:
    @router.get("/create_task_room", name="task.create_task_room_page")
    async def create_task_room_page(request: Request):
        return render_template(request, "create_task_room.html")


def register_task_search_page_route(router: APIRouter) -> None:
    @router.get("/search_task", name="task.search_task_room_page")
    async def search_task_room_page(request: Request):
        return render_template(request, "search_task_room.html")
