"""Pure unit tests – no HTTP, no database, no Redis required."""

import asyncio
import re
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# rate_limit.py
# ---------------------------------------------------------------------------


class _FakeRequest:
    """Minimal request stub for get_client_ip tests."""

    def __init__(self, forwarded="", client_host=None):
        self._forwarded = forwarded
        self.client = type("C", (), {"host": client_host})() if client_host else None

    @property
    def headers(self):
        return {"X-Forwarded-For": self._forwarded} if self._forwarded else {}


def test_get_block_message_1day():
    from rate_limit import get_block_message

    msg = get_block_message("1日")
    assert "1日" in msg


def test_get_block_message_30min():
    from rate_limit import get_block_message

    msg = get_block_message("30分")
    assert "30分" in msg


def test_get_block_message_unknown_label():
    from rate_limit import get_block_message

    msg = get_block_message(None)
    assert isinstance(msg, str) and len(msg) > 0


def test_get_client_ip_from_forwarded_header():
    from rate_limit import get_client_ip

    req = _FakeRequest(forwarded="203.0.113.1, 192.168.1.1")
    assert get_client_ip(req) == "203.0.113.1"


def test_get_client_ip_single_ip_in_header():
    from rate_limit import get_client_ip

    req = _FakeRequest(forwarded="10.0.0.5")
    assert get_client_ip(req) == "10.0.0.5"


def test_get_client_ip_from_client():
    from rate_limit import get_client_ip

    req = _FakeRequest(client_host="172.16.0.1")
    assert get_client_ip(req) == "172.16.0.1"


def test_get_client_ip_unknown():
    from rate_limit import get_client_ip

    req = _FakeRequest()
    assert get_client_ip(req) == "unknown"


# ---------------------------------------------------------------------------
# FSQR.fsqr_app – pure helper functions
# ---------------------------------------------------------------------------


def test_calculate_deletion_context_normal():
    from FSQR.fsqr_app import _calculate_deletion_context

    record = {"retention_days": 7, "time": datetime(2026, 3, 1, 12, 0)}
    days, date_str = _calculate_deletion_context(record)
    assert days == 7
    assert date_str == "2026-03-08 12:00"


def test_calculate_deletion_context_30days():
    from FSQR.fsqr_app import _calculate_deletion_context

    record = {"retention_days": 30, "time": datetime(2026, 1, 1, 0, 0)}
    days, date_str = _calculate_deletion_context(record)
    assert days == 30
    assert date_str == "2026-01-31 00:00"


def test_calculate_deletion_context_no_time():
    from FSQR.fsqr_app import _calculate_deletion_context

    record = {"retention_days": 7}
    days, date_str = _calculate_deletion_context(record)
    assert days == 7
    assert date_str is None


def test_calculate_deletion_context_default_retention():
    from FSQR.fsqr_app import _calculate_deletion_context

    record = {"time": datetime(2026, 3, 1, 0, 0)}  # retention_days キーなし
    days, date_str = _calculate_deletion_context(record)
    assert days == 7


# ---------------------------------------------------------------------------
# Note.note_app – _is_valid_room_id
# ---------------------------------------------------------------------------


def test_is_valid_room_id_valid():
    from Note.note_app import _is_valid_room_id

    assert _is_valid_room_id("abc123") is True
    assert _is_valid_room_id("ABCXYZ") is True
    assert _is_valid_room_id("123456") is True


def test_is_valid_room_id_invalid():
    from Note.note_app import _is_valid_room_id

    assert _is_valid_room_id("") is False
    assert _is_valid_room_id("abc12") is False  # 5文字
    assert _is_valid_room_id("abc1234") is False  # 7文字
    assert _is_valid_room_id("abc!@#") is False  # 無効な文字


# ---------------------------------------------------------------------------
# Group.group_app – is_safe_path
# ---------------------------------------------------------------------------


def test_is_safe_path_valid():
    from Group.group_app import is_safe_path

    assert is_safe_path("/var/uploads", "/var/uploads/roomid/file.txt") is True


def test_is_safe_path_traversal():
    from Group.group_app import is_safe_path

    assert is_safe_path("/var/uploads", "/var/uploads/../etc/passwd") is False


def test_is_safe_path_nested_safe():
    from Group.group_app import is_safe_path

    assert is_safe_path("/var/uploads", "/var/uploads/roomid/subdir/file.txt") is True


