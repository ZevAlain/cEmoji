import sys
from PyQt5.QtWidgets import QApplication, QLabel, QSizePolicy, QMessageBox, QStyle
from PyQt5.QtGui import QPixmap, QPainter, QIcon, QCursor, QMovie
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData
import os
import cEmoji as main

# 获取当前应用程序的路径
# current_path = os.path.dirname(os.path.realpath(__file__))
current_path = os.path.dirname(sys.executable)

# 设置文件夹路径
emoji_folder = os.path.join(current_path, "emoji/")
emoji_small_folder = os.path.join(current_path, "emoji_small/")
# print(emoji_small_folder)

# 通过引用QLabel类来实现鼠标事件
class ClickableLabel(QLabel):
    # 定义一个信号
    image_deleted = pyqtSignal()
    def __init__(self, *args, **kwargs):
        super(ClickableLabel, self).__init__(*args, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFixedSize(120, 120)  # 设置缩略图固定尺寸
        self.setStyleSheet("border: 1px solid lightgray;")  # 设置浅色分界线
        self.delete_icon = None  # 添加属性来存储删除图标
        

    def setPixmap(self, image_path):
        pixmap = QPixmap(image_path)
        scaled_pixmap = pixmap.scaled(
            self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        super().setPixmap(scaled_pixmap)

    def mousePressEvent(self, event):
        # 删除之前的删除图标
        if self.delete_icon:
            self.delete_icon.deleteLater()
            self.delete_icon = None
        
        for label in self.parent().findChildren(ClickableLabel):
            # 重置其他图片的样式
            label.setStyleSheet("border: 1px solid lightgray;")
            # 如果存在删除图标，则删除
            if label.delete_icon:
                label.delete_icon.deleteLater()
                label.delete_icon = None

        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            # 左击图片显示蓝色边框，并且复制该图片
            # for label in self.parent().findChildren(ClickableLabel):
            #     label.setStyleSheet("border: 1px solid lightgray;")
            # self.setStyleSheet("border: 4px solid blue;")

            # image_path = os.path.join(emoji_folder, self.objectName())

            # if image_path.lower().endswith('.gif'):
            #     self.movie = QMovie(image_path)
            #     self.setMovie(self.movie)
            #     self.movie.start()
            # else:
            #     QApplication.clipboard().setPixmap(QPixmap(image_path))
            for label in self.parent().findChildren(ClickableLabel):
                label.setStyleSheet("border: 1px solid lightgray;")
            self.setStyleSheet("border: 4px solid blue;")

            image_path = os.path.join(emoji_folder, self.objectName())

            if image_path.lower().endswith('.gif'):
                self.movie = QMovie(image_path)
                self.setMovie(self.movie)
                self.movie.start()

                clipboard = QApplication.clipboard()

                # Convert and copy each frame of the GIF
                mime_data = QMimeData()
                frame_images = []
                for frame_number in range(self.movie.frameCount()):
                    self.movie.jumpToFrame(frame_number)
                    frame_image = self.movie.currentPixmap().toImage()
                    frame_images.append(frame_image)

                mime_data.setImageData(frame_images)  # Set the list of frame images as MIME data
                clipboard.setMimeData(mime_data)
            else:
                pixmap = QPixmap(image_path)
                clipboard = QApplication.clipboard()
                clipboard.setPixmap(pixmap)
        
        elif event.button() == Qt.RightButton:
            # 右击图片显示红色边框
            for label in self.parent().findChildren(ClickableLabel):
                label.setStyleSheet("border: 0px solid lightgray;")

            self.delete_icon = QLabel(self)
            delete_icon = QApplication.style().standardIcon(QStyle.SP_MessageBoxCritical)
            self.delete_icon.setPixmap(delete_icon.pixmap(20, 20))
            self.delete_icon.setGeometry(self.width() - 20, 0, 20, 20)
            self.delete_icon.setAlignment(Qt.AlignCenter)
            self.delete_icon.setStyleSheet("background-color: red; border-radius: 10px;")
            self.delete_icon.show()
            self.delete_icon.setCursor(QCursor(Qt.PointingHandCursor))
            self.delete_icon.mousePressEvent = self.delete_icon_click
            self.delete_icon.enterEvent = self.delete_icon_hover
            self.delete_icon.leaveEvent = self.delete_icon_leave
            
    def delete_icon_click(self, event):
        # 左击“X”图标的事件处理程序
        if event.button() == Qt.LeftButton:
            msg = QMessageBox(self)
            msg.setWindowTitle("确认删除")
            msg.setText("你确定要删除这个表情吗？")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            ret = msg.exec_()
            
            if ret == QMessageBox.Yes:
                image_path = os.path.join(emoji_folder, self.objectName())
                image_small_path = os.path.join(emoji_small_folder, self.objectName())
                
                # 如果文件存在则删除
                if os.path.exists(image_path):
                    os.remove(image_path)
                if os.path.exists(image_small_path):
                    os.remove(image_small_path)
                
                # 发出信号
                self.image_deleted.emit()
                
    
    def delete_icon_hover(self, event):
        # 鼠标悬停在“X”图标上时的事件处理程序
        self.delete_icon.setStyleSheet("background-color: lightblue; border-radius: 10px;")
        
    def delete_icon_leave(self, event):
        # 鼠标离开“X”图标时的事件处理程序
        self.delete_icon.setStyleSheet("background-color: red; border-radius: 10px;")
