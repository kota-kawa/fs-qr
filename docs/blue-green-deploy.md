# Blue-Green 無停止デプロイ

GitHub Actions 等の自動デプロイで発生していた「切替中 約1分の 502 Bad Gateway」を
なくすための構成。アプリ（gunicorn）を **blue / green の2スロット**で扱い、
新しい色が healthy になってから nginx を切替えるため、受け口が一瞬も消えない。

切替は nginx の `upstream fsqr_app`（`fs-qr.conf`）に **blue/green の両 server を記載**し、
待機側を `down` でマークすることで行う。デプロイスクリプトがこの `down` を付け替えて
`nginx -s reload` する（設定は `fs-qr.conf` 1本に集約。include や別ファイルは使わない）。

```nginx
upstream fsqr_app {
    server 127.0.0.1:5000;        # blue (active)
    server 127.0.0.1:5030 down;   # green (standby) ← デプロイ時に down を付け替える
    keepalive 32;
}
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
   cd "$DEPLOY_PATH"          # 本番デプロイ先。例: /var/www/fs-qr
   git fetch origin main && git reset --hard origin/main
   docker compose down --remove-orphans   # 旧 web/scheduler 等を停止・削除（named volume は保持）
   ```

2. `fs-qr.conf` を nginx に配置して反映（初期状態は blue=5000 が active、green=5030 が `down`）:

   ```bash
   sudo cp fs-qr.conf /etc/nginx/sites-available/fs-qr.conf   # 配置先は環境に合わせる
   # ※ /_protected/ alias パス（storage の絶対パス）が DEPLOY_PATH と一致しているか確認。
   # ※ デプロイスクリプトはこの配置済み conf を直接書き換える。配置先が
   #    /etc/nginx/sites-available/fs-qr.conf でない場合は NGINX_SITE_CONF で指定する。
   sudo nginx -t && sudo nginx -s reload
   ```

  以降の自動デプロイでは `fs-qr.conf` を再コピーしない（スクリプトが配置済み conf の
  `down` だけを書き換えて現在の active 色を保持する）。`fs-qr.conf` 自体を更新したい
  ときだけ手動で再コピーする（その際 active 色は blue に戻る点に注意）。

### 大容量アップロード上限の反映

FSQR と Group の合計 1GiB アップロードには、nginx の
`client_max_body_size 1025M` が必要です。自動デプロイは nginx 設定を再コピーしないため、
既存サーバーではアプリのデプロイ前または同時に次を一度だけ実行します。`1025M` は
multipart と FSQR の暗号化エンベロープを受け入れる余裕であり、実ファイルの 1GiB 上限は
アプリ側で検証します。

```bash
conf=/etc/nginx/sites-available/fs-qr.conf  # NGINX_SITE_CONF と同じパス
backup="${conf}.before-1gb-$(date +%Y%m%d%H%M%S)"
sudo cp "$conf" "$backup"
sudo sed -i 's/client_max_body_size 500M;/client_max_body_size 1025M;/' "$conf"
sudo nginx -t && sudo nginx -s reload
```

ロールバック時は、作成したバックアップを戻してから設定検証・reload を実行します。

```bash
sudo cp "$backup" "$conf"
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

デプロイを行う SSH ユーザ（`SERVER_USER`）が、nginx 設定の読み取り・バックアップ・
上書き・構文チェック・reload を **非対話 sudo** で実行できること。
GitHub Actions は TTY なしの SSH で動くため、パスワード入力が必要な sudo は使えない。

サーバ上で実際のパスを確認する:

```bash
command -v cat cp nginx
```

`/etc/sudoers.d/fsqr-deploy` の例:

```
<SERVER_USER> ALL=(root) NOPASSWD: /usr/bin/cat, /usr/bin/cp, /usr/sbin/nginx
```

環境によって `cat` / `cp` が `/bin` 配下の場合は、その実パスに合わせる。
スクリプトは既定で `sudo -n` を使い、必要権限がなければ web コンテナをビルドする前に
失敗させる。root で実行する場合は sudo を使わない。

---

## 以降のデプロイ（毎回これだけ）

```bash
bash scripts/deploy_bluegreen.sh
```

スクリプトが自動で「非アクティブな色」をビルド→healthy 待ち→nginx 切替→旧色停止
を行う。**新コンテナが healthy にならない / `nginx -t` が通らない場合は切替せず中断**
するため、サービスは止まらない。

調整用の環境変数: `HEALTH_TIMEOUT`（既定180秒）, `DRAIN_SECONDS`（既定15秒）,
`NGINX_SITE_CONF`（配置済み fs-qr.conf のパス）, `REPO_DIR`。

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

- **アップロード中の切替に注意。** `client_max_body_size 1025M` / gunicorn
  `graceful_timeout 30s`。旧コンテナ stop 時に進行中の大容量アップロードは切れる。
  `DRAIN_SECONDS` を延ばすか、長時間アップロードが少ない時間帯に流す。

- **scheduler は単一のまま。** 2重起動・スケールさせない（Redis ロックで単一実行前提）。

- **GeoIP 自動更新**は各 web で `./geoip` 共有に書き込む。steady-state は単一 web の
  ため実害は小さいが、起動時 DL が healthy 到達を遅らせる場合は
  `GEOIP_AUTO_UPDATE=false` を web 側 env に設定し、更新を別途運用する。

---

## ロールバック

最も簡単なのは、`.deploy/active_color` を戻したい色の「反対」にしてもう一度
`scripts/deploy_bluegreen.sh` を実行すること（前の色を立て直して切替える）。

手動で戻す場合は、旧コンテナを起動し直し、配置済み `fs-qr.conf` の `down` を付け替える:

```bash
# 例: green へ切替えた直後に blue へ戻す
docker compose --profile blue up -d --no-deps web-blue
conf=/etc/nginx/sites-available/fs-qr.conf   # NGINX_SITE_CONF と同じ
sudo sed -ri \
  -e 's|^([[:space:]]*)server[[:space:]]+127\.0\.0\.1:5000([[:space:]]+down)?[[:space:]]*;.*$|\1server 127.0.0.1:5000;        # active|' \
  -e 's|^([[:space:]]*)server[[:space:]]+127\.0\.0\.1:5030([[:space:]]+down)?[[:space:]]*;.*$|\1server 127.0.0.1:5030 down;   # standby|' \
  "$conf"
sudo nginx -t && sudo nginx -s reload
echo blue > .deploy/active_color
```
