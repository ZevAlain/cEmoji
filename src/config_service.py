from configparser import ConfigParser
from dataclasses import dataclass

from src.app_paths import CONFIG_FILE, ensure_app_dirs


CONFIG_SECTION = "config"


@dataclass
class AppConfig:
    close_app_flag: bool = False
    close_app_mode: int = 0
    delete_flag: int = 0
    hotkey: str = "Ctrl+Alt+E"
    hide_after_copy: bool = False


class ConfigService:
    def __init__(self, path=CONFIG_FILE):
        self.path = path

    def load(self):
        parser = self._read()
        return AppConfig(
            close_app_flag=parser.getboolean(CONFIG_SECTION, "close_app_flag", fallback=False),
            close_app_mode=parser.getint(CONFIG_SECTION, "close_app_mode", fallback=0),
            delete_flag=parser.getint(CONFIG_SECTION, "delete_flag", fallback=0),
            hotkey=parser.get(CONFIG_SECTION, "hotkey", fallback="Ctrl+Alt+E"),
            hide_after_copy=parser.getboolean(CONFIG_SECTION, "hide_after_copy", fallback=False),
        )

    def set_value(self, key, value):
        parser = self._read()
        parser.set(CONFIG_SECTION, key, str(value))
        self._write(parser)

    def set_values(self, values):
        parser = self._read()
        for key, value in values.items():
            parser.set(CONFIG_SECTION, key, str(value))
        self._write(parser)

    def _read(self):
        ensure_app_dirs()
        parser = ConfigParser()
        parser.read(self.path, encoding="utf-8")
        if not parser.has_section(CONFIG_SECTION):
            parser.add_section(CONFIG_SECTION)
        return parser

    def _write(self, parser):
        ensure_app_dirs()
        if not self.path.exists():
            with self.path.open("w", encoding="utf-8") as config_file:
                parser.write(config_file)
            return

        lines = self.path.read_text(encoding="utf-8").splitlines(keepends=True)
        updated_lines = []
        seen_keys = set()
        current_section = None

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                current_section = stripped[1:-1]
                updated_lines.append(line)
                continue

            if current_section == CONFIG_SECTION and "=" in line and not stripped.startswith(("#", ";")):
                key = line.split("=", 1)[0].strip()
                if parser.has_option(CONFIG_SECTION, key):
                    updated_lines.append(f"{key} = {parser.get(CONFIG_SECTION, key)}\n")
                    seen_keys.add(key)
                    continue

            updated_lines.append(line)

        if not any(line.strip() == f"[{CONFIG_SECTION}]" for line in updated_lines):
            updated_lines.extend([f"\n[{CONFIG_SECTION}]\n"])

        for key, value in parser.items(CONFIG_SECTION):
            if key not in seen_keys:
                updated_lines.append(f"{key} = {value}\n")

        self.path.write_text("".join(updated_lines), encoding="utf-8")
