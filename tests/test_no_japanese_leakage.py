"""記事多言語ページへの日本語混入がないことを確認する回帰テスト。"""

import re

from starlette.testclient import TestClient

from Articles.articles_registry import get_all_articles
from i18n import SUPPORTED_LANGUAGES

KANA_RE = re.compile(r"[ぁ-ゖァ-ヺ]")
CJK_RE = re.compile(r"[一-鿿]")
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.I | re.S)
LD_RE = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.S)
TAG_RE = re.compile(r"<[^>]+>")

# 言語名エンドニム（ページ内に必ず表示される正当な日本語/CJK 文字列）
ALLOWED_STRINGS = {
    "日本語", "简体中文", "繁體中文", "한국어",
}


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


def test_no_japanese_leakage(test_client: TestClient) -> None:
    """全記事 × 全言語（ja除く）で日本語が漏れていないことを確認する。"""
    langs = [lang for lang in SUPPORTED_LANGUAGES if lang != "ja"]
    leaks: list[tuple[str, str, str]] = []

    for article in get_all_articles():
        url = "/" + article["slug"]
        ja_segs = _segments(test_client.get(url + "?lang=ja").text)

        for lang in langs:
            tr_segs = _segments(test_client.get(url + "?lang=" + lang).text)
            if len(tr_segs) != len(ja_segs):
                continue
            for ja_seg, tr_seg in zip(ja_segs, tr_segs):
                if _has_japanese(tr_seg, lang) and _has_japanese(ja_seg, "en"):
                    leaks.append((url, lang, tr_seg[:80]))

    assert leaks == [], (
        f"{len(leaks)} 件の日本語混入を検出:\n"
        + "\n".join(f"  {url} [{lang}]: {seg}" for url, lang, seg in leaks[:20])
    )
