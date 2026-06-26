from pathlib import Path
import shutil
import tempfile
import zipfile

from PIL import Image, ImageSequence

from src.app_paths import EMOJI_DIR, EMOJI_SMALL_DIR, ensure_app_dirs


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif"}
THUMBNAIL_SIZE = (100, 100)
_emoji_index = None


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
    _emoji_index = sorted(images, key=lambda path: path.stat().st_ctime, reverse=True)
    return list(_emoji_index)


def get_emoji_index():
    global _emoji_index
    if _emoji_index is None:
        refresh_index()
    return _emoji_index


def import_images(filenames):
    imported = 0
    for filename in filenames:
        source = Path(filename)
        if not source.is_file() or source.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if _import_image_file(source):
            imported += 1
    if imported:
        refresh_index()
    return imported


def import_zip_files(filenames):
    imported = 0
    for filename in filenames:
        archive_path = Path(filename)
        if not archive_path.is_file():
            continue

        with tempfile.TemporaryDirectory(prefix="cEmoji_") as temp_dir:
            extract_dir = Path(temp_dir)
            _extract_zip(archive_path, extract_dir)
            imported += import_images(extract_dir.rglob("*"))
    if imported:
        refresh_index()
    return imported


def import_clipboard_image(image, filename):
    ensure_app_dirs()
    destination = EMOJI_DIR / filename
    if destination.exists():
        return False
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
        refresh_index()
    return removed


def original_image_path(filename):
    return EMOJI_DIR / filename


def _import_image_file(source):
    ensure_app_dirs()
    destination = EMOJI_DIR / source.name
    if destination.exists():
        return False

    shutil.copy2(source, destination)
    create_thumbnail(destination, EMOJI_SMALL_DIR / source.name)
    return True


def create_thumbnail(source, destination):
    with Image.open(source) as image:
        if image.format == "GIF":
            _create_gif_thumbnail(image, destination)
            return

        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")
        image.thumbnail(THUMBNAIL_SIZE)
        image.save(destination, quality=100)


def _create_gif_thumbnail(image, destination):
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


def _safe_zip_path(info):
    filename = _decode_zip_filename(info)
    relative_path = Path(filename)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return None
    return relative_path


def _decode_zip_filename(info):
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("gbk")
    except UnicodeError:
        return info.filename
