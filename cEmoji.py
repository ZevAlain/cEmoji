import os
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QScrollArea, \
    QSizePolicy, QLineEdit, QMessageBox, QGridLayout, QHBoxLayout, QSystemTrayIcon, QAction, QMenu, QCheckBox, \
    QLabel
from PyQt5.QtGui import QIcon
from PyQt5 import QtCore  # Add this line to import QtCore
# import threading
import my_icon
import base64
import src.cEmojiUtils as cEmojiUtils
import src.cEmojiWidgets as cEmojiWidgets
import src.cEmojiDialogs as cEmojiDialogs
import configparser
import version
from configparser import ConfigParser

# 排他处理
# app_lock = threading.Lock()

# if not app_lock.acquire(False):
#     QMessageBox.information(None, "提示", "进程已经在运行当中，请检查当前任务栏或托盘中是否存在。")
#     sys.exit()

# 获取当前应用程序的路径
# current_path = os.path.dirname(os.path.realpath(__file__))
current_path = os.path.dirname(sys.executable)

# 设置文件夹路径
emoji_folder = os.path.join(current_path, "emoji/")
emoji_small_folder = os.path.join(current_path, "emoji_small/")
# print(emoji_small_folder)

# 如果文件夹不存在，则创建文件夹
if not os.path.exists(emoji_folder):
    os.makedirs(emoji_folder)
if not os.path.exists(emoji_small_folder):
    os.makedirs(emoji_small_folder)

# 改成从ini读取，调用示例
# etc_emoji_folder = os.path.join(current_path, "etc/")
# config_etc_emoji_folder = os.path.join(etc_emoji_folder, "cEmoji.ini")
# 读取ini
# close_app_flag = cEmojiUtils.read_ini_value(config_etc_emoji_folder, "config", "close_app_flag", "True")
# 写入ini
# cEmojiUtils.write_ini_value(config_etc_emoji_folder, "config", "close_app_mode", "True")

# 定义全局变量保存关闭应用程序的标志和关闭应用程序方式

# 读取ini文件
config = configparser.ConfigParser()
config.read("./etc/cEmoji.ini", encoding="utf-8")

# True:不提示弹窗 False：提示弹窗（默认True）
close_app_flag = config.getboolean("config", "close_app_flag")

# 0：nothing 1：结束应用程序 2：最小化（默认0）
close_app_mode = config.getint("config", "close_app_mode")

# 0：非管理模式 1：管理模式（默认0）
delete_flag = 0