def test_is_safe_path_sibling_directory():
    from Group.group_app import is_safe_path

    assert is_safe_path("/var/uploads/room1", "/var/uploads/room2/file.txt") is False


def test_is_safe_path_equals_base():
    from Group.group_app import is_safe_path

    assert is_safe_path("/var/uploads", "/var/uploads") is True


# ---------------------------------------------------------------------------
# Note.note_app – _generate_room_id
# ---------------------------------------------------------------------------


def test_generate_room_id_length():
    from Note.note_app import _generate_room_id

    assert len(_generate_room_id()) == 6


def test_generate_room_id_alphanumeric():
    from Note.note_app import _generate_room_id

    for _ in range(20):
        rid = _generate_room_id()
        assert re.match(r"^[a-zA-Z0-9]{6}$", rid), f"無効なルームID: {rid}"


# ---------------------------------------------------------------------------
# FSQR.fsqr_app – _calculate_deletion_context (追加ケース)
# ---------------------------------------------------------------------------


def test_calculate_deletion_context_1day():
    from FSQR.fsqr_app import _calculate_deletion_context

    record = {"retention_days": 1, "time": datetime(2026, 3, 1, 0, 0)}
    days, date_str = _calculate_deletion_context(record)
    assert days == 1
    assert date_str == "2026-03-02 00:00"


# ---------------------------------------------------------------------------
# rate_limit – get_block_message エッジケース
# ---------------------------------------------------------------------------


def test_get_block_message_empty_string():
    from rate_limit import get_block_message

    msg = get_block_message("")
    assert isinstance(msg, str) and len(msg) > 0


# ---------------------------------------------------------------------------
# Note.note_app – _is_valid_room_id 追加エッジケース
# ---------------------------------------------------------------------------


def test_is_valid_room_id_with_space():
    from Note.note_app import _is_valid_room_id

    assert _is_valid_room_id("abc 23") is False


def test_is_valid_room_id_unicode():
    from Note.note_app import _is_valid_room_id

    assert _is_valid_room_id("日本語abc") is False


# ---------------------------------------------------------------------------
# rate_limit – get_client_ip: 空白のみの X-Forwarded-For ヘッダー
# ---------------------------------------------------------------------------


def test_get_client_ip_whitespace_forwarded_uses_client():
    from rate_limit import get_client_ip

    req = type(
        "R",
        (),
        {
            "headers": {"X-Forwarded-For": "   "},
            "client": type("C", (), {"host": "10.1.2.3"})(),
        },
    )()
    assert get_client_ip(req) == "10.1.2.3"


# ---------------------------------------------------------------------------
# cache_utils – CustomJSONEncoder
# ---------------------------------------------------------------------------


def test_custom_json_encoder_datetime():
    import json
    from datetime import datetime

    from cache_utils import CustomJSONEncoder

    result = json.loads(
        json.dumps(datetime(2026, 1, 1, 12, 0, 0), cls=CustomJSONEncoder)
    )
    assert result == "2026-01-01T12:00:00"


def test_custom_json_encoder_date():
    import json
    from datetime import date

    from cache_utils import CustomJSONEncoder

    result = json.loads(json.dumps(date(2026, 1, 1), cls=CustomJSONEncoder))
    assert result == "2026-01-01"


def test_custom_json_encoder_timedelta():
    import json
    from datetime import timedelta

    from cache_utils import CustomJSONEncoder

    result = json.loads(json.dumps(timedelta(days=1), cls=CustomJSONEncoder))
    assert isinstance(result, str)


def test_custom_json_encoder_decimal():
    import json
    from decimal import Decimal

    from cache_utils import CustomJSONEncoder

    result = json.loads(json.dumps(Decimal("3.14"), cls=CustomJSONEncoder))
    assert abs(result - 3.14) < 1e-10


# ---------------------------------------------------------------------------
# cache_utils – cache_data decorator
# ---------------------------------------------------------------------------


def test_cache_data_miss_calls_function():
    """キャッシュミス時は関数を呼び出して結果を返す"""
    from cache_utils import cache_data

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    @cache_data(ttl=60, key_prefix="test")
    async def my_func():
        return [{"name": "hello"}]

    with patch("cache_utils.redis_client", mock_redis):
        result = asyncio.run(my_func())

    assert result == [{"name": "hello"}]
    mock_redis.get.assert_awaited_once()


