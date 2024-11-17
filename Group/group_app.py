from flask import Flask, redirect, request, jsonify, render_template, send_file, Blueprint
import qrcode
import uuid
import random
import os
import urllib
import zipfile
import io
from . import group_data

group_bp = Blueprint('group', __name__)

# 一つ上のディレクトリを取得
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)  # 一つ上のディレクトリ
STATIC_DIR = os.path.join(PARENT_DIR, 'static')  # 一つ上のディレクトリの static フォルダ

# アップロード先フォルダ
UPLOAD_FOLDER = os.path.join(STATIC_DIR, 'group_uploads')


@group_bp.route('/group/<room_id>')
def group_list(room_id):
    room_data = group_data.get_data(room_id)
    # id と password を抽出（データが1件の場合）
    record = room_data[0]
    user_id = record['id']
    password = record['password']
    print(f"ID: {user_id}, Password: {password}")
    return render_template('Group/group.html', room_id=room_id, user_id=user_id, password=password)

@group_bp.route('/create_room')
def create_room():
    return render_template('Group/create_group_room.html')






@group_bp.route('/create_group_room', methods=['POST'])  # '/upload' というURLに対してPOSTメソッドを受け付けるルートを定義
def create_group_room():  # upload関数を定義
    uid = str(uuid.uuid4())[:10]  # ランダムな10文字のユニークIDを生成
    id = request.form.get('id', '名無し')  # フォームから 'name' フィールドを取得し、なければ '名無し' を使う
    password = str(random.randrange(10**5, 10**6))  # 6桁のランダムな数字を文字列として生成し、パスワードとする
    room_id = str(id + '-' + uid)  # 'id' と 'uid' を組み合わせたセキュアIDを作成
    print(room_id)

    # セキュアIDに基づいたフォルダーを作成
    folder_path = os.path.join(UPLOAD_FOLDER, room_id)
    os.makedirs(folder_path, exist_ok=True)  # フォルダーが存在しない場合のみ作成

    group_data.create_room(id=id, password=password, room_id=room_id)  # ファイル情報を保存
    return redirect('/group' + '/' + room_id)

@group_bp.route('/group_upload/<room_id>', methods=['POST'])
def group_upload(room_id):
    room_data = group_data.get_data(room_id)
    if not room_data:
        return jsonify({"status": "error", "message": "パラメータが不正です"}), 400

    uploaded_files = request.files.getlist('upfile')
    if not uploaded_files:
        return jsonify({"status": "error", "message": "アップロードされたファイルがありません。"}), 400

    error_files = []
    for file in uploaded_files:
        if file.filename == '':
            continue
        save_path = os.path.join(UPLOAD_FOLDER, room_id)
        os.makedirs(save_path, exist_ok=True)  # フォルダがなければ作成
        file_path = os.path.join(save_path, file.filename)

        try:
            file.save(file_path)
            # ファイルサイズチェック
            if os.path.getsize(file_path) == 0:
                error_files.append(file.filename)
                os.remove(file_path)
        except Exception as e:
            return jsonify({"status": "error", "message": f"ファイル保存中にエラーが発生しました: {str(e)}"}), 500

    if error_files:
        return jsonify({
            "status": "error",
            "message": "以下のファイルの保存に失敗しました。",
            "files": error_files
        }), 500

    return jsonify({"status": "success", "message": "ファイルが正常にアップロードされました。"})




    # 正常終了メッセージを返す
    return jsonify({"status": "success", "message": "ファイルが正常にアップロードされました"}), 200



# ディレクトリの中の情報の表示
@group_bp.route("/check/<room_id>")
def list_files(room_id):
    TARGET_DIRECTORY = os.path.join(UPLOAD_FOLDER, room_id)
    try:
        # ディレクトリ内のファイル情報を取得
        files = []
        for file_name in os.listdir(TARGET_DIRECTORY):
            file_path = os.path.join(TARGET_DIRECTORY, file_name)
            print(file_path)
            if os.path.isfile(file_path):
                # ファイルの詳細情報を取得
                file_info = {
                    "name": file_name,
                }
                files.append(file_info)
        
        # ファイル情報をJSONとして返す
        return jsonify(files)
    except Exception as e:
        # エラーメッセージを返す
        return jsonify({"error": str(e)}), 500



@group_bp.route('/download/all/<room_id>', methods=['GET'])
def download_all_files(room_id):
    # ルームフォルダのパスを構築
    room_folder = os.path.join(UPLOAD_FOLDER, room_id)
    
    if not os.path.exists(room_folder):
        return jsonify({"error": "指定されたルームIDのファイルが見つかりません。"}), 404

    try:
        # メモリ上にZIPファイルを作成
        zip_stream = io.BytesIO()
        with zipfile.ZipFile(zip_stream, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # ルームフォルダ内のすべてのファイルを取得
            for filename in os.listdir(room_folder):
                file_path = os.path.join(room_folder, filename)
                if os.path.isfile(file_path):
                    # ファイルを開いて内容を読み込む
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                        # ZIPファイルにファイルを追加
                        zipf.writestr(filename, file_data)
        
        # ストリームのポインタを先頭に移動
        zip_stream.seek(0)
        
        # ZIPファイルをクライアントに送信
        return send_file(
            zip_stream,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'{room_id}_files.zip'
        )
    except Exception as e:
        return jsonify({"error": f"すべてのファイルのダウンロード中にエラーが発生しました: {str(e)}"}), 500







@group_bp.route('/download/<room_id>/<path:filename>', methods=['GET'])
def download_file(room_id, filename):
    # URLデコードしてファイル名を安全に扱う
    decoded_filename = urllib.parse.unquote(filename)
    
    # 保存フォルダ内のファイルパスを構築
    room_folder = os.path.join(UPLOAD_FOLDER, room_id)
    file_path = os.path.join(room_folder, decoded_filename)
    
    # ファイルが存在するか確認して送信
    try:
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({"error": "ファイルが見つかりません。"}), 404
    except Exception as e:
        return jsonify({"error": f"ダウンロード中にエラーが発生しました: {str(e)}"}), 500
    




@group_bp.route('/delete/<room_id>/<filename>', methods=['DELETE'])
def delete_file(room_id, filename):
    # 指定されたルームのディレクトリを組み立て
    decoded_filename = urllib.parse.unquote(filename)
    room_folder = os.path.join(UPLOAD_FOLDER, room_id)
    file_path = os.path.join(room_folder, decoded_filename)
    
    try:
        # ファイルが存在するか確認
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({"message": "ファイルが削除されました。"}), 200
        else:
            return jsonify({"error": "ファイルが見つかりません。"}), 404
    except Exception as e:
        return jsonify({"error": f"削除中にエラーが発生しました: {str(e)}"}), 500


    

@group_bp.route('/search_room_page')
def search_room_page():
    return render_template('Group/search_room.html')

@group_bp.route('/search_room', methods=['POST'])
def search_room():
    id = request.form.get('id', '')
    password = request.form.get('password', '')
    room_id = group_data.pich_room_id(id,password)
    if not room_id:
        return room_msg('IDかパスワードが間違っています')
    return redirect('/group/'+room_id)



def room_msg(s):  # テンプレートを使ってエラー画面を表示
    return render_template('error.html', message=s)
