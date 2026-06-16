"""Gunicorn 設定（本番）。

環境変数で調整できるようにしつつ、従来の挙動（4 ワーカー / timeout 360）を
デフォルト値として維持する。``uvicorn.workers.UvicornWorker`` は gunicorn の
``max_requests`` / ``max_requests_jitter`` を uvicorn の ``limit_max_requests``
として解釈するため、ワーカーの定期再起動によるメモリ肥大の抑制が有効に働く。
"""

import os


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


bind = "0.0.0.0:5000"
worker_class = "uvicorn.workers.UvicornWorker"

# 非同期ワーカーのため少数で多数の同時接続を捌ける。既定は従来同様 4。
# CPU コア数の多いホストでは WEB_CONCURRENCY で引き上げる（DB の max_connections
# とプール設定の整合を必ず確認すること）。
workers = _int_env("WEB_CONCURRENCY", 4)

# 一定リクエストごとにワーカーを入れ替え、長時間稼働によるメモリ肥大を防ぐ。
# jitter で全ワーカーの同時再起動を避ける。0 で無効化。
max_requests = _int_env("GUNICORN_MAX_REQUESTS", 1000, minimum=0)
max_requests_jitter = _int_env("GUNICORN_MAX_REQUESTS_JITTER", 100, minimum=0)

# 大きなアップロード/ダウンロードを考慮した従来同様のタイムアウト。
timeout = _int_env("GUNICORN_TIMEOUT", 360)
graceful_timeout = _int_env("GUNICORN_GRACEFUL_TIMEOUT", 30)
keepalive = _int_env("GUNICORN_KEEPALIVE", 5)

accesslog = os.getenv("GUNICORN_ACCESS_LOG", "/app/logs/access.log")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "/app/logs/error.log")
