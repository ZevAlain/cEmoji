from dataclasses import dataclass
from pathlib import Path
import json
import time
import uuid

from src.app_paths import EMOJI_DIR, ETC_DIR, ensure_app_dirs


COLLECTIONS_FILE = ETC_DIR / "local_collections.json"
DEFAULT_COLLECTION_ID = "local"
DEFAULT_COLLECTION_NAME = "本地"
BUILTIN_COLLECTION_ID = "cemoji"
BUILTIN_COLLECTION_NAME = "cEmoji"

_collections_cache = None


@dataclass(frozen=True)
class Collection:
    id: str
    name: str
    created_at: float = 0


def ensure_initialized(assign_missing=True):
    data = load_data()
    changed = False
    if not data["collections"]:
        data["collections"].append({"id": DEFAULT_COLLECTION_ID, "name": DEFAULT_COLLECTION_NAME, "created_at": time.time()})
        data["collections"].append({"id": BUILTIN_COLLECTION_ID, "name": BUILTIN_COLLECTION_NAME, "created_at": time.time()})
        data["active_collection_id"] = DEFAULT_COLLECTION_ID
        changed = True

    existing_ids = {collection["id"] for collection in data["collections"]}
    if DEFAULT_COLLECTION_ID not in existing_ids:
        data["collections"].insert(0, {"id": DEFAULT_COLLECTION_ID, "name": DEFAULT_COLLECTION_NAME, "created_at": time.time()})
        existing_ids.add(DEFAULT_COLLECTION_ID)
        changed = True

    if BUILTIN_COLLECTION_ID not in existing_ids:
        insert_index = 1 if data["collections"] and data["collections"][0]["id"] == DEFAULT_COLLECTION_ID else len(data["collections"])
        data["collections"].insert(insert_index, {"id": BUILTIN_COLLECTION_ID, "name": BUILTIN_COLLECTION_NAME, "created_at": time.time()})
        existing_ids.add(BUILTIN_COLLECTION_ID)
        changed = True

    if data.get("active_collection_id") not in existing_ids:
        data["active_collection_id"] = DEFAULT_COLLECTION_ID
        changed = True

    if assign_missing:
        assigned = set(data["items"])
        for path in image_files():
            if path.name not in assigned:
                data["items"][path.name] = [BUILTIN_COLLECTION_ID]
                changed = True

    valid_names = {path.name for path in image_files()}
    for filename in list(data["items"]):
        if filename not in valid_names:
            del data["items"][filename]
            changed = True
            continue
        ids = [collection_id for collection_id in data["items"][filename] if collection_id in existing_ids]
        if not ids:
            ids = [BUILTIN_COLLECTION_ID]
        if ids != data["items"][filename]:
            data["items"][filename] = ids
            changed = True

    if migrate_default_items_to_builtin(data, valid_names):
        changed = True

    if changed:
        save_data(data)
    return data


def migrate_default_items_to_builtin(data, valid_names):
    if not valid_names:
        return False
    builtin_names = {filename for filename, collection_ids in data["items"].items() if BUILTIN_COLLECTION_ID in collection_ids}
    local_names = {filename for filename, collection_ids in data["items"].items() if DEFAULT_COLLECTION_ID in collection_ids}
    if builtin_names or local_names != valid_names:
        return False

    for filename in valid_names:
        data["items"][filename] = [BUILTIN_COLLECTION_ID]
    return True


def image_files():
    ensure_app_dirs()
    if not EMOJI_DIR.exists():
        return []
    from src import emoji_store

    return [path for path in EMOJI_DIR.iterdir() if path.is_file() and path.suffix.lower() in emoji_store.IMAGE_SUFFIXES]


def load_data():
    global _collections_cache
    if _collections_cache is not None:
        return clone_data(_collections_cache)

    try:
        data = json.loads(COLLECTIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}

    normalized = normalize_data(data)
    _collections_cache = normalized
    return clone_data(normalized)


def normalize_data(data):
    collections = []
    seen = set()
    for raw in data.get("collections", []) if isinstance(data, dict) else []:
        collection_id = str(raw.get("id", "")).strip()
        name = str(raw.get("name", "")).strip()
        if not collection_id or not name or collection_id in seen:
            continue
        seen.add(collection_id)
        collections.append({"id": collection_id, "name": name, "created_at": float(raw.get("created_at") or 0)})

    items = {}
    raw_items = data.get("items", {}) if isinstance(data, dict) else {}
    if isinstance(raw_items, dict):
        for filename, collection_ids in raw_items.items():
            clean_name = Path(str(filename)).name
            if not clean_name:
                continue
            if isinstance(collection_ids, str):
                collection_ids = [collection_ids]
            if not isinstance(collection_ids, list):
                continue
            ids = []
            for collection_id in collection_ids:
                collection_id = str(collection_id).strip()
                if collection_id and collection_id not in ids:
                    ids.append(collection_id)
            if ids:
                items[clean_name] = ids

    return {
        "version": 1,
        "active_collection_id": str(data.get("active_collection_id") or DEFAULT_COLLECTION_ID) if isinstance(data, dict) else DEFAULT_COLLECTION_ID,
        "collections": collections,
        "items": items,
    }


