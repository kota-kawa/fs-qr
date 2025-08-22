from flask import Flask, redirect, request, jsonify, render_template, send_file, Blueprint, session, abort, flash
import uuid
import random
import os
import urllib
import zipfile
import io
from werkzeug.utils import secure_filename  # ファイル名を安全に扱うために追加
from dotenv import load_dotenv

#　自動削除用のモジュール
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

# 同じパッケージ内の group_data モジュールをインポート
from . import group_data

group_bp = Blueprint('group', __name__, template_folder='templates')

# .envファイルの読み込み
load_dotenv()

management_password = os.getenv("MANAGEMENT_PASSWORD")

# 一つ上のディレクトリを取得
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)  # 一つ上のディレクトリ
STATIC_DIR = os.path.join(PARENT_DIR, 'static')  # 一つ上のディレクトリの static フォルダ

# アップロード先フォルダ
UPLOAD_FOLDER = os.path.join(STATIC_DIR, 'group_uploads')

# ---------------------------
# 安全なディレクトリパスか確認するヘルパー関数
# ---------------------------
def is_safe_path(base_path, target_path):
    return os.path.commonprefix([os.path.abspath(target_path), os.path.abspath(base_path)]) == os.path.abspath(base_path)

# ---------------------------
# 古いルームを削除する関数
# ---------------------------
def delete_expired_rooms():
    # group_dataモジュール内の関数を呼び出して、古いルームを削除
    group_data.remove_expired_rooms()

# スケジューラをセットアップ（例：毎日1回実行）
scheduler = BackgroundScheduler()
scheduler.add_job(func=delete_expired_rooms, trigger="interval", days=1)
scheduler.start()

# アプリ終了時にスケジューラをシャットダウンするように登録
atexit.register(lambda: scheduler.shutdown())

# ---------------------------
# グループ画面のルート
# ---------------------------
@group_bp.route('/group')
def group():
    return render_template('group.html')

# ---------------------------
# 特定のルームIDのグループルーム画面を表示するルート
# ---------------------------
@group_bp.route('/group_room/<room_id>')
def group_list(room_id):
    # まずデータを取得
    room_data = group_data.get_data(room_id)
    # 見つからなければ 404 を返す
    if not room_data:
        abort(404)
    # レコードがあれば通常どおり処理
    record = room_data[0]
    user_id = record.get('id', '不明')
    password = record.get('password', '不明')
    # センシティブ情報はログに出力しないよう注意
    print(f"Room ID: {room_id}")
    return render_template(
        'group_room.html',
        room_id=room_id,
        user_id=user_id,
        password=password
    )

# ---------------------------
# ルーム作成画面のルート
# ---------------------------
@group_bp.route('/create_room')
def create_room():
    return render_template('create_group_room.html')

# ---------------------------
# 新規グループルームの作成処理（POSTリクエスト）
# ---------------------------
@group_bp.route('/create_group_room', methods=['POST'])
def create_group_room():
    """
    フォームからの入力を元に新しいルームを作成する。
    10文字のランダムなユニークIDと、6桁のランダムなパスワードを生成する。
    入力されたIDが英数字でなければエラーを返す。
    作成したルームIDのフォルダをセキュアな方法で生成し、group_dataモジュールにルーム情報を保存する。
    その後、作成されたルームのページへリダイレクトする。
    """
    uid = str(uuid.uuid4())[:10]  # ランダムな10文字のユニークIDを生成
    id = request.form.get('id', '名無し')  # フォームからIDを取得
    if not id.isalnum():  # IDを安全な文字列のみ許可
        return jsonify({"error": "IDに無効な文字が含まれています。"}), 400
    if len(id) < 5 or len(id) > 10:  # IDの長さチェック
        return jsonify({"error": "IDは5文字以上10文字以下で入力してください。"}), 400
    password = str(random.randrange(10**5, 10**6))  # 6桁のランダムパスワード
    room_id = f"{id}-{uid}"
    print(f"Room ID Created: {room_id}")

    # セキュアなパスでフォルダ作成
    folder_path = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
    os.makedirs(folder_path, exist_ok=True)

    group_data.create_room(id=id, password=password, room_id=room_id)
    return redirect(f'/group_room/{room_id}')

