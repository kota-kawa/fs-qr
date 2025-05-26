from flask import Blueprint, render_template, request, redirect, url_for
from sqlalchemy import text
from fs_data          import db_session as fs_db
from Group.group_data import db_session as grp_db

# ── ハードコーディング管理パスワード ─────────────
ADMIN_DB_PW = "kkawagoe"

db_admin_bp = Blueprint(
    "db_admin",
    __name__,
    url_prefix="/db_admin",
    template_folder="templates" 
)


# ─────────────────────────────────────────────
@db_admin_bp.route("/", methods=["GET", "POST"])
def dashboard():
    # POST → クエリにパスワードをのせてリダイレクト
    if request.method == "POST":
        return redirect(url_for(".dashboard",
                                pw=request.form.get("password", "")))

    pw = request.args.get("pw", "")
    if pw != ADMIN_DB_PW:
        return render_template("db_admin.html", authenticated=False)

    # 認証成功 －－ 件数集計
    def cnt(table, sess):
        return sess.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()

    summary = [
        {"name": "fsqr",         "count": cnt("fsqr",         fs_db)},
        {"name": "room",         "count": cnt("room",         grp_db)},
        {"name": "note_room",    "count": cnt("note_room",    grp_db)},
        {"name": "note_content", "count": cnt("note_content", grp_db)},
    ]

    # 直近10件取得
    def recent(table, sess, time_col):
        q = f"SELECT * FROM {table} ORDER BY {time_col} DESC LIMIT 10"
        return sess.execute(text(q)).mappings().all()

    recent_rows = {
        "fsqr":         recent("fsqr",         fs_db,  "time"),
        "room":         recent("room",         grp_db, "time"),
        "note_room":    recent("note_room",    grp_db, "time"),
        "note_content": recent("note_content", grp_db, "updated_at"),
    }

    return render_template(
        "db_admin.html",
        authenticated=True,
        summary=summary,
        recent=recent_rows,
        pw=ADMIN_DB_PW
    )
