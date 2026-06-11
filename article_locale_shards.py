from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from Articles.articles_registry import ARTICLES


REPO_ROOT = Path(__file__).resolve().parent
ARTICLE_TEMPLATE_DIR = REPO_ROOT / "Articles" / "templates"
ARTICLE_SHARED_SHARD = "articles/_shared"


@lru_cache(maxsize=1)
def _article_sources() -> tuple[dict[str, str], dict[str, set[str]], set[str], str]:
    template_texts: dict[str, str] = {}
    metadata_by_slug: dict[str, set[str]] = {}
    categories: set[str] = set()

    for article in ARTICLES:
        slug = str(article["slug"])
        template_path = ARTICLE_TEMPLATE_DIR / str(article["template"])
        template_texts[slug] = template_path.read_text(encoding="utf-8")
        metadata_by_slug[slug] = {
            str(article["title"]),
            str(article["description"]),
        }
        categories.add(str(article["category"]))

    shared_text = ""
    for path in sorted(ARTICLE_TEMPLATE_DIR.glob("_*.html")) + [
        ARTICLE_TEMPLATE_DIR / "articles.html"
    ]:
        if path.exists():
            shared_text += "\n" + path.read_text(encoding="utf-8")

    return template_texts, metadata_by_slug, categories, shared_text


def article_phrase_shard_for_key(key: str) -> str | None:
    if not key:
        return None

    template_texts, metadata_by_slug, categories, shared_text = _article_sources()

    if key in categories or key in shared_text:
        return ARTICLE_SHARED_SHARD

    matches: set[str] = set()
    for slug, metadata_values in metadata_by_slug.items():
        if key in metadata_values:
            matches.add(slug)

    for slug, template_text in template_texts.items():
        if key in template_text:
            matches.add(slug)

    if not matches:
        return None
    if len(matches) == 1:
        return f"articles/{next(iter(matches))}"
    return ARTICLE_SHARED_SHARD
