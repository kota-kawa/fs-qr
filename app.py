from flask import Flask, redirect, request, jsonify, render_template, send_file, Blueprint
import os
import time
import qrcode
import uuid
import random
from os.path import basename
import fs_data  # ファイルやデータを管理するモジュール --- (*1)
#ファイルを削除
import shutil
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from Group.group_app import group_bp

#.envファイルの読み込み
load_dotenv()




# 環境変数の値を取得
admin_key = os.getenv("ADMIN_KEY")

app = Flask(__name__)
MASTER_PW = admin_key

BASE_DIR = os.path.dirname(__file__)
QR = BASE_DIR+'/static/qrcode'
STATIC = BASE_DIR+'/static/upload'
SAVE_FILE = BASE_DIR + '/static/data/data.json'

# Blueprintを '/admin' プレフィックスで登録
app.register_blueprint(group_bp)




@app.route('/')
def index():
    # ファイルのアップロードフォームを表示 --- (*3)
    return render_template('index.html')



@app.route('/upload', methods=['POST'])  # '/upload' というURLに対してPOSTメソッドを受け付けるルートを定義
def upload():  # upload関数を定義
    uid = str(uuid.uuid4())[:10]  # ランダムな10文字のユニークIDを生成
    id = request.form.get('name', '名無し')  # フォームから 'name' フィールドを取得し、なければ '名無し' を使う
    password = str(random.randrange(10**5, 10**6))  # 6桁のランダムな数字を文字列として生成し、パスワードとする

    secure_id = str(id + '-' + uid)  # 'id' と 'uid' を組み合わせたセキュアIDを作成

    upfile = request.files.getlist('upfile', None)  # アップロードされたファイルリストを取得
    if upfile is None:  # ファイルがアップロードされていなければ
        return msg('アップロード失敗')  # エラーメッセージを返す

    for file in upfile:  # アップロードされた各ファイルに対して
        file.save(STATIC + '/' + secure_id + file.filename)  # ファイルを指定フォルダに保存
        secure_id = (secure_id + file.filename).replace('.zip', '')

    im = qrcode.make('https://fs-qr.net/' + 'download/' + secure_id)  # セキュアIDを含んだURLからQRコードを生成
    im.save(QR + '/qrcode-' + secure_id + '.jpg')  # QRコード画像を保存

    fs_data.save_file(uid=uid, id=id, password=password, secure_id=secure_id)  # ファイル情報を保存

    return render_template('info.html', id=id, password=password, secure_id=secure_id,  # アップロード完了情報を表示するためのHTMLページをレンダリング
                           mode='upload',
                           url=request.host_url + 'download/' + secure_id)  # ダウンロードリンクを含む情報を表示



@app.route('/download/<secure_id>')
def download(secure_id):
    # URLが正しいか判定 --- (*8)
    data = fs_data.get_data(secure_id)
    if not data:
        return msg('パラメータが不正です')
    for i in data:
        id = i["id"]
    # ダウンロードページを表示 --- (*9)
    return render_template('info.html',
                           data=data, mode='download',id=id, secure_id=secure_id,
                           url=request.host_url + 'download_go/' + secure_id)


@app.route('/download_go/<secure_id>', methods=['POST'])
def download_go(secure_id):
    # URLが正しいか再び判定 --- (*10)
    data = fs_data.get_data(secure_id)
    if not data:
        return msg('パラメータが不正です')

    path=STATIC+'/'+secure_id+'.zip'

    # ダウンロードできるようにファイルを送信 --- (*14)
    return send_file(path, download_name=secure_id+'.zip', as_attachment=False)


@app.route('/admin/list')
def admin_list():
    # マスターパスワードの確認 --- (*15)
    if request.args.get('pw', '') != MASTER_PW:
        return msg('マスターパスワードが違います')
    # 全データをデータベースから取り出して表示 --- (*16)
    return render_template('admin_list.html',
                           files=fs_data.get_all(), pw=MASTER_PW)


@app.route('/admin/remove/<secure_id>')
def admin_remove(secure_id):
    # マスターパスワードを確認してファイルとデータを削除 --- (*17)
    if request.args.get('pw', '') != MASTER_PW:
        return msg('マスターパスワードが違います')

    # URLが正しいか再び判定 --- (*10)
    data = fs_data.get_data(secure_id)
    if not data:
        return msg('パラメータが不正です')

    fs_data.remove_data(secure_id)
    return redirect('/remove-succes')


@app.route('/all-remove', methods=['POST'])
def all():
    fs_data.all_remove()
    shutil.rmtree('static/upload')
    shutil.rmtree('static/qrcode')
    os.mkdir('static/upload')
    os.mkdir('static/qrcode')
    return redirect('/remove-succes')


@app.route('/kensaku')
def kensaku():
    # ファイルのアップロードフォームを表示 --- (*3)
    return render_template('kensaku-form.html')


@app.route('/try_login', methods=['POST'])
def kekka():
    id = request.form.get('name', '')
    password = request.form.get('pw', '')
    
    secure_id = fs_data.try_login(id,password)

    if not secure_id:
        return msg('IDかパスワードが間違っています')
    
    return redirect('/download/'+secure_id)


def msg(s):  # テンプレートを使ってエラー画面を表示
    return render_template('error.html', message=s)


# 削除した後に表示される画面
@app.route('/remove-succes')
def after_remove():
    return render_template('after-remove.html')


# --- テンプレートのフィルタなど拡張機能の指定 --- (*12)
# CSSなど静的ファイルの後ろにバージョンを自動追記 --- (*13)
@app.context_processor
def add_staticfile():
    return dict(staticfile=staticfile_cp)


def staticfile_cp(fname):
    path = os.path.join(app.root_path, 'static', fname)
    mtime = str(int(os.stat(path).st_mtime))
    return '/static/' + fname + '?v=' + str(mtime)

# 日時フォーマットを簡易表示するフィルタ設定 --- (*18)

def filter_datetime(tm):
    return time.strftime(
        '%Y/%m/%d %H:%M:%S',
        time.localtime(tm))
 


# フィルタをテンプレートエンジンに登録
app.jinja_env.filters['datetime'] = filter_datetime

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')



