import sys
from PyQt5.QtWidgets import QApplication, QLabel, QSizePolicy, QMessageBox, QStyle
from PyQt5.QtGui import QPixmap, QPainter, QIcon, QCursor, QMovie
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData
import os
import cEmoji as main
import subprocess
import configparser

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

    instances = []  # 类变量，用于存储所有的实例
        
    def __init__(self, *args, **kwargs):
        super(ClickableLabel, self).__init__(*args, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFixedSize(120, 120)  # 设置缩略图固定尺寸
        self.setStyleSheet("border: 1px solid lightgray;")  # 设置浅色分界线
        self.delete_icon = None  # 添加属性来存储删除图标
        self.gif_icon = None  # 添加属性来存储gif图标
        self.instances.append(self)  # 在创建新的实例时，将其添加到类变量中

    def setPixmap(self, image_path):
        pixmap = QPixmap(image_path)
        scaled_pixmap = pixmap.scaled(
            self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        if image_path.lower().endswith('.gif'):
            self.add_gif_icon()
        super().setPixmap(scaled_pixmap)

    def mousePressEvent(self, event):
        # 判断是否在管理模式
        if self.is_in_manage_mode():
            return # 终止该方法后面的处理

        # 重置样式
        self.reset_style()
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
                # self.movie = QMovie(image_path)
                # self.setMovie(self.movie)
                # self.movie.start()

                # clipboard = QApplication.clipboard()

                # # Convert and copy each frame of the GIF
                # mime_data = QMimeData()
                # frame_images = []
                # for frame_number in range(self.movie.frameCount()):
                #     self.movie.jumpToFrame(frame_number)
                #     frame_image = self.movie.currentPixmap().toImage()
                #     frame_images.append(frame_image)

                # mime_data.setImageData(frame_images)  # Set the list of frame images as MIME data
                # clipboard.setMimeData(mime_data)
                command_bin = os.path.join(current_path, "bin")
                
                command = os.path.join(command_bin, "cpgif.exe")
                result = subprocess.Popen([command, image_path], creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
                
                if result.returncode != 0:
                    pass
                else:
                    pass
            else:
                pixmap = QPixmap(image_path)
                clipboard = QApplication.clipboard()
                clipboard.setPixmap(pixmap)
        
        elif event.button() == Qt.RightButton:
            # 右击图片显示红色边框
            for label in self.parent().findChildren(ClickableLabel):
                label.setStyleSheet("border: 0px solid lightgray;")

            self.add_delete_icon()
            

    # 重置样式
    def reset_style(self):
        # 删除之前的删除图标
        if self.delete_icon:
            self.delete_icon.deleteLater()
            self.delete_icon = None

        if self.parent():  # 检查 parent 是否为 None
            # 重置其他图片的样式
            for label in self.parent().findChildren(ClickableLabel):
                label.setStyleSheet("border: 1px solid lightgray;")
                # 如存在删除图标，则删除
                if label.delete_icon:
                    label.delete_icon.deleteLater()
                    label.delete_icon = None

    # 批量添加删除图标
    @classmethod
    def add_delete_icons_to_all(cls):
        for instance in cls.instances:
            instance.add_delete_icon()

    # 图片的gificon
    def add_gif_icon(self):
        # 设置icon文件夹路径
        icon_folder = os.path.join(current_path, "icon")
        icon_path = os.path.join(icon_folder, "gif_icon.png")
        self.gif_icon = QLabel(self)
        pixmap = QPixmap(icon_path)  # 使用自己的图片路径创建QPixmap
        self.gif_icon.setPixmap(pixmap)
        self.gif_icon.setGeometry(0, self.height() - pixmap.height(), pixmap.width(), pixmap.height())  # 放置在左下角
        self.gif_icon.setAlignment(Qt.AlignCenter)
        # self.gif_icon.setStyleSheet("background-color: red; border-radius: 10px;")
        self.gif_icon.show()
        self.gif_icon.setCursor(QCursor(Qt.PointingHandCursor))

    # 图片的删除icon
    def add_delete_icon(self):
        self.delete_icon = QLabel(self)
        delete_icon = QApplication.style().standardIcon(QStyle.SP_MessageBoxCritical)
        self.delete_icon.setPixmap(delete_icon.pixmap(20, 20))
        self.delete_icon.setGeometry(self.width() - 20, 0, 20, 20)
        self.delete_icon.setAlignment(Qt.AlignCenter)
        self.delete_icon.setStyleSheet("background-color: red; border-radius: 10px;")
        self.delete_icon.show()
        self.delete_icon.setCursor(QCursor(Qt.PointingHandCursor))

        # 读取ini文件
        config = configparser.ConfigParser()
        config.read('./etc/cEmoji.ini', encoding='utf-8')
        if config.getint('config', 'delete_flag') == 0:
            self.delete_icon.mousePressEvent = self.delete_icon_click
        elif config.getint('config', 'delete_flag') == 1:
            self.delete_icon.mousePressEvent = self.delete_to_all_icon_click
        self.delete_icon.enterEvent = self.delete_icon_hover
        self.delete_icon.leaveEvent = self.delete_icon_leave


    # 删除图片的信号
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
    
    # 批量删除
    def delete_to_all_icon_click(self, event):
        # 左击“X”图标的事件处理程序
        if event.button() == Qt.LeftButton:
            image_path = os.path.join(emoji_folder, self.objectName())
            image_small_path = os.path.join(emoji_small_folder, self.objectName())
            
            # 如果文件存在则删除
            if os.path.exists(image_path):
                os.remove(image_path)
            if os.path.exists(image_small_path):
                os.remove(image_small_path)
            
            # 发出信号
            self.image_deleted.emit()

            # 重置样式
            self.reset_style()
            
            # 批量添加删除图标
            self.add_delete_icons_to_all()

    # 判断是否在管理模式下
    def is_in_manage_mode(self):
        # 读取ini文件
        config = configparser.ConfigParser()
        config.read('./etc/cEmoji.ini', encoding='utf-8')
        if config.getint('config', 'delete_flag') == 1:
            msg = QMessageBox(self)
            msg.setWindowTitle("出错啦Σ(っ °Д °;)っ")
            msg.setText("复制请取消管理模式")
            msg.setStandardButtons(QMessageBox.Ok)  # 只设置一个 OK 按钮

            msg.exec_()  # 显示对话框并等待用户响应，但不管用户做什么选择，代码都会继续执行

            return True
    
    def delete_icon_hover(self, event):
        # 鼠标悬停在“X”图标上时的事件处理程序
        self.delete_icon.setStyleSheet("background-color: lightblue; border-radius: 10px;")
        
    def delete_icon_leave(self, event):
        # 鼠标离开“X”图标时的事件处理程序
        self.delete_icon.setStyleSheet("background-color: red; border-radius: 10px;")
