from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

from share_links import encrypt_share_password


def _fresh_client(test_client):
    return test_client.__class__(test_client.app)


def test_e2e_fsqr_upload_search_share_download_and_delete(test_client, tmp_path):
    room_id = "fqe2e1"
    password = "135790"
    secure_id = f"{room_id}-1234567890-report.txt"
    share_token = "fsqr-e2e-share-token-1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    record = {
        "id": room_id,
        "password": "scrypt:hashed-password",
        "secure_id": secure_id,
        "file_type": "single",
        "original_filename": "report.txt",
        "retention_days": 3,
        "time": None,
    }
    link = {
        "service_key": "fsqr",
        "resource_id": secure_id,
        "metadata": {
            "id": room_id,
            "password_enc": encrypt_share_password(password),
        },
    }

    remove_mock = AsyncMock()
    with (
        patch("FSQR.fsqr_app.STATIC", str(tmp_path)),
        patch("FSQR.fsqr_app.uuid.uuid4", return_value="1234567890abcdef"),
        patch(
            "FSQR.fsqr_app.create_share_link",
            new=AsyncMock(return_value=share_token),
        ),
        patch("FSQR.fsqr_data.save_file", new_callable=AsyncMock) as save_mock,
        patch(
            "FSQR.fsqr_data.get_data",
            new_callable=AsyncMock,
            return_value=[record],
        ),
        patch(
            "FSQR.fsqr_data.get_data_by_credentials",
            new_callable=AsyncMock,
            return_value=[record],
        ),
        patch("FSQR.fsqr_data.remove_data", remove_mock),
        patch(
            "FSQR.fsqr_app.resolve_share_link",
            new=AsyncMock(return_value=link),
        ),
        patch(
            "FSQR.fsqr_app.check_rate_limit",
            new=AsyncMock(return_value=(True, None, None)),
        ),
        patch("FSQR.fsqr_app.register_success", new=AsyncMock()),
    ):
        upload_response = test_client.post(
            "/upload",
            files={
                "upfile": (
                    "report.txt.enc",
                    b"encrypted-by-browser",
                    "application/octet-stream",
                )
            },
            data={
                "name": room_id,
                "download_password": password,
                "file_type": "single",
                "original_filename": "report.txt",
                "retention_days": "3",
            },
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
        )
        assert upload_response.status_code == 200
        assert upload_response.json()["data"]["redirect_url"] == (
            f"/upload_complete/{secure_id}"
        )
        assert (tmp_path / f"{secure_id}.enc").read_bytes() == b"encrypted-by-browser"
        save_mock.assert_awaited_once()

        complete_response = test_client.get(f"/upload_complete/{secure_id}")
        assert complete_response.status_code == 200
        assert "report.txt" in complete_response.text
        assert share_token in complete_response.text
        assert password in complete_response.text

        search_client = _fresh_client(test_client)
        search_response = search_client.post(
            "/try_login",
            data={"name": room_id, "pw": password},
        )
        assert search_response.status_code == 302
        assert search_response.headers["location"] == f"/download/{secure_id}"

        download_page = search_client.get(search_response.headers["location"])
        assert download_page.status_code == 200
        assert password in download_page.text

        direct_download = search_client.post(f"/download_go/{secure_id}")
        assert direct_download.status_code == 200
        assert direct_download.content == b"encrypted-by-browser"
        assert direct_download.headers["x-file-type"] == "single"

        share_client = _fresh_client(test_client)
        share_response = share_client.get(f"/fs-qr/s/{share_token}")
        assert share_response.status_code == 200
        assert password in share_response.text
        assert "scrypt:hashed-password" not in share_response.text

        share_download = share_client.post(f"/fs-qr/s/{share_token}/download")
        assert share_download.status_code == 200
        assert share_download.content == b"encrypted-by-browser"

        delete_response = test_client.post(f"/fs-qr/delete/{secure_id}")
        assert delete_response.status_code == 302
        assert delete_response.headers["location"] == "/remove-succes"
        remove_mock.assert_awaited_once_with(secure_id)


