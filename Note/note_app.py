import uuid, random, re
from flask import Blueprint, render_template, flash, redirect, request, jsonify, abort, session
from . import note_data as nd
from apscheduler.schedulers.background import BackgroundScheduler

# スケジューラ：古いノートルームを毎日自動削除
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=nd.remove_expired_rooms,
    trigger='interval',
    days=1,
    id='remove_expired_note_rooms'
)
scheduler.start()
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
    if not re.match(r'^[a-zA-Z0-9]+$', id_):
        return jsonify({'error': 'IDに無効な文字が含まれています。半角英数字のみ使用してください。'}), 400
    if len(id_) < 5 or len(id_) > 10:
        return jsonify({'error': 'IDは5文字以上10文字以下で入力してください'}), 400
    pw = str(random.randrange(10**5, 10**6))
    room_id = f"{id_}-{uid}"
    nd.create_room(id_, pw, room_id)
    session['room_id'] = room_id
    return redirect('/note_room')

# ルーム本体
@note_bp.route('/note_room')
def note_room():
    # セッションからroom_idを取得
    room_id = session.get('room_id')
    if not room_id:
        abort(404)
    
    # note_room テーブルからユーザー情報を取得して存在チェック
    rows = nd._exec(
        "SELECT id, password FROM note_room WHERE room_id = :r",
        {"r": room_id},
        fetch=True
    )
    if not rows:
        abort(404)
    meta = rows[0]

    # note_content テーブルからコンテンツを取得（なければ初期レコード作成）
    content_row = nd.get_row(room_id)

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
    if not re.match(r'^[a-zA-Z0-9]+$', id_) or not re.match(r'^[0-9]+$', pw):
        flash("ID またはパスワードが不正です。")
        return redirect('/search_note_room')
    room_id = nd.pich_room_id(id_, pw)
    if not room_id:
        flash("ID かパスワードが間違っています。")
        return redirect('/search_note_room')
    session['room_id'] = room_id
    return redirect('/note_room')