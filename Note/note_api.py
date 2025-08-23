# Note/note_api.py
from flask import Blueprint, request, jsonify
from datetime import datetime
from . import note_data as nd
import diff_match_patch as dmp_module 
import time
import logging

# ログ設定
logger = logging.getLogger(__name__)

api_bp = Blueprint('note_api', __name__, url_prefix='/api')

# ここで最大文字数を定義（必要に応じて変更してください）
MAX_CONTENT_LENGTH = 5000  # 追加: 最大文字数を5000文字に設定
MAX_RETRY_ATTEMPTS = 3  # 最大リトライ回数

@api_bp.route('/note/<room_id>', methods=['GET', 'POST'])
def note_sync(room_id):
    if request.method == 'GET':
        try:
            row = nd.get_row(room_id)
            if row["updated_at"] is None:
                return jsonify({"error": "room not found or not initialized"}), 404
            return jsonify({
                "content": row["content"],
                "updated_at": row["updated_at"].isoformat(sep=' ', timespec='microseconds')
            })
        except Exception as e:
            logger.error(f"GET error for room {room_id}: {e}")
            return jsonify({"error": "Internal server error"}), 500

    # POST
    try:
        data = request.get_json(silent=True) or {}
        client_content = data.get('content', '')
        client_last_known_updated_at = data.get('last_known_updated_at')
        client_original_content = data.get('original_content')

        # 文字数チェック（サーバー側）
        if len(client_content) > MAX_CONTENT_LENGTH:
            return jsonify({
                "status": "error",
                "error": f"Content exceeds max length of {MAX_CONTENT_LENGTH} characters."
            }), 400

        # 必須パラメータチェック
        if client_last_known_updated_at is None or client_original_content is None:
            logger.warning(f"Missing required parameters for room {room_id}, using fallback")
            nd.save_content(room_id, client_content)
            row = nd.get_row(room_id)
            return jsonify({
                "status": "ok_unconditional_fallback",
                "updated_at": row["updated_at"].isoformat(sep=' ', timespec='microseconds'),
                "content": row["content"]
            })

        # リトライロジック付きの同期処理
        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                # 1. 条件付き更新を試みる
                rowcount = nd.save_content(room_id, client_content, client_last_known_updated_at)

                if rowcount > 0:  # 更新成功 (競合なし)
                    row = nd.get_row(room_id)
                    return jsonify({
                        "status": "ok",
                        "updated_at": row["updated_at"].isoformat(sep=' ', timespec='microseconds'),
                        "content": row["content"]
                    })
                else:  # 更新失敗 (競合発生) - マージを試みる
                    merge_result = attempt_merge(room_id, client_content, client_original_content)
                    if merge_result:
                        return merge_result
                    
                    # マージも失敗した場合、次のリトライへ
                    if attempt < MAX_RETRY_ATTEMPTS - 1:
                        time.sleep(0.1 * (attempt + 1))  # 指数バックオフ
                        continue
                    else:
                        # 最終的に失敗
                        final_row = nd.get_row(room_id)
                        return jsonify({
                            "status": "conflict_max_retries",
                            "error": "Unable to resolve conflict after multiple attempts. Please refresh and try again.",
                            "updated_at": final_row["updated_at"].isoformat(sep=' ', timespec='microseconds'),
                            "content": final_row["content"]
                        }), 409

            except Exception as e:
                logger.error(f"Error in sync attempt {attempt + 1} for room {room_id}: {e}")
                if attempt == MAX_RETRY_ATTEMPTS - 1:
                    raise

    except Exception as e:
        logger.error(f"Critical error in note_sync for room {room_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500

def attempt_merge(room_id, client_content, client_original_content):
    """マージ処理を試行する"""
    try:
        current_db_row = nd.get_row(room_id)
        server_text = current_db_row["content"]
        server_timestamp = current_db_row["updated_at"].isoformat(sep=' ', timespec='microseconds')

        dmp = dmp_module.diff_match_patch()
        # クライアントの変更点からパッチを作成
        patches = dmp.patch_make(client_original_content, client_content)
        # 現在のサーバーテキストにパッチを適用
        merged_text, patch_results = dmp.patch_apply(patches, server_text)

        if all(patch_results):  # 全てのパッチが正常に適用された場合
            # マージ結果を保存 (条件付き更新)
            merged_rowcount = nd.save_content(room_id, merged_text, server_timestamp)
            if merged_rowcount > 0:
                final_row = nd.get_row(room_id)
                return jsonify({
                    "status": "ok_merged",
                    "updated_at": final_row["updated_at"].isoformat(sep=' ', timespec='microseconds'),
                    "content": final_row["content"]
                })
            else:
                # マージ処理中にもさらに別の更新が入った場合
                logger.warning(f"Merge conflict during save for room {room_id}")
                return None  # リトライへ
        else:  # パッチ適用失敗 (マージ不可)
            final_row = nd.get_row(room_id)
            return jsonify({
                "status": "conflict_merge_failed",
                "error": "Automatic merge failed. Please review the latest content.",
                "updated_at": final_row["updated_at"].isoformat(sep=' ', timespec='microseconds'),
                "content": final_row["content"]
            }), 409
    except Exception as e:
        logger.error(f"Error in attempt_merge for room {room_id}: {e}")
        return None
