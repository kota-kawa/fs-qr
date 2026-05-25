"""解説記事の中央レジストリ。

記事を1件追加するときは、原則として以下の2ステップだけで完結する:

1. このファイルの ``ARTICLES`` リストへエントリを1件追加する。
2. ``Articles/templates/`` に本文テンプレート(``template`` で指定した名前)を置く。
   新規記事は ``_article_base.html`` を継承すると SEO 用メタ情報や
   パンくず構造化データが自動で出力されるため、本文だけ書けばよい。

ここに登録された内容を元に、ルーティング・記事一覧ページ・sitemap.xml の
記事エントリがすべて自動生成される。個別ルートや一覧ページのカード定義を
手で書き足す必要はない。

種別(``type``):
    "guide"   サービスの考え方・使い方を説明する普遍的(エバーグリーン)な解説。
              一覧では「サービス解説ガイド」セクションに常に上部固定で表示され、
              公開日や NEW バッジは出さない。初期の6件がこれにあたる。
    "article" 日付つきで増えていくブログ的な記事。一覧では「新着記事」セクションに
              新しい順で並び、公開から一定期間は NEW バッジが付く。

フィールド:
    slug:        URL パス。``/<slug>`` で配信される(先頭スラッシュは付けない)。
    title:       一覧カードと構造化データに使うタイトル。
    description: 一覧カードの説明文。
    icon:        Font Awesome のアイコンクラス(例: ``fa-lightbulb``)。
    category:    一覧ページの絞り込みに使うカテゴリ名。
    date:        公開日(``YYYY-MM-DD``)。article は新しい順に並び、sitemap の
                 lastmod にも使われる。
    template:    ``Articles/templates/`` 配下の本文テンプレートファイル名。
    type:        "guide" または "article"(上記参照)。
    default:     初期(デフォルト)記事かどうか。True の6件は既存のガイドで、
                 常に維持する基本セット。
"""

from __future__ import annotations

from typing import Any

TYPE_GUIDE = "guide"
TYPE_ARTICLE = "article"

# 既存の6件はサービス解説ガイド(エバーグリーン)としてデフォルト保持する。
# 日次で増やすブログ記事は type="article" でこのリスト末尾に append していく。
ARTICLES: list[dict[str, Any]] = [
    {
        "slug": "fs-qr-concept",
        "title": "FS!QRの基本的な考え方",
        "description": "FS!QRの設計思想や技術的な考え方について、開発背景とコンセプトを詳しく解説します。",
        "icon": "fa-lightbulb",
        "category": "サービス紹介",
        "date": "2025-08-31",
        "template": "fs-qr-concept.html",
        "type": TYPE_GUIDE,
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
        "type": TYPE_GUIDE,
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
        "type": TYPE_GUIDE,
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
        "type": TYPE_GUIDE,
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
        "type": TYPE_GUIDE,
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
        "type": TYPE_GUIDE,
        "default": True,
    },
    # ── 日次で追加するブログ記事(type="article")はここから下に1件ずつ append する ──
    {
        "slug": "smartphone-receiving",
        "title": "スマホでファイルを受け取る方法",
        "description": "共有されたファイルをスマートフォンで受け取る手順を、QRコードの読み取りからダウンロードまで初心者にもわかりやすく解説します。",
        "icon": "fa-mobile-screen-button",
        "category": "活用事例",
        "date": "2026-05-26",
        "template": "smartphone-receiving.html",
        "type": TYPE_ARTICLE,
        "default": False,
    },
    {
        "slug": "pc-mobile-transfer",
        "title": "PCとスマホ間でのシームレスなファイル転送",
        "description": "ケーブル不要！PCからスマホ、スマホからPCへ、ブラウザとQRコードだけで簡単にファイルを送受信するテクニックを紹介します。",
        "icon": "fa-sync-alt",
        "category": "活用事例",
        "date": "2026-05-26",
        "template": "pc-mobile-transfer.html",
        "type": TYPE_ARTICLE,
        "default": False,
    },
    {
        "slug": "browser-based-sharing",
        "title": "ブラウザだけで完結する！大容量ファイルの共有術",
        "description": "専用アプリやアカウント作成はもういらない。ブラウザだけで安全に大容量ファイルを送るための具体的なステップを解説します。",
        "icon": "fa-upload",
        "category": "活用事例",
        "date": "2026-05-26",
        "template": "browser-based-sharing.html",
        "type": TYPE_ARTICLE,
        "default": False,
    },
    {
        "slug": "auto-delete-benefits",
        "title": "一時的な共有に最適！自動削除機能のメリット",
        "description": "「送りっぱなし」のリスクを防ぐ。FS!QRの自動削除機能がなぜセキュリティに有効なのか、その理由を詳しく紐解きます。",
        "icon": "fa-clock",
        "category": "サービス紹介",
        "date": "2026-05-26",
        "template": "auto-delete-benefits.html",
        "type": TYPE_ARTICLE,
        "default": False,
    },
    {
        "slug": "telework-security",
        "title": "テレワークでのセキュリティ向上！パスワード保護の活用",
        "description": "在宅勤務時の機密情報受け渡しに。パスワードとIDによる2重の保護機能を使って、より安全に業務ファイルを共有する方法。",
        "icon": "fa-user-shield",
        "category": "セキュリティ",
        "date": "2026-05-26",
        "template": "telework-security.html",
        "type": TYPE_ARTICLE,
        "default": False,
    },
    {
        "slug": "event-material-distribution",
        "title": "QRコードを活用したイベント・会議での資料配布",
        "description": "紙の資料はもう不要？会議やセミナーで参加者に素早く資料を配布するための、QRコード活用法と具体的なメリット。",
        "icon": "fa-users",
        "category": "活用事例",
        "date": "2026-05-26",
        "template": "event-material-distribution.html",
        "type": TYPE_ARTICLE,
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


def get_all_articles() -> list[dict[str, Any]]:
    """登録済みの全エントリ(ガイド + 記事)のコピーを返す。

    ルーティング登録や sitemap 生成など、種別を問わず全件を扱う用途で使う。
    """
    return list(ARTICLES)


def get_guides() -> list[dict[str, Any]]:
    """サービス解説ガイド(type="guide")を登録順で返す。

    エバーグリーンな基本コンテンツなので日付では並べ替えず、登録順を保つ。
    """
    return [a for a in ARTICLES if a.get("type", TYPE_ARTICLE) == TYPE_GUIDE]


def get_blog_articles_sorted() -> list[dict[str, Any]]:
    """ブログ記事(type="article")を新しい順に並べて返す。"""
    return sorted(
        (a for a in ARTICLES if a.get("type", TYPE_ARTICLE) == TYPE_ARTICLE),
        key=lambda a: a["date"],
        reverse=True,
    )


def get_article_by_slug(slug: str) -> dict[str, Any] | None:
    for article in ARTICLES:
        if article["slug"] == slug:
            return article
    return None
