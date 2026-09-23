# ADR-0008: ドメイン設計を軽量に保ち、CQRS と Event Sourcing を採用しない

- 状態: 採用
- 日付: 2026-09-23
- 対象: `docs/knowledge/domain_model.md`、`docs/knowledge/development_conventions.md`

## 背景

要件定義とドメイン駆動設計の考え方（境界づけられたコンテキスト、Entity / Value Object、
レイヤー分離、CQRS、Event Sourcing）をガイドラインへ取り込むにあたり、どこまでをこの
リポジトリに適用するかを決める必要がある。FS!QR の 4 サービスは一時的な共有を提供し、共有した
内容（ファイル、ノート本文、タスク）は保存期間が過ぎると自動削除される。データ層は raw SQL の
関数群（`*_data.py`）で構成され、入力の検証は route が `models.py` の Pydantic モデルで行う。
FSQR / Group / Note / Task のパッケージどうしは互いを import せず、複数サービスをまたぐ処理
（`top_search.py`、`Admin/`、`scheduler.py`）が各サービスのモジュールを呼び出す形になっている。

## 判断

- 境界づけは既存のサービスパッケージ（FSQR / Group / Note / Task / Admin / Articles）と、
  4 サービス共通の `room_*.py` で表す。FSQR / Group / Note / Task のパッケージどうしの import は
  追加しない。
- 業務ルールは data 層、認可モジュール、`models.py` に集約する。Entity / Value Object /
  Repository のクラス階層は導入しない。
- 読み取り専用モデルを分ける CQRS は採用しない。
- Event Sourcing は採用しない。ルームの履歴は `status` と `deleted_at` の tombstone と
  アプリケーションログで扱う。

## 理由

- 読み取り（ルーム画面、Admin の一覧と件数、トップの横断検索）は書き込みと同じテーブルへの
  単純なクエリで足りており、別モデルを同期し続けるコストに見合わない。
- 保存期間が過ぎたら共有した内容を消すことがサービスの価値であり、すべての変更イベントを保持して状態を
  再現する設計はこれと衝突する。
- 関数ベースのデータ層の上にクラス階層を重ねると二重構造になり、`AGENTS.md` が禁じる過剰な
  抽象化にあたる。値の検証を `models.py` に 1 か所で定義すれば、Value Object で得たい効果
  （検証の重複を防ぐこと）は得られる。

## 影響

- 新しい読み取り要求は、まず既存テーブルへのクエリと `cache_utils.py` のキャッシュで足りるかを
  確認する。
- 次のいずれかが起きたら、新しい ADR で見直す: 監査のために操作履歴の完全な再現が求められる、
  集計・分析の読み取り負荷が書き込み側のテーブルやインデックスの設計を歪める、サービスの
  パッケージ間で同じ業務ルールの重複が `room_*.py` へ寄せられない形で増える。
