import pyinstaller
import os
import sys

print(sys.path)

pyinstaller.configure()

os.system('python cEmoji.py') # 运行cEmoji.py生成必要文件

pyinstaller.build_main('./cEmoji.py') # 用pyinstaller打包

