from flask import (
    Flask,
    request,
    send_file,
    send_from_directory,
    jsonify,
    render_template,
    redirect,
    url_for,
    abort,
)
from werkzeug.middleware.proxy_fix import ProxyFix

import os
import time
import uuid
import secrets
import fs_data  # ファイルやデータを管理するモジュール
from fs_data import db_session as fs_db_session
from Group.group_data import db_session as group_db_session
from Note.note_data import db_session as note_db_session
from Note.note_app   import note_bp
from Note.note_api     import api_bp
from Admin.db_admin import db_admin_bp

import shutil
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from Group.group_app import group_bp
from werkzeug.utils import secure_filename
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

# .envファイルの読み込み
load_dotenv()

# 環境変数の値を取得
admin_key = os.getenv("ADMIN_KEY")
secret_key = os.getenv("SECRET_KEY")
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 例: 50MBまで許可
# Chrome の Third-Party Cookie 警告対策
app.config.update(
    SESSION_COOKIE_SECURE=True,    # 常に Secure フラグを付与
    SESSION_COOKIE_SAMESITE='Lax'  # 適切な SameSite ポリシーを設定
)
app.secret_key = secret_key 

MASTER_PW = admin_key

BASE_DIR = os.path.dirname(__file__)
STATIC = os.path.join(BASE_DIR, 'static', 'upload')
# Ensure the upload directory exists to avoid FileNotFoundError
os.makedirs(STATIC, exist_ok=True)

app.register_blueprint(group_bp)
app.register_blueprint(note_bp)
app.register_blueprint(api_bp) 
app.register_blueprint(db_admin_bp)
# ---------------------------
# 古いルームを削除する関数
# ---------------------------
def delete_expired_files():
    fs_data.remove_expired_files()

# スケジューラのセットアップ（毎日1回実行）
scheduler = BackgroundScheduler()
scheduler.add_job(func=delete_expired_files, trigger="interval", days=1)
scheduler.start()

# アプリ終了時にスケジューラをシャットダウンするように登録
atexit.register(lambda: scheduler.shutdown())
# ---------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fs-qr')
def fs_qr():
    return render_template('fs-qr.html')


@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/usage')
def usage():
    return render_template('usage.html')


@app.route('/safe-sharing')
def safe_sharing():
    return render_template('safe-sharing.html')


@app.route('/encryption')
def encryption():
    return render_template('encryption.html')


@app.route('/education-business')
def education_business():
    return render_template('education-business.html')


@app.route('/risk-mitigation')
def risk_mitigation():
    return render_template('risk-mitigation.html')

@app.route('/articles')
def articles():
    articles = [
        {"title": "FS!QRの基本的な使い方", "url": "/usage"},
        {"title": "安全な共有のポイント", "url": "/safe-sharing"},
        {"title": "暗号化の基礎知識", "url": "/encryption"},
        {"title": "教育・業務での活用例", "url": "/education-business"},
        {"title": "リスクと対策の考え方", "url": "/risk-mitigation"},
    ]
    return render_template('articles.html', articles=articles)

@app.route('/ads.txt')
def ads_txt():
    return send_from_directory(app.root_path, 'ads.txt')

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

    fs_data.save_file(uid=uid, id=id, password=password, secure_id=secure_id)

        # ここでは JSON でリダイレクト先を返す
    return jsonify({
        "redirect_url": url_for('upload_complete', secure_id=secure_id)
    })

@app.route('/upload_complete/<secure_id>')
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
        url=url_for('download', secure_id=secure_id, _external=True)
    )

@app.route('/download/<secure_id>')
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
        url=url_for('download_go', secure_id=secure_id)
    )

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
    os.mkdir(os.path.join(BASE_DIR, 'static', 'upload'))
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

@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404

@app.context_processor
def add_staticfile():
    return dict(staticfile=staticfile_cp)

#　データベースのセッションを正しく削除
@app.teardown_appcontext
def shutdown_session(exception=None):
    fs_db_session.remove()
    group_db_session.remove()
    note_db_session.remove()


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
    app.run(debug=True, host='0.0.0.0')
