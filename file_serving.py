"""ファイル配信ヘルパー。

大きなアップロードファイルの実体転送を Python ワーカー（uvicorn のイベント
ループ）に抱えさせると、転送が終わるまでそのワーカーが占有され、同時接続が増えた
ときのボトルネックになる。本番では nginx の ``X-Accel-Redirect`` を使い、認証・
認可だけをアプリが行い、実ファイルのバイト送出は nginx に委譲する。

``X_ACCEL_REDIRECT_ENABLED`` が無効な環境（ローカル開発・テスト・nginx を介さない
起動）では従来どおり :class:`starlette.responses.FileResponse` で配信するため、
挙動は完全に後方互換となる。
"""

from __future__ import annotations

import logging
import os
import urllib.parse
from typing import Mapping, Optional

from starlette.background import BackgroundTask
from starlette.responses import FileResponse, Response

from settings import X_ACCEL_LOCATIONS, X_ACCEL_REDIRECT_ENABLED

logger = logging.getLogger(__name__)


def _build_accel_uri(internal_prefix: str, fs_root: str, path: str) -> Optional[str]:
    """``path`` を nginx 内部ロケーション用の URI に変換する。

    ``path`` が ``fs_root`` の外（例: レガシー保存場所）にある場合は ``None`` を返し、
    呼び出し側で :class:`FileResponse` にフォールバックさせる。
    """
    try:
        rel = os.path.relpath(os.path.abspath(path), os.path.abspath(fs_root))
    except ValueError:
        # Windows のドライブ違いなどで relpath が失敗するケース。
        return None
    # ``fs_root`` 配下でなければオフロード不可。パストラバーサルもここで弾く。
    if rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel):
        return None
    quoted = "/".join(urllib.parse.quote(seg) for seg in rel.split(os.sep))
    return internal_prefix.rstrip("/") + "/" + quoted


def build_file_response(
    path: str,
    *,
    media_type: str,
    headers: Optional[Mapping[str, str]] = None,
    background: Optional[BackgroundTask] = None,
    accel_scope: Optional[str] = None,
) -> Response:
    """ファイル配信レスポンスを生成する。

    ``X_ACCEL_REDIRECT_ENABLED`` かつ ``accel_scope`` が設定済みで、対象ファイルが
    そのスコープの保存ルート配下にある場合は ``X-Accel-Redirect`` で nginx に委譲する。
    それ以外は :class:`FileResponse` を返す。
    """
    response_headers = dict(headers or {})

    if X_ACCEL_REDIRECT_ENABLED and accel_scope:
        location = X_ACCEL_LOCATIONS.get(accel_scope)
        if location:
            internal_prefix, fs_root = location
            accel_uri = _build_accel_uri(internal_prefix, fs_root, path)
            if accel_uri is not None:
                # nginx が実体ファイルから Content-Length を再計算するため、
                # アプリ側の値を残すと不整合になる。削除して nginx に任せる。
                for key in list(response_headers):
                    if key.lower() == "content-length":
                        del response_headers[key]
                response_headers["X-Accel-Redirect"] = accel_uri
                # nginx 側のロケーションで Content-Type を確定させるが、保険として
                # アプリの意図する型も渡しておく。
                return Response(
                    status_code=200,
                    media_type=media_type,
                    headers=response_headers,
                    background=background,
                )
            logger.debug("X-Accel offload skipped (path outside scope root): %s", path)

    return FileResponse(
        path,
        media_type=media_type,
        headers=response_headers,
        background=background,
    )
