# Blue-Green 無停止デプロイ

GitHub Actions 等の自動デプロイで発生していた「切替中 約1分の 502 Bad Gateway」を
なくすための構成。アプリ（gunicorn）を **blue / green の2スロット**で扱い、
新しい色が healthy になってから nginx を切替えるため、受け口が一瞬も消えない。

```
                         ┌─ include /etc/nginx/fsqr_active_backend.conf
nginx (host) ─ upstream ─┤      └─ "server 127.0.0.1:5000;"  ← blue が active
 fsqr_app                │         "server 127.0.0.1:5030;"  ← green が active
                         └─ どちらか一方だけを指す（デプロイ時に reload で切替）
```

| 色    | compose service | profile | ホストポート       |
|-------|-----------------|---------|--------------------|
| blue  | `web-blue`      | `blue`  | `127.0.0.1:5000`   |
| green | `web-green`     | `green` | `127.0.0.1:5030`   |

db / redis / scheduler は常駐の単一インスタンスで、Blue-Green の対象外。
セッション・レート制限・キャッシュ・ロック・WebSocket fanout はすべて Redis 共有
なので、切替時に blue/green が一瞬重なっても整合する。

---

## 初回セットアップ（サーバ上で1回だけ）

> ⚠️ **旧構成からの移行**: 旧 `web` サービスのコンテナがホスト 5000 を掴んでいると、
> 最初の `web-blue`（127.0.0.1:5000）が起動できない。移行時は一度だけ旧スタックを落とす。

1. リポジトリ（`DEPLOY_PATH`）を最新へ更新し、旧コンテナを撤去:

   ```bash
   cd "$DEPLOY_PATH"          # 例: /home/kota/fs-qr または /var/www/fs-qr
   git fetch origin main && git reset --hard origin/main
   docker compose down --remove-orphans   # 旧 web/scheduler 等を停止・削除（named volume は保持）
   ```

2. nginx に backend ファイルを配置（初期は blue=5000）し、`fs-qr.conf` を反映:

   ```bash
   sudo cp deploy/fsqr_active_backend.conf.example /etc/nginx/fsqr_active_backend.conf
   # fs-qr.conf を /etc/nginx/sites-available/ 等へ配置済みの前提。
   # ※ fs-qr.conf の /_protected/ alias パス（storage の絶対パス）が DEPLOY_PATH と
   #    一致しているか確認すること。
   sudo nginx -t && sudo nginx -s reload
   ```

3. インフラ（db / redis）を起動:

   ```bash
   docker compose up -d db redis
   ```

4. 最初の色（blue）をデプロイ（scheduler もこの中で起動・更新される）:

   ```bash
   REPO_DIR="$DEPLOY_PATH" bash scripts/deploy_bluegreen.sh
   ```

`.deploy/active_color` に現在の active 色が記録される。

### sudo 権限（必須）

デプロイを行う SSH ユーザ（`SERVER_USER`）が以下をパスワードなしで実行できること:

```
# /etc/sudoers.d/fsqr-deploy（例）
<SERVER_USER> ALL=(root) NOPASSWD: /usr/sbin/nginx, /usr/bin/tee /etc/nginx/fsqr_active_backend.conf
```

---

## 以降のデプロイ（毎回これだけ）

```bash
bash scripts/deploy_bluegreen.sh
```

スクリプトが自動で「非アクティブな色」をビルド→healthy 待ち→nginx 切替→旧色停止
を行う。**新コンテナが healthy にならない / `nginx -t` が通らない場合は切替せず中断**
するため、サービスは止まらない。

調整用の環境変数: `HEALTH_TIMEOUT`（既定180秒）, `DRAIN_SECONDS`（既定15秒）,
`NGINX_BACKEND_FILE`, `REPO_DIR`。

### GitHub Actions（実装済み）

`.github/workflows/tests.yml` の `deploy` ジョブ（main push 時）は、SSH 先で
`git reset --hard origin/main` → `docker compose up -d db redis` →
`REPO_DIR="$DEPLOY_PATH" bash scripts/deploy_bluegreen.sh` を実行するよう更新済み。
旧来の `docker compose up -d --build`（単一 web を作り直して 502 を出していた処理）は
撤去した。失敗時はスクリプトが切替を行わず中断し、ジョブの `on_error` が作業ツリーを
元コミットへ戻す（旧コンテナは生きたまま）。

実行ユーザの sudo 要件は上記「sudo 権限」を参照。

---

## 運用上の必須ルール

- **DB マイグレーションは expand/contract（後方互換）厳守。**
  各 web コンテナは起動時に `run_migrations()` を実行する（MySQL `GET_LOCK` で
  多重実行はレース安全）。ただし切替の谷間で「新スキーマ × 旧コード」が必ず共存する
  ため、カラム削除・リネーム・`NOT NULL` 追加などの破壊的変更は **2段階**
  （①追加デプロイ → ②旧コード撤去後に削除デプロイ）に分ける。

- **アップロード中の切替に注意。** `client_max_body_size 500M` / gunicorn
  `graceful_timeout 30s`。旧コンテナ stop 時に進行中の大容量アップロードは切れる。
  `DRAIN_SECONDS` を延ばすか、長時間アップロードが少ない時間帯に流す。

- **scheduler は単一のまま。** 2重起動・スケールさせない（Redis ロックで単一実行前提）。

- **GeoIP 自動更新**は各 web で `./geoip` 共有に書き込む。steady-state は単一 web の
  ため実害は小さいが、起動時 DL が healthy 到達を遅らせる場合は
  `GEOIP_AUTO_UPDATE=false` を web 側 env に設定し、更新を別途運用する。

---

## ロールバック

直前の色へ戻すだけ。旧コンテナを起動し直して nginx を戻す:

```bash
# 例: green へ切替えた直後に blue へ戻す
docker compose --profile blue up -d --no-deps web-blue
printf 'server 127.0.0.1:5000;\n' | sudo tee /etc/nginx/fsqr_active_backend.conf
sudo nginx -t && sudo nginx -s reload
echo blue > .deploy/active_color
```
