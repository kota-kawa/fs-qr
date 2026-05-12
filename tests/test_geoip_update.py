import gzip
import os


def test_candidate_urls_include_current_and_previous_month(monkeypatch):
    from datetime import datetime, timezone

    import geoip_update

    monkeypatch.setattr(geoip_update, "GEOIP_DB_SOURCE_URL", "")

    urls = geoip_update._candidate_urls(datetime(2026, 5, 12, tzinfo=timezone.utc))

    assert urls[0].endswith("dbip-country-lite-2026-05.mmdb.gz")
    assert urls[1].endswith("dbip-country-lite-2026-04.mmdb.gz")


def test_update_geoip_database_replaces_target_atomically(tmp_path, monkeypatch):
    import geoip_update

    db_path = tmp_path / "dbip-country-lite.mmdb"
    source_gz = tmp_path / "source.mmdb.gz"
    source_data = b"fake-mmdb"
    with gzip.open(source_gz, "wb") as fp:
        fp.write(source_data)

    def fake_download(url, destination):
        with open(source_gz, "rb") as src, open(destination, "wb") as dst:
            dst.write(src.read())
        return "fake-sha256"

    monkeypatch.setattr(geoip_update, "GEOIP_DB_PATH", str(db_path))
    monkeypatch.setattr(geoip_update, "GEOIP_AUTO_UPDATE", True)
    monkeypatch.setattr(
        geoip_update, "GEOIP_DB_SOURCE_URL", "https://example.com/db.mmdb.gz"
    )
    monkeypatch.setattr(geoip_update, "_download", fake_download)
    monkeypatch.setattr(geoip_update, "_validate_mmdb", lambda path: None)

    assert geoip_update.update_geoip_database(force=True) is True
    assert db_path.read_bytes() == source_data
    assert os.path.exists(f"{db_path}.metadata")
