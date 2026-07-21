from pathlib import Path
from dataclasses import dataclass
import hashlib
import json
import shutil
import tempfile
import zipfile

from src.app_paths import EMOJI_DIR, EMOJI_SMALL_DIR, PINNED_FILE, ensure_app_dirs
from src import collection_store


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif"}
THUMBNAIL_SIZE = (100, 100)
_emoji_index = None
_pinned_names = None


@dataclass
class ImportSummary:
    imported: int = 0
    skipped: int = 0
    failed: int = 0
    added_to_collection: int = 0

    def add(self, other):
        self.imported += other.imported
        self.skipped += other.skipped
        self.failed += other.failed
        self.added_to_collection += other.added_to_collection


def count_emojis():
    return len(get_emoji_index())


def list_emojis(search_text="", collection_id=None):
    query = search_text.lower()
    collection_names = collection_store.filenames_for_collection(collection_id)
    paths = [path for path in get_emoji_index() if display_name_for_thumbnail(path) in collection_names]
    if not query:
        return paths
    return [path for path in paths if query in display_title_for_thumbnail(path).lower()]


def refresh_index():
    global _emoji_index
    ensure_app_dirs()
    images = [path for path in EMOJI_SMALL_DIR.iterdir() if path.is_file()]
    pinned_names = _load_pinned_names()
    _emoji_index = sorted(
        images,
        key=lambda path: (
            display_name_for_thumbnail(path) not in pinned_names,
            -path.stat().st_ctime,
        ),
    )
    return list(_emoji_index)


def get_emoji_index():
    global _emoji_index
    if _emoji_index is None:
        refresh_index()
    return _emoji_index


def import_images(filenames, progress_callback=None, collection_id=None):
    summary = ImportSummary()
    candidates = list(filenames)
    total = len(candidates)
    known_hashes = _existing_image_hashes()
    for index, filename in enumerate(candidates, start=1):
        source = Path(filename)
        if progress_callback is not None:
            progress_callback(index - 1, total, source.name)
        if not source.is_file() or source.suffix.lower() not in IMAGE_SUFFIXES:
            summary.failed += 1
            continue
        try:
            result = _import_image_file(source, known_hashes)
        except Exception:
            summary.failed += 1
        else:
            result_status, result_name = result
            if result_status == "imported":
                summary.imported += 1
                collection_store.add_file_to_collection(result_name, collection_id)
                summary.added_to_collection += 1
            elif result_status == "skipped":
                summary.skipped += 1
                if result_name:
                    before = set(collection_store.file_collection_ids(result_name))
                    collection_store.add_file_to_collection(result_name, collection_id)
                    after = set(collection_store.file_collection_ids(result_name))
                    if after != before:
                        summary.added_to_collection += 1
            else:
                summary.failed += 1
        if progress_callback is not None:
            progress_callback(index, total, source.name)
    if summary.imported:
        refresh_index()
    return summary


def import_zip_files(filenames, progress_callback=None, collection_id=None):
    summary = ImportSummary()
    candidates = list(filenames)
    total = _count_zip_image_entries(candidates)
    completed = 0
    for filename in candidates:
        archive_path = Path(filename)
        if progress_callback is not None:
            progress_callback(completed, total, archive_path.name)
        if not archive_path.is_file():
            summary.failed += 1
            continue

        try:
            with tempfile.TemporaryDirectory(prefix="cEmoji_") as temp_dir:
                extract_dir = Path(temp_dir)
                _extract_zip(archive_path, extract_dir)
                image_paths = [path for path in extract_dir.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES]

                def zip_progress(current, _total, inner_filename):
                    if progress_callback is not None:
                        progress_callback(completed + current, total, inner_filename)

                summary.add(import_images(image_paths, zip_progress, collection_id))
                completed += len(image_paths)
                if progress_callback is not None:
                    progress_callback(completed, total, archive_path.name)
        except Exception:
            summary.failed += 1
    if summary.imported:
        refresh_index()
    return summary


def import_clipboard_image(image, filename, collection_id=None):
    ensure_app_dirs()
    destination = EMOJI_DIR / filename
    if destination.exists():
        collection_store.add_file_to_collection(filename, collection_id)
        return False
    image_hash = _pil_image_hash(image)
    existing = find_existing_image_by_hash(image_hash)
    if existing is not None:
        collection_store.add_file_to_collection(existing.name, collection_id)
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    EMOJI_SMALL_DIR.mkdir(parents=True, exist_ok=True)
    image.save(destination, "PNG")
    create_thumbnail(destination, EMOJI_SMALL_DIR / filename)
    collection_store.add_file_to_collection(filename, collection_id)
    refresh_index()
    return True


def delete_emoji(filename):
    removed = False
    for folder in (EMOJI_DIR, EMOJI_SMALL_DIR):
        path = folder / filename
        if path.exists():
            path.unlink()
            removed = True
    if removed:
        collection_store.remove_file(filename)
        set_pinned(filename, False)
        refresh_index()
    return removed


