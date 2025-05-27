# Note/note_api.py
from flask import Blueprint, request, jsonify
from datetime import datetime
from . import note_data as nd
import diff_match_patch as dmp_module # <--- 追加: diff-match-patchライブラリ

api_bp = Blueprint('note_api', __name__, url_prefix='/api')

# ───────────────────────────────────────────────
@api_bp.route('/note/<room_id>', methods=['GET', 'POST'])
def note_sync(room_id):
    if request.method == 'GET':
        row = nd.get_row(room_id)
        if row["updated_at"] is None: # get_rowが初期レコード作成するので基本的にはNoneにならないはず
            # 初期レコード作成に失敗した場合や、room_idが存在しないnote_roomを指している場合など
            return jsonify({"error": "room not found or not initialized"}), 404
        return jsonify({
            "content": row["content"],
            "updated_at": row["updated_at"].isoformat(sep=' ', timespec='seconds')
        })

    # POST
    data = request.get_json(silent=True) or {}
    client_content = data.get('content', '')
    client_last_known_updated_at = data.get('last_known_updated_at')
    client_original_content = data.get('original_content')

    if client_last_known_updated_at is None or client_original_content is None:
        # 必須パラメータ不足の場合はエラーまたはフォールバック
        # ここではひとまず従来通りの上書き保存（ただし推奨されない）
        nd.save_content(room_id, client_content)
        row = nd.get_row(room_id)
        return jsonify({
            "status": "ok_unconditional_fallback",
            "updated_at": row["updated_at"].isoformat(sep=' ', timespec='seconds'),
            "content": row["content"]
        })

    # 1. 条件付き更新を試みる
    rowcount = nd.save_content(room_id, client_content, client_last_known_updated_at)

    if rowcount > 0: # 更新成功 (競合なし)
        row = nd.get_row(room_id)
        return jsonify({
            "status": "ok",
            "updated_at": row["updated_at"].isoformat(sep=' ', timespec='seconds'),
            "content": row["content"] # 更新後の内容を返す
        })
    else: # 更新失敗 (競合発生)
        # 2. 競合解決のためマージを試みる
        current_db_row = nd.get_row(room_id)
        server_text = current_db_row["content"]
        server_timestamp = current_db_row["updated_at"].isoformat(sep=' ', timespec='seconds')

        dmp = dmp_module.diff_match_patch()
        # クライアントの変更点からパッチを作成
        patches = dmp.patch_make(client_original_content, client_content)
        # 現在のサーバーテキストにパッチを適用
        merged_text, patch_results = dmp.patch_apply(patches, server_text)

        if all(patch_results): # 全てのパッチが正常に適用された場合
            # 3. マージ結果を保存 (ここでも条件付き更新)
            #    マージベースとしたserver_timestampで条件更新
            merged_rowcount = nd.save_content(room_id, merged_text, server_timestamp)
            if merged_rowcount > 0:
                final_row = nd.get_row(room_id)
                return jsonify({
                    "status": "ok_merged",
                    "updated_at": final_row["updated_at"].isoformat(sep=' ', timespec='seconds'),
                    "content": final_row["content"]
                })
            else:
                # マージ処理中にもさらに別の更新が入った超レアケース
                final_row = nd.get_row(room_id) # 最新の状態を返す
                return jsonify({
                    "status": "conflict_during_merge_save",
                    "error": "Conflict occurred while saving merged content. Please review.",
                    "updated_at": final_row["updated_at"].isoformat(sep=' ', timespec='seconds'),
                    "content": final_row["content"]
                }), 409 # HTTP 409 Conflict
        else: # パッチ適用失敗 (マージ不可)
            final_row = nd.get_row(room_id) # 最新の状態を返す
            return jsonify({
                "status": "conflict_merge_failed",
                "error": "Automatic merge failed. Please review the latest content.",
                "updated_at": final_row["updated_at"].isoformat(sep=' ', timespec='seconds'),
                "content": final_row["content"]
            }), 409 # HTTP 409 Conflict
