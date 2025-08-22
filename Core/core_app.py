from flask import Blueprint, render_template, request, send_file, jsonify, redirect, url_for, abort
import os
import uuid
import secrets
import re
import fs_data
from werkzeug.utils import secure_filename

core_bp = Blueprint('core', __name__, template_folder='templates')

# Base configuration (same as in app.py)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # Parent directory (app.py location)
STATIC = os.path.join(BASE_DIR, 'static', 'upload')
# Ensure the upload directory exists to avoid FileNotFoundError
os.makedirs(STATIC, exist_ok=True)

@core_bp.route('/fs-qr')
def fs_qr():
    return render_template('fs-qr.html')

@core_bp.route('/fs-qr-upload')
def fs_qr_upload():
    return render_template('fs-qr-upload.html')

@core_bp.route('/upload', methods=['POST'])
def upload():
    # よりセキュアな乱数の生成
    uid = str(uuid.uuid4())[:10]  # ランダムな10文字のユニークID
    id = request.form.get('name', '名無し')
    
    # idの検証（半角英数字のみ許可）
    if not id or not id.replace(' ', '').replace('\t', '').replace('\n', ''):
        return json_or_msg('IDを入力してください。')
    if not re.match(r'^[a-zA-Z0-9]+$', id):
        return json_or_msg('IDに無効な文字が含まれています。半角英数字のみ使用してください。')
    if len(id) < 5 or len(id) > 10:
        return json_or_msg('IDは5文字以上10文字以下で入力してください。')
    
    # 6桁のパスワードをsecretsで生成（数字のみの場合はsecrets.randbelow等）
    password = str(secrets.randbelow(10**6)).zfill(6)

    # secure_idに不必要な文字が混入しないよう明示的に整形
    # filenameからは別途secure_filenameを利用するためここではidとuidのみ結合
    secure_id_base = f"{id}-{uid}-"

    upfiles = request.files.getlist('upfile')
    if not upfiles:
        return json_or_msg('アップロード失敗')

    # ファイル数制限チェック
    if len(upfiles) > 10:
        return json_or_msg('ファイル数は最大10個までです')

    # ファイルサイズ制限チェック (50MB = 50 * 1024 * 1024 bytes)
    total_size = 0
    MAX_TOTAL_SIZE = 50 * 1024 * 1024  # 50MB
    
    for file in upfiles:
        if file.filename:
            # ファイルの内容を読んでサイズを計算
            file.seek(0, 2)  # ファイルの末尾に移動
            file_size = file.tell()  # 現在位置（=ファイルサイズ）を取得
            file.seek(0)  # ファイルの先頭に戻す
            total_size += file_size
    
    if total_size > MAX_TOTAL_SIZE:
        return json_or_msg('ファイルの合計サイズは50MBまでです')

    # ファイルパス生成用リスト
    uploaded_files = []

    for file in upfiles:
        filename = secure_filename(file.filename)  # ファイル名をサニタイズ
        if not filename:
            return json_or_msg('不正なファイル名です')
        
        save_path = os.path.join(STATIC, secure_id_base + filename)
        file.save(save_path)
        uploaded_files.append(filename)

    # 最終的なsecure_idは全ファイル名を元にするが、zip処理が前提なら一貫したルールで
    # '.'の除去などは行わないが、相対パス排除はsecure_filenameに任せている。
    secure_id = (secure_id_base + uploaded_files[-1]).replace('.zip', '')

    fs_data.save_file(uid=uid, id=id, password=password, secure_id=secure_id)

        # ここでは JSON でリダイレクト先を返す
    return jsonify({
        "redirect_url": url_for('core.upload_complete', secure_id=secure_id)
    })

@core_bp.route('/upload_complete/<secure_id>')
def upload_complete(secure_id):
    data = fs_data.get_data(secure_id)
    if not data:
        abort(404)
    # 存在するなら従来どおり
    row = data[0]
    id_val = row["id"]
    password_val = row["password"]

    return render_template(
        'info.html',
        id=id_val,
        password=password_val,
        secure_id=secure_id,
        mode='upload',
        url=url_for('core.download', secure_id=secure_id, _external=True)
    )

@core_bp.route('/download/<secure_id>')
def download(secure_id):
    data = fs_data.get_data(secure_id)
    if not data:
        abort(404)
    id_val = data[0]["id"]

    return render_template(
        'info.html',
        data=data,
        mode='download',
        id=id_val,
        secure_id=secure_id,
        url=url_for('core.download_go', secure_id=secure_id)
    )

@core_bp.route('/download_go/<secure_id>', methods=['POST'])
def download_go(secure_id):
    data = fs_data.get_data(secure_id)
    if not data:
        return msg('パラメータが不正です')
    
    # パス操作をos.path.joinで実施
    path = os.path.join(STATIC, secure_id + '.zip')

    # ファイルが存在するかチェック
    if not os.path.exists(path):
        return msg('ファイルが存在しません')

    return send_file(path, download_name=secure_id+'.zip', as_attachment=False)

@core_bp.route('/kensaku')
def kensaku():
    return render_template('kensaku-form.html')

@core_bp.route('/try_login', methods=['POST'])
def kekka():
    id = request.form.get('name', '').strip()
    password = request.form.get('pw', '').strip()
    
    # 入力検証（半角英数字のみ許可）
    if not re.match(r'^[a-zA-Z0-9]+$', id) or not re.match(r'^[0-9]+$', password):
        return msg('IDまたはパスワードに不正な文字が含まれています。')

    secure_id = fs_data.try_login(id, password)

    if not secure_id:
        return msg('IDかパスワードが間違っています')

    return redirect(url_for('core.download', secure_id=secure_id))

@core_bp.route('/remove-succes')
def after_remove():
    return render_template('after-remove.html')

def msg(s):
    return render_template('error.html', message=s)

def json_or_msg(message, status_code=400):
    """Return JSON error for AJAX requests, HTML for regular requests"""
    if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded' and \
       request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"error": message}), status_code
    # For multipart/form-data requests from XMLHttpRequest, also return JSON
    if 'multipart/form-data' in request.headers.get('Content-Type', ''):
        return jsonify({"error": message}), status_code
    return msg(message)