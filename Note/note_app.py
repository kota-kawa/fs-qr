import uuid, random
from flask import Blueprint, render_template, flash, redirect, request, jsonify
from . import note_data as nd

note_bp = Blueprint('note', __name__, template_folder='templates')

# ルートメニュー
@note_bp.route('/note')
def note_menu():
    return render_template('note_menu.html')      # 別途用意済み

# ルーム作成フォーム
@note_bp.route('/create_note_room')
def create_note_room_page():
    return render_template('create_note_room.html')

# ルーム作成処理
@note_bp.route('/create_note_room', methods=['POST'])
def create_note_room():
    uid = str(uuid.uuid4())[:10]
    id_ = request.form.get('id', '名無し')
    if not id_.isalnum():
        return jsonify({'error': 'IDに無効な文字'}), 400
    pw = str(random.randrange(10**5, 10**6))
    room_id = f"{id_}-{uid}"
    nd.create_room(id_, pw, room_id)
    return redirect(f'/note_room/{room_id}')

# ルーム本体
@note_bp.route('/note_room/<room_id>')
def note_room(room_id):
    row = nd.get_row(room_id)
    if row["updated_at"] is None:
        return jsonify({'error': 'room not found'}), 404
    # ID / パスワード取得
    meta = nd._exec("SELECT id,password FROM note_room WHERE room_id=:r",
                    {"r":room_id}, fetch=True)[0]
    return render_template('note_room.html',
                           room_id=room_id,
                           user_id=meta["id"],
                           password=meta["password"])

# --- 検索ページ表示 -----------------------------------
@note_bp.route('/search_note_room')
def search_note_room_page():
    return render_template('search_note_room.html')

# --- 検索処理 -----------------------------------------
@note_bp.route('/search_note_room_process', methods=['POST'])
def search_note_room():
    id_  = request.form.get('id','').strip()
    pw   = request.form.get('password','').strip()
    if not id_.isalnum() or not pw.isdigit():
        flash("ID またはパスワードが不正です。")
        return redirect('/search_note_room')
    room_id = nd.pich_room_id(id_, pw)
    if not room_id:
        flash("ID かパスワードが間違っています。")
        return redirect('/search_note_room')
    return redirect(f'/note_room/{room_id}')