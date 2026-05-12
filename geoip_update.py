import asyncio
import gzip
import hashlib
import json
import logging
import os
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterable

from settings import (
    BASE_DIR,
    GEOIP_AUTO_UPDATE,
    GEOIP_DB_PATH,
    GEOIP_DB_SOURCE_URL,
    GEOIP_UPDATE_INTERVAL_HOURS,
)

logger = logging.getLogger(__name__)

DBIP_COUNTRY_LITE_URL_TEMPLATE = (
    "https://download.db-ip.com/free/dbip-country-lite-{year}-{month:02d}.mmdb.gz"
)
GEOIP_LOCK_STALE_SECONDS = 60 * 60
GEOIP_LOCK_WAIT_SECONDS = 60


def resolve_geoip_db_path() -> str:
    if os.path.isabs(GEOIP_DB_PATH):
        return GEOIP_DB_PATH
    return os.path.join(BASE_DIR, GEOIP_DB_PATH)


def _month_candidates(now: datetime, count: int = 3) -> Iterable[tuple[int, int]]:
    year = now.year
    month = now.month
    for _ in range(count):
        yield year, month
        month -= 1
        if month == 0:
            year -= 1
            month = 12


def _candidate_urls(now: datetime | None = None) -> list[str]:
    if GEOIP_DB_SOURCE_URL:
        return [GEOIP_DB_SOURCE_URL]
    now = now or datetime.now(timezone.utc)
    return [
        DBIP_COUNTRY_LITE_URL_TEMPLATE.format(year=year, month=month)
        for year, month in _month_candidates(now)
    ]


def _is_fresh(path: str) -> bool:
    if not os.path.exists(path):
        return False
    max_age_seconds = GEOIP_UPDATE_INTERVAL_HOURS * 60 * 60
    return time.time() - os.path.getmtime(path) < max_age_seconds


@contextmanager
def _file_lock(lock_path: str, wait_seconds: int = GEOIP_LOCK_WAIT_SECONDS):
    start = time.monotonic()
    fd = None
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("ascii"))
            break
        except FileExistsError:
            try:
                lock_age = time.time() - os.path.getmtime(lock_path)
                if lock_age > GEOIP_LOCK_STALE_SECONDS:
                    os.unlink(lock_path)
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() - start >= wait_seconds:
                raise TimeoutError(
                    f"Timed out waiting for GeoIP update lock: {lock_path}"
                )
            time.sleep(1)

    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(lock_path)
        except FileNotFoundError:
            pass


def _download(url: str, destination: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "fs-qr-geoip-updater/1.0 (+https://fs-qr.com)",
            "Accept": "application/octet-stream",
        },
    )
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=60) as response:
        with open(destination, "wb") as fp:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                fp.write(chunk)
    return digest.hexdigest()


def _decompress_gzip(source: str, destination: str) -> None:
    with gzip.open(source, "rb") as src, open(destination, "wb") as dst:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            dst.write(chunk)


def _validate_mmdb(path: str) -> None:
    import maxminddb

    with maxminddb.open_database(path) as reader:
        record = reader.get("8.8.8.8")
    country = (record or {}).get("country", {})
    if country.get("iso_code") != "US":
        raise RuntimeError("GeoIP database validation failed for 8.8.8.8")


def _write_metadata(path: str, url: str, sha256: str) -> None:
    metadata = {
        "source": "DB-IP Lite Country MMDB",
        "url": url,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "sha256_gzip": sha256,
        "license": "CC BY 4.0",
        "attribution": "IP Geolocation by DB-IP",
    }
    with open(f"{path}.metadata", "w", encoding="utf-8") as fp:
        json.dump(metadata, fp, ensure_ascii=False, indent=2)


def update_geoip_database(force: bool = False) -> bool:
    if not GEOIP_AUTO_UPDATE and not force:
        return False

    db_path = resolve_geoip_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    if not force and _is_fresh(db_path):
        return False

    lock_path = f"{db_path}.lock"
    with _file_lock(lock_path):
        if not force and _is_fresh(db_path):
            return False

        errors = []
        for url in _candidate_urls():
            with tempfile.TemporaryDirectory(prefix="geoip-update-") as tmpdir:
                compressed_path = os.path.join(tmpdir, "geoip.mmdb.gz")
                candidate_path = os.path.join(tmpdir, "geoip.mmdb")
                try:
                    sha256 = _download(url, compressed_path)
                    _decompress_gzip(compressed_path, candidate_path)
                    _validate_mmdb(candidate_path)
                    os.replace(candidate_path, db_path)
                    _write_metadata(db_path, url, sha256)
                    logger.info("GeoIP database updated from %s", url)
                    return True
                except Exception as exc:
                    errors.append(f"{url}: {exc}")
                    logger.warning("GeoIP database update failed from %s: %s", url, exc)

        raise RuntimeError("GeoIP database update failed: " + "; ".join(errors))


async def update_geoip_database_async(force: bool = False) -> bool:
    return await asyncio.to_thread(update_geoip_database, force)


async def geoip_update_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await update_geoip_database_async(force=False)
        except Exception as exc:
            logger.warning("GeoIP database background update failed: %s", exc)
        try:
            await asyncio.wait_for(
                stop_event.wait(), timeout=GEOIP_UPDATE_INTERVAL_HOURS * 60 * 60
            )
        except asyncio.TimeoutError:
            continue


def main() -> int:
    updated = update_geoip_database(force=True)
    print(
        f"GeoIP database {'updated' if updated else 'already current'}: {resolve_geoip_db_path()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
