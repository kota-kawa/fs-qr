"""解説記事の中央レジストリ。

記事を1件追加するときは、原則として以下の2ステップだけで完結する:

1. このファイルの ``ARTICLES`` リストへエントリを1件追加する。
2. ``Articles/templates/`` に本文テンプレート(``template`` で指定した名前)を置く。
   新規記事は ``_article_base.html`` を継承すると SEO 用メタ情報や
   パンくず構造化データが自動で出力されるため、本文だけ書けばよい。

ここに登録された内容を元に、ルーティング・記事一覧ページ・sitemap.xml の
記事エントリがすべて自動生成される。個別ルートや一覧ページのカード定義を
手で書き足す必要はない。

フィールド:
    slug:        URL パス。``/<slug>`` で配信される(先頭スラッシュは付けない)。
    title:       一覧カードと構造化データに使うタイトル。
    description: 一覧カードの説明文。
    icon:        Font Awesome のアイコンクラス(例: ``fa-lightbulb``)。
    category:    一覧ページの絞り込みに使うカテゴリ名。
    date:        公開日(``YYYY-MM-DD``)。一覧は新しい順に並び、sitemap の
                 lastmod にも使われる。
    template:    ``Articles/templates/`` 配下の本文テンプレートファイル名。
    default:     初期(デフォルト)記事かどうか。True の6件は既存記事で、
                 一覧では並び順に関わらず常に表示される基本セット。
"""

from __future__ import annotations

from typing import Any

# 既存の6記事をデフォルト(初期セット)として保持する。
# 以降の日次追加はこのリストの末尾に append していくだけでよい。
ARTICLES: list[dict[str, Any]] = [
    {
        "slug": "fs-qr-concept",
        "title": "FS!QRの基本的な考え方",
        "description": "FS!QRの設計思想や技術的な考え方について、開発背景とコンセプトを詳しく解説します。",
        "icon": "fa-lightbulb",
        "category": "サービス紹介",
        "date": "2025-08-31",
        "template": "fs-qr-concept.html",
        "default": True,
    },
    {
        "slug": "safe-sharing",
        "title": "安全な共有のポイント",
        "description": "ファイル共有を安全に行うためのベストプラクティスとセキュリティのポイントを解説します。",
        "icon": "fa-shield-alt",
        "category": "セキュリティ",
        "date": "2025-08-31",
        "template": "safe-sharing.html",
        "default": True,
    },
    {
        "slug": "encryption",
        "title": "暗号化の基礎知識",
        "description": "FS!QRで使用されている暗号化技術について、わかりやすく基礎から説明します。",
        "icon": "fa-lock",
        "category": "セキュリティ",
        "date": "2025-08-21",
        "template": "encryption.html",
        "default": True,
    },
    {
        "slug": "education",
        "title": "教育での活用例",
        "description": "学校や教育機関でFS!QRを効果的に活用するための具体的な事例を紹介します。",
        "icon": "fa-graduation-cap",
        "category": "活用事例",
        "date": "2025-08-21",
        "template": "education.html",
        "default": True,
    },
    {
        "slug": "business",
        "title": "業務での活用例",
        "description": "ビジネス現場でFS!QRを活用して業務効率を向上させる方法を実例とともに解説します。",
        "icon": "fa-briefcase",
        "category": "活用事例",
        "date": "2025-08-21",
        "template": "business.html",
        "default": True,
    },
    {
        "slug": "risk-mitigation",
        "title": "リスクと対策の考え方",
        "description": "ファイル共有におけるリスクを理解し、適切な対策を講じるための考え方を学びます。",
        "icon": "fa-exclamation-triangle",
        "category": "セキュリティ",
        "date": "2025-08-21",
        "template": "risk-mitigation.html",
        "default": True,
    },
    # ── 日次で追加する記事はここから下に1件ずつ append する ──
    {
        "slug": "smartphone-receiving",
        "title": "スマホでファイルを受け取る方法",
        "description": "共有されたファイルをスマートフォンで受け取る手順を、QRコードの読み取りからダウンロードまで初心者にもわかりやすく解説します。",
        "icon": "fa-mobile-screen-button",
        "category": "活用事例",
        "date": "2026-05-26",
        "template": "smartphone-receiving.html",
        "default": False,
    },
]

# 一覧の絞り込みチップに使う、登録順を保ったカテゴリ一覧。
_seen: set[str] = set()
CATEGORIES: list[str] = []
for _article in ARTICLES:
    _category = _article["category"]
    if _category not in _seen:
        _seen.add(_category)
        CATEGORIES.append(_category)


def get_articles_sorted() -> list[dict[str, Any]]:
    """新しい順(同日ならデフォルト記事を優先)に並べたコピーを返す。"""
    return sorted(
        ARTICLES,
        key=lambda a: (a["date"], a.get("default", False)),
        reverse=True,
    )


def get_article_by_slug(slug: str) -> dict[str, Any] | None:
    for article in ARTICLES:
        if article["slug"] == slug:
            return article
    return None
