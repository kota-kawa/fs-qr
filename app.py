from flask import (
    Flask,
    redirect,
    render_template,
    request,
    send_from_directory,
)
from werkzeug.middleware.proxy_fix import ProxyFix

import os
import time
from database import db_session
from Note.note_app   import note_bp
from Note.note_api     import api_bp
from Admin.db_admin import db_admin_bp
from Admin.admin_app import admin_bp
from FSQR.fsqr_app import fsqr_bp
from Articles.articles_app import articles_bp

from dotenv import load_dotenv
from Group.group_app import group_bp

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
app.register_blueprint(fsqr_bp)
app.register_blueprint(articles_bp)
def _canonical_redirect():
    if request.query_string:
        return redirect(request.base_url, code=301)
    return None


@app.route('/')
def index():
    canonical = _canonical_redirect()
    if canonical:
        return canonical
    return render_template('index.html')

@app.route('/privacy-policy')
def privacy_policy():
    canonical = _canonical_redirect()
    if canonical:
        return canonical
    return render_template('privacy.html')

@app.route('/about')
def about():
    canonical = _canonical_redirect()
    if canonical:
        return canonical
    return render_template('about.html')

@app.route('/contact')
def contact():
    canonical = _canonical_redirect()
    if canonical:
        return canonical
    return render_template('contact.html')

@app.route('/usage')
def usage():
    canonical = _canonical_redirect()
    if canonical:
        return canonical
    return render_template('usage.html')

@app.route('/site-operator')
def site_operator():
    canonical = _canonical_redirect()
    if canonical:
        return canonical
    return render_template('site_operator.html')

@app.route('/all-in-one')
def all_in_one():
    canonical = _canonical_redirect()
    if canonical:
        return canonical
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
    db_session.remove()


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