def rename_emoji(filename, new_filename):
    new_filename = Path(new_filename).name.strip()
    if not new_filename:
        return False, "文件名不能为空"

    old_original = EMOJI_DIR / filename
    old_thumbnail = EMOJI_SMALL_DIR / filename
    if not old_original.exists():
        return False, "原图不存在"

    suffix = old_original.suffix
    if Path(new_filename).suffix.lower() not in IMAGE_SUFFIXES:
        new_filename = new_filename + suffix

    if Path(new_filename).suffix.lower() != suffix.lower():
        return False, "不能修改文件格式"

    new_filename = _readable_filename(new_filename)
    new_original = EMOJI_DIR / new_filename
    new_thumbnail = EMOJI_SMALL_DIR / new_filename
    if new_original.exists() or new_thumbnail.exists():
        return False, "同名表情已存在"

    try:
        old_original.rename(new_original)
        if old_thumbnail.exists():
            old_thumbnail.rename(new_thumbnail)
    except OSError as error:
        if new_original.exists() and not old_original.exists():
            try:
                new_original.rename(old_original)
            except OSError:
                pass
        if new_thumbnail.exists() and not old_thumbnail.exists():
            try:
                new_thumbnail.rename(old_thumbnail)
            except OSError:
                pass
        return False, str(error)

    pinned_names = _load_pinned_names()
    if filename in pinned_names:
        pinned_names.discard(filename)
        pinned_names.add(new_filename)
        _save_pinned_names(pinned_names)

    collection_store.rename_file(filename, new_filename)
    refresh_index()
    return True, new_filename


def clear_emojis():
    ensure_app_dirs()
    EMOJI_DIR.mkdir(parents=True, exist_ok=True)
    EMOJI_SMALL_DIR.mkdir(parents=True, exist_ok=True)
    removed = sum(1 for path in EMOJI_DIR.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)
    for folder in (EMOJI_DIR, EMOJI_SMALL_DIR):
        for path in folder.iterdir():
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                try:
                    path.unlink()
                except OSError:
                    pass
    _save_pinned_names(set())
    collection_store.clear_all_items()
    refresh_index()
    return removed


def clear_collection_emojis(collection_id):
    filenames = list(collection_store.filenames_for_collection(collection_id))
    removed_files = 0
    removed_from_collection = 0
    for filename in filenames:
        collection_ids = collection_store.file_collection_ids(filename)
        if len(collection_ids) > 1:
            if collection_store.remove_file_from_collection(filename, collection_id):
                removed_from_collection += 1
        elif delete_emoji(filename):
            removed_files += 1
    refresh_index()
    return removed_files, removed_from_collection


