from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

from src.app_paths import ETC_DIR, ensure_app_dirs


INDEX_URL = "https://zevalain.github.io/cEmoji/cloud_index.json"
SOURCE_REPOSITORY = "ZevAlain/EmojiPackage"
RAW_BASE_URL = "https://raw.githubusercontent.com/ZevAlain/EmojiPackage/master"
CACHE_FILE = ETC_DIR / "cloud_library_cache.json"
DOWNLOADED_FILE = ETC_DIR / "cloud_downloaded_items.json"
PREVIEW_CACHE_DIR = ETC_DIR / "cloud_preview_cache"
CACHE_TTL_SECONDS = 24 * 60 * 60
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif"}
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_PREVIEW_CACHE_BYTES = 200 * 1024 * 1024
REQUEST_TIMEOUT = 20
USER_AGENT = "cEmoji"


@dataclass(frozen=True)
class CloudEmoji:
    name: str
    path: str
    download_url: str
    size: int = 0

    @property
    def suffix(self):
        return Path(self.name).suffix.lower()

    @property
    def is_gif(self):
        return self.suffix == ".gif"


@dataclass(frozen=True)
class CloudPackage:
    name: str
    path: str
    items: tuple

    @property
    def count(self):
        return len(self.items)

    @property
    def gif_count(self):
        return sum(1 for item in self.items if item.is_gif)

    @property
    def static_count(self):
        return self.count - self.gif_count


def parse_index(index_data):
    packages = []
    for package_data in index_data.get("packages", []):
        items = []
        for item_data in package_data.get("items", []):
            name = Path(str(item_data.get("name", ""))).name
            path = str(item_data.get("path", name))
            suffix = Path(name).suffix.lower()
            path_suffix = Path(path).suffix.lower()
            download_url = str(item_data.get("download_url", ""))
            if not name or suffix not in IMAGE_SUFFIXES or path_suffix not in IMAGE_SUFFIXES or not download_url:
                continue
            items.append(
                CloudEmoji(
                    name=name,
                    path=path,
                    download_url=download_url,
                    size=int(item_data.get("size") or 0),
                )
            )
        if items:
            packages.append(
                CloudPackage(
                    name=str(package_data.get("name") or package_data.get("path") or "未命名合集"),
                    path=str(package_data.get("path") or package_data.get("name") or ""),
                    items=tuple(items),
                )
            )
    return packages


def load_cached_index(max_age_seconds=CACHE_TTL_SECONDS):
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    cached_at = float(data.get("cached_at") or 0)
    if max_age_seconds is not None and time.time() - cached_at > max_age_seconds:
        return None
    index_data = data.get("index")
    return index_data if isinstance(index_data, dict) else None


def save_cached_index(index_data):
    ensure_app_dirs()
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"cached_at": time.time(), "index": index_data}
    CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def load_downloaded_item_hashes():
    try:
        data = json.loads(DOWNLOADED_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(data, dict):
        return {str(path): str(content_hash) for path, content_hash in data.items() if str(path) and str(content_hash)}
    return {}


def mark_downloaded_items(item_hashes):
    ensure_app_dirs()
    downloaded_hashes = load_downloaded_item_hashes()
    downloaded_hashes.update({str(path): str(content_hash) for path, content_hash in item_hashes.items() if str(path) and str(content_hash)})
    DOWNLOADED_FILE.parent.mkdir(parents=True, exist_ok=True)
    DOWNLOADED_FILE.write_text(json.dumps(dict(sorted(downloaded_hashes.items())), ensure_ascii=False, indent=2), encoding="utf-8")
    return downloaded_hashes


def load_local_index():
    candidates = [
        Path(__file__).resolve().parents[1] / "docs" / "public" / "cloud_index.json",
        Path(__file__).resolve().parents[1] / "resource" / "cloud_index.json",
    ]
    for candidate in candidates:
        try:
            return json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    return None


def fetch_index(force_refresh=False):
    if not force_refresh:
        cached = load_cached_index()
        if cached is not None:
            return cached, "cache"

    try:
        index_data = fetch_json(INDEX_URL)
    except Exception:
        stale = load_cached_index(max_age_seconds=None)
        if stale is not None:
            return stale, "stale-cache"
        local_index = load_local_index()
        if local_index is not None:
            return local_index, "local"
        raise

    save_cached_index(index_data)
    return index_data, "remote"


def fetch_json(url):
    data = fetch_bytes(url, max_bytes=8 * 1024 * 1024)
    return json.loads(data.decode("utf-8"))


def fetch_bytes(url, max_bytes=MAX_IMAGE_BYTES):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        chunks = []
        total = 0
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("文件超过大小限制")
            chunks.append(chunk)
    return b"".join(chunks)


def fetch_preview_bytes(item):
    cached = load_preview_cache(item)
    if cached is not None:
        return cached
    data = fetch_bytes(item.download_url, MAX_IMAGE_BYTES)
    if not validate_image_bytes(item.name, data):
        raise ValueError("图片安全校验失败")
    save_preview_cache(item, data)
    return data


def load_preview_cache(item):
    path = preview_cache_path(item)
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if not validate_image_bytes(item.name, data):
        try:
            path.unlink()
        except OSError:
            pass
        return None
    touch_file(path)
    return data


def save_preview_cache(item, data):
    ensure_app_dirs()
    PREVIEW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = preview_cache_path(item)
    path.write_bytes(data)
    touch_file(path)
    trim_preview_cache()


def preview_cache_path(item):
    digest = hashlib.sha256(item.path.encode("utf-8")).hexdigest()
    return PREVIEW_CACHE_DIR / f"{digest}{item.suffix}"


def touch_file(path):
    now = time.time()
    try:
        os.utime(path, (now, now))
    except OSError:
        pass


def trim_preview_cache(max_bytes=MAX_PREVIEW_CACHE_BYTES):
    try:
        files = [path for path in PREVIEW_CACHE_DIR.iterdir() if path.is_file()]
    except OSError:
        return
    entries = []
    total = 0
    for path in files:
        try:
            stat = path.stat()
        except OSError:
            continue
        total += stat.st_size
        entries.append((stat.st_atime, path, stat.st_size))
    if total <= max_bytes:
        return
    for _access_time, path, size in sorted(entries):
        try:
            path.unlink()
        except OSError:
            continue
        total -= size
        if total <= max_bytes:
            break


def validate_image_bytes(filename, data):
    suffix = Path(filename).suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        return False
    if len(data) > MAX_IMAGE_BYTES:
        return False
    return image_data_suffix(data) is not None


def image_data_suffix(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    return None


def download_emoji_to(item, target_dir):
    data = fetch_bytes(item.download_url, MAX_IMAGE_BYTES)
    if not validate_image_bytes(item.name, data):
        raise ValueError("图片安全校验失败")
    target_name = Path(item.name).with_suffix(image_data_suffix(data) or item.suffix).name
    target_path = Path(target_dir) / target_name
    target_path.write_bytes(data)
    return target_path
