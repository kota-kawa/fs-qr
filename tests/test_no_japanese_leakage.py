"""記事多言語ページへの日本語混入がないことを確認する回帰テスト。"""

import asyncio
import re
from httpx import ASGITransport, AsyncClient
import pytest

from Articles.articles_registry import get_all_articles
from i18n import SUPPORTED_LANGUAGES

KANA_RE = re.compile(r"[ぁ-ゖァ-ヺ]")
CJK_RE = re.compile(r"[一-鿿]")
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.I | re.S)
LD_RE = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.S)
TAG_RE = re.compile(r"<[^>]+>")

# 言語名エンドニム（ページ内に必ず表示される正当な日本語/CJK 文字列）
ALLOWED_STRINGS = {
    "日本語",
    "简体中文",
    "繁體中文",
    "한국어",
}
ARTICLE_CASES = tuple(get_all_articles())


def _segments(html: str) -> list[str]:
    ld_strings = []
    for block in LD_RE.findall(html):
        ld_strings.extend(re.findall(r'"((?:[^"\\]|\\.)*)"', block))
    stripped = SCRIPT_STYLE_RE.sub(" ", html)
    stripped = re.sub(r"<!--.*?-->", " ", stripped, flags=re.S)
    attrs = re.findall(
        r'(?:content|alt|title|placeholder|aria-label)="([^"]*)"', stripped
    )
    text = TAG_RE.sub("\n", stripped)
    segs = [s.strip() for s in text.split("\n") if s.strip()]
    return segs + attrs + ld_strings


def _has_japanese(s: str, lang: str) -> bool:
    if s in ALLOWED_STRINGS:
        return False
    if KANA_RE.search(s):
        return True
    if lang not in ("zh-CN", "zh-TW") and CJK_RE.search(s):
        return True
    return False


@pytest.mark.parametrize(
    "article",
    ARTICLE_CASES,
    ids=[article["slug"] for article in ARTICLE_CASES],
)
def test_no_japanese_leakage(test_client, article) -> None:
    """全記事 × 全言語（ja除く）で日本語が漏れていないことを確認する。"""
    langs = [lang for lang in SUPPORTED_LANGUAGES if lang != "ja"]
    leaks: list[tuple[str, str, str]] = []

    app = test_client.app

    async def run_test():
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:

            async def fetch_segs(url: str, lang: str) -> tuple[str, list[str]]:
                resp = await client.get(f"{url}?lang={lang}")
                return lang, _segments(resp.text)

            url = "/" + article["slug"]
            ja_resp = await client.get(url + "?lang=ja")
            ja_segs = _segments(ja_resp.text)

            tasks = [fetch_segs(url, lang) for lang in langs]
            results = await asyncio.gather(*tasks)

            for lang, tr_segs in results:
                if len(tr_segs) != len(ja_segs):
                    continue
                for ja_seg, tr_seg in zip(ja_segs, tr_segs):
                    if _has_japanese(tr_seg, lang) and _has_japanese(ja_seg, "en"):
                        leaks.append((url, lang, tr_seg[:80]))

    asyncio.run(run_test())

    assert leaks == [], f"{len(leaks)} 件の日本語混入を検出:\n" + "\n".join(
        f"  {url} [{lang}]: {seg}" for url, lang, seg in leaks[:20]
    )
