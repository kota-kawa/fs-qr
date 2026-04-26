# Project Specifications & Guidelines

## 全体ルール (General Rules)
<!-- プロジェクト全体で遵守すべき原則 -->
- 画面上の主要ラベルは日本語に統一する。`Room ID` は「ルームID」、`Password` は「パスワード」、`Create Room` は「ルームを作成」と表記する。

## コーディング規約 (Coding Conventions)
<!-- 言語ごとのスタイルガイド、フォーマッター設定など -->
- **Python**:
  - 
- **JavaScript/React**:
  - 

## 命名規則 (Naming Conventions)
<!-- 変数、関数、クラス、ファイル名の命名ルール -->
- **Variables/Functions**: 
- **Classes**: 
- **Files**: 
- **Constants**: 

## ディレクトリ構成方針 (Directory Structure Policy)
<!-- ファイルの配置ルール、モジュール分割の方針 -->
- 

## エラーハンドリング方針 (Error Handling Policy)
<!-- 例外処理、ログ出力、ユーザーへのフィードバック方法 -->
- 破壊的操作（削除など）は `showConfirmModal()` を使い、操作内容と取り消せない可能性を明示する。
- 入力値エラーやアップロード制限は、対象フォーム内の `role="alert"` / `aria-live` 付きインライン領域へ表示する。
- 処理完了・通信失敗など画面全体の通知は `showAlertModal()` または `role="status"` のステータス領域へ集約する。
- ブラウザ標準の `alert()` / `confirm()` は、共通モーダルが初期化できない場合のフォールバックに限定する。
- サイズ・件数などの文言は「上限はNです。現在はMです。」の形にそろえ、括弧書きの揺れを避ける。

## テスト方針 (Testing Policy)
<!-- テストの種類、カバレッジ目標、使用ツール -->
- **Unit Tests**: 
- **E2E Tests**: 
