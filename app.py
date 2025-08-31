from flask import (
    Flask,
    render_template,
    send_from_directory,
)
from werkzeug.middleware.proxy_fix import ProxyFix

import os
import time
import fs_data  # ファイルやデータを管理するモジュール
from fs_data import db_session as fs_db_session
from Group.group_data import db_session as group_db_session
from Note.note_data import db_session as note_db_session
from Note.note_app   import note_bp
from Note.note_api     import api_bp
from Admin.db_admin import db_admin_bp
from Admin.admin_app import admin_bp
from Core.core_app import core_bp
from Articles.articles_app import articles_bp

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from Group.group_app import group_bp
import atexit

# .envファイルの読み込み
load_dotenv()

# 環境変数の値を取得
admin_key = os.getenv("ADMIN_KEY")
secret_key = os.getenv("SECRET_KEY")
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MBまで許可
# Chrome の Third-Party Cookie 警告対策
app.config.update(
    SESSION_COOKIE_SECURE=True,    # 常に Secure フラグを付与
    SESSION_COOKIE_SAMESITE='Lax'  # 適切な SameSite ポリシーを設定
)
app.secret_key = secret_key 

MASTER_PW = admin_key

BASE_DIR = os.path.dirname(__file__)

app.register_blueprint(group_bp)
app.register_blueprint(note_bp)
app.register_blueprint(api_bp) 
app.register_blueprint(db_admin_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(core_bp)
app.register_blueprint(articles_bp)
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

@app.route('/all-in-one')
def all_in_one():
    return render_template('all-in-one-gpt.html')

@app.route('/ads.txt')
def ads_txt():
    return send_from_directory(app.root_path, 'ads.txt')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory(app.root_path, 'sitemap.xml')

@app.route('/robots.txt')
def robots():
    return send_from_directory(app.root_path, 'robots.txt')



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
