# 解説記事の追加方法

解説記事は **中央レジストリ駆動** で管理している。記事を1本増やすときに
ルートや一覧ページのカード定義を手で書き足す必要はない。

## 2つの種別（type）

一覧ページ `/articles` は内容を2セクションに分けて表示する。

- **`type: "guide"` … サービス解説ガイド**
  サービスの考え方・使い方を説明する普遍的（エバーグリーン）な解説。
  一覧では常に上部に固定表示し、公開日や NEW バッジは出さない。
  初期の6件（fs-qr-concept / safe-sharing / encryption / education /
  business / risk-mitigation）がこれにあたり、`default: True` で維持される。
- **`type: "article"` … 新着記事**
  日付つきで増えていくブログ的な記事。一覧では下段に新しい順で並び、
  公開から14日以内は **NEW** バッジが付く。日次で追加するのはこちら。

> 日次で記事を追加するときは原則 `type: "article"` を使う。

## 記事を1本追加する手順

### 1. 本文テンプレートを作る

`Articles/templates/<slug>.html` を作成し、`_article_base.html` を継承する。
SEO 用メタタグ・OGP・Article/BreadcrumbList の構造化データは自動生成されるので、
冒頭でメタ変数を `set` し、本文を `article_body` ブロックに書くだけでよい。

雛形は `Articles/templates/smartphone-receiving.html` を参照。

#### サービス導線（CTA）

全ての記事には FS!QR / Group / Note いずれかのサービスへの導線（CTA）を末尾に
表示する。`_article_base.html` を継承した記事は、冒頭で

```jinja
{% set cta_service = "group" %}   {# "fsqr"（既定） / "group" / "note" #}
```

と書くだけで自動表示される（未指定なら FS!QR）。CTA の見た目・文言は
`Articles/templates/_article_cta.html` に集約されている。`_article_base.html` を
使わない既存ガイドは、本文末尾で同テンプレートを `{% include %}` している。

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
    "type": "article",                 # 日次記事は "article"（解説は "guide"）
    "default": False,                  # 既存6ガイドのみ True
}
```

これだけで以下がすべて自動で反映される。

- `/<slug>` の配信ルート
- `/articles` 一覧ページの「新着記事」セクションのカード（新しい順・カテゴリ絞り込み・検索対象）
- 公開から14日以内なら **NEW** バッジ
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

## デフォルトのガイド

`type: "guide"` / `default: True` の6件（fs-qr-concept / safe-sharing /
encryption / education / business / risk-mitigation）は初期セット。本文
テンプレートは従来どおり各自で完結しており、`_article_base.html` は継承していない。
これらは常に維持される基本記事として扱う。
