from configparser import ConfigParser
from pathlib import Path

# 计算个数
def getCountFromEmoji_small(path):
    return sum(1 for item in Path(path).rglob("*") if item.is_file())

# 读取ini函数 etc/config.ini
# 文件不存在，读取不到，或者读取出错一律返回default_value传入的值。
def read_ini_value(filename, section, key, default_value=None):
    path = Path(filename)
    if not path.exists():
        return default_value

    config = ConfigParser()
    try:
        config.read(path, encoding="utf-8")
        return config.get(section, key, fallback=default_value)
    except Exception:
        return default_value

# 写ini函数 etc/config.ini
# 文件不存在则创建，文件存在section不存在会自动创建section。
def write_ini_value(filename, section, key, value):
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)

    config = ConfigParser()
    config.read(path, encoding="utf-8")
    
    if not config.has_section(section):
        config.add_section(section)
        
    config.set(section, key, str(value))
    
    with path.open("w", encoding="utf-8") as f:
        config.write(f)
