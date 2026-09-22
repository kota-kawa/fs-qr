# main ブランチの保護設定

GitHub 上の `main` の保護設定と必須 CI チェックの記録です（2026-09-23 時点、
`gh api` で branch protection、rulesets、environments を取得して確認）。設定を
変更したら、同じ PR でこの文書を更新してください。

## 必須ステータスチェック

`.github/workflows/tests.yml` の各ジョブの `name:`（表示名）がそのままチェック名になります。表示名を変えると
必須チェックが「待ち」のまま外れなくなるため、名前を変えるときは保護設定も同時に更新します。

| チェック名（ジョブの `name`） | ジョブ ID | 必須 |
| --- | --- | --- |
| `Ruff (Python lint + format)` | `lint`（Ruff、文書パス検証、環境変数検証） | 必須 |
| `pip-audit (dependency vulnerabilities)` | `audit` | 必須 |
| `mypy (static type checking)` | `typecheck` | 必須 |
| `Pytest (Python 3.13)` | `test`（matrix） | 必須 |
| `Pytest (Python 3.14)` | `test`（matrix） | 必須 |
| `Hocuspocus (Node test + audit + bundle)` | `node` | 任意 |
| `Docker build + Trivy scan` | `image-scan` | 任意 |

- ブランチは最新の `main` に追従している必要があります（strict）。
- `Deploy (manual production)` は `workflow_dispatch` かつ `main` のときだけ動く手動デプロイで、
  必須チェックではありません（[ADR-0007](../docs/decisions/0007-manual-production-deployment.md)）。

## プルリクエストの条件

- PR 経由でのみ `main` を更新できます（直接 push、force push、ブランチ削除は不可）。
- 必須の承認数は 0 です。ただしレビューコメントのスレッドはすべて解決済みである必要があります
  （required conversation resolution）。
- 新しい push があると古い承認は無効になります（dismiss stale reviews）。
- リポジトリ ruleset「Protect main」が併用されており、削除と非 fast-forward の禁止、PR 必須、
  マージ方法は merge / squash / rebase を許可しています。
- 管理者にも同じ条件を強制する設定（enforce admins）は無効です。

## CI の並行実行

`concurrency.group` は workflow と ref ごとで `cancel-in-progress: true` です。同じ ref への
連続 push や連続マージは直前の実行を打ち切ります。`main` へのマージは直前の CI 完了を待ちます
（[AGENTS.md](../AGENTS.md)）。

## Environments

- `production`: デプロイジョブが参照する protected environment です。required reviewer を
  設定しないと承認待ちになりません。2026-09-23 時点では GitHub 上に `production` Environment が
  まだ作成されていないため、初回の手動デプロイ前に Settings → Environments で作成し、
  reviewer を設定してください。

## 確認・変更の方法

```bash
gh api repos/kota-kawa/fs-qr/branches/main/protection
gh api repos/kota-kawa/fs-qr/rulesets
gh api repos/kota-kawa/fs-qr/environments
```

必須チェックの追加・削除は GitHub の Settings → Branches → `main` から行い、変更後にこの表を
更新します。
