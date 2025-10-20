import io
import os
import zipfile

import fs_data

from flask import (
    Blueprint,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from sqlalchemy import text
from werkzeug.utils import secure_filename

from fs_data          import db_session as fs_db
from Group.group_data import db_session as grp_db
from Group            import group_data

# ────────────────────────────────────────────
ADMIN_DB_PW = "kkawagoe"       # ハードコーディング

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "upload")
GROUP_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "group_uploads")

db_admin_bp = Blueprint(
    "db_admin",
    __name__,
    url_prefix="/admin",
    template_folder="templates"       # Admin/templates を使用
)

# ────────────────────────────────────────────
def table_exists(sess, table_name):
    """指定テーブルが現在の DB に存在するか"""
    q = """
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = :t
    """
    return bool(sess.execute(text(q), {"t": table_name}).scalar())

def safe_count(sess, table):
    """テーブルが無ければ 0 行、あれば行数を返す"""
    if not table_exists(sess, table):
        return 0
    return sess.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()

def safe_recent(sess, table, time_col, limit=10):
    """
    テーブルが無ければ None （存在しない印）
    テーブルがあるが 0 行なら [] （空リスト）
    """
    if not table_exists(sess, table):
        return None
    q = f"SELECT * FROM {table} ORDER BY {time_col} DESC LIMIT {limit}"
    return sess.execute(text(q)).mappings().all()

# ────────────────────────────────────────────
def _get_record(secure_id):
    data = fs_data.get_data(secure_id)
    if not data:
        return None
    return data[0]


def _resolve_file_path(record):
    secure_id = record.get("secure_id")
    file_type = record.get("file_type", "multiple")

    if file_type == "single":
        filename = f"{secure_id}.enc"
        display_name = record.get("original_filename") or filename
        mimetype = "application/octet-stream"
    else:
        filename = f"{secure_id}.zip"
        display_name = filename
        mimetype = "application/zip"

    path = os.path.join(UPLOAD_DIR, filename)
    return path, filename, display_name, mimetype


def _get_room_record(room_id):
    data = group_data.get_data(room_id)
    if not data:
        return None
    return data[0]


def _get_room_folder(room_id):
    if not room_id:
        return None
    folder_name = secure_filename(str(room_id))
    if not folder_name:
        return None
    return os.path.join(GROUP_UPLOAD_DIR, folder_name)


def _collect_room_files(room_id):
    folder = _get_room_folder(room_id)
    if not folder or not os.path.isdir(folder):
        return []

    files = []
    try:
        for name in os.listdir(folder):
            file_path = os.path.join(folder, name)
            if os.path.isfile(file_path):
                files.append({
                    "stored_name": name,
                    "display_name": name,
                    "size": os.path.getsize(file_path),
                })
    except OSError:
        return []

    files.sort(key=lambda item: item["display_name"].lower())
    return files


@db_admin_bp.route("/", methods=["GET", "POST"])
def dashboard():
    # パスワード POST → GET に付け替え
    if request.method == "POST":
        return redirect(url_for(".dashboard",
                                pw=request.form.get("password", "")))

    pw = request.args.get("pw", "")
    if pw != ADMIN_DB_PW:
        # pw が未定義のままだとテンプレート側で JSON 化時にエラーとなるため、
        # 未認証時も空文字を渡しておく。
        return render_template("db_admin.html", authenticated=False, pw="")

    # 件数サマリ
    summary = [
        {"name": "fsqr",         "count": safe_count(fs_db,  "fsqr")},
        {"name": "room",         "count": safe_count(grp_db, "room")},
        {"name": "note_room",    "count": safe_count(grp_db, "note_room")},
        {"name": "note_content", "count": safe_count(grp_db, "note_content")},
    ]

    # 直近レコード
    recent_rows = {
        "fsqr":         safe_recent(fs_db,  "fsqr",         "time"),
        "room":         safe_recent(grp_db, "room",         "time"),
        "note_room":    safe_recent(grp_db, "note_room",    "time"),
        "note_content": safe_recent(grp_db, "note_content", "updated_at"),
    }

    return render_template(
        "db_admin.html",
        authenticated=True,
        summary=summary,
        recent=recent_rows,
        pw=ADMIN_DB_PW
    )


@db_admin_bp.route("/file/<secure_id>")
def file_detail(secure_id):
    pw = request.args.get("pw", "")
    if pw != ADMIN_DB_PW:
        return jsonify({"error": "forbidden"}), 403

    record = _get_record(secure_id)
    if not record:
        return jsonify({"error": "not_found"}), 404

    path, stored_name, display_name, _ = _resolve_file_path(record)
    files = []
    if os.path.exists(path):
        files.append({
            "stored_name": stored_name,
            "display_name": display_name,
            "size": os.path.getsize(path)
        })

    created_at = record.get("time")
    if hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat(sep=" ")

    payload = {
        "secure_id": record.get("secure_id"),
        "id": record.get("id"),
        "password": record.get("password"),
        "file_type": record.get("file_type", "multiple"),
        "original_filename": record.get("original_filename"),
        "created_at": created_at,
        "files": files,
    }
    return jsonify(payload)


@db_admin_bp.route("/file/<secure_id>/download")
def file_download(secure_id):
    pw = request.args.get("pw", "")
    if pw != ADMIN_DB_PW:
        abort(403)

    record = _get_record(secure_id)
    if not record:
        abort(404)

    path, stored_name, display_name, mimetype = _resolve_file_path(record)

    if not os.path.exists(path):
        abort(404)

    return send_file(
        path,
        download_name=display_name,
        mimetype=mimetype,
        as_attachment=True,
    )


@db_admin_bp.route("/room/<room_id>")
def room_detail(room_id):
    pw = request.args.get("pw", "")
    if pw != ADMIN_DB_PW:
        return jsonify({"error": "forbidden"}), 403

    record = _get_room_record(room_id)
    if not record:
        return jsonify({"error": "not_found"}), 404

    created_at = record.get("time")
    if hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat(sep=" ")

    files = _collect_room_files(record.get("room_id"))

    payload = {
        "room_id": record.get("room_id"),
        "id": record.get("id"),
        "password": record.get("password"),
        "retention_days": record.get("retention_days"),
        "created_at": created_at,
        "files": files,
    }

    return jsonify(payload)


@db_admin_bp.route("/room/<room_id>/download")
def room_download(room_id):
    pw = request.args.get("pw", "")
    if pw != ADMIN_DB_PW:
        abort(403)

    record = _get_room_record(room_id)
    if not record:
        abort(404)

    folder = _get_room_folder(record.get("room_id"))
    if not folder or not os.path.isdir(folder):
        abort(404)

    file_entries = _collect_room_files(record.get("room_id"))
    if not file_entries:
        abort(404)

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipf:
        for entry in file_entries:
            file_path = os.path.join(folder, entry["stored_name"])
            zipf.write(file_path, arcname=entry["display_name"])

    archive.seek(0)

    download_name = secure_filename(f"{record.get('room_id')}_files.zip") or "room_files.zip"

    return send_file(
        archive,
        mimetype="application/zip",
        download_name=download_name,
        as_attachment=True,
    )
