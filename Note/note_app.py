import random, re
from datetime import timedelta
from flask import Blueprint, render_template, flash, redirect, request, jsonify, url_for
from . import note_data as nd
from rate_limit import (
    SCOPE_NOTE,
    check_rate_limit,
    get_block_message,
    get_client_ip,
    register_failure,
    register_success,
)

note_bp = Blueprint('note', __name__, template_folder='templates')

# クエリのない正規URLへリダイレクト
def _canonical_redirect():
    if request.query_string:
        return redirect(request.base_url, code=301)
    return None

# ルーム情報取得ヘルパー
def _get_room_if_valid(room_id, password):
    meta = nd.get_room_meta(room_id, password=password)
    if not meta:
        return None
    # コンテンツが存在しない場合は初期化
    nd.get_row(room_id)
    return meta

# ルートメニュー
@note_bp.route('/note_menu')
def note_menu():
    canonical = _canonical_redirect()
    if canonical:
        return canonical
    return render_template('note_menu.html')      # 別途用意済み

# ルーム作成フォーム
@note_bp.route('/create_note_room')
def create_note_room_page():
    return render_template('create_note_room.html')

# ルーム作成処理
@note_bp.route('/create_note_room', methods=['POST'])
def create_note_room():
    json_data = request.get_json(silent=True) or {}

    # フォームに複数のidフィールドが存在する場合を考慮して最初の空でない値を使用
    id_candidates = request.form.getlist('id')
    if not id_candidates:
        id_candidates = [json_data.get('id', '')]
    id_ = next((v.strip() for v in id_candidates if v.strip()), '')
    id_mode = request.form.get('idMode') or json_data.get('idMode', 'auto')  # ID生成モードを取得

    retention_value = request.form.get('retention_days')
    if retention_value is None:
        retention_value = json_data.get('retention_days', 7)
    try:
        retention_days = int(retention_value)
    except (TypeError, ValueError):
        retention_days = 7

    if retention_days not in (1, 7, 30):
        retention_days = 7

    # IDが提供されていない場合はエラーを返す
    if not id_:
        return jsonify({'error': 'IDが指定されていません。'}), 400
    
    # ID検証
    if not re.match(r'^[a-zA-Z0-9]+$', id_):
        return jsonify({'error': 'IDに無効な文字が含まれています。半角英数字のみ使用してください。'}), 400
    if len(id_) != 6:
        return jsonify({'error': 'IDは6文字の半角英数字で入力してください'}), 400
    
    # room_idの重複チェック
    room_id = id_
    existing_room = nd._exec(
        "SELECT room_id FROM note_room WHERE room_id = :r",
        {"r": room_id},
        fetch=True
    )
    
    if existing_room:
        if id_mode == 'auto':
            # 自動生成モードの場合はフロントエンドに新しいIDの生成を促す
            return jsonify({'error': '生成されたIDが重複しています。新しいIDで再試行してください。', 'retry_auto': True}), 409
        else:
            # 手動入力モードの場合はエラーを返す
            return jsonify({'error': 'このIDは既に使用されています。別のIDを使用してください。'}), 409
    
    pw = str(random.randrange(10**5, 10**6))
    nd.create_room(room_id, pw, room_id, retention_days=retention_days)
    return redirect(url_for('note.note_room', room_id=room_id, password=pw))

# ルームアクセスページ
@note_bp.route('/note')
def note_room_access():
    canonical = _canonical_redirect()
    if canonical:
        return canonical
    return render_template('note_room_access.html')


# ルーム本体
@note_bp.route('/note/<room_id>/<password>')
def note_room(room_id, password):
    ip = get_client_ip()
    allowed, _, block_label = check_rate_limit(SCOPE_NOTE, ip)
    if not allowed:
        return render_template('error.html', message=get_block_message(block_label)), 429

    meta = _get_room_if_valid(room_id, password)
    if not meta:
        _, block_label = register_failure(SCOPE_NOTE, ip)
        if block_label:
            return render_template('error.html', message=get_block_message(block_label)), 429
        return render_template('error.html', message='指定されたルームが見つからないか、パスワードが間違っています'), 404

    register_success(SCOPE_NOTE, ip)

    retention_days = meta.get("retention_days", 7)
    created_at = meta.get("time")
    deletion_date = None
    if created_at:
        try:
            deletion_date = (created_at + timedelta(days=retention_days)).strftime('%Y-%m-%d %H:%M')
        except Exception:
            deletion_date = None

    return render_template('note_room.html',
                           room_id=room_id,
                           user_id=meta["id"],
                           password=password,
                           retention_days=retention_days,
                           deletion_date=deletion_date)

# --- 検索ページ表示 -----------------------------------
@note_bp.route('/search_note')
def search_note_room_page():
    return render_template('search_note_room.html')

# --- 検索処理 -----------------------------------------
@note_bp.route('/search_note_process', methods=['POST'])
def search_note_room():
    id_  = request.form.get('id','').strip()
    pw   = request.form.get('password','').strip()
    ip = get_client_ip()
    allowed, _, block_label = check_rate_limit(SCOPE_NOTE, ip)
    if not allowed:
        flash(get_block_message(block_label))
        return redirect('/search_note')
    if not re.match(r'^[a-zA-Z0-9]+$', id_) or not re.match(r'^[0-9]+$', pw):
        _, block_label = register_failure(SCOPE_NOTE, ip)
        if block_label:
            flash(get_block_message(block_label))
        else:
            flash("ID またはパスワードが不正です。")
        return redirect('/search_note')
    room_id = nd.pich_room_id(id_, pw)
    if not room_id:
        _, block_label = register_failure(SCOPE_NOTE, ip)
        if block_label:
            flash(get_block_message(block_label))
        else:
            flash("ID かパスワードが間違っています。")
        return redirect('/search_note')
    register_success(SCOPE_NOTE, ip)
    return redirect(url_for('note.note_room', room_id=room_id, password=pw))

# ---------------------------
# QRコード用の直接アクセスルート
# ---------------------------
@note_bp.route('/note_direct/<room_id>/<password>')
def note_direct_access(room_id, password):
    """
    QRコード用の直接アクセス。room_idとpasswordでルームの存在を確認し、
    対応するルームURLにリダイレクトする。
    """
    ip = get_client_ip()
    allowed, _, block_label = check_rate_limit(SCOPE_NOTE, ip)
    if not allowed:
        return render_template('error.html', message=get_block_message(block_label)), 429

    meta = _get_room_if_valid(room_id, password)
    if not meta:
        _, block_label = register_failure(SCOPE_NOTE, ip)
        if block_label:
            return render_template('error.html', message=get_block_message(block_label)), 429
        return render_template('error.html', message='指定されたルームが見つからないか、パスワードが間違っています'), 404

    register_success(SCOPE_NOTE, ip)

    return redirect(url_for('note.note_room', room_id=room_id, password=password))