def test_cache_data_hit_returns_cached_value():
    """キャッシュヒット時はキャッシュから値を返す（関数は呼ばれない）"""
    import json

    from cache_utils import cache_data

    cached_value = [{"name": "cached"}]
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps(cached_value))

    call_count = 0

    @cache_data(ttl=60, key_prefix="test")
    async def my_func():
        nonlocal call_count
        call_count += 1
        return [{"name": "not cached"}]

    with patch("cache_utils.redis_client", mock_redis):
        result = asyncio.run(my_func())

    assert result == cached_value
    assert call_count == 0


def test_cache_data_redis_error_still_calls_function():
    """Redis エラー時も関数を呼び出して結果を返す"""
    from cache_utils import cache_data

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=Exception("Connection refused"))

    @cache_data(ttl=60, key_prefix="test")
    async def my_func():
        return "fallback"

    with patch("cache_utils.redis_client", mock_redis):
        result = asyncio.run(my_func())

    assert result == "fallback"


# ---------------------------------------------------------------------------
# rate_limit – async functions
# ---------------------------------------------------------------------------


def test_check_rate_limit_not_blocked():
    """ブロックなし → (True, None, None)"""
    from rate_limit import check_rate_limit

    mock_r = AsyncMock()
    mock_r.get = AsyncMock(return_value=None)

    with patch("rate_limit.get_redis_client", return_value=mock_r):
        allowed, until, label = asyncio.run(check_rate_limit("qr", "10.0.0.1"))

    assert allowed is True
    assert until is None
    assert label is None


def test_check_rate_limit_blocked():
    """ブロック中 → (False, until, label)"""
    from rate_limit import check_rate_limit

    mock_r = AsyncMock()
    mock_r.get = AsyncMock(return_value="1日")
    mock_r.ttl = AsyncMock(return_value=3600)

    with patch("rate_limit.get_redis_client", return_value=mock_r):
        allowed, until, label = asyncio.run(check_rate_limit("qr", "10.0.0.1"))

    assert allowed is False
    assert label == "1日"
    assert until is not None


def test_check_rate_limit_redis_error_fails_open():
    """Redis エラー時はフェイルオープン → True"""
    from rate_limit import check_rate_limit

    mock_r = AsyncMock()
    mock_r.get = AsyncMock(side_effect=Exception("Redis down"))

    with patch("rate_limit.get_redis_client", return_value=mock_r):
        allowed, _, _ = asyncio.run(check_rate_limit("qr", "10.0.0.1"))

    assert allowed is True


def test_register_failure_below_threshold_no_block():
    """しきい値未満の失敗ではブロックされない"""
    from rate_limit import register_failure

    mock_r = AsyncMock()
    mock_r.get = AsyncMock(return_value=None)
    mock_r.incr = AsyncMock(return_value=1)
    mock_r.expire = AsyncMock()

    with patch("rate_limit.get_redis_client", return_value=mock_r):
        until, label = asyncio.run(register_failure("qr", "10.0.0.1"))

    assert until is None
    assert label is None


def test_register_failure_10_triggers_30min_block():
    """10回失敗 → 30分ブロック"""
    from rate_limit import register_failure

    mock_r = AsyncMock()
    mock_r.get = AsyncMock(return_value=None)
    mock_r.incr = AsyncMock(return_value=10)
    mock_r.set = AsyncMock()
    mock_r.delete = AsyncMock()

    with patch("rate_limit.get_redis_client", return_value=mock_r):
        until, label = asyncio.run(register_failure("qr", "10.0.0.1"))

    assert label == "30分"
    assert until is not None


def test_register_failure_50_triggers_1day_block():
    """50回失敗 → 1日ブロック"""
    from rate_limit import register_failure

    mock_r = AsyncMock()
    mock_r.get = AsyncMock(return_value=None)
    mock_r.incr = AsyncMock(return_value=50)
    mock_r.set = AsyncMock()
    mock_r.delete = AsyncMock()

    with patch("rate_limit.get_redis_client", return_value=mock_r):
        until, label = asyncio.run(register_failure("qr", "10.0.0.1"))

    assert label == "1日"
    assert until is not None


