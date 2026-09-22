# 並列作業と worktree の運用手順

worktree を分けるかどうかの判断基準は [AGENTS.md](../../AGENTS.md) にあります。ここでは分けた
後に壊れやすい点と、その回避手順だけを書きます。

## 作成と片付け

```bash
git worktree add ../fs-qr-<話題> -b <feature|fix|docs>/<内容> main
# 作業が終わり PR がマージされたら
git worktree remove ../fs-qr-<話題>
git branch -d <ブランチ>
```

Claude Code の Agent が作る worktree はリポジトリ直下の `.claude/worktrees/` 配下に置かれ、
`.gitignore` で除外されています。残ったものは `git worktree list` で確認して片付けます。

## 共有資源

- `.env` は git 管理外です。新しい worktree には存在しないため `python3 app.py` や
  `docker-compose up` は起動できません。起動が必要な作業は元の作業ツリーで行い、`.env` を
  コピーして別の場所へ増やさないでください。
- ポート: web-blue 5000、web-green 5030、Hocuspocus 1234（いずれも 127.0.0.1）。Compose の
  プロジェクト名はディレクトリ名から決まるため、別 worktree で `docker-compose up` すると
  別プロジェクトとして同じ host ポートを取り合い、volume も別名で新規作成されます。
  稼働させるスタックは常に 1 つにします。
- MySQL / Redis: Compose の `db` / `redis` はスタック内だけに公開され、host からは直接
  つなぎません。テストは `tests/conftest.py` が DB と Redis をモックするため、worktree 単位で
  独立して実行できます。
- 仮想環境: `.venv/` は worktree ごとに作り直すか、CI と同じ系列の `python3` を直接使います。
  Python 3.13 でも通る構文かは CI が検証します。
- `hocuspocus/node_modules/` は worktree ごとに `npm ci` が必要です。`package-lock.json` を
  変える作業は 1 つの worktree に限定します。

## 生成物の扱い

次のファイルは生成物で、並列作業で衝突しやすいものです。触る作業は 1 本に限定し、他の PR が
マージされたら rebase 後に再生成して差分を確認します。

| 生成物 | 生成コマンド | CI での検証 |
| --- | --- | --- |
| `locales/*/LC_MESSAGES/messages.po` | `python3 scripts/generate_babel_catalogs.py` | `--check` |
| `static/js/note_room_realtime/yjs-collaboration.js` | `hocuspocus/` で `npm run build:client` | `git diff --exit-code` |
| `alembic/versions/`（head） | 手書き。`down_revision` を head に合わせる | スキーマ整合性テスト |
| `db_init/create_tables.sql` | 手書き。migration と列順を揃える | スキーマ整合性テスト |

## 依存のある作業の順序

1. 先行 PR がマージされるまで、後続 PR は先行ブランチを base にせず `main` から切ります。
   先行の成果が必要なら、先行 PR のマージを待ってから rebase します。
2. rebase 後は生成物を再生成し、変更箇所のテストと Ruff を再実行します。
3. `main` へのマージは直前のマージの CI 完了を待ちます（`cancel-in-progress` により直前の
   コミットの検証が打ち切られるため）。
4. 並列作業中に他の作業への依存が判明したら、担当 worktree の外を触らず、止めてユーザーに報告
   します。
