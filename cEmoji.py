import os
import sys
import shutil
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog, QScrollArea, \
    QLabel, QSizePolicy, QLineEdit, QMessageBox, QGridLayout, QMainWindow
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import Qt
from PyQt5 import QtCore  # Add this line to import QtCore
from PIL import Image
import my_icon
import base64

# 获取当前应用程序的路径
# current_path = os.path.dirname(os.path.realpath(__file__))
current_path = os.path.dirname(sys.executable)

# 设置文件夹路径
emoji_folder = os.path.join(current_path, "emoji/")
emoji_small_folder = os.path.join(current_path, "emoji_small/")

# 如果文件夹不存在，则创建文件夹
if not os.path.exists(emoji_folder):
    os.makedirs(emoji_folder)
if not os.path.exists(emoji_small_folder):
    os.makedirs(emoji_small_folder)


class ClickableLabel(QLabel):
    def __init__(self, *args, **kwargs):
        super(ClickableLabel, self).__init__(*args, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFixedSize(120, 120)  # Set fixed size for all images
        self.setStyleSheet("border: 1px solid lightgray;")  # 设置浅色分界线

    def setPixmap(self, image_path):
        pixmap = QPixmap(image_path)
        scaled_pixmap = pixmap.scaled(
            self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        super().setPixmap(scaled_pixmap)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            # Remove blue border from previously clicked labels
            for label in self.parent().findChildren(ClickableLabel):
                label.setStyleSheet("border: 1px solid lightgray;")

            # Set blue border for the clicked label
            self.setStyleSheet("border: 4px solid blue;")

            image_path = os.path.join(emoji_folder, self.objectName())
            QApplication.clipboard().setPixmap(QPixmap(image_path))  # Copy the image itself


class ImageViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('cEmoji')
        self.setFixedSize(500, 600)  # 设置窗口大小为400x600像素

        # 设置标题栏图标
        with open('tmp.ico', 'wb') as tmp:
            tmp.write(base64.b64decode(my_icon.Icon().img))

        icon = QIcon('tmp.ico')
        self.setWindowIcon(icon)
        os.remove('tmp.ico')

        # 创建主布局
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        # 添加始终置顶按钮
        self.always_on_top_button = QPushButton('始终置顶', self)
        self.always_on_top_button.clicked.connect(self.toggle_always_on_top)
        self.always_on_top_button.setCheckable(True)  # 让按钮具有可选中状态
        self.main_layout.addWidget(self.always_on_top_button)

        # 创建上传按钮
        self.upload_button = QPushButton('导入图片', self)
        self.upload_button.clicked.connect(self.upload_image)

        # 创建搜索框
        self.search_bar = QLineEdit(self)
        self.search_bar.textChanged.connect(self.display_emoji)

        # 设置搜索框样式为透明
        self.search_bar.setStyleSheet("background-color: transparent;")

        # 设置搜索框的占位文本
        self.search_bar.setPlaceholderText("输入表情标题搜索")

        # 添加上传按钮和搜索框到主布局
        self.main_layout.addWidget(self.upload_button)
        self.main_layout.addWidget(self.search_bar)

        # 创建滚动区域
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)

        # 创建滚动区域内容
        self.scroll_area_content = QWidget(self.scroll_area)
        self.scroll_area.setWidget(self.scroll_area_content)

        # 创建滚动区域布局
        self.scroll_area_layout = QGridLayout()  # 修改为QGridLayout
        self.scroll_area_content.setLayout(self.scroll_area_layout)

        # 添加滚动区域到主布局
        self.main_layout.addWidget(self.scroll_area)

        # 显示emoji图片
        self.display_emoji()

    def toggle_always_on_top(self):
        # 获取当前窗口的“始终置顶”状态
        is_always_on_top = self.windowFlags() & QtCore.Qt.WindowStaysOnTopHint

        # 切换状态
        if is_always_on_top:
            self.setWindowFlags(self.windowFlags() & ~
                                QtCore.Qt.WindowStaysOnTopHint)
            self.always_on_top_button.setChecked(False)
        else:
            self.setWindowFlags(self.windowFlags() |
                                QtCore.Qt.WindowStaysOnTopHint)
            self.always_on_top_button.setChecked(True)

        # 更新窗口标志以应用更改
        self.show()

    def upload_image(self):
        # 打开文件选择框
        filenames, _ = QFileDialog.getOpenFileNames(
            self, "Select image", "", "Image files (*.jpg *.png)")

        for filename in filenames:
            dest_filename = emoji_folder + os.path.basename(filename)

            # 检查文件是否存在，如果存在则不复制
            if os.path.exists(dest_filename):
                QMessageBox.warning(self, 'Warning', 'File already exists.')
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

        self.display_emoji()

    def display_emoji(self):
        # 清除当前显示的所有图片
        for i in reversed(range(self.scroll_area_layout.count())):
            self.scroll_area_layout.itemAt(i).widget().setParent(None)

        # 获取所有的emoji图片
        emoji_images = [f for f in os.listdir(emoji_small_folder) if os.path.isfile(
            os.path.join(emoji_small_folder, f)) and self.search_bar.text().lower() in f.lower()]

        # 将图片添加到滚动区域布局
        for i, img_file in enumerate(emoji_images):
            label = ClickableLabel(self)
            # Save the original filename in the object name
            label.setObjectName(img_file)
            label.setPixmap(os.path.join(emoji_small_folder, img_file))

            row = i // 3
            column = i % 3
            self.scroll_area_layout.addWidget(label, row, column)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    image_viewer = ImageViewer()
    image_viewer.show()

    sys.exit(app.exec_())
