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
    {
        "slug": "remote-work-file-sharing-checklist",
        "title": "リモートワークのファイル共有チェックリスト",
        "description": "在宅勤務や外出先からの業務でファイル共有を安全に進めるために、送信前・共有中・完了後に確認したい実践ポイントを整理します。",
        "icon": "fa-laptop",
        "category": "リモートワーク",
        "date": "2026-05-26",
        "template": "remote-work-file-sharing-checklist.html",
        "type": TYPE_ARTICLE,
        "default": False,
    },
    {
        "slug": "home-office-confidential-files",
        "title": "在宅勤務で機密ファイルを扱うときの実践ルール",
        "description": "顧客情報、見積書、契約書などを自宅や社外から扱うときに、誤送信や共有しっぱなしを防ぐための運用ルールを解説します。",
        "icon": "fa-lock",
        "category": "リモートワーク",
        "date": "2026-05-26",
        "template": "home-office-confidential-files.html",
        "type": TYPE_ARTICLE,
        "default": False,
    },
    {
        "slug": "remote-team-material-handoff",
        "title": "リモートチームの資料受け渡しを滞らせない方法",
        "description": "離れた場所で働くメンバー同士が、会議資料・確認用画像・作業ファイルを迷わず受け渡すための共有フローを紹介します。",
        "icon": "fa-users",
        "category": "リモートワーク",
        "date": "2026-05-26",
        "template": "remote-team-material-handoff.html",
        "type": TYPE_ARTICLE,
        "default": False,
    },
    {
        "slug": "school-meeting-class-examples",
        "title": "学校・会議・授業でのファイル共有具体例",
        "description": "学校の授業やビジネス会議、ゼミなどでFS!QRを効果的に活用する具体例を紹介。QRコードや共同編集ノートを使ったペーパーレスなファイル共有方法を解説します。",
        "icon": "fa-chalkboard-user",
        "category": "活用事例",
        "date": "2026-05-29",
        "template": "school-meeting-class-examples.html",
        "type": TYPE_ARTICLE,
        "default": False,
    },
    {
        "slug": "send-large-files-free",
        "title": "大容量ファイルを無料で送る方法と注意点！安全なファイル共有のコツ",
        "description": "動画や高画質な写真など、メールで送れない大容量ファイルを無料で安全に送る方法を解説。容量制限やセキュリティの注意点も紹介します。",
        "icon": "fa-paper-plane",
        "category": "サービス紹介",
        "date": "2026-06-02",
        "template": "send-large-files-free.html",
        "type": TYPE_ARTICLE,
        "default": False,
    },
    {
        "slug": "no-registration-file-sharing",
        "title": "会員登録不要！すぐ使えるファイル共有サービスが便利な理由",
        "description": "アカウント登録なしで今すぐファイルを共有したい方へ。登録不要のファイル転送サービスを利用するメリットと、安全に使うためのポイントを解説します。",
        "icon": "fa-user-xmark",
        "category": "サービス紹介",
        "date": "2026-06-02",
        "template": "no-registration-file-sharing.html",
        "type": TYPE_ARTICLE,
        "default": False,
    },
    {
        "slug": "meeting-minutes-shared-note",
        "title": "リアルタイム共同編集ノートで議事録を作る方法",
        "description": "会議メモや議事録を複数人で同時編集するときの進め方を、事前準備、会議中の書き分け、終了後の整理まで実践的に解説します。",
        "icon": "fa-pen-to-square",
        "category": "活用事例",
        "date": "2026-06-05",
        "template": "meeting-minutes-shared-note.html",
        "type": TYPE_ARTICLE,
        "default": False,
    },
    {
        "slug": "temporary-client-file-room",
        "title": "取引先と一時的にファイルをやり取りするグループルーム運用",
        "description": "取引先や外部パートナーと資料、画像、見積書などを一時的に受け渡すためのグループルーム運用を、準備から終了後の整理まで解説します。",
        "icon": "fa-handshake",
        "category": "ビジネス",
        "date": "2026-06-05",
        "template": "temporary-client-file-room.html",
        "type": TYPE_ARTICLE,
        "default": False,
    },
    {
        "slug": "file-sharing-troubleshooting",
        "title": "ファイル共有でよくある失敗と解決方法",
        "description": "QRコードが読めない、パスワードを伝え忘れた、容量が大きい、期限切れになったなど、ファイル共有で起こりやすい失敗と対処法をまとめます。",
        "icon": "fa-screwdriver-wrench",
        "category": "トラブル対策",
        "date": "2026-06-05",
        "template": "file-sharing-troubleshooting.html",
        "type": TYPE_ARTICLE,
        "default": False,
    },
    {
        "slug": "send-photos-without-quality-loss",
        "title": "写真を画質を落とさずに送る方法｜送ると劣化する原因と対策",
        "description": "LINEやメールで写真を送ると画質が悪くなるのはなぜ？劣化する仕組みと、元の画質のまま送るための具体的な方法をiPhone・Android別にわかりやすく解説します。",
        "icon": "fa-image",
        "category": "デジタル豆知識",
        "date": "2026-06-10",
        "template": "send-photos-without-quality-loss.html",
        "type": TYPE_ARTICLE,
        "default": False,
    },
    {
        "slug": "remove-photo-location-data",
        "title": "写真の位置情報(GPS)を削除してから送る方法｜iPhone・Android・PC別",
        "description": "スマホで撮った写真には撮影場所のGPS情報が埋め込まれていることをご存じですか？SNSや共有で自宅がバレるのを防ぐため、位置情報(Exif)を削除してから送る方法を端末別に解説します。",
        "icon": "fa-location-crosshairs",
        "category": "セキュリティ",
        "date": "2026-06-10",
        "template": "remove-photo-location-data.html",
        "type": TYPE_ARTICLE,
        "default": False,
    },
    {
        "slug": "file-size-units-kb-mb-gb",
        "title": "KB・MB・GBの違いと容量の目安｜写真・動画は何MB？早わかり表",
        "description": "KB・MB・GBの違いを初心者にもわかりやすく解説。写真1枚や動画1分が何MBかの目安、メールで送れる容量、スマホの空き容量の考え方まで、具体例と早わかり表でまとめました。",
        "icon": "fa-database",
        "category": "デジタル豆知識",
        "date": "2026-06-10",
        "template": "file-size-units-kb-mb-gb.html",
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
    return [
        article
        for _, article in sorted(
            (
                (index, a)
                for index, a in enumerate(ARTICLES)
                if a.get("type", TYPE_ARTICLE) == TYPE_ARTICLE
            ),
            key=lambda item: (item[1]["date"], item[0]),
            reverse=True,
        )
    ]


def get_article_by_slug(slug: str) -> dict[str, Any] | None:
    for article in ARTICLES:
        if article["slug"] == slug:
            return article
    return None
