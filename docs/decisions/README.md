# 技術判断（Decision Records）

ここには、現在の構成を拘束する重要な判断と、その理由・トレードオフを短く残します。
実装の詳細な説明は [ARCHITECTURE.md](../../ARCHITECTURE.md)、具体的な運用手順は
既存の運用文書を参照してください。

## 一覧

- [ADR-0001: 起動時 Alembic migration](0001-startup-alembic-migrations.md)
- [ADR-0002: Blue-Green と共有インフラ](0002-blue-green-deployment.md)
- [ADR-0003: Note realtime の Redis pub/sub](0003-note-realtime-redis-pubsub.md)
- [ADR-0004: FSQR のブラウザ側暗号化](0004-browser-side-fsqr-encryption.md)
- [ADR-0005: Group realtime の Redis pub/sub](0005-group-realtime-redis-pubsub.md)

## 追加ルール

新しい ADR は `NNNN-kebab-case.md` とし、少なくとも「状態」「背景」「判断」「理由」「影響」
を含めます。作業ログや一時的な workaround は ADR にしません。既存判断を覆す場合は、
旧 ADR を書き換えず、新しい ADR から supersede 先を示します。
