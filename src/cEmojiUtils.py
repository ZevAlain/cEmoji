import os

global emoji_folder
global emoji_small_folder
global current_path

# 计算个数
def getCountFromEmoji_small(path):
    count = 0
    for _, _, files in os.walk(path):
        count += len(files)
    return count

