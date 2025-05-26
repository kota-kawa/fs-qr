# Note/note_api.py
from flask import Blueprint, request, jsonify
from datetime import datetime
from . import note_data as nd

api_bp = Blueprint('note_api', __name__, url_prefix='/api')

# ───────────────────────────────────────────────
@api_bp.route('/note/<room_id>', methods=['GET', 'POST'])
def note_sync(room_id):
    if request.method == 'GET':
        row = nd.get_row(room_id)
        if row["updated_at"] is None:
            return jsonify({"error": "room not found"}), 404
        return jsonify({
            "content": row["content"],
            "updated_at": row["updated_at"].isoformat(sep=' ', timespec='seconds')
        })

    # POST
    data = request.get_json(silent=True) or {}
    content = data.get('content', '')
    nd.save_content(room_id, content)
    row = nd.get_row(room_id)
    return jsonify({
        "status": "ok",
        "updated_at": row["updated_at"].isoformat(sep=' ', timespec='seconds')
    })
