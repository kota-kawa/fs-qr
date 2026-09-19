"""Group アップロードの同時実行時整合性を検証する。"""

import io
from types import SimpleNamespace
from unittest.mock import patch


def _upload(name: str, content: bytes):
    return SimpleNamespace(filename=name, file=io.BytesIO(content))


def test_group_upload_renames_duplicate_names_under_room_lock(tmp_path):
    from Group import group_routes_file as routes

    upload_root = tmp_path / "uploads"
    room_path = upload_root / "abc123"
    room_path.mkdir(parents=True)

    def save(file):
        saved, errors, rejected = [], [], []
        with (
            patch.object(routes, "UPLOAD_FOLDER", str(upload_root)),
            patch.object(routes, "validate_upload_file_content", return_value=None),
        ):
            result = routes._save_uploaded_files(
                [file],
                room_id="abc123",
                save_path=str(room_path),
                saved_files=saved,
                error_files=errors,
                rejected_files=rejected,
            )
        return result, saved, errors, rejected

    assert save(_upload("report.txt", b"first"))[1] == ["report.txt"]
    result, saved, errors, rejected = save(_upload("report.txt", b"second"))

    assert result is None
    assert saved == ["report (1).txt"]
    assert errors == []
    assert rejected == []
    assert (room_path / "report.txt").read_bytes() == b"first"
    assert (room_path / "report (1).txt").read_bytes() == b"second"
    assert (
        not (room_path / ".fsqr-upload.lock").is_file()
        or (room_path / ".fsqr-upload.lock").stat().st_size == 0
    )
