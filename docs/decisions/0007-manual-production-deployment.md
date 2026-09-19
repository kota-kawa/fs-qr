# ADR-0007: 本番デプロイを手動実行・承認制にする

- 状態: 採用
- 日付: 2026-09-19
- 対象: `.github/workflows/tests.yml`、`docs/blue-green-deploy.md`

## 背景

`main` への push から本番へ直ちにデプロイすると、CI が成功していても、画面や主要な
ユーザーフローを確認する前に公開される。今回はステージング環境を追加せず、デプロイ前に
人が確認できるゲートを GitHub Actions に置く。

## 判断

- `main` への push と pull request は CI のみ実行する。
- 本番デプロイは GitHub Actions の `workflow_dispatch` で `main` を選択した場合だけ実行する。
- デプロイジョブに protected `production` Environment を設定し、required reviewer の承認後に
  SSH デプロイを開始する。
- 承認待ちの間に `main` が進んでも、手動実行時の `github.sha` をサーバーへ checkout する。

## 理由

- ステージング用の DB、Redis、ドメイン、アップロード領域を新設せずに本番公開前の確認を挟める。
- GitHub の権限管理と監査履歴で、誰が本番デプロイを承認したかを残せる。
- branch の最新状態ではなく承認対象の commit を固定することで、承認後の意図しない変更を防げる。

## 影響

- `main` を更新しただけでは本番へ反映されない。Actions から手動実行し、さらに Environment
  の承認が必要になる。
- リポジトリの Settings → Environments → `production` で required reviewer を設定しないと、
  Environment は承認待ちにならない。
- ステージング環境がないため、本番データ・本番環境での確認になる。確認操作は読み取り中心とし、
  アップロードや共同編集データを不用意に残さない。