def clone_data(data):
    return json.loads(json.dumps(data, ensure_ascii=False))


def save_data(data):
    global _collections_cache
    ensure_app_dirs()
    COLLECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_data(data)
    _collections_cache = normalized
    COLLECTIONS_FILE.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")


def collections():
    data = ensure_initialized()
    return [Collection(collection["id"], collection["name"], collection.get("created_at", 0)) for collection in data["collections"]]


def active_collection_id():
    return ensure_initialized()["active_collection_id"]


def set_active_collection(collection_id):
    data = ensure_initialized()
    ids = {collection["id"] for collection in data["collections"]}
    if collection_id not in ids:
        return False
    data["active_collection_id"] = collection_id
    save_data(data)
    return True


def collection_name(collection_id):
    for collection in collections():
        if collection.id == collection_id:
            return collection.name
    return DEFAULT_COLLECTION_NAME


def create_collection(name):
    name = unique_collection_name(name)
    data = ensure_initialized()
    collection_id = uuid.uuid4().hex[:12]
    data["collections"].append({"id": collection_id, "name": name, "created_at": time.time()})
    data["active_collection_id"] = collection_id
    save_data(data)
    return collection_id


def unique_collection_name(name):
    base = str(name).strip() or "新合集"
    existing = {collection.name for collection in collections()} if _collections_cache is not None or COLLECTIONS_FILE.exists() else set()
    if base not in existing:
        return base
    index = 2
    while f"{base} {index}" in existing:
        index += 1
    return f"{base} {index}"


def rename_collection(collection_id, name):
    name = str(name).strip()
    if not name:
        return False
    data = ensure_initialized()
    existing = {collection["name"] for collection in data["collections"] if collection["id"] != collection_id}
    if name in existing:
        return False
    for collection in data["collections"]:
        if collection["id"] == collection_id:
            collection["name"] = name
            save_data(data)
            return True
    return False


def delete_collection(collection_id):
    if collection_id == DEFAULT_COLLECTION_ID:
        return []
    data = ensure_initialized()
    filenames = filenames_for_collection(collection_id)
    data["collections"] = [collection for collection in data["collections"] if collection["id"] != collection_id]
    for filename in list(data["items"]):
        ids = [item_id for item_id in data["items"][filename] if item_id != collection_id]
        if ids:
            data["items"][filename] = ids
        else:
            del data["items"][filename]
    if data["active_collection_id"] == collection_id:
        data["active_collection_id"] = DEFAULT_COLLECTION_ID
    save_data(data)
    return filenames


def add_file_to_collection(filename, collection_id=None):
    filename = Path(filename).name
    collection_id = collection_id or active_collection_id()
    data = ensure_initialized(assign_missing=False)
    ids = data["items"].setdefault(filename, [])
    if collection_id not in ids:
        ids.append(collection_id)
    save_data(data)


def add_files_to_collection(filenames, collection_id=None):
    collection_id = collection_id or active_collection_id()
    data = ensure_initialized(assign_missing=False)
    for filename in filenames:
        clean_name = Path(filename).name
        ids = data["items"].setdefault(clean_name, [])
        if collection_id not in ids:
            ids.append(collection_id)
    save_data(data)


def remove_file(filename):
    data = ensure_initialized()
    data["items"].pop(Path(filename).name, None)
    save_data(data)


def remove_file_from_collection(filename, collection_id):
    filename = Path(filename).name
    data = ensure_initialized()
    ids = data["items"].get(filename, [])
    if collection_id not in ids or len(ids) <= 1:
        return False
    data["items"][filename] = [item_id for item_id in ids if item_id != collection_id]
    save_data(data)
    return True


def clear_all_items():
    data = ensure_initialized()
    data["items"] = {}
    save_data(data)


def rename_file(old_filename, new_filename):
    data = ensure_initialized()
    old_filename = Path(old_filename).name
    new_filename = Path(new_filename).name
    if old_filename in data["items"]:
        data["items"][new_filename] = data["items"].pop(old_filename)
        save_data(data)


def filenames_for_collection(collection_id=None):
    collection_id = collection_id or active_collection_id()
    data = ensure_initialized()
    return {filename for filename, collection_ids in data["items"].items() if collection_id in collection_ids}


def file_collection_ids(filename):
    data = ensure_initialized()
    return list(data["items"].get(Path(filename).name, []))
