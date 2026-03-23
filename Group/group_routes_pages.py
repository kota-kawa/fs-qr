from fastapi import APIRouter, Request

from web import render_template

from .group_common import canonical_redirect


def register_group_main_pages_routes(router: APIRouter):
    @router.get("/group_menu", name="group.group")
    async def group(request: Request):
        canonical = canonical_redirect(request)
        if canonical:
            return canonical
        return render_template(request, "group.html")

    @router.get("/group", name="group.group_list")
    async def group_list(request: Request):
        canonical = canonical_redirect(request)
        if canonical:
            return canonical
        return render_template(request, "group_room_access.html")


def register_group_create_room_page_route(router: APIRouter):
    @router.get("/create_room", name="group.create_room")
    async def create_room(request: Request):
        return render_template(request, "create_group_room.html")


def register_group_search_page_route(router: APIRouter):
    @router.get("/search_group", name="group.search_room_page")
    async def search_room_page(request: Request):
        return render_template(request, "search_room.html")
