# 再利用可能な知識

ここには、複数回の作業で役立つ失敗パターン、診断の入口、実装上の注意だけを置きます。
単発の作業ログ、個人環境の値、未確認の仮説は保存しません。

## 文書一覧

- [開発規約](development_conventions.md): プロジェクト構成、コマンド、スキーマ同期、実装規約、命名、責務分割、テスト方針、サブエージェントの指定。コード変更の前に読む。
- [デバッグと検証の入口](debugging.md): 起動、DB、Redis、アップロード、デプロイ、テストの切り分け。
- [API 契約とマイグレーションの注意点](contracts-and-migrations.md): 変えてはいけない境界、migration の作り方、Blue-Green での制約、過去の事故。
- [並列作業と worktree の運用手順](parallel_work.md): 共有資源、生成物、依存のある作業の順序。
- [フロントエンドの実描画確認](frontend_visual_verification.md): Playwright での確認手順、ビューポート、観点、PR への記載。
- [繰り返した回帰と再発防止](recurring_regressions.md): git 履歴から抽出した回帰の型と防止策。
- [リアルタイム機能の運用知識](realtime.md): Note / Group の接続モデル、認証、同期、障害時の確認点。
- [サービス共通コンポーネント](shared-service-components.md): ルーム処理、共有 UI、LP、互換層の構成と拡張ルール。
- 翻訳カタログの構造と検証は、重複を避けるため [locales/README.md](../../locales/README.md) を正とする。

新しい知見を追加する前に、既存の `ARCHITECTURE.md`、`spec.md`、`locales/README.md`、
既存の運用文書に同じ内容がないか確認します。内容が設計の採否と理由なら
`docs/decisions/`、手順そのものなら既存の運用文書を更新します。文書を追加・削除したら
`AGENTS.md` の「ドキュメントの参照先」とこの一覧を同じコミットで更新し、
`python3 scripts/check_doc_paths.py` でパス参照を確認します。
