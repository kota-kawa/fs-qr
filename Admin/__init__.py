# Admin/db_admin.py
from flask import Blueprint, render_template, request, redirect, url_for
from sqlalchemy import text
from fs_data            import db_session as fs_db
from Group.group_data   import db_session as grp_db

# ── ハードコーディングされた管理パスワード ──────────────
ADMIN_DB_PW = "kkawagoe"

db_admin_bp = Blueprint("db_admin", __name__, url_prefix="/admin")

# ─────────────────────────────────────────────────────────
@db_admin_bp.route("/", methods=["GET", "POST"])
def dashboard():
    # ----- ログインフォーム POST → GET リダイレクト -----
    if request.method == "POST":
        return redirect(url_for(".dashboard", pw=request.form.get("password", "")))

    # ----- 認証判定 -------------------------------------
    pw = request.args.get("pw", "")
    if pw != ADMIN_DB_PW:
        return render_template("db_admin.html", authenticated=False)

    # ----- 集計 -----------------------------------------
    def cnt(table, sess):
        return sess.execute(text(f"SELECT COUNT(*) AS c FROM {table}")).scalar()

    summary = [
        {"name": "fsqr",          "count": cnt("fsqr",          fs_db)},
        {"name": "room",          "count": cnt("room",          grp_db)},
        {"name": "note_room",     "count": cnt("note_room",     grp_db)},
        {"name": "note_content",  "count": cnt("note_content",  grp_db)},
    ]

    # ----- 直近 10 行を取得（時間列のあるテーブルのみ） ---
    def recent(table, sess, time_col):
        q = f"SELECT * FROM {table} ORDER BY {time_col} DESC LIMIT 10"
        return sess.execute(text(q)).mappings().all()

    recent_rows = {
        "fsqr":         recent("fsqr",         fs_db, "time"),
        "room":         recent("room",         grp_db, "time"),
        "note_room":    recent("note_room",    grp_db, "time"),
        "note_content": recent("note_content", grp_db, "updated_at"),
    }

    return render_template("db_admin.html",
                           authenticated=True,
                           summary=summary,
                           recent=recent_rows,
                           pw=ADMIN_DB_PW)
