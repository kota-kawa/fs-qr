import ipaddress
import os
from collections.abc import Callable
from typing import Any

from settings import GEOIP_DB_PATH

_geoip_reader_cache: dict[str, Any] = {"path": None, "mtime": None, "reader": None}


def get_country_code(
    ip: str, reader_factory: Callable[[], Any] | None = None
) -> str | None:
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_private:
            return None
    except ValueError:
        return None

    if reader_factory is None:
        reader_factory = _get_geoip_reader
    reader = reader_factory()
    if not reader:
        return None

    try:
        # maxminddb returns a dict
        record = reader.get(ip)
        if not record:
            return None
        # Support both standard GeoIP2/GeoLite2 (record['country']['iso_code'])
        # and flat schemas (record['country_code']) used in some DBs/tests
        if "country" in record and isinstance(record["country"], dict):
            return record["country"].get("iso_code")
        return record.get("country_code")
    except Exception:
        return None


def _get_geoip_reader():
    if not os.path.exists(GEOIP_DB_PATH):
        return None

    current_mtime = os.path.getmtime(GEOIP_DB_PATH)
    if (
        _geoip_reader_cache["path"] == GEOIP_DB_PATH
        and _geoip_reader_cache["mtime"] == current_mtime
    ):
        return _geoip_reader_cache["reader"]

    import maxminddb

    try:
        reader = maxminddb.open_database(GEOIP_DB_PATH)
        _geoip_reader_cache["path"] = GEOIP_DB_PATH
        _geoip_reader_cache["mtime"] = current_mtime
        _geoip_reader_cache["reader"] = reader
        return reader
    except Exception:
        return None