def test_e2e_group_room_create_join_file_operations_and_delete(test_client, tmp_path):
    room_id = "ge2e01"
    password = "000042"
    share_token = "group-e2e-share-token-1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    room_record = {
        "id": room_id,
        "room_id": room_id,
        "password": password,
        "retention_days": 7,
        "time": None,
    }
    state = {"exists": False}

    async def get_group_data(candidate_room_id):
        if state["exists"] and candidate_room_id == room_id:
            return [room_record]
        return None

    async def create_group_room(**_kwargs):
        state["exists"] = True

    async def pick_group_room(candidate_id, candidate_password):
        if (
            state["exists"]
            and candidate_id == room_id
            and candidate_password == password
        ):
            return room_id
        return None

    async def remove_group_room(candidate_room_id):
        if candidate_room_id == room_id:
            state["exists"] = False
            return True
        return False

    detector = type("Detector", (), {"from_buffer": lambda self, _: "text/plain"})()
    legacy_root = tmp_path / "legacy"
    with (
        patch("Group.group_routes_room.UPLOAD_FOLDER", str(tmp_path)),
        patch("Group.group_routes_file.UPLOAD_FOLDER", str(tmp_path)),
        patch("Group.group_storage.LEGACY_UPLOAD_FOLDER", str(legacy_root)),
        patch(
            "Group.group_routes_room.generate_room_password",
            return_value=password,
        ),
        patch(
            "Group.group_routes_room.create_share_link",
            new=AsyncMock(return_value=share_token),
        ),
        patch(
            "Group.group_routes_room.resolve_share_link",
            new=AsyncMock(
                return_value={
                    "service_key": "group",
                    "resource_id": room_id,
                    "metadata": {
                        "id": room_id,
                        "password_enc": encrypt_share_password(password),
                    },
                }
            ),
        ),
        patch(
            "Group.group_routes_room.group_data.get_data",
            new=AsyncMock(side_effect=get_group_data),
        ),
        patch(
            "Group.group_routes_room.group_data.create_room",
            new=AsyncMock(side_effect=create_group_room),
        ) as create_mock,
        patch(
            "Group.group_routes_room.group_data.pich_room_id",
            new=AsyncMock(side_effect=pick_group_room),
        ),
        patch(
            "Group.group_routes_room.group_data.remove_data",
            new=AsyncMock(side_effect=remove_group_room),
        ) as remove_mock,
        patch(
            "Group.group_routes_room.check_rate_limit",
            new=AsyncMock(return_value=(True, None, None)),
        ),
        patch("Group.group_routes_room.register_success", new=AsyncMock()),
        patch("file_validation._MIME_DETECTOR", detector),
        patch("Group.group_routes_file.notify_group_files_updated", new=AsyncMock()),
        patch(
            "Group.group_routes_file.check_exponential_backoff",
            new=AsyncMock(return_value=(True, None, None)),
        ),
        patch("Group.group_routes_file.clear_exponential_backoff", new=AsyncMock()),
    ):
        assert test_client.get("/group").status_code == 200
        assert test_client.get("/create_room").status_code == 200

        create_response = test_client.post(
            "/create_group_room",
            data={"id": room_id, "idMode": "manual", "retention_days": "7"},
            headers={"X-Requested-With": "fetch", "Accept": "application/json"},
        )
        assert create_response.status_code == 200
        create_payload = create_response.json()["data"]
        assert create_payload["redirect_url"] == f"/group/r/{room_id}"
        assert create_payload["password"] == password
        assert create_payload["share_url"].endswith(f"/group/s/{share_token}")
        create_mock.assert_awaited_once()

        room_response = test_client.get(create_payload["redirect_url"])
        assert room_response.status_code == 200
        assert password in room_response.text
        assert share_token in room_response.text

        search_client = _fresh_client(test_client)
        search_response = search_client.post(
            "/search_group_process",
            data={"id": room_id, "password": password},
        )
        assert search_response.status_code == 302
        assert search_response.headers["location"] == f"/group/r/{room_id}"
        assert search_client.get(search_response.headers["location"]).status_code == 200

        share_client = _fresh_client(test_client)
        share_response = share_client.get(f"/group/s/{share_token}")
        assert share_response.status_code == 200
        assert password in share_response.text

        upload_response = test_client.post(
            f"/group_upload/{room_id}",
            files=[
                ("upfile", ("notes.txt", b"group notes", "text/plain")),
                ("upfile", ("summary.md", b"# summary", "text/markdown")),
            ],
        )
        assert upload_response.status_code == 200
        assert upload_response.json()["data"]["saved_files"] == [
            "notes.txt",
            "summary.md",
        ]

        list_response = test_client.get(f"/check/{room_id}")
        assert list_response.status_code == 200
        files = list_response.json()["data"]["files"]
        assert [item["name"] for item in files] == ["notes.txt", "summary.md"]
        assert files[0]["previewable"] is True

        preview_response = test_client.get(f"/preview/{room_id}/notes.txt")
        assert preview_response.status_code == 200
        assert preview_response.content == b"group notes"

        download_response = test_client.get(f"/download/{room_id}/notes.txt")
        assert download_response.status_code == 200
        assert download_response.content == b"group notes"

        archive_response = test_client.get(f"/download/all/{room_id}")
        assert archive_response.status_code == 200
        assert archive_response.headers["content-type"] == "application/zip"

        delete_file_response = test_client.delete(f"/delete/{room_id}/summary.md")
        assert delete_file_response.status_code == 200
        assert not (tmp_path / room_id / "summary.md").exists()

        delete_room_response = test_client.post(f"/group/r/{room_id}/delete")
        assert delete_room_response.status_code == 302
        assert delete_room_response.headers["location"] == "/remove-succes"
        remove_mock.assert_awaited_once_with(room_id)


