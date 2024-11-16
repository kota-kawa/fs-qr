from flask import Flask, redirect, request, jsonify, render_template, send_file, Blueprint
import qrcode
import uuid
import random
import os
from . import group_data

group_bp = Blueprint('group', __name__)

# 一つ上のディレクトリを取得
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)  # 一つ上のディレクトリ
STATIC_DIR = os.path.join(PARENT_DIR, 'static')  # 一つ上のディレクトリの static フォルダ

# アップロード先フォルダ
UPLOAD_FOLDER = os.path.join(STATIC_DIR, 'group_uploads')





@group_bp.route('/group/<secure_id>')
def group_list(secure_id):
    return render_template('group.html', secure_id=secure_id)

@group_bp.route('/create_room')
def create_room():
    return render_template('create_group_room.html')




@group_bp.route('/create_group_room', methods=['POST'])  # '/upload' というURLに対してPOSTメソッドを受け付けるルートを定義
def create_group_room():  # upload関数を定義
    uid = str(uuid.uuid4())[:10]  # ランダムな10文字のユニークIDを生成
    id = request.form.get('room_id', '名無し')  # フォームから 'name' フィールドを取得し、なければ '名無し' を使う
    password = str(random.randrange(10**5, 10**6))  # 6桁のランダムな数字を文字列として生成し、パスワードとする

    secure_id = str(id + '-' + uid)  # 'id' と 'uid' を組み合わせたセキュアIDを作成
    print(secure_id)

    # セキュアIDに基づいたフォルダーを作成
    folder_path = os.path.join(UPLOAD_FOLDER, secure_id)
    os.makedirs(folder_path, exist_ok=True)  # フォルダーが存在しない場合のみ作成

    return redirect('/group' + '/' + secure_id)


@group_bp.route('/group_upload/<secure_id>', methods=['POST'])  # '/upload' というURLに対してPOSTメソッドを受け付けるルートを定義
def group_upload(secure_id):  # upload関数を定義
    # アップロードされたファイルを取得
    uploaded_files = request.files.getlist('upfile')  # file0, file1, ...のキーに対応するファイルを取得
    if not uploaded_files:
        return jsonify({"status": "error", "message": "アップロードされたファイルがありません。"}), 400

  
    for file in uploaded_files:  # アップロードされた各ファイルに対して
        if file.filename == '':
            continue  # ファイル名が空の場合はスキップ
        save_path = os.path.join(UPLOAD_FOLDER + "/" + secure_id + "/" + file.filename)
        file.save(save_path)  # ファイルを指定フォルダに保存
        try:
            file.save(save_path)
        except Exception as e:
            return jsonify({"status": "error", "message": f"ファイル保存中にエラーが発生しました: {str(e)}"}), 500


    # 正常終了メッセージを返す
    return jsonify({"status": "success", "message": "ファイルが正常にアップロードされました"}), 200



# ディレクトリの中の情報の表示
@group_bp.route("/check/<secure_id>")
def list_files(secure_id):
    TARGET_DIRECTORY = os.path.join(UPLOAD_FOLDER, secure_id)
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



@group_bp.route('/search_room_page')
def search_room_page():
    return render_template('search_room.html')

@group_bp.route('/search_room', methods=['POST'])
def search_room():
    id = request.form.get('name', '')
    password = request.form.get('pw', '')
    
    #secure_id = fs_data.try_login(id,password)
    secure_id ="eee"
    #if not secure_id:
        #return msg('IDかパスワードが間違っています')
    
    return redirect('/group/'+secure_id)



def msg(s):  # テンプレートを使ってエラー画面を表示
    return render_template('error.html', message=s)
