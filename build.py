import pyinstaller
import os

pyinstaller.configure()

os.system('python cEmoji.py') # 运行cEmoji.py生成必要文件

pyinstaller.build_main('./cEmoji.py') # 用pyinstaller打包

