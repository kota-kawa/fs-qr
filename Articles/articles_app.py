from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse

from web import render_template

router = APIRouter()


def _canonical_redirect(request: Request):
    if request.url.query:
        url = request.url.replace(query="")
        return RedirectResponse(str(url), status_code=301)
    return None


@router.get("/articles", name="articles.articles")
async def articles(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    articles_list = [
        {"title": "FS!QRの基本的な考え方", "url": "/fs-qr-concept"},
        {"title": "安全な共有のポイント", "url": "/safe-sharing"},
        {"title": "暗号化の基礎知識", "url": "/encryption"},
        {"title": "教育での活用例", "url": "/education"},
        {"title": "業務での活用例", "url": "/business"},
        {"title": "リスクと対策の考え方", "url": "/risk-mitigation"},
    ]
    return render_template(request, "articles.html", articles=articles_list)


@router.get("/fs-qr-concept", name="articles.fs_qr_concept")
async def fs_qr_concept(request: Request):
    return render_template(request, "fs-qr-concept.html")


@router.get("/safe-sharing", name="articles.safe_sharing")
async def safe_sharing(request: Request):
    return render_template(request, "safe-sharing.html")


@router.get("/encryption", name="articles.encryption")
async def encryption(request: Request):
    return render_template(request, "encryption.html")


@router.get("/education", name="articles.education")
async def education(request: Request):
    return render_template(request, "education.html")


@router.get("/business", name="articles.business")
async def business(request: Request):
    return render_template(request, "business.html")


@router.get("/risk-mitigation", name="articles.risk_mitigation")
async def risk_mitigation(request: Request):
    return render_template(request, "risk-mitigation.html")
