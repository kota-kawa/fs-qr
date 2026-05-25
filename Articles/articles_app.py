from datetime import date, datetime

from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse

from i18n import is_language_query_only
from web import render_cached_template, render_template

from Articles.articles_registry import (
    CATEGORIES,
    get_articles_sorted,
)

router = APIRouter()

# 公開からこの日数以内の記事に「NEW」バッジを付ける。
_NEW_BADGE_DAYS = 14


def _with_new_flag(articles: list[dict]) -> list[dict]:
    today = date.today()
    annotated = []
    for article in articles:
        try:
            published = datetime.strptime(article["date"], "%Y-%m-%d").date()
            is_new = (today - published).days <= _NEW_BADGE_DAYS
        except (ValueError, KeyError):
            is_new = False
        annotated.append({**article, "is_new": is_new})
    return annotated


def _canonical_redirect(request: Request):
    if request.url.query and not is_language_query_only(request):
        url = request.url.replace(query="")
        return RedirectResponse(str(url), status_code=301)
    return None


@router.get("/articles", name="articles.articles")
async def articles(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return render_template(
        request,
        "articles.html",
        articles=_with_new_flag(get_articles_sorted()),
        categories=CATEGORIES,
    )


def _make_article_handler(template_name: str):
    async def handler(request: Request):
        return await render_cached_template(request, template_name)

    return handler


# レジストリの各記事を /<slug> で配信するルートを動的に登録する。
# 記事を追加するときは articles_registry.ARTICLES にエントリを足すだけでよい。
for _article in get_articles_sorted():
    router.add_api_route(
        f"/{_article['slug']}",
        _make_article_handler(_article["template"]),
        methods=["GET"],
        name=f"articles.{_article['slug'].replace('-', '_')}",
    )
