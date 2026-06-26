from pathlib import Path
import sys


def _app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


APP_DIR = _app_dir()


def _data_dir(name):
    packaged_path = APP_DIR / name
    if packaged_path.exists():
        return packaged_path

    source_path = APP_DIR / "resource" / name
    if source_path.exists():
        return source_path

    return packaged_path


EMOJI_DIR = _data_dir("emoji")
EMOJI_SMALL_DIR = _data_dir("emoji_small")
ICON_DIR = _data_dir("icon")
BIN_DIR = APP_DIR / "bin"
ETC_DIR = APP_DIR / "etc"
CONFIG_FILE = ETC_DIR / "cEmoji.ini"


def ensure_app_dirs():
    EMOJI_DIR.mkdir(parents=True, exist_ok=True)
    EMOJI_SMALL_DIR.mkdir(parents=True, exist_ok=True)
    ETC_DIR.mkdir(parents=True, exist_ok=True)
