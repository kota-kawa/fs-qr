import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch

# プロジェクトルートをsys.pathに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# databaseモジュールを強制的にモック化する
# これにより、aiomysqlなどのドライバがなくてもapp.pyをインポート可能にする
mock_database = MagicMock()
mock_database.db_session = MagicMock()
# await db_session.remove() に対応するための非同期モック
mock_database.db_session.remove = AsyncMock()
mock_database.engine = AsyncMock()

# redisモジュールもモック化
mock_redis = MagicMock()
mock_redis_asyncio = MagicMock()
sys.modules["redis"] = mock_redis
sys.modules["redis.asyncio"] = mock_redis_asyncio

# starsessionsモジュールもモック化
mock_starsessions = MagicMock()
sys.modules["starsessions"] = mock_starsessions

# SessionMiddleware が ASGI アプリとして正しく振る舞うようにする
class MockSessionMiddleware:
    def __init__(self, app, **kwargs):
        self.app = app

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)

mock_starsessions.SessionMiddleware = MockSessionMiddleware

mock_starsessions_stores = MagicMock()
sys.modules["starsessions.stores"] = mock_starsessions_stores
mock_starsessions_stores_redis = MagicMock()
sys.modules["starsessions.stores.redis"] = mock_starsessions_stores_redis

# diff_match_patchモジュールもモック化
mock_dmp = MagicMock()
sys.modules["diff_match_patch"] = mock_dmp

# 実際にモジュールとして登録
sys.modules["database"] = mock_database

# これ以降のインポートでは、databaseモジュールは上記のモックが使われる
import pytest
from starlette.testclient import TestClient

@pytest.fixture(scope="module")
def test_client():
    # さらに細かい部分のモックが必要な場合はここでpatchする
    # Note.note_dataなどがDBにアクセスするのを防ぐ
    
    with patch("Note.note_data.ensure_tables", new_callable=AsyncMock), \
         patch("Note.note_realtime.startup", new_callable=AsyncMock), \
         patch("Note.note_realtime.shutdown", new_callable=AsyncMock), \
         patch("Note.note_data.get_room_meta_direct", new_callable=AsyncMock) as mock_get_room, \
         patch("FSQR.fsqr_data.get_data", new_callable=AsyncMock) as mock_fsqr_get, \
         patch("Group.group_data.get_data_direct", new_callable=AsyncMock) as mock_group_get:
        
        # appのインポートはモック設定後に行う
        from app import app
        
        with TestClient(app) as client:
            yield client