# ---------------------------
# グループアップロード処理（ファイルアップロード）
# ---------------------------
@group_bp.route('/group_upload/<room_id>', methods=['POST'])
def group_upload(room_id):
    """
    指定されたルームIDに対して、アップロードされたファイルを保存する。
    ルームが存在しなければエラーを返す。
    アップロードされた各ファイルについて、ファイル名の安全性を確保し、サイズが0バイトのファイルは削除する。
    エラーが発生したファイルはエラーレスポンスとして返す。
    """
    room_data = group_data.get_data(room_id)
    if not room_data:
        return jsonify({"error": "無効なルームIDです。"}), 400

    uploaded_files = request.files.getlist('upfile')
    if not uploaded_files:
        return jsonify({"error": "ファイルがアップロードされていません。"}), 400

    # ファイル数制限チェック
    if len(uploaded_files) > 10:
        return jsonify({"error": "ファイル数は最大10個までです。"}), 400

    # ファイルサイズ制限チェック (50MB = 50 * 1024 * 1024 bytes)
    total_size = 0
    MAX_TOTAL_SIZE = 50 * 1024 * 1024  # 50MB
    
    for file in uploaded_files:
        if file.filename:
            # ファイルの内容を読んでサイズを計算
            file.seek(0, 2)  # ファイルの末尾に移動
            file_size = file.tell()  # 現在位置（=ファイルサイズ）を取得
            file.seek(0)  # ファイルの先頭に戻す
            total_size += file_size
    
    if total_size > MAX_TOTAL_SIZE:
        return jsonify({"error": "ファイルの合計サイズは50MBまでです。"}), 400

    error_files = []
    save_path = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
    os.makedirs(save_path, exist_ok=True)

    for file in uploaded_files:
        if file.filename == '':
            continue
        file.filename = secure_filename(file.filename)
        file_path = os.path.join(save_path, file.filename)

        try:
            file.save(file_path)
            # ファイルサイズチェック
            if os.path.getsize(file_path) == 0:
                error_files.append(file.filename)
                os.remove(file_path)
        except Exception as e:
            error_files.append(file.filename)

    if error_files:
        return jsonify({
            "status": "error",
            "message": "以下のファイルが保存できませんでした。",
            "files": error_files
        }), 500

    return jsonify({"status": "success", "message": "ファイルが正常にアップロードされました。"})

# ---------------------------
# ルーム内のファイル一覧を取得するルート
# ---------------------------
@group_bp.route("/check/<room_id>")
def list_files(room_id):
    """
    指定されたルームIDに対応するフォルダ内の全ファイルの名前をJSON形式で返す。
    フォルダが存在しなかったり、不正なパスの場合はエラーを返す。
    """
    target_directory = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
    if not os.path.exists(target_directory):
        return jsonify({"error": "ルームIDのディレクトリが見つかりません。"}), 404

    if not is_safe_path(UPLOAD_FOLDER, target_directory):
        return jsonify({"error": "不正なパスが検出されました。"}), 400

    try:
        files = [{"name": file_name} for file_name in os.listdir(target_directory) if os.path.isfile(os.path.join(target_directory, file_name))]
        return jsonify(files)
    except Exception as e:
        return jsonify({"error": f"エラー: {str(e)}"}), 500

