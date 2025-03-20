from flask import Flask, request,send_file, jsonify, render_template, redirect, url_for
import os
import time
import qrcode
import uuid
import random
import secrets
from os.path import basename
import fs_data  # ファイルやデータを管理するモジュール
import shutil
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from Group.group_app import group_bp
from werkzeug.utils import secure_filename

# .envファイルの読み込み
load_dotenv()

# 環境変数の値を取得
admin_key = os.getenv("ADMIN_KEY")

app = Flask(__name__)
MASTER_PW = admin_key

BASE_DIR = os.path.dirname(__file__)
QR = os.path.join(BASE_DIR, 'static', 'qrcode')
STATIC = os.path.join(BASE_DIR, 'static', 'upload')

app.register_blueprint(group_bp)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fs-qr')
def fs_qr():
    return render_template('fs-qr.html')

@app.route('/fs-qr-upload')
def fs_qr_upload():
    return render_template('fs-qr-upload.html')

@app.route('/upload', methods=['POST'])
def upload():
    # よりセキュアな乱数の生成
    uid = str(uuid.uuid4())[:10]  # ランダムな10文字のユニークID
    id = request.form.get('name', '名無し')
    # 6桁のパスワードをsecretsで生成（数字のみの場合はsecrets.randbelow等）
    password = str(secrets.randbelow(10**6)).zfill(6)

    # secure_idに不必要な文字が混入しないよう明示的に整形
    # filenameからは別途secure_filenameを利用するためここではidとuidのみ結合
    secure_id_base = f"{id}-{uid}-"

    upfiles = request.files.getlist('upfile')
    if not upfiles:
        return msg('アップロード失敗')

    # ファイルパス生成用リスト
    uploaded_files = []

    for file in upfiles:
        filename = secure_filename(file.filename)  # ファイル名をサニタイズ
        if not filename:
            return msg('不正なファイル名です')
        
        save_path = os.path.join(STATIC, secure_id_base + filename)
        file.save(save_path)
        uploaded_files.append(filename)

    # 最終的なsecure_idは全ファイル名を元にするが、zip処理が前提なら一貫したルールで
    # '.'の除去などは行わないが、相対パス排除はsecure_filenameに任せている。
    secure_id = (secure_id_base + uploaded_files[-1]).replace('.zip', '')

    # QRコード生成 (外部入力のない内部生成値なので基本問題なし)
    qr_url = 'https://fs-qr.net/' + 'download/' + secure_id
    im = qrcode.make(qr_url)
    qr_path = os.path.join(QR, 'qrcode-' + secure_id + '.jpg')
    im.save(qr_path)

    fs_data.save_file(uid=uid, id=id, password=password, secure_id=secure_id)

        # ここでは JSON でリダイレクト先を返す
    return jsonify({
        "redirect_url": url_for('upload_complete', secure_id=secure_id)
    })



@app.route('/upload_complete/<secure_id>')
def upload_complete(secure_id):
    # DBからアップロード情報を取得
    data = fs_data.get_data(secure_id)
    if not data:
        return render_template('error.html', message='パラメータが不正です')

    # 最初のレコードからIDとパスワードを取得
    row = data[0]
    id_val = row["id"]
    password_val = row["password"]

    # info.html を mode='upload' で表示
    return render_template(
        'info.html',
        id=id_val,
        password=password_val,
        secure_id=secure_id,
        mode='upload',
        url=request.host_url + 'download/' + secure_id
    )

@app.route('/download/<secure_id>')
def download(secure_id):
    # URLパラメータをサニタイズ（DBからデータを取得して判定）
    data = fs_data.get_data(secure_id)
    if not data:
        return msg('パラメータが不正です')
    # dataからidを取得
    id = data[0]["id"] if data else None

    return render_template('info.html',
                           data=data, mode='download', id=id, secure_id=secure_id,
                           url=request.host_url + 'download_go/' + secure_id)

@app.route('/download_go/<secure_id>', methods=['POST'])
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

@app.route('/admin/list')
def admin_list():
    # マスターパスワードの確認
    if request.args.get('pw', '') != MASTER_PW:
        return msg('マスターパスワードが違います')
    return render_template('admin_list.html',
                           files=fs_data.get_all(), pw=MASTER_PW)

@app.route('/admin/remove/<secure_id>')
def admin_remove(secure_id):
    if request.args.get('pw', '') != MASTER_PW:
        return msg('マスターパスワードが違います')

    data = fs_data.get_data(secure_id)
    if not data:
        return msg('パラメータが不正です')

    fs_data.remove_data(secure_id)
    return redirect('/remove-succes')

@app.route('/all-remove', methods=['POST'])
def all():
    # 全削除時もパス固定で行う(アプリケーション内部で操作)
    fs_data.all_remove()
    shutil.rmtree(os.path.join(BASE_DIR, 'static', 'upload'))
    shutil.rmtree(os.path.join(BASE_DIR, 'static', 'qrcode'))
    os.mkdir(os.path.join(BASE_DIR, 'static', 'upload'))
    os.mkdir(os.path.join(BASE_DIR, 'static', 'qrcode'))
    return redirect('/remove-succes')

@app.route('/kensaku')
def kensaku():
    return render_template('kensaku-form.html')

@app.route('/try_login', methods=['POST'])
def kekka():
    id = request.form.get('name', '')
    password = request.form.get('pw', '')

    secure_id = fs_data.try_login(id, password)

    if not secure_id:
        return msg('IDかパスワードが間違っています')

    return redirect('/download/' + secure_id)

def msg(s):
    return render_template('error.html', message=s)

@app.route('/remove-succes')
def after_remove():
    return render_template('after-remove.html')

@app.context_processor
def add_staticfile():
    return dict(staticfile=staticfile_cp)

def staticfile_cp(fname):
    path = os.path.join(app.root_path, 'static', fname)
    if os.path.exists(path):
        mtime = str(int(os.stat(path).st_mtime))
        return '/static/' + fname + '?v=' + str(mtime)
    return '/static/' + fname

def filter_datetime(tm):
    return time.strftime('%Y/%m/%d %H:%M:%S', time.localtime(tm))

app.jinja_env.filters['datetime'] = filter_datetime

if __name__ == '__main__':
    # 本番運用時はdebug=Falseに設定すること。
    app.run(debug=False, host='0.0.0.0')
    #app.run(debug=True)
