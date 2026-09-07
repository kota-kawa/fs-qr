"""サービス別の PWA manifest を動的に配信する router。

4 サービス (FSQR / Group / Note / Task) の manifest は name / short_name /
start_url / theme_color / icon だけが異なるため、静的 JSON を 4 本置かずに
1 つのテーブルから組み立てて返す。

Serves the per-service web app manifests from a single table so the four
near-identical static JSON files do not have to be kept in sync by hand.
"""

from __future__ import annotations

from fastapi import APIRouter
from starlette.responses import JSONResponse, Response

router = APIRouter()

# manifest の共通部分 / Fields shared by every service manifest.
_COMMON: dict[str, object] = {
    "scope": "/",
    "display": "standalone",
    "background_color": "#ffffff",
}

# サービス固有の値。theme_color は各ページの <meta name="theme-color"> と揃える。
# Per-service values; theme_color mirrors each page's theme-color meta tag.
SERVICE_MANIFESTS: dict[str, dict[str, str]] = {
    "fsqr": {
        "name": "FS!QR",
        "short_name": "FS!QR",
        "start_url": "/",
        "theme_color": "#342ae3",
        "icon": "/static/apple-touch-icon.png",
    },
    "group": {
        "name": "FS!QR Group",
        "short_name": "Group",
        "start_url": "/group_menu",
        "theme_color": "#342ae3",
        "icon": "/static/apple-touch-icon.png",
    },
    "note": {
        "name": "FS!QR Note",
        "short_name": "Note",
        "start_url": "/note_menu",
        "theme_color": "#342ae3",
        "icon": "/static/apple-touch-icon.png",
    },
    "task": {
        "name": "FS!QR Task",
        "short_name": "Task",
        "start_url": "/task_menu",
        "theme_color": "#f59e0b",
        "icon": "/static/apple-touch-icon5.png",
    },
}

MANIFEST_MEDIA_TYPE = "application/manifest+json"


def build_manifest(service: str) -> dict[str, object] | None:
    """サービス名から manifest の dict を組み立てる。未知の名前は None。"""
    config = SERVICE_MANIFESTS.get(service)
    if config is None:
        return None
    return {
        "name": config["name"],
        "short_name": config["short_name"],
        "start_url": config["start_url"],
        **_COMMON,
        "theme_color": config["theme_color"],
        "icons": [
            {
                "src": config["icon"],
                "sizes": "180x180",
                "type": "image/png",
            }
        ],
    }


@router.get("/manifest/{service}.webmanifest", name="pwa.manifest")
async def service_manifest(service: str) -> Response:
    manifest = build_manifest(service)
    if manifest is None:
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return JSONResponse(
        manifest,
        media_type=MANIFEST_MEDIA_TYPE,
        headers={"Cache-Control": "public, max-age=86400"},
    )