def test_e2e_note_room_create_join_sync_share_and_delete(test_client):
    room_id = "ne2e01"
    password = "246810"
    share_token = "note-e2e-share-token-1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    expires_at = datetime(2099, 1, 8, 9, 0, 0)
    meta = {"id": room_id, "retention_days": 7, "expires_at": expires_at}
    row = {
        "content": "initial note",
        "updated_at": datetime(2099, 1, 1, 9, 0, 0),
        "version": 0,
    }

    remove_mock = AsyncMock()
    with (
        patch("Note.note_app.generate_room_password", return_value=password),
        patch("Note.note_app._room_id_exists", new=AsyncMock(return_value=False)),
        patch(
            "Note.note_app.create_share_link",
            new=AsyncMock(return_value=share_token),
        ),
        patch(
            "Note.note_app.resolve_share_link",
            new=AsyncMock(
                return_value={
                    "service_key": "note",
                    "resource_id": room_id,
                    "metadata": {
                        "id": room_id,
                        "password_enc": encrypt_share_password(password),
                    },
                }
            ),
        ),
        patch("Note.note_data.create_room", new_callable=AsyncMock) as create_mock,
        patch(
            "Note.note_data.get_room_meta_direct",
            new=AsyncMock(return_value=meta),
        ),
        patch("Note.note_data.get_row", new=AsyncMock(return_value=row)),
        patch("Note.note_data.pick_room_id", new=AsyncMock(return_value=room_id)),
        patch("Note.note_data.remove_room", remove_mock),
        patch(
            "Note.note_app.check_rate_limit",
            new=AsyncMock(return_value=(True, None, None)),
        ),
        patch("Note.note_app.register_success", new=AsyncMock()),
        patch(
            "Note.note_api.sync_note_content",
            new=AsyncMock(
                return_value=(
                    {
                        "data": {
                            "note_status": "ok",
                            "content": "updated note",
                            "version": 1,
                        }
                    },
                    200,
                    None,
                )
            ),
        ) as sync_mock,
        patch("Note.note_app.note_ws_hub.broadcast", new_callable=AsyncMock),
        patch("Note.note_app.publish_room_expired", new_callable=AsyncMock),
        patch("Note.note_app.note_ws_hub.close_room", new_callable=AsyncMock),
    ):
        assert test_client.get("/note").status_code == 200
        assert test_client.get("/create_note_room").status_code == 200

        create_response = test_client.post(
            "/create_note_room",
            data={"id": room_id, "idMode": "manual", "retention_days": "7"},
            headers={"X-Requested-With": "fetch", "Accept": "application/json"},
        )
        assert create_response.status_code == 200
        create_payload = create_response.json()["data"]
        assert create_payload["redirect_url"] == f"/note/r/{room_id}"
        assert create_payload["password"] == password
        assert create_payload["share_url"].endswith(f"/note/s/{share_token}")
        create_mock.assert_awaited_once_with(
            room_id, password, room_id, retention_days=7
        )

        room_response = test_client.get(create_payload["redirect_url"])
        assert room_response.status_code == 200
        assert password in room_response.text
        assert share_token in room_response.text

        note_get_response = test_client.get(f"/api/note/{room_id}")
        assert note_get_response.status_code == 200
        assert note_get_response.json()["data"]["content"] == "initial note"

        note_post_response = test_client.post(
            f"/api/note/{room_id}",
            json={
                "content": "updated note",
                "base_version": 0,
                "original_content": "initial note",
            },
        )
        assert note_post_response.status_code == 200
        assert note_post_response.json()["data"]["note_status"] == "ok"
        sync_mock.assert_awaited_once_with(
            room_id,
            "updated note",
            0,
            "initial note",
        )

        search_client = _fresh_client(test_client)
        search_response = search_client.post(
            "/search_note_process",
            data={"id": room_id, "password": password},
        )
        assert search_response.status_code == 302
        assert search_response.headers["location"] == f"/note/r/{room_id}"
        assert search_client.get(search_response.headers["location"]).status_code == 200

        share_client = _fresh_client(test_client)
        share_response = share_client.get(f"/note/s/{share_token}")
        assert share_response.status_code == 200
        assert password in share_response.text

        delete_response = test_client.post(f"/note/r/{room_id}/delete")
        assert delete_response.status_code == 302
        assert delete_response.headers["location"] == "/remove-succes"
        remove_mock.assert_awaited_once_with(room_id)
