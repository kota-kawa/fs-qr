# ADR-0001: 起動時に Alembic migration を適用する

- 状態: 採用
- 対象: `migration_runner.py`、`alembic/`、`app.py`

## 背景

web コンテナは Blue-Green で一時的に複数世代が存在し、新しいコードが必要とする
スキーマをアプリ起動前に適用する必要があります。一方、複数コンテナが同時に migration
を実行すると競合します。

## 判断

アプリ startup で `alembic upgrade head` を実行し、MySQL の `GET_LOCK` で migration を
排他します。空の Docker volume の初期作成だけは `db_init/create_tables.sql` に任せ、
既存環境の差分は `alembic/versions/` で管理します。

## 理由

- web と schema の更新を同じ deploy に含められる。
- DB ロックにより複数 web の同時起動でも upgrade を一つにできる。
- revision 履歴から既存環境の適用順を追跡できる。

## 影響

- migration は旧コードと新コードの共存を壊さない expand/contract で作る必要がある。
- 起動時に DB が利用できないと、既定では web が healthy にならない。
- 破壊的な schema change は追加と削除を別デプロイに分ける。