def test_register_failure_already_blocked_returns_existing():
    """すでにブロック中なら既存のブロック情報を返す"""
    from rate_limit import register_failure

    mock_r = AsyncMock()
    mock_r.get = AsyncMock(return_value="30分")
    mock_r.ttl = AsyncMock(return_value=1800)

    with patch("rate_limit.get_redis_client", return_value=mock_r):
        until, label = asyncio.run(register_failure("qr", "10.0.0.1"))

    assert label == "30分"
    assert until is not None


def test_register_failure_redis_error_returns_none():
    """Redis エラー時は (None, None) を返す"""
    from rate_limit import register_failure

    mock_r = AsyncMock()
    mock_r.get = AsyncMock(side_effect=Exception("Redis down"))

    with patch("rate_limit.get_redis_client", return_value=mock_r):
        until, label = asyncio.run(register_failure("qr", "10.0.0.1"))

    assert until is None
    assert label is None


def test_register_success_deletes_keys():
    """成功時はカウンターとブロックキーを削除する"""
    from rate_limit import register_success

    mock_r = AsyncMock()
    mock_r.delete = AsyncMock()

    with patch("rate_limit.get_redis_client", return_value=mock_r):
        asyncio.run(register_success("qr", "10.0.0.1"))

    mock_r.delete.assert_awaited_once()


def test_register_success_redis_error_does_not_raise():
    """Redis エラー時も例外を発生させない"""
    from rate_limit import register_success

    mock_r = AsyncMock()
    mock_r.delete = AsyncMock(side_effect=Exception("Redis down"))

    with patch("rate_limit.get_redis_client", return_value=mock_r):
        asyncio.run(register_success("qr", "10.0.0.1"))  # must not raise


def test_check_exponential_backoff_blocked():
    """指数バックオフ中なら False を返す"""
    from rate_limit import check_exponential_backoff

    mock_r = AsyncMock()
    mock_r.get = AsyncMock(return_value="4秒")
    mock_r.ttl = AsyncMock(return_value=4)

    with patch("rate_limit.get_redis_client", return_value=mock_r):
        allowed, until, label = asyncio.run(
            check_exponential_backoff("group_file_delete", "10.0.0.1:abc123")
        )

    assert allowed is False
    assert until is not None
    assert label == "4秒"


def test_register_exponential_backoff_failure_doubles_delay():
    """失敗回数に応じて指数バックオフを設定する"""
    from rate_limit import register_exponential_backoff_failure

    mock_r = AsyncMock()
    mock_r.incr = AsyncMock(return_value=3)
    mock_r.set = AsyncMock()

    with patch("rate_limit.get_redis_client", return_value=mock_r):
        until, label = asyncio.run(
            register_exponential_backoff_failure(
                "group_file_delete",
                "10.0.0.1:abc123",
                base_seconds=2,
                max_seconds=300,
            )
        )

    assert until is not None
    assert label == "8秒"
    mock_r.set.assert_awaited_once()


def test_clear_exponential_backoff_deletes_keys():
    """成功時は指数バックオフのキーを削除する"""
    from rate_limit import clear_exponential_backoff

    mock_r = AsyncMock()
    mock_r.delete = AsyncMock()

    with patch("rate_limit.get_redis_client", return_value=mock_r):
        asyncio.run(clear_exponential_backoff("group_file_delete", "10.0.0.1:abc123"))

    mock_r.delete.assert_awaited_once()


# ---------------------------------------------------------------------------
# Admin.db_admin – helper functions
# ---------------------------------------------------------------------------


def test_validate_recent_limit_valid():
    from Admin.db_admin import _validate_recent_limit

    assert _validate_recent_limit(10) == 10


def test_validate_recent_limit_zero_raises():
    from Admin.db_admin import _validate_recent_limit

    with pytest.raises(ValueError):
        _validate_recent_limit(0)


def test_validate_recent_limit_negative_raises():
    from Admin.db_admin import _validate_recent_limit

    with pytest.raises(ValueError):
        _validate_recent_limit(-5)


def test_validate_recent_limit_non_int_raises():
    from Admin.db_admin import _validate_recent_limit

    with pytest.raises(TypeError):
        _validate_recent_limit("10")


def test_resolve_file_path_multiple_type():
    from Admin.db_admin import _resolve_file_path

    record = {"secure_id": "abc123-uid-file", "file_type": "multiple"}
    path, stored_name, display_name, mimetype = _resolve_file_path(record)

    assert stored_name == "abc123-uid-file.zip"
    assert display_name == "abc123-uid-file.zip"
    assert mimetype == "application/zip"
    assert path.endswith(stored_name)


