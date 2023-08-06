import sys
from PyQt5.QtWidgets import QApplication, QLabel, QSizePolicy
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
import os

# 获取当前应用程序的路径
# current_path = os.path.dirname(os.path.realpath(__file__))
current_path = os.path.dirname(sys.executable)

# 设置文件夹路径
emoji_folder = os.path.join(current_path, "emoji/")
emoji_small_folder = os.path.join(current_path, "emoji_small/")
# print(emoji_small_folder)

# 缺少注释
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