# 主程序
class ImageViewer(QWidget):
    def __init__(self):
        super().__init__()

        ################################################################
        # 主界面初始化
        ################################################################
        self.setWindowTitle("cEmoji") # 设置title
        self.setFixedSize(500, 600)  # 设置窗口大小为400x600像素

        # 设置标题栏图标，创建临时ico文件。使用完毕删除
        with open("tmp.ico", "wb") as tmp:
            tmp.write(base64.b64decode(my_icon.Icon().img))

        icon = QIcon("tmp.ico")
        self.setWindowIcon(icon)

        # 创建主布局
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        ################################################################
        # 创建托盘
        ################################################################
        # 创建退出操作并连接到退出方法
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.on_exit)

        # 创建系统托盘菜单并添加退出操作
        self.tray_icon_menu = QMenu(self)
        self.tray_icon_menu.addAction(exit_action)

        # 创建系统托盘图标并设置图标和菜单
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("tmp.ico"))  # 替换为你的应用程序图标路径
        self.tray_icon.setContextMenu(self.tray_icon_menu)
        self.tray_icon.setToolTip("cEmoji-Exit请右击")  # 添加此行

        # 连接系统托盘图标的激活事件到对应方法
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

        # 删除临时图标
        os.remove("tmp.ico")

        ################################################################
        # 创建始终置顶，上传，管理按钮
        ################################################################
        # 添加按钮布局
        self.buttons_layout = QHBoxLayout()
        self.main_layout.addLayout(self.buttons_layout)

        # 在按钮布局中添加三个按钮
        self.always_on_top_button = QPushButton("始终置顶")
        # 设置为可检查按钮  
        self.always_on_top_button.setCheckable(True)
        self.manage_button = QPushButton("管理")
        # 设置为可检查按钮  
        self.manage_button.setCheckable(True)

        self.upload_button = QPushButton("上传")

        self.buttons_layout.addWidget(self.always_on_top_button)
        self.buttons_layout.addWidget(self.upload_button) 
        self.buttons_layout.addWidget(self.manage_button)

        # 设置按钮策略
        self.always_on_top_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.upload_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.manage_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 连接信号和槽 
        self.always_on_top_button.clicked.connect(self.toggle_always_on_top)
        self.upload_button.clicked.connect(self.show_upload_dialog) 
        self.manage_button.clicked.connect(self.show_manage_dialog)

        ################################################################
        # 创建搜索框
        ################################################################
        # 创建搜索框
        self.search_bar = QLineEdit(self)
        self.search_bar.textChanged.connect(self.display_emoji)

        # 设置搜索框样式为透明
        self.search_bar.setStyleSheet("background-color: transparent;")

        # 设置搜索框的占位文本
        searchMessage = "输入表情标题搜索(当前表情数量: " + str(cEmojiUtils.getCountFromEmoji_small(emoji_small_folder)) + ")"
        self.search_bar.setPlaceholderText(searchMessage)

        # 添加上传按钮和搜索框到主布局
        self.main_layout.addWidget(self.upload_button)
        self.main_layout.addWidget(self.search_bar)

        ################################################################
        # 创建搜索框
        ################################################################
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

        # 版本号显示
        self.version_label = QLabel("版本号：" + version.cEmojiversion, self)
        self.main_layout.addWidget(self.version_label, alignment=QtCore.Qt.AlignBottom | QtCore.Qt.AlignRight)

        # 显示emoji图片
        self.display_emoji()

        self.write_ini("delete_flag", "0")

    ################################################################
    # 托盘相关处理
    ################################################################
    def closeEvent(self, event):
        global close_app_flag, close_app_mode

        # 如果之前选择了关闭方式并勾选了记住选项，则直接使用先前选择的方式
        if close_app_flag:
            if close_app_mode == 1:
                self.on_exit()
            elif close_app_mode == 2:
                event.ignore()
                self.hide()
                self.tray_icon.show()
            return

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("要关闭cEmoji吗QAQ")
        close_button = msg_box.addButton("狠心关闭", QMessageBox.YesRole)
        minimize_button = msg_box.addButton("缩小至托盘", QMessageBox.NoRole)
        remember_choice = QCheckBox("记住我的选择")
        msg_box.setCheckBox(remember_choice)

        # 用于记录选择的按钮
        clicked_role = [None]

        def button_clicked(button):
            if button == close_button:
                clicked_role[0] = "close"
            elif button == minimize_button:
                clicked_role[0] = "minimize"

        msg_box.buttonClicked.connect(button_clicked)

        msg_box.exec_()

        if clicked_role[0] == "close":
            close_app_mode = 1
            if remember_choice.isChecked():
                close_app_flag = True

                # # 修改配置
                # config.set("config", "close_app_flag", str(close_app_flag))
                # config.set("config", "close_app_mode", str(close_app_mode))

                # # 将更改写回文件
                # with open("./etc/cEmoji.ini", "w") as configfile:
                #     config.write(configfile)

                # 将配置写入ini文件
                self.write_ini("close_app_flag", str(close_app_flag))
                self.write_ini("close_app_mode", str(close_app_mode))

            self.on_exit()
        elif clicked_role[0] == "minimize":
            close_app_mode = 2
            if remember_choice.isChecked():
                close_app_flag = True

                # # 修改配置
                # config.set("config", "close_app_flag", str(close_app_flag))
                # config.set("config", "close_app_mode", str(close_app_mode))

                # # 将更改写回文件
                # with open("./etc/cEmoji.ini", "w") as configfile:
                #     config.write(configfile)

                # 将配置写入ini文件
                self.write_ini("close_app_flag", str(close_app_flag))
                self.write_ini("close_app_mode", str(close_app_mode))

            event.ignore()
            self.hide()
            self.tray_icon.show()
        else:
            event.ignore()

    # 托盘可以右键关闭
    def on_exit(self):
        self.tray_icon.hide()
        QApplication.quit()

    # 托盘图标
    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()

    ################################################################
    # 始终置顶按钮事件
    ################################################################
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

    ################################################################
    # 上传按钮事件
    ################################################################
    def show_upload_dialog(self):
        msg_box = QMessageBox(self)
        msg_box.setText("请选择上传类型:")
        msg_box.setWindowTitle("cEmoji")
        button_image = msg_box.addButton("图片", QMessageBox.YesRole)
        button_zip = msg_box.addButton("压缩包", QMessageBox.NoRole)
        cancel_button = msg_box.addButton("取消上传", QMessageBox.RejectRole)

        ret = msg_box.exec_()

        if msg_box.clickedButton() == button_image:
            cEmojiDialogs.upload_image(self)
        elif msg_box.clickedButton() == button_zip:
            cEmojiDialogs.upload_zip(self)
        else:
            pass

    ################################################################
    # 管理按钮事件
    ################################################################
    def show_manage_dialog(self):
        global delete_flag
        # 判断是否在管理模式
        if delete_flag == 0:
            delete_flag = 1

            # # 修改配置
            # config.set("config", "delete_flag", str(delete_flag))

            # # 将更改写回文件
            # with open("./etc/cEmoji.ini", "w") as configfile:
            #     config.write(configfile)

            # 将配置写入ini文件
            self.write_ini("delete_flag", str(delete_flag))

            # 刷新瀑布图区域
            self.display_emoji()

             # 批量添加删除图标
            cEmojiWidgets.ClickableLabel.add_delete_icons_to_all()
        elif delete_flag == 1:
            delete_flag = 0

            # # 修攍置
            # config.set("config", "delete_flag", str(delete_flag))

            # # 将替换写因文件
            # with open("./etc/cEmoji.ini", "w") as configfile:
            #     config.write(configfile)

            # 将配置写入ini文件
            self.write_ini("delete_flag", str(delete_flag))

            # 刷新瀑布图区域
            self.display_emoji()

        # # 查找父窗口（self）中所有的 ClickableLabel 对象
        # clickable_labels = self.findChildren(cEmojiWidgets.ClickableLabel(self))

        # print("我是clickable_labels" + clickable_labels)

        # # 在每一个 ClickableLabel 对象上调用 reset_style 和 add_delete_icon 方法
        # for label in clickable_labels:
        #     label.reset_style()
        #     label.add_delete_icon()

        # global close_app_flag, close_app_mode

        # msg = QMessageBox(self)
        # msg.setWindowTitle("管理")
        # reset_button = QPushButton("重置关闭方式")
        # layout = QVBoxLayout()
        # layout.addWidget(reset_button)
        # widget = QWidget()
        # widget.setLayout(layout)
        # msg.layout().addWidget(widget)

        # # 重置关闭方式的按钮事件
        # def reset_close_mode():
        #     global close_app_flag, close_app_mode
        #     close_app_flag = False
        #     close_app_mode = 0
        #     QMessageBox.information(self, "重置成功", "重置关闭方式成功")

        # reset_button.clicked.connect(reset_close_mode)
        # msg.exec_()

    ################################################################
    # 将配置写入ini文件
    # 参数1：self（默认）
    # 参数2：key
    # 参数3：value
    ################################################################
    def write_ini(self, key, value):
        # 使用ConfigParser进行常规操作
        config = ConfigParser()
        config.read("./etc/cEmoji.ini", encoding="utf-8")

        # 修改某个设置
        config.set("config", key, value)

        # 将配置写回文件时保留注释
        with open("./etc/cEmoji.ini", "r", encoding="utf-8") as f:
            lines = f.readlines()

        with open("./etc/cEmoji.ini", "w", encoding="utf-8") as f:
            for line in lines:
                stripped = line.strip()
                if "=" in stripped:  # 这是一个配置项
                    key = stripped.split("=")[0].strip()
                    section = None
                    for s in config.sections():
                        if key in config[s]:
                            section = s
                            break
                    # 如果键已更改，则写入新值，否则写入原始行
                    if section and config.get(section, key) != stripped.split("=")[1].strip():
                        f.write(f"{key} = {config.get(section, key)}\n")
                    else:
                        f.write(line)
                else:
                    f.write(line)

    ################################################################
    # 刷新瀑布图区域
    ################################################################
    def display_emoji(self):
        # 清除当前显示的所有图片
        for i in reversed(range(self.scroll_area_layout.count())):
            self.scroll_area_layout.itemAt(i).widget().setParent(None)

        # 获取所有的emoji图片
        emoji_images = [f for f in os.listdir(emoji_small_folder) if os.path.isfile(
            os.path.join(emoji_small_folder, f)) and self.search_bar.text().lower() in f.lower()]

        # 按文件创建时间排序
        sorted_emoji_images = sorted(emoji_images, key=lambda f: os.path.getctime(os.path.join(emoji_small_folder, f)), reverse=True)

        # 将图片添加到滚动区域布局
        for i, img_file in enumerate(sorted_emoji_images):
            label = cEmojiWidgets.ClickableLabel(self)
            label.setObjectName(img_file)
            label.setPixmap(os.path.join(emoji_small_folder, img_file))
            label.setStyleSheet("position:relative;")

            # 连接信号来刷新图片界面
            label.image_deleted.connect(self.display_emoji)
            
            row = i // 3
            column = i % 3
            self.scroll_area_layout.addWidget(label, row, column)

        # 更新搜索框的占位文本
        searchMessage = "输入表情标题搜索(当前表情数量: " + str(cEmojiUtils.getCountFromEmoji_small(emoji_small_folder)) + ")"
        self.search_bar.setPlaceholderText(searchMessage)

################################################################
# 主处理
################################################################
if __name__ == "__main__":
    # 主界面初始化
    app = QApplication(sys.argv)

    image_viewer = ImageViewer()
    image_viewer.show()

    # app_lock.release()
    sys.exit(app.exec_())
