# 解説記事の追加方法

解説記事は **中央レジストリ駆動** で管理している。記事を1本増やすときに
ルートや一覧ページのカード定義を手で書き足す必要はない。

## 記事を1本追加する手順

### 1. 本文テンプレートを作る

`Articles/templates/<slug>.html` を作成し、`_article_base.html` を継承する。
SEO 用メタタグ・OGP・Article/BreadcrumbList の構造化データは自動生成されるので、
冒頭でメタ変数を `set` し、本文を `article_body` ブロックに書くだけでよい。

雛形は `Articles/templates/smartphone-receiving.html` を参照。

### 2. レジストリに登録する

`Articles/articles_registry.py` の `ARTICLES` リスト末尾にエントリを1件 append する。

```python
{
    "slug": "my-new-article",          # URL は /my-new-article
    "title": "記事タイトル",
    "description": "一覧カードの説明文",
    "icon": "fa-file-lines",           # Font Awesome アイコン
    "category": "活用事例",             # 一覧の絞り込みカテゴリ
    "date": "2026-05-26",              # 公開日（新しい順に並ぶ／sitemap lastmod）
    "template": "my-new-article.html",
    "default": False,                  # 既存6記事のみ True
}
```

これだけで以下がすべて自動で反映される。

- `/<slug>` の配信ルート
- `/articles` 一覧ページのカード（新しい順・カテゴリ絞り込み・検索対象）
- 公開から14日以内なら一覧に **NEW** バッジ
- `sitemap.xml` の記事エントリ

### 3. 多言語対応（カード文言）

一覧ページは全言語で日本語が残らないことをテストで検証している
(`tests/test_basic_routes.py`)。新規記事の **タイトルと説明文** を
`locales/en.json` の `phrases` に追加すること。

```json
"記事タイトル": "Article Title",
"一覧カードの説明文": "Card description in English"
```

en 以外の言語は en にフォールバックする（`i18n.LANGUAGE_FALLBACKS`）ため、
最低限 en を用意すれば日本語の混在は起きない。主要言語の品質を上げたい場合は
`locales/<lang>.json` にも個別に追加する。本文（記事詳細ページ）は
i18n テスト対象外なので、日本語のままでも差し支えない。

## デフォルト記事

`default: True` の6記事（fs-qr-concept / safe-sharing / encryption /
education / business / risk-mitigation）は初期セット。本文テンプレートは
従来どおり各自で完結しており、`_article_base.html` は継承していない。
これらは常に維持される基本記事として扱う。
