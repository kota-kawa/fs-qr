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
  日付つきで増えていく実務記事。一覧では下段に新しい順で並び、公開前に
  独自性・正確性・サービスとの関連性を確認した記事だけを追加する。

> 記事を追加するときは、本文と全対応言語の翻訳を完成させ、品質確認が終わるまで
> `indexable: False` にしておく。公開記事は一般的なサービス紹介ではなく、読者が
> 実際に試せる手順・検証結果・制約・判断材料を含むものに限定する。

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
    "date": "2026-05-26",              # 公開日（新しい順に並ぶ）
    "template": "my-new-article.html",
    "type": "article",                 # 新着記事は "article"（解説は "guide"）
    "default": False,                  # 既存6ガイドのみ True
    "indexable": False,                 # 品質確認後に sitemap / 一覧へ出す場合のみ True
}
```

本文を更新した記事はテンプレートに `article_modified`（`YYYY-MM-DD`）を指定する。
画面の更新日、構造化データ、sitemap の `lastmod` に同じ日付が反映される。

これだけで以下がすべて自動で反映される。

- `/<slug>` の配信ルート
- `indexable: True` の場合のみ `/articles` 一覧ページの「新着記事」セクションのカード（新しい順・カテゴリ絞り込み・検索対象）
- `indexable: True` の場合のみ `sitemap.xml` の記事エントリ

AdSense 再審査中は、公開対象を6件のサービス解説ガイドと、実際の操作トラブル・
プライバシー対策を扱う厳選記事に限定する。新規記事を作っただけでは検索・広告対象に
しない。本文の独自性、実画面の説明、運営者情報、最終確認日、導線を確認してから
`Articles/articles_registry.py` の indexable 設定に追加する。

### 3. 多言語対応（カード文言）

一覧ページは全言語で日本語が残らないことをテストで検証している
(`tests/test_basic_routes.py`)。新規記事の **タイトルと説明文** を
`locales/en/phrases/articles/<slug>.json` に追加すること。

```json
"記事タイトル": "Article Title",
"一覧カードの説明文": "Card description in English"
```

審査対象の記事は、対応している全言語で本文・見出し・メタ情報を個別に用意する。
英語フォールバック（`i18n.LANGUAGE_FALLBACKS`）に依存すると、記事の文脈や注意書きが
崩れるため、公開前に `locales/<lang>/phrases/articles/<slug>.json` を各言語で確認する。
カテゴリやCTAなど複数記事で共有する文言は
`locales/<lang>/phrases/articles/_shared.json` に追加する。
本文（記事詳細ページ）の翻訳も同じ `<slug>.json` に追加する。記事単位で閉じるため、
記事を削除・更新するときに対象ファイルを追いやすい。

翻訳追加後は次を実行し、`ui` / `js` のキー破損や `phrases` の重複がないことを
確認する。

```bash
python3 scripts/validate_locales.py
```

## デフォルトのガイド

`type: "guide"` / `default: True` の6件（fs-qr-concept / safe-sharing /
encryption / education / business / risk-mitigation）は初期セット。本文
テンプレートは従来どおり各自で完結しており、`_article_base.html` は継承していない。
これらは常に維持される基本記事として扱う。
