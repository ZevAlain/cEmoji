import os
import configparser

global emoji_folder
global emoji_small_folder
global current_path

# 计算个数
def getCountFromEmoji_small(path):
    count = 0
    for _, _, files in os.walk(path):
        count += len(files)
    return count

# 读取ini函数 etc/config.ini
# 文件不存在，读取不到，或者读取出错一律返回default_value传入的值。
def read_ini_value(filename, section, key, default_value=None):
    if not os.path.exists(filename):
        return default_value

    config = configparser.ConfigParser()
    try:
        config.read(filename)
        if section in config and key in config[section]:
            return config[section][key]
        else:
            return default_value
    except Exception as e:
        return default_value

# 写ini函数 etc/config.ini
# 文件不存在则创建，文件存在section不存在会自动创建section。
def write_ini_value(filename, section, key, value):
    # 检查文件是否存在,不存在就创建
    if not os.path.exists(filename):
        open(filename, 'w').close()

    config = configparser.ConfigParser()
    config.read(filename)
    
    if not config.has_section(section):
        config.add_section(section)
        
    config.set(section, key, value)
    
    with open(filename, 'w') as f:
        config.write(f)
