# フロントエンドの実描画確認（Playwright）

CSS、テンプレートの構造、静的 JS のイベント処理など見た目や操作に影響する変更は、PR を作る前に
ブラウザで実描画・実操作し、スクリーンショットを目視で確認します。型定義や API クライアント、
サーバー側だけの変更は対象外です。

## 準備

Playwright はリポジトリの依存関係に含めません。確認用にローカルへ入れます。

```bash
python3 -m pip install --user playwright
python3 -m playwright install chromium
```

Claude Code の Playwright MCP（`browser_navigate` / `browser_resize` / `browser_take_screenshot`）
を使う場合も、確認する画面・ビューポート・観点は同じです。

## 描画対象の用意

1. 基本は起動済みの Compose スタック（`docker-compose up --build`、web-blue は
   `http://localhost:5000`）を使います。DB と Redis が必要です。
2. DB を使わずに確認する場合は、`tests/conftest.py` のモック済み `TestClient` で対象ページの
   HTML を取得してファイルに保存し、`static/` と一緒に `python3 -m http.server` で配信して
   開きます。テンプレート・CSS・JS だけの変更ならこの方法で十分です（PR #387 で使った手順）。
3. リファクタ後の回帰確認では、`git show <変更前コミット>:<path>` で旧実装を取り出し、
   同じ HTML を旧 CSS / 旧 JS でも描画して数値を比較します。

## 確認するビューポートと画面

| 区分 | 幅×高さ | 用途 |
| --- | --- | --- |
| PC | 1280×800 | 既定のデスクトップ表示 |
| スマホ | 390×844 | `static/css/00-breakpoints.css` のモバイル分岐 |

- 共通部品（`templates/`、`static/js/shared/`、`static/css/17-room-access.css` 〜 `static/css/20-status-page.css`）を変えたときは、FSQR /
  Group / Note / Task の 4 サービスそれぞれで入口ページ、ルーム画面、LP を確認します。
  サービス色は CSS custom property で渡しているため、1 サービスだけの確認では配色の取り違えを
  見落とします。
- 特定サービスだけの変更でも、そのサービスの LP と入口ページ、ルーム画面の 3 種類を見ます。

## 確認する観点

- レイアウト崩れ、文字切れ、要素の重なり、余白、横スクロールの発生
  （`document.documentElement.scrollWidth <= clientWidth`）。
- 配色: 変更前後で `getComputedStyle` の色（RGB 値）が意図通りか。`theme-color` meta と
  PWA manifest（`pwa_manifest.py`）の色が入口ページの装飾色と混ざっていないか。
- 操作: クリック、開閉（FAQ、ドロップダウン、モーダル）、コピー成功・失敗時の文言、フォーム送信、
  キーボード操作。カスタムセレクトなどの JS 拡張が実際に適用されているか（wrapper 要素の有無）。
- 読み込み順: `defer` の有無と `_scripts.html` の同期読み込み順を本番と同じにした状態で、
  `window.FSQR_I18N` などの初期化前に文言を評価していないか。
- コンソール: 未処理の Promise rejection、CSP 違反、404 が出ていないか
  （`page.on("console")` / `page.on("pageerror")`）。
- 多言語: 文言の長い言語（de、ru、bn など）で折り返しやボタン幅が崩れないか。少なくとも `?lang=en`
  を 1 回見ます。

## 最小のスクリプト例

```python
from playwright.sync_api import sync_playwright

TARGETS = ["/fs-qr", "/group", "/note", "/task"]
VIEWPORTS = {"pc": (1280, 800), "sp": (390, 844)}

with sync_playwright() as p:
    browser = p.chromium.launch()
    for path in TARGETS:
        for name, (width, height) in VIEWPORTS.items():
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://localhost:5000{path}", wait_until="networkidle")
            overflow = page.evaluate(
                "document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            page.screenshot(path=f"/tmp/shot{path.replace('/', '_')}-{name}.png", full_page=True)
            print(path, name, "overflow:", overflow, "errors:", errors)
            page.close()
    browser.close()
```

取得したスクリーンショットは必ず自分で開いて目視します。数値だけで判断しません。

## PR 本文に書くこと

- 確認した画面（URL）とビューポート、確認したサービス。
- 実測結果（横スクロール量、比較した色や座標、コンソールエラーの有無）。
- 見つけて直した項目と、直さずに残した項目（理由つき）。
- スクリーンショットを添付する場合は `docs/screenshots/<話題>/` にコミットして参照します。
  一時的な確認画像はコミットしません。
