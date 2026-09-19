import asyncio
import hashlib
import os
from contextlib import asynccontextmanager, contextmanager

import fcntl

from werkzeug.utils import secure_filename

from settings import BASE_DIR, GROUP_UPLOAD_DIR


STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_FOLDER = GROUP_UPLOAD_DIR
LEGACY_UPLOAD_FOLDER = os.path.join(STATIC_DIR, "group_uploads")
UPLOAD_LOCK_FILENAME = ".fsqr-upload.lock"


def _room_lock_path(room_id, *, primary_root=None):
    """Return a stable lock path outside the room payload directory.

    The lock must survive ``rmtree(room_folder)``.  Hashing the public room ID
    keeps the filename safe even if a caller passes an unexpected value.
    """

    root = os.path.abspath(primary_root or UPLOAD_FOLDER)
    digest = hashlib.sha256(str(room_id).encode("utf-8")).hexdigest()
    return root, os.path.join(root, f".fsqr-upload-{digest}.lock")


def _open_room_lock(room_id, *, primary_root=None):
    root, lock_path = _room_lock_path(room_id, primary_root=primary_root)
    os.makedirs(root, exist_ok=True)
    lock_file = open(lock_path, "a+")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
    except Exception:
        lock_file.close()
        raise
    return lock_file


def _close_room_lock(lock_file):
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    finally:
        lock_file.close()


@contextmanager
def room_upload_lock(room_id, *, primary_root=None):
    """Synchronize file writes/deletes for one room across workers."""

    lock_file = _open_room_lock(room_id, primary_root=primary_root)
    try:
        yield
    finally:
        _close_room_lock(lock_file)


@asynccontextmanager
async def async_room_upload_lock(room_id, *, primary_root=None):
    """Async counterpart that does not block the event loop while waiting."""

    lock_file = await asyncio.to_thread(
        _open_room_lock, room_id, primary_root=primary_root
    )
    try:
        yield
    finally:
        await asyncio.to_thread(_close_room_lock, lock_file)


def is_safe_path(base_path, target_path):
    base_abs = os.path.abspath(base_path)
    target_abs = os.path.abspath(target_path)
    try:
        return os.path.commonpath([target_abs, base_abs]) == base_abs
    except ValueError:
        return False


def room_folder(room_id, *, root=None):
    return os.path.join(root or UPLOAD_FOLDER, secure_filename(str(room_id)))


def iter_room_folders(room_id, *, primary_root=None, include_legacy=True):
    roots = [primary_root or UPLOAD_FOLDER]
    if include_legacy:
        roots.append(LEGACY_UPLOAD_FOLDER)

    seen = set()
    for root in roots:
        root_abs = os.path.abspath(root)
        if root_abs in seen:
            continue
        seen.add(root_abs)
        folder = room_folder(room_id, root=root)
        if is_safe_path(root, folder):
            yield root, folder


def existing_room_folders(room_id, *, primary_root=None, include_legacy=True):
    return [
        (root, folder)
        for root, folder in iter_room_folders(
            room_id, primary_root=primary_root, include_legacy=include_legacy
        )
        if os.path.isdir(folder)
    ]


def collect_room_files(room_id, *, primary_root=None, include_legacy=True):
    files = {}
    for _, folder in iter_room_folders(
        room_id, primary_root=primary_root, include_legacy=include_legacy
    ):
        if not os.path.isdir(folder):
            continue
        for file_name in os.listdir(folder):
            if file_name == UPLOAD_LOCK_FILENAME or file_name.startswith(".fsqr-"):
                continue
            file_path = os.path.join(folder, file_name)
            if os.path.isfile(file_path) and file_name not in files:
                files[file_name] = file_path
    return files


def room_files_usage(room_id, *, primary_root=None, include_legacy=True):
    """Return (file_count, total_size_bytes) for all files stored in a room."""
    files = collect_room_files(
        room_id, primary_root=primary_root, include_legacy=include_legacy
    )
    total_size = 0
    for file_path in files.values():
        try:
            total_size += os.path.getsize(file_path)
        except OSError:
            continue
    return len(files), total_size


def resolve_room_file(room_id, filename, *, primary_root=None, include_legacy=True):
    for _, folder in iter_room_folders(
        room_id, primary_root=primary_root, include_legacy=include_legacy
    ):
        file_path = os.path.join(folder, filename)
        if not is_safe_path(folder, file_path):
            continue
        if os.path.basename(file_path) == UPLOAD_LOCK_FILENAME or os.path.basename(
            file_path
        ).startswith(".fsqr-"):
            continue
        if os.path.isfile(file_path):
            return folder, file_path
    return None, None


def unique_room_filename(room_id, filename, *, primary_root=None):
    existing_names = set(
        collect_room_files(
            room_id, primary_root=primary_root, include_legacy=True
        ).keys()
    )
    if filename not in existing_names:
        return filename

    stem, ext = os.path.splitext(filename)
    counter = 1
    while True:
        candidate = f"{stem} ({counter}){ext}"
        if candidate not in existing_names:
            return candidate
        counter += 1
