"""一時スキャン: 本番描画パスでja/各言語を位置合わせし、欠けている翻訳原文を特定する。"""

import json
import re

from starlette.testclient import TestClient

from Articles.articles_registry import get_all_articles
from i18n import SUPPORTED_LANGUAGES

KANA_RE = re.compile(r"[\u3041-\u3096\u30a1-\u30fa]")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.I | re.S)
LD_RE = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
ALLOW = {"\u65e5\u672c\u8a9e", "\u7b80\u4f53\u4e2d\u6587", "\u7e41\u9ad4\u4e2d\u6587", "\ud55c\uad6d\uc5b4"}


def segments(html):
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


def has_japanese(s, lang):
    if s in ALLOW:
        return False
    if KANA_RE.search(s):
        return True
    if lang not in ("zh-CN", "zh-TW") and CJK_RE.search(s):
        return True
    return False


def test_extract(test_client: TestClient):
    langs = [l for l in SUPPORTED_LANGUAGES if l != "ja"]
    missing = {}
    mismatches = []
    for article in get_all_articles():
        url = "/" + article["slug"]
        ja_html = test_client.get(url + "?lang=ja").text
        ja_segs = segments(ja_html)
        for lang in langs:
            tr_segs = segments(test_client.get(url + "?lang=" + lang).text)
            if len(tr_segs) != len(ja_segs):
                mismatches.append((url, lang, len(ja_segs), len(tr_segs)))
                continue
            for ja_seg, tr_seg in zip(ja_segs, tr_segs):
                if has_japanese(tr_seg, lang) and has_japanese(ja_seg, "en"):
                    missing.setdefault(ja_seg, [])
                    if lang not in missing[ja_seg]:
                        missing[ja_seg].append(lang)
    with open("/tmp/ja_missing_sources.json", "w") as f:
        json.dump(missing, f, ensure_ascii=False, indent=1)
    print("unique missing sources:", len(missing))
    print("segment-count mismatches:", len(mismatches))
    for mm in mismatches[:10]:
        print("  MISMATCH:", mm)
