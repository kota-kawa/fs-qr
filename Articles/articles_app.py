from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import RedirectResponse

from i18n import is_language_query_only
from web import render_cached_template, render_template

from Articles.articles_registry import (
    CATEGORIES,
    get_all_articles,
    get_indexable_blog_articles_sorted,
    get_indexable_guides,
)

router = APIRouter()

# 公開からこの日数以内の記事に「NEW」バッジを付ける。
_NEW_BADGE_DAYS = 14
ARTICLES_PER_PAGE = 9


def _with_new_flag(articles: list[dict]) -> list[dict]:
    today = date.today()
    annotated = []
    for article in articles:
        try:
            published = datetime.strptime(article["date"], "%Y-%m-%d").date()
            is_new = (today - published).days <= _NEW_BADGE_DAYS
        except ValueError, KeyError:
            is_new = False
        annotated.append({**article, "is_new": is_new})
    return annotated


def _canonical_redirect(request: Request):
    if request.url.query and not is_language_query_only(request):
        url = request.url.replace(query="")
        return RedirectResponse(str(url), status_code=301)
    return None


def _paginate_articles(articles: list[dict], page_number: int) -> dict:
    total_count = len(articles)
    total_pages = max(1, (total_count + ARTICLES_PER_PAGE - 1) // ARTICLES_PER_PAGE)
    if page_number < 1 or page_number > total_pages:
        raise HTTPException(status_code=404, detail="Article page not found")

    start = (page_number - 1) * ARTICLES_PER_PAGE
    end = start + ARTICLES_PER_PAGE
    page_articles = articles[start:end]
    return {
        "articles": _with_new_flag(page_articles),
        "article_page": page_number,
        "article_total_pages": total_pages,
        "article_total_count": total_count,
        "article_visible_start": start + 1 if page_articles else 0,
        "article_visible_end": min(end, total_count),
        "articles_per_page": ARTICLES_PER_PAGE,
    }


def _articles_page_response(request: Request, page_number: int):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical

    guides = get_indexable_guides() if page_number == 1 else []
    pagination = _paginate_articles(get_indexable_blog_articles_sorted(), page_number)
    visible_categories = {
        article["category"] for article in [*guides, *pagination["articles"]]
    }
    return render_template(
        request,
        "articles.html",
        guides=guides,
        categories=[
            category for category in CATEGORIES if category in visible_categories
        ],
        **pagination,
    )


@router.get("/articles", name="articles.articles")
async def articles(request: Request):
    return _articles_page_response(request, 1)


@router.get("/articles/page/{page_number}", name="articles.articles_page")
async def articles_page(request: Request, page_number: int):
    if page_number == 1:
        query = request.url.query if is_language_query_only(request) else ""
        url = request.url.replace(path="/articles", query=query)
        return RedirectResponse(str(url), status_code=301)
    return _articles_page_response(request, page_number)


def _make_article_handler(template_name: str, indexable: bool):
    async def handler(request: Request):
        if not indexable:
            return render_template(request, template_name, article_indexable=False)
        return await render_cached_template(request, template_name)

    return handler


# レジストリの各記事を /<slug> で配信するルートを動的に登録する。
# 記事を追加するときは articles_registry.ARTICLES にエントリを足すだけでよい。
for _article in get_all_articles():
    router.add_api_route(
        f"/{_article['slug']}",
        _make_article_handler(_article["template"], bool(_article.get("indexable"))),
        methods=["GET"],
        name=f"articles.{_article['slug'].replace('-', '_')}",
    )