def export_emojis(archive_path, collection_id=None):
    ensure_app_dirs()
    if collection_id is None:
        image_paths = sorted(path for path in EMOJI_DIR.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)
    else:
        filenames = collection_store.filenames_for_collection(collection_id)
        image_paths = sorted(EMOJI_DIR / filename for filename in filenames if (EMOJI_DIR / filename).is_file())
    if not image_paths:
        return 0

    archive_path = Path(archive_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for image_path in image_paths:
            archive.write(image_path, image_path.name)
    return len(image_paths)


def existing_image_hashes():
    return _existing_image_hashes()


def image_content_hash(path):
    return _image_content_hash(Path(path))


def find_existing_image_by_content(source):
    try:
        return find_existing_image_by_hash(_image_content_hash(source))
    except OSError:
        return None


def find_existing_image_by_hash(content_hash):
    ensure_app_dirs()
    for path in EMOJI_DIR.iterdir():
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        try:
            if _image_content_hash(path) == content_hash:
                return path
        except OSError:
            continue
    return None


def original_image_path(filename):
    return EMOJI_DIR / filename


def display_name_for_thumbnail(thumbnail_path):
    return _readable_filename(Path(thumbnail_path).name)


def display_title_for_thumbnail(thumbnail_path):
    return Path(display_name_for_thumbnail(thumbnail_path)).stem


def display_title_for_filename(filename):
    return Path(_readable_filename(filename)).stem


def is_pinned(filename):
    return filename in _load_pinned_names()


def set_pinned(filename, enabled):
    pinned_names = _load_pinned_names()
    if enabled:
        pinned_names.add(filename)
    else:
        pinned_names.discard(filename)
    _save_pinned_names(pinned_names)
    refresh_index()


def _load_pinned_names():
    global _pinned_names
    if _pinned_names is not None:
        return set(_pinned_names)
    try:
        data = json.loads(PINNED_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _pinned_names = set()
        return set()
    if not isinstance(data, list):
        _pinned_names = set()
        return set()
    _pinned_names = {str(name) for name in data}
    return set(_pinned_names)


def _save_pinned_names(pinned_names):
    global _pinned_names
    ensure_app_dirs()
    _pinned_names = set(pinned_names)
    PINNED_FILE.parent.mkdir(parents=True, exist_ok=True)
    PINNED_FILE.write_text(json.dumps(sorted(pinned_names), ensure_ascii=False, indent=2), encoding="utf-8")


def _import_image_file(source, known_hashes=None):
    ensure_app_dirs()
    destination_name = _readable_filename(source.name)
    destination = EMOJI_DIR / destination_name
    if destination.exists():
        return "skipped", destination_name

    source_hash = _image_content_hash(source)
    if known_hashes is None:
        known_hashes = _existing_image_hashes()
    if source_hash in known_hashes:
        existing = find_existing_image_by_hash(source_hash)
        return "skipped", existing.name if existing is not None else ""

    destination.parent.mkdir(parents=True, exist_ok=True)
    EMOJI_SMALL_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    create_thumbnail(destination, EMOJI_SMALL_DIR / destination_name)
    known_hashes.add(source_hash)
    return "imported", destination_name


def _existing_image_hashes():
    ensure_app_dirs()
    EMOJI_DIR.mkdir(parents=True, exist_ok=True)
    hashes = set()
    for path in EMOJI_DIR.iterdir():
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            try:
                hashes.add(_image_content_hash(path))
            except OSError:
                pass
    return hashes


def _image_content_hash(path):
    if Path(path).suffix.lower() == ".gif":
        return _file_hash(path)

    from PIL import Image

    with Image.open(path) as image:
        return _pil_image_hash(image)


def _file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as image_file:
        for chunk in iter(lambda: image_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pil_image_hash(image):
    digest = hashlib.sha256()
    normalized = image.convert("RGBA")
    digest.update(str(normalized.size).encode("utf-8"))
    digest.update(normalized.tobytes())
    return digest.hexdigest()


def create_thumbnail(source, destination):
    from PIL import Image

    with Image.open(source) as image:
        if image.format == "GIF":
            _create_gif_thumbnail(image, destination)
            return

        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")
        image.thumbnail(THUMBNAIL_SIZE)
        image.save(destination, quality=100)


def _create_gif_thumbnail(image, destination):
    from PIL import ImageSequence

    frames = []
    for frame in ImageSequence.Iterator(image):
        frame = frame.copy()
        frame.thumbnail(THUMBNAIL_SIZE)
        frames.append(frame)

    if frames:
        frames[0].save(destination, format="GIF", save_all=True, append_images=frames[1:])


def _extract_zip(archive_path, extract_dir):
    with zipfile.ZipFile(archive_path, "r") as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue

            relative_path = _safe_zip_path(info)
            if relative_path is None:
                continue

            destination = extract_dir / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)


def _count_zip_image_entries(filenames):
    total = 0
    for filename in filenames:
        archive_path = Path(filename)
        if not archive_path.is_file():
            continue
        try:
            with zipfile.ZipFile(archive_path, "r") as archive:
                total += sum(
                    1
                    for info in archive.infolist()
                    if not info.is_dir() and Path(_decode_zip_filename(info)).suffix.lower() in IMAGE_SUFFIXES
                )
        except zipfile.BadZipFile:
            total += 1
    return max(total, 1)


def _safe_zip_path(info):
    filename = _decode_zip_filename(info)
    relative_path = Path(filename)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return None
    return relative_path


def _decode_zip_filename(info):
    if info.flag_bits & 0x800:
        return _readable_filename(info.filename)
    raw_filename = info.filename.encode("cp437", errors="replace")
    candidates = []
    for encoding in ("utf-8", "cp932", "gbk", "big5"):
        try:
            candidates.append(raw_filename.decode(encoding))
        except UnicodeError:
            pass
    candidates.append(info.filename)
    return max(candidates, key=_filename_score)


def _readable_filename(filename):
    candidates = [filename]
    for wrong_encoding in ("cp437", "cp1252", "latin1"):
        try:
            raw_filename = filename.encode(wrong_encoding)
        except UnicodeError:
            continue
        for right_encoding in ("utf-8", "cp932", "gbk", "big5"):
            try:
                candidates.append(raw_filename.decode(right_encoding))
            except UnicodeError:
                pass
    return max(candidates, key=_filename_score)


def _filename_score(filename):
    score = 0
    for character in filename:
        codepoint = ord(character)
        if character in "�ÃÂÄÅÐÑÒÓÔÕÖØÙÚÛÜÝÞßãâäåðñòóôõöøùúûüýþÿ":
            score -= 3
        elif character.isprintable():
            score += 1
        else:
            score -= 5
        if 0x3040 <= codepoint <= 0x30ff or 0x3400 <= codepoint <= 0x9fff:
            score += 3
    return score
