# Locale Catalogs

翻訳ファイルは言語ごとのディレクトリに分割して管理する。

```text
locales/
  en/
    ui.json
    js.json
    phrases/
      articles/
        _shared.json
        browser-based-sharing.json
        send-large-files-free.json
      pages.json
      product.json
      seo.json
      legacy.json
```

## セクション

- `ui.json`: Jinja の `t("...")` で参照するサーバーサイドUI文言。
- `js.json`: `window.FSQR_I18N` 経由で参照するフロントエンド文言。
- `phrases/*.json`: 既存テンプレートの日本語原文を、レンダリング後に置換するための互換カタログ。

`phrases` は肥大化しやすいため、用途ごとにシャードを分ける。

- `articles/<slug>.json`: 記事単位のタイトル、説明、本文。
- `articles/_shared.json`: 記事一覧、カテゴリ、CTAなど記事間で共有する文言。
- `pages.json`: privacy / terms / about / usage など固定ページ。
- `product.json`: FS!QR / Group / Note の画面文言。
- `seo.json`: SEO、JSON-LD、meta description などの補完スクリプト由来。
- `legacy.json`: 出所がまだ特定できていない既存文言。新規追加では使わない。

## 追加ルール

新しいUI文言は、可能な限り安定キーを持つ `ui.json` または `js.json` に追加する。
日本語本文そのものをキーにする `phrases` は、既存テンプレートとの互換用として扱う。

記事カードや本文の翻訳を追加する場合は、該当言語の
`locales/<lang>/phrases/articles/<slug>.json` に追加する。カテゴリやCTAのように
複数記事で共有する文言は `locales/<lang>/phrases/articles/_shared.json` に入れる。
SEO補完は
`locales/<lang>/phrases/seo.json` に入れる。

`locale_store.py` は `phrases/**/*.json` を再帰的に読み込むため、記事が増えても
1ファイルへ追記し続ける必要はない。

## 検証

変更後は以下を実行する。

```bash
python3 scripts/validate_locales.py
```

この検証は `ui` / `js` のキー揃い、プレースホルダー、JSON構造、重複キー、
旧 `locales/<lang>.json` の混入をチェックする。`phrases` の言語間差分は
既存資産にばらつきがあるため通常は警告に留める。完全一致まで確認したい場合は
以下を使う。

```bash
python3 scripts/validate_locales.py --strict-phrases
```
