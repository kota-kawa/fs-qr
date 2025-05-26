from flask import Blueprint, render_template, request, redirect, url_for
from sqlalchemy import text
from fs_data          import db_session as fs_db
from Group.group_data import db_session as grp_db

# ────────────────────────────────────────────
ADMIN_DB_PW = "kkawagoe"       # ハードコーディング

db_admin_bp = Blueprint(
    "db_admin",
    __name__,
    url_prefix="/db_admin",
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
@db_admin_bp.route("/", methods=["GET", "POST"])
def dashboard():
    # パスワード POST → GET に付け替え
    if request.method == "POST":
        return redirect(url_for(".dashboard",
                                pw=request.form.get("password", "")))

    pw = request.args.get("pw", "")
    if pw != ADMIN_DB_PW:
        return render_template("db_admin.html", authenticated=False)

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
