from flask import Blueprint, render_template, request, redirect, send_from_directory, abort
import os
import shutil
import fs_data

admin_bp = Blueprint('admin', __name__, template_folder='templates')

# Base configuration
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # Parent directory (app.py location)

@admin_bp.route('/admin/list')
def admin_list():
    from app import MASTER_PW
    # マスターパスワードの確認
    if request.args.get('pw', '') != MASTER_PW:
        from Core.core_app import msg
        return msg('マスターパスワードが違います')
    return render_template('admin_list.html',
                           files=fs_data.get_all(), pw=MASTER_PW)

@admin_bp.route('/admin/remove/<string:secure_id>')
def admin_remove(secure_id):
    from app import MASTER_PW
    if request.args.get('pw', '') != MASTER_PW:
        from Core.core_app import msg
        return msg('マスターパスワードが違います')

    # Import validation function from core_app
    from Core.core_app import _validate_secure_id
    if not _validate_secure_id(secure_id):
        from Core.core_app import msg
        return msg('パラメータが不正です')

    data = fs_data.get_data(secure_id)
    if not data:
        from Core.core_app import msg
        return msg('パラメータが不正です')

    fs_data.remove_data(secure_id)
    return redirect('/remove-succes')

@admin_bp.route('/all-remove', methods=['POST'])
def all():
    from app import MASTER_PW
    # マスターパスワードの確認
    if request.form.get('pw', '') != MASTER_PW:
        from Core.core_app import msg
        return msg('マスターパスワードが違います')
    
    # 全削除時もパス固定で行う(アプリケーション内部で操作)
    fs_data.all_remove()
    shutil.rmtree(os.path.join(BASE_DIR, 'static', 'upload'))
    os.mkdir(os.path.join(BASE_DIR, 'static', 'upload'))
    return redirect('/remove-succes')