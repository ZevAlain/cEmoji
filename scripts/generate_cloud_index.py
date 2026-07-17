from pathlib import Path
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone


REPOSITORY = "ZevAlain/EmojiPackage"
BRANCH_CANDIDATES = ("master", "main")
OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "public" / "cloud_index.json"
EXCLUDE_CONFIG = Path(__file__).with_name("cloud_index_excludes.json")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif"}
USER_AGENT = "cEmoji-index-generator"


def request_json(url):
    headers = {"User-Agent": USER_AGENT}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def load_excluded_package_paths():
    if not EXCLUDE_CONFIG.exists():
        return set()
    data = json.loads(EXCLUDE_CONFIG.read_text(encoding="utf-8"))
    paths = data.get("excluded_package_paths", [])
    return {str(path).strip().strip("/") for path in paths if str(path).strip()}


def tree_url(branch):
    return f"https://api.github.com/repos/{REPOSITORY}/git/trees/{branch}?recursive=1"


def raw_url(branch, path):
    return f"https://raw.githubusercontent.com/{REPOSITORY}/{branch}/" + "/".join(urllib.parse.quote(part) for part in path.split("/"))


def fetch_tree():
    last_error = None
    for branch in BRANCH_CANDIDATES:
        try:
            data = request_json(tree_url(branch))
        except Exception as error:
            last_error = error
            continue
        if data.get("tree"):
            return branch, data["tree"]
    raise RuntimeError(f"无法读取仓库文件树：{last_error}")


def main():
    branch, tree = fetch_tree()
    excluded_package_paths = load_excluded_package_paths()
    grouped = {}
    for entry in tree:
        if entry.get("type") != "blob":
            continue
        path = entry.get("path", "")
        name = Path(path).name
        suffix = Path(name).suffix.lower()
        if suffix not in IMAGE_SUFFIXES or "/" not in path:
            continue
        package_path = path.split("/", 1)[0]
        if package_path in excluded_package_paths:
            continue
        grouped.setdefault(package_path, []).append(
            {
                "name": name,
                "path": path,
                "download_url": raw_url(branch, path),
                "size": int(entry.get("size") or 0),
                "type": suffix.lstrip("."),
            }
        )

    packages = []
    for package_path, items in sorted(grouped.items()):
        packages.append(
            {
                "name": package_path,
                "path": package_path,
                "count": len(items),
                "gif_count": sum(1 for item in items if item["type"] == "gif"),
                "static_count": sum(1 for item in items if item["type"] != "gif"),
                "items": items,
            }
        )

    payload = {
        "source": REPOSITORY,
        "branch": branch,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "packages": packages,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(packages)} packages")


if __name__ == "__main__":
    main()
