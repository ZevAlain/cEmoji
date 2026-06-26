from pathlib import Path
from dataclasses import dataclass
import hashlib
import json
import shutil
import tempfile
import zipfile

from src.app_paths import EMOJI_DIR, EMOJI_SMALL_DIR, PINNED_FILE, ensure_app_dirs


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif"}
THUMBNAIL_SIZE = (100, 100)
_emoji_index = None
_pinned_names = None


@dataclass
class ImportSummary:
    imported: int = 0
    skipped: int = 0
    failed: int = 0

    def add(self, other):
        self.imported += other.imported
        self.skipped += other.skipped
        self.failed += other.failed


def count_emojis():
    return len(get_emoji_index())


def list_emojis(search_text=""):
    query = search_text.lower()
    if not query:
        return list(get_emoji_index())
    return [path for path in get_emoji_index() if query in path.name.lower()]


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


def import_images(filenames, progress_callback=None):
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
            if result == "imported":
                summary.imported += 1
            elif result == "skipped":
                summary.skipped += 1
            else:
                summary.failed += 1
        if progress_callback is not None:
            progress_callback(index, total, source.name)
    if summary.imported:
        refresh_index()
    return summary


def import_zip_files(filenames, progress_callback=None):
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

                summary.add(import_images(image_paths, zip_progress))
                completed += len(image_paths)
                if progress_callback is not None:
                    progress_callback(completed, total, archive_path.name)
        except Exception:
            summary.failed += 1
    if summary.imported:
        refresh_index()
    return summary


def import_clipboard_image(image, filename):
    ensure_app_dirs()
    destination = EMOJI_DIR / filename
    if destination.exists():
        return False
    if _pil_image_hash(image) in _existing_image_hashes():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    EMOJI_SMALL_DIR.mkdir(parents=True, exist_ok=True)
    image.save(destination, "PNG")
    create_thumbnail(destination, EMOJI_SMALL_DIR / filename)
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
        set_pinned(filename, False)
        refresh_index()
    return removed


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
    refresh_index()
    return removed


def original_image_path(filename):
    return EMOJI_DIR / filename


def display_name_for_thumbnail(thumbnail_path):
    return _readable_filename(Path(thumbnail_path).name)


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
        return "skipped"

    source_hash = _image_content_hash(source)
    if known_hashes is None:
        known_hashes = _existing_image_hashes()
    if source_hash in known_hashes:
        return "skipped"

    destination.parent.mkdir(parents=True, exist_ok=True)
    EMOJI_SMALL_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    create_thumbnail(destination, EMOJI_SMALL_DIR / destination_name)
    known_hashes.add(source_hash)
    return "imported"


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
