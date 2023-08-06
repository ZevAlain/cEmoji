from patoolib import programs
import patoolib
import shutil
import time
from PyQt5.QtWidgets import QFileDialog, QMessageBox
import os
from PIL import Image
import patoolib
import sys

# 获取当前应用程序的路径
# current_path = os.path.dirname(os.path.realpath(__file__))
current_path = os.path.dirname(sys.executable)

# 设置文件夹路径
emoji_folder = os.path.join(current_path, "emoji/")
emoji_small_folder = os.path.join(current_path, "emoji_small/")

def upload_image(self):
    # 创建进度条
    # progress = QProgressDialog("正在上传...", "取消上传", 0, 100, self)
    # progress.setWindowModality(Qt.WindowModal)
    # progress.setWindowTitle("上传进度")

    # 打开文件选择框
    filenames, _ = QFileDialog.getOpenFileNames(
        self, "Select image", "", "Image files (*.jpg *.png)")

    for i, filename in enumerate(filenames):
        if not filename:
            continue
        # 设置进度条的值
        # progress_value = int(i / len(filenames) * 100)
        # progress.setValue(progress_value)
        
        dest_filename = emoji_folder + os.path.basename(filename)
        # existsFileList = []

        # 检查文件是否存在，如果存在则不复制
        if os.path.exists(dest_filename):
            # 文件存在，警告消息输出暂时去除。
            # existsFileList.append(dest_filename)
            # QMessageBox.warning(self, 'Warning', 'File already exists.')
            continue

        # 拷贝文件到emoji文件夹
        shutil.copy(filename, dest_filename)

        # 创建缩略图
        image = Image.open(dest_filename)
        if image.mode not in ["RGB", "RGBA"]:
            image = image.convert("RGB")
        image.thumbnail((100, 100))
        image.save(emoji_small_folder +
                    os.path.basename(filename), quality=100)

        # if progress.wasCanceled():
        #     break

    self.display_emoji()
    # progress.close()

def upload_zip(self):
    # # 创建进度条
    # progress = QProgressDialog("正在上传...", "取消上传", 0, 100, self)
    # progress.setWindowModality(Qt.WindowModal)
    # progress.setWindowTitle("上传进度")
    # 选择多个zip文件
    
    up_current_path = current_path
    filenames, _ = QFileDialog.getOpenFileNames(self, "Select ZIP", "", "ZIP files (*.zip)")

    # 遍历zip
    for i, filename in enumerate(filenames):
        if not filename:
            continue

        # # 设置进度条的值
        # progress_value = int(i / len(filenames) * 100)
        # progress.setValue(progress_value)

        # 创建临时文件夹
        tmp_folder = f"cEmoji_tmp_{int(time.time())}"
        tmpEmojiPath = os.path.join(up_current_path, tmp_folder)
        os.mkdir(tmpEmojiPath)

        # 解压文件
        patoolib.extract_archive(filename, outdir=tmpEmojiPath)

        # 遍历临时文件夹
        for root, dirs, files in os.walk(tmpEmojiPath):
            for file in files:
                # 获取文件路径
                file_path = os.path.join(tmpEmojiPath, file)
                # 判断后缀名
                if Path(file_path).suffix in ['.jpg', '.png']:
                    dest_filename = emoji_folder + os.path.basename(file)
                    # existsFileList = []

                    # 检查文件是否存在，如果存在则不复制
                    if os.path.exists(dest_filename):
                        #文件存在，警告消息输出暂时去除。
                        # existsFileList.append(dest_filename)
                        # QMessageBox.warning(self, 'Warning', 'File already exists.')
                        continue

                    # 拷贝文件到emoji文件夹
                    shutil.copy(file_path, dest_filename)

                    # 创建缩略图
                    image = Image.open(dest_filename)
                    if image.mode not in ["RGB", "RGBA"]:
                        image = image.convert("RGB")
                    image.thumbnail((100, 100))
                    image.save(emoji_small_folder +
                            os.path.basename(file), quality=100)

        # 删除临时文件夹
        shutil.rmtree(tmpEmojiPath)

        # if progress.wasCanceled():
        #     break
        
    self.display_emoji()
    # progress.close()

def opt_image_dia(self):
    msg = QMessageBox(self)
    msg.setWindowTitle("提示")
    msg.setText("待实现")
    msg.exec_()
