from flask import Flask, redirect, request, jsonify
from flask import render_template, send_file
import os
import time
import qrcode
import uuid
import random
import zipfile
from os.path import basename
import fs_data  # ファイルやデータを管理するモジュール 
#ファイルを削除
import shutil

app = Flask(__name__)
MASTER_PW = '*****'  # 管理用パスワード 

BASE_DIR = os.path.dirname(__file__)
QR = BASE_DIR+'/static/qrcode'
STATIC = BASE_DIR+'/static/upload'


@app.route('/')
def index():
    # ファイルのアップロードフォームを表示
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    # アップロードしたファイルのオブジェクト 
    uid = str(uuid.uuid4())[:10]
    id = request.form.get('name', '名無し')

    password=str(random.randrange(10**5,10**6))

    secure_id=str(id+'-'+uid)

    im = qrcode.make('https://fs-qr.net/' + 'download/' + secure_id)
    im.save(QR+'/qrcode-'+secure_id+'.jpg')

    upfile = request.files.getlist('upfile', None)
    if upfile is None:
        return msg('アップロード失敗')

    os.mkdir(STATIC+'/'+secure_id)


    
    compFile = zipfile.ZipFile(STATIC+'/'+secure_id+'.zip', 'w', zipfile.ZIP_DEFLATED)

    for file in upfile:
        filename = secure_id+'-'+file.filename
        file.save(STATIC+'/'+secure_id+'/'+filename)

        file_path=STATIC+'/'+secure_id+'/'+filename
        compFile.write(file_path, basename(file_path))

    compFile.close()
    

    shutil.rmtree(STATIC+'/'+secure_id)


    # アップロードしたファイル説明を取得
    fs_data.save_file(uid=uid, id=id, password=password, secure_id=secure_id)


    data = fs_data.get_data(secure_id)

    # ダウンロード先の表示 
    return render_template('info.html',id=id,password=password,secure_id=secure_id,
                           data=data, mode='upload',
                           url=request.host_url + 'download/' + secure_id)


@app.route('/download/<secure_id>')
def download(secure_id):
    # URLが正しいか判定
    data = fs_data.get_data(secure_id)
    if not data:
        return msg('パラメータが不正です')
    
    for i in data:
        id = i["id"]
    # ダウンロードページを表示
    return render_template('info.html',
                           data=data, mode='download',id=id, secure_id=secure_id,
                           url=request.host_url + 'download_go/' + secure_id)


@app.route('/download_go/<secure_id>', methods=['POST'])
def download_go(secure_id):
    # URLが正しいか再び判定 
    data = fs_data.get_data(secure_id)
    if not data:
        return msg('パラメータが不正です')

    path=STATIC+'/'+secure_id+'.zip'

    # ダウンロードできるようにファイルを送信
    return send_file(path,
                     as_attachment=True,
                     attachment_filename=secure_id+'.zip')


@app.route('/admin/list')
def admin_list():
    # マスターパスワードの確認 
    if request.args.get('pw', '') != MASTER_PW:
        return msg('マスターパスワードが違います')
    # 全データをデータベースから取り出して表示 
    return render_template('admin_list.html',
                           files=fs_data.get_all(), pw=MASTER_PW)


@app.route('/admin/remove/<secure_id>')
def admin_remove(secure_id):
    # マスターパスワードを確認してファイルとデータを削除 
    if request.args.get('pw', '') != MASTER_PW:
        return msg('マスターパスワードが違います')

    # URLが正しいか再び判定 
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

    # ファイルのアップロードフォームを表示 
    return render_template('kensaku-form.html')


@app.route('/try_login', methods=['POST'])
def kekka():
    id = request.form.get('name', '')
    password = request.form.get('pw', '')
    
    secure_id = fs_data.try_login(id,password)

    if not secure_id:
        return msg('パラメータが不正です')

    
    return redirect('/download/'+secure_id)


def msg(s):  # テンプレートを使ってエラー画面を表示
    return render_template('error.html', message=s)


# 削除した後に表示される画面
@app.route('/remove-succes')
def after_remove():
    return render_template('after-remove.html')


# --- テンプレートのフィルタなど拡張機能の指定
# CSSなど静的ファイルの後ろにバージョンを自動追記 
@app.context_processor
def add_staticfile():
    return dict(staticfile=staticfile_cp)


def staticfile_cp(fname):
    path = os.path.join(app.root_path, 'static', fname)
    mtime = str(int(os.stat(path).st_mtime))
    return '/static/' + fname + '?v=' + str(mtime)

# 日時フォーマットを簡易表示するフィルタ設定 


def filter_datetime(tm):
    return time.strftime(
        '%Y/%m/%d %H:%M:%S',
        time.localtime(tm))


# フィルタをテンプレートエンジンに登録
app.jinja_env.filters['datetime'] = filter_datetime

if __name__ == '__main__':
    app.run(debug=True)