# ---------------------------
# ルーム内のすべてのファイルをZIP圧縮してダウンロードするルート
# ---------------------------
@group_bp.route('/download/all/<room_id>', methods=['GET'])
def download_all_files(room_id):
    """
    指定されたルームIDのフォルダ内のすべてのファイルをZIPファイルにまとめ、
    バイトストリームとしてクライアントに送信する。
    フォルダが存在しなければエラーを返す。
    """
    room_folder = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
    if not os.path.exists(room_folder):
        return jsonify({"error": "指定されたルームIDのファイルが見つかりません。"}), 404

    try:
        zip_stream = io.BytesIO()
        with zipfile.ZipFile(zip_stream, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for filename in os.listdir(room_folder):
                file_path = os.path.join(room_folder, filename)
                if os.path.isfile(file_path) and is_safe_path(room_folder, file_path):
                    with open(file_path, 'rb') as f:
                        zipf.writestr(filename, f.read())
        zip_stream.seek(0)
        return send_file(zip_stream, mimetype='application/zip', as_attachment=True, download_name=f'{room_id}_files.zip')
    except Exception as e:
        return jsonify({"error": f"エラー: {str(e)}"}), 500

# ---------------------------
# 単一ファイルをダウンロードするルート
# ---------------------------
@group_bp.route('/download/<room_id>/<path:filename>', methods=['GET'])
def download_file(room_id, filename):
    """
    指定されたルームIDとファイル名に対して、ファイルを安全な形式に変換した上で、
    ダウンロードできるように送信する。パスの安全性もチェックする。
    """
    decoded_filename = secure_filename(urllib.parse.unquote(filename))
    room_folder = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
    file_path = os.path.join(room_folder, decoded_filename)

    if not is_safe_path(room_folder, file_path):
        return jsonify({"error": "不正なパスが検出されました。"}), 400

    try:
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({"error": "ファイルが見つかりません。"}), 404
    except Exception as e:
        return jsonify({"error": f"エラー: {str(e)}"}), 500

# ---------------------------
# ファイルを削除するルート
# ---------------------------
@group_bp.route('/delete/<room_id>/<filename>', methods=['DELETE'])
def delete_file(room_id, filename):
    """
    指定されたルームIDとファイル名に対応するファイルを削除する。
    削除前にパスの安全性を確認し、ファイルが存在しなければエラーを返す。
    """
    decoded_filename = secure_filename(urllib.parse.unquote(filename))
    room_folder = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
    file_path = os.path.join(room_folder, decoded_filename)

    if not is_safe_path(room_folder, file_path):
        return jsonify({"error": "不正なパスが検出されました。"}), 400

    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({"message": "ファイルが削除されました。"}), 200
        else:
            return jsonify({"error": "ファイルが見つかりません。"}), 404
    except Exception as e:
        return jsonify({"error": f"エラー: {str(e)}"}), 500

# ---------------------------
# ルーム検索画面のルート
# ---------------------------
@group_bp.route('/search_room')
def search_room_page():
    return render_template('search_room.html')

# ---------------------------
# ルーム検索処理（POSTリクエスト）
# ---------------------------
@group_bp.route('/search_room_process', methods=['POST'])
def search_room():
    """
    フォームから送信されたIDとパスワードを用いてルームを検索する。
    入力値の検証を行い、該当するルームIDが見つかればそのルームページへリダイレクトする。
    入力値に不正な値がある場合やルームが見つからなかった場合はエラーメッセージを返す。
    """
    id = request.form.get('id', '').strip()
    password = request.form.get('password', '').strip()

    if not id.isalnum() or not password.isdigit():  # 入力検証
        return jsonify({"error": "IDまたはパスワードに不正な値が含まれています。"}), 400

    room_id = group_data.pich_room_id(id, password)
    if not room_id:
        return room_msg('IDかパスワードが間違っています')
    return redirect(f'/group_room/{room_id}')

# ---------------------------
# エラーメッセージを表示するための補助関数
# ---------------------------
def room_msg(s):
    return render_template('error.html', message=s)


# ---------------------------
# ルーム管理用のルート（ルーム一覧の表示、ルーム削除等）
# ---------------------------
@group_bp.route('/manage_rooms', methods=['GET', 'POST'])
def manage_rooms():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == management_password:
            session['management_authenticated'] = True
        else:
            flash('パスワードが違います。')
            return render_template('manage_rooms_login.html')
    if not session.get('management_authenticated'):
        return render_template('manage_rooms_login.html')
    
    # 認証済みの場合、ルーム一覧を表示
    rooms = group_data.get_all()
    return render_template('manage_rooms.html', rooms=rooms)

# ---------------------------
# 管理者ログアウト用のルート
# ---------------------------
@group_bp.route('/logout_management')
def logout_management():
    session.pop('management_authenticated', None)
    return redirect('/manage_rooms')

# ---------------------------
# 特定ルームの削除処理
# ---------------------------
@group_bp.route('/delete_room/<room_id>', methods=['POST'])
def delete_room(room_id):
    # 指定ルームの削除処理（DB削除と対応ファイルの削除）
    group_data.remove_data(room_id)
    return redirect('/manage_rooms')

# ---------------------------
# 全ルームを削除する処理
# ---------------------------
@group_bp.route('/delete_all_rooms', methods=['POST'])
def delete_all_rooms():
    # 全ルームを削除する処理
    group_data.all_remove()
    return redirect('/manage_rooms')