def test_resolve_file_path_single_type_with_original_name():
    from Admin.db_admin import _resolve_file_path

    record = {
        "secure_id": "abc123-uid-file",
        "file_type": "single",
        "original_filename": "myfile.txt",
    }
    path, stored_name, display_name, mimetype = _resolve_file_path(record)

    assert stored_name == "abc123-uid-file.enc"
    assert display_name == "myfile.txt"
    assert mimetype == "application/octet-stream"


def test_resolve_file_path_single_type_no_original_name():
    from Admin.db_admin import _resolve_file_path

    record = {
        "secure_id": "abc123-uid-file",
        "file_type": "single",
        "original_filename": "",
    }
    _, stored_name, display_name, _ = _resolve_file_path(record)

    assert stored_name == "abc123-uid-file.enc"
    assert display_name == stored_name


def test_get_room_folder_valid():
    from Admin.db_admin import _get_room_folder

    folder = _get_room_folder("abc123")
    assert folder is not None
    assert "abc123" in folder


def test_get_room_folder_empty_string_returns_none():
    from Admin.db_admin import _get_room_folder

    assert _get_room_folder("") is None


def test_get_room_folder_none_returns_none():
    from Admin.db_admin import _get_room_folder

    assert _get_room_folder(None) is None


def test_collect_room_files_missing_dir_returns_empty():
    from Admin.db_admin import _collect_room_files

    result = _collect_room_files("nonexistent_room_xyz_99999")
    assert result == []


def test_collect_room_files_with_files():
    """ファイルが存在するディレクトリからファイル一覧を返す"""
    import os
    import tempfile

    from Admin.db_admin import _collect_room_files

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("Admin.db_admin.GROUP_UPLOAD_DIR", tmpdir):
            # Create a fake room directory with a file
            folder = os.path.join(tmpdir, "testroom")
            os.makedirs(folder)
            with open(os.path.join(folder, "hello.txt"), "w") as f:
                f.write("content")

            result = _collect_room_files("testroom")

    assert len(result) == 1
    assert result[0]["stored_name"] == "hello.txt"
    assert result[0]["size"] == 7


# ---------------------------------------------------------------------------
# Note.note_sync – _format_updated_at
# ---------------------------------------------------------------------------


def test_format_updated_at_with_datetime():
    from datetime import datetime

    from Note.note_sync import _format_updated_at

    dt = datetime(2026, 1, 1, 12, 0, 0, 123456)
    result = _format_updated_at(dt)
    assert "2026-01-01 12:00:00" in result


def test_format_updated_at_with_none():
    from Note.note_sync import _format_updated_at

    assert _format_updated_at(None) is None


# ---------------------------------------------------------------------------
# Note.note_sync – sync_note_content
# ---------------------------------------------------------------------------


def test_sync_note_content_too_long_returns_400():
    """コンテンツが最大長を超える場合は 400 エラーを返す"""
    from Note.note_sync import MAX_CONTENT_LENGTH, sync_note_content

    long_content = "x" * (MAX_CONTENT_LENGTH + 1)
    payload, status, changed = asyncio.run(
        sync_note_content("room1", long_content, None, None)
    )

    assert status == 400
    assert changed is False
    assert "error" in payload


def test_sync_note_content_missing_params_uses_fallback():
    """last_known_updated_at が None の場合は無条件フォールバックを使う"""
    from datetime import datetime

    from Note.note_sync import sync_note_content

    mock_row = {"content": "saved", "updated_at": datetime(2026, 1, 1)}

    with (
        patch("Note.note_sync.nd.save_content", new_callable=AsyncMock),
        patch(
            "Note.note_sync.nd.get_row", new_callable=AsyncMock, return_value=mock_row
        ),
    ):
        payload, status, changed = asyncio.run(
            sync_note_content("room1", "new content", None, None)
        )

    assert status == 200
    assert payload["status"] == "ok"
    assert payload["data"]["note_status"] == "ok_unconditional_fallback"
    assert changed is True


