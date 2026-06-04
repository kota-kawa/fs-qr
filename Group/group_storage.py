import os

from werkzeug.utils import secure_filename

from settings import BASE_DIR, GROUP_UPLOAD_DIR


STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_FOLDER = GROUP_UPLOAD_DIR
LEGACY_UPLOAD_FOLDER = os.path.join(STATIC_DIR, "group_uploads")


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
