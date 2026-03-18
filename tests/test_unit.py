"""Pure unit tests – no HTTP, no database, no Redis required."""
from datetime import datetime


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
    assert _is_valid_room_id("abc12")  is False   # 5文字
    assert _is_valid_room_id("abc1234") is False  # 7文字
    assert _is_valid_room_id("abc!@#") is False   # 無効な文字


# ---------------------------------------------------------------------------
# Group.group_app – is_safe_path
# ---------------------------------------------------------------------------

def test_is_safe_path_valid():
    from Group.group_app import is_safe_path
    assert is_safe_path("/var/uploads", "/var/uploads/roomid/file.txt") is True


def test_is_safe_path_traversal():
    from Group.group_app import is_safe_path
    assert is_safe_path("/var/uploads", "/var/uploads/../etc/passwd") is False