def test_sync_note_content_successful_save_returns_ok():
    """rowcount > 0 の正常保存は status=ok を返す"""
    from datetime import datetime

    from Note.note_sync import sync_note_content

    mock_row = {"content": "new content", "updated_at": datetime(2026, 1, 1)}

    with (
        patch("Note.note_sync.nd.save_content", new_callable=AsyncMock, return_value=1),
        patch(
            "Note.note_sync.nd.get_row", new_callable=AsyncMock, return_value=mock_row
        ),
    ):
        payload, status, changed = asyncio.run(
            sync_note_content(
                "room1",
                "new content",
                "2026-01-01 00:00:00.000000",
                "original",
            )
        )

    assert status == 200
    assert payload["status"] == "ok"
    assert payload["data"]["note_status"] == "ok"
    assert changed is True


def test_sync_note_content_conflict_max_retries_returns_409():
    """rowcount == 0 が続き merge も失敗する場合は 409 を返す"""
    from datetime import datetime

    from Note.note_sync import sync_note_content

    mock_row = {"content": "server content", "updated_at": datetime(2026, 1, 1)}

    with (
        patch("Note.note_sync.nd.save_content", new_callable=AsyncMock, return_value=0),
        patch(
            "Note.note_sync.nd.get_row", new_callable=AsyncMock, return_value=mock_row
        ),
        patch(
            "Note.note_sync.attempt_merge", new_callable=AsyncMock, return_value=None
        ),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        payload, status, changed = asyncio.run(
            sync_note_content(
                "room1",
                "client content",
                "2026-01-01 00:00:00.000000",
                "original",
            )
        )

    assert status == 409
    assert payload["status"] == "error"
    assert payload["data"]["note_status"] == "conflict_max_retries"
    assert changed is False


# ---------------------------------------------------------------------------
# file_validation
# ---------------------------------------------------------------------------


def test_validate_upload_limits_rejects_too_many_files():
    from io import BytesIO
    from types import SimpleNamespace

    from file_validation import validate_upload_limits

    files = [
        SimpleNamespace(filename="a.txt", file=BytesIO(b"a")),
        SimpleNamespace(filename="b.txt", file=BytesIO(b"b")),
    ]

    error = validate_upload_limits(
        files,
        max_files=1,
        max_total_size_bytes=10,
        max_total_size_mb=1,
    )

    assert error == "ファイル数は最大1個までです。"


def test_validate_upload_limits_rejects_too_large_total_size():
    from io import BytesIO
    from types import SimpleNamespace

    from file_validation import validate_upload_limits

    files = [SimpleNamespace(filename="a.txt", file=BytesIO(b"abcd"))]

    error = validate_upload_limits(
        files,
        max_files=10,
        max_total_size_bytes=3,
        max_total_size_mb=1,
    )

    assert error == "ファイルの合計サイズは1MBまでです。"


def test_validate_requested_filename_blocks_dangerous_pattern():
    from file_validation import validate_requested_filename

    assert (
        validate_requested_filename("../secret.txt")
        == "不正なファイル名が検出されました。"
    )


def test_validate_requested_filename_blocks_blank_string():
    from file_validation import validate_requested_filename

    assert validate_requested_filename("   ") == "無効なファイル名です。"


def test_normalize_upload_filename_uses_secure_filename():
    from file_validation import normalize_upload_filename

    assert normalize_upload_filename("../hello.txt") == "hello.txt"


def test_sanitize_group_upload_filename_falls_back_when_hidden():
    from file_validation import sanitize_group_upload_filename

    with patch("file_validation.time.time", return_value=1234567890):
        result = sanitize_group_upload_filename(".bashrc")

    assert result == "file_1234567890"


def test_build_content_disposition_attachment_uses_rfc5987():
    from file_validation import build_content_disposition_attachment

    header = build_content_disposition_attachment('evil\r\nx: y".txt')

    assert "\r" not in header
    assert "\n" not in header
    assert 'filename="evilx: y.txt"' in header
    assert "filename*=UTF-8''evilx%3A%20y.txt" in header


def test_validate_upload_file_content_blocks_svg_mime():
    from io import BytesIO
    from types import SimpleNamespace

    from file_validation import validate_upload_file_content

    upload = SimpleNamespace(filename="image.png", file=BytesIO(b"<svg></svg>"))
    detector = SimpleNamespace(from_buffer=lambda _: "image/svg+xml")

    with patch("file_validation._MIME_DETECTOR", detector):
        result = validate_upload_file_content(upload)

    assert result == "HTML/SVG ファイルはアップロードできません。"
