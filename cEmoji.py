import base64
import ctypes
from ctypes import wintypes
import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QEvent, QLockFile, QTimer, Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence, QPalette, QPixmapCache
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QKeySequenceEdit,
    QSizePolicy,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

import my_icon
import version
import src.cEmojiWidgets as cEmojiWidgets
from src import emoji_store
from src.app_paths import ensure_app_dirs
from src.config_service import ConfigService


HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040
GA_ROOT = 2
WM_HOTKEY = 0x0312
HOTKEY_ID = 1001
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000


if sys.platform == "win32":
    user32 = ctypes.windll.user32
    user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    user32.GetAncestor.restype = ctypes.c_void_p
    user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    user32.SetWindowPos.restype = ctypes.c_bool
    user32.RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
    user32.RegisterHotKey.restype = ctypes.c_bool
    user32.UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.UnregisterHotKey.restype = ctypes.c_bool


def set_window_topmost(window, enabled):
    if sys.platform == "win32":
        hwnd = user32.GetAncestor(int(window.winId()), GA_ROOT) or int(window.winId())
        insert_after = ctypes.c_void_p(HWND_TOPMOST if enabled else HWND_NOTOPMOST)
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
        if not user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, flags):
            raise ctypes.WinError()
        return

    window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
    window.show()


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


def hotkey_to_windows(hotkey_text):
    sequence = QKeySequence(hotkey_text)
    if sequence.isEmpty():
        return None

    combination = sequence[0]
    key = combination.key()
    modifiers = combination.keyboardModifiers()
    win_modifiers = MOD_NOREPEAT

    if modifiers & Qt.KeyboardModifier.ControlModifier:
        win_modifiers |= MOD_CONTROL
    if modifiers & Qt.KeyboardModifier.AltModifier:
        win_modifiers |= MOD_ALT
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        win_modifiers |= MOD_SHIFT
    if modifiers & Qt.KeyboardModifier.MetaModifier:
        win_modifiers |= MOD_WIN

    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        vk = int(key)
    elif Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        vk = int(key)
    elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
        vk = 0x70 + (int(key) - int(Qt.Key.Key_F1))
    else:
        return None

    return win_modifiers, vk


class ImageViewer(QWidget):
    def __init__(self):
        super().__init__()
        ensure_app_dirs()

        self.config_service = ConfigService()
        self.app_config = self.config_service.load()
        self._tmp_icon_path = None
        self._exiting = False
        self._hotkey_registered = False
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self.display_emoji)

        self.setWindowTitle("cEmoji")
        self.setFixedSize(500, 600)

        icon = self.create_icon()
        self.setWindowIcon(icon)

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(12, 12, 12, 10)
        self.main_layout.setSpacing(8)
        self.setLayout(self.main_layout)

        self.setup_tray(icon)
        self.setup_search()
        self.setup_buttons()
        self.setup_emoji_view()
        self.setup_footer()
        self.apply_system_theme()
        if self.register_hotkey(self.app_config.hotkey):
            self.hotkey_status_label.setText("已启用，可呼出/隐藏主界面")
        else:
            self.hotkey_status_label.setText("注册失败")

        self.display_emoji()
        if self.app_config.delete_flag != 0:
            self.set_config_value("delete_flag", 0)

    def create_icon(self):
        icon_bytes = base64.b64decode(my_icon.Icon().img)
        tmp_icon = tempfile.NamedTemporaryFile(delete=False, suffix=".ico")
        tmp_icon.write(icon_bytes)
        tmp_icon.close()
        self._tmp_icon_path = tmp_icon.name
        return QIcon(self._tmp_icon_path)

    def setup_tray(self, icon):
        show_action = QAction("显示界面", self)
        show_action.triggered.connect(self.show_main_window)

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.on_exit)

        self.tray_icon_menu = QMenu(self)
        self.tray_icon_menu.addAction(show_action)
        self.tray_icon_menu.addSeparator()
        self.tray_icon_menu.addAction(exit_action)

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setContextMenu(self.tray_icon_menu)
        self.tray_icon.setToolTip("cEmoji")
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

    def setup_buttons(self):
        self.buttons_layout = QHBoxLayout()
        self.main_layout.addLayout(self.buttons_layout)

        self.always_on_top_button = QPushButton("始终置顶")
        self.always_on_top_button.setCheckable(True)
        self.upload_button = QPushButton("上传")
        self.manage_button = QPushButton("管理")
        self.manage_button.setCheckable(True)
        self.clear_button = QPushButton("清空所有表情包")

        for button in (self.always_on_top_button, self.upload_button, self.manage_button, self.clear_button):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.buttons_layout.addWidget(button)

        self.always_on_top_button.clicked.connect(self.toggle_always_on_top)
        self.upload_button.clicked.connect(self.show_upload_dialog)
        self.manage_button.clicked.connect(self.show_manage_dialog)
        self.clear_button.clicked.connect(self.clear_all_emojis)

    def setup_search(self):
        self.search_bar = QLineEdit(self)
        self.search_bar.textChanged.connect(self.schedule_display_emoji)
        self.search_bar.setStyleSheet("background-color: transparent;")
        self.update_search_placeholder()
        self.main_layout.addWidget(self.search_bar)

    def setup_emoji_view(self):
        self.emoji_view = cEmojiWidgets.EmojiListWidget(self)
        self.emoji_view.emoji_deleted.connect(self.display_emoji)
        self.main_layout.addWidget(self.emoji_view)

    def setup_footer(self):
        self.shortcut_frame = QFrame(self)
        self.shortcut_layout = QHBoxLayout(self.shortcut_frame)
        self.shortcut_layout.setContentsMargins(0, 0, 0, 0)
        self.shortcut_label = QLabel("快捷呼出/隐藏", self)
        self.hotkey_edit = QKeySequenceEdit(QKeySequence(self.app_config.hotkey), self)
        self.hotkey_edit.setMaximumWidth(150)
        self.hotkey_edit.setToolTip("在这里输入快捷键，用于呼出或隐藏主界面")
        self.hotkey_edit.editingFinished.connect(self.save_hotkey)
        self.hotkey_status_label = QLabel("在这里输入快捷键来控制", self)
        self.shortcut_layout.addWidget(self.shortcut_label)
        self.shortcut_layout.addWidget(self.hotkey_edit)
        self.shortcut_layout.addWidget(self.hotkey_status_label, stretch=1)
        self.main_layout.addWidget(self.shortcut_frame)

        self.footer_layout = QHBoxLayout()
        self.main_layout.addLayout(self.footer_layout)

        self.copy_tip_label = QLabel("鼠标左键单击图片可复制到剪切板，右键可置顶", self)
        self.version_label = QLabel("版本号：" + version.cEmojiversion, self)
        self.footer_layout.addWidget(self.copy_tip_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.footer_layout.addStretch(1)
        self.footer_layout.addWidget(self.version_label, alignment=Qt.AlignmentFlag.AlignRight)

    def closeEvent(self, event):
        self._exiting = True
        self.cleanup()
        event.accept()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized() and not self._exiting:
            QTimer.singleShot(0, self.hide_to_tray)

    def hide_to_tray(self):
        if self._exiting:
            return
        self.hide()
        self.tray_icon.show()

    def on_exit(self):
        self._exiting = True
        self.cleanup()
        QApplication.quit()

    def cleanup(self):
        self.unregister_hotkey()
        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()
        if self._tmp_icon_path and os.path.exists(self._tmp_icon_path):
            os.remove(self._tmp_icon_path)
            self._tmp_icon_path = None

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_main_window()

    def show_main_window(self):
        self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def toggle_main_window(self):
        if self.isVisible() and not self.isMinimized():
            self.hide_to_tray()
            return

        self.show_main_window()

    def toggle_always_on_top(self):
        enabled = self.always_on_top_button.isChecked()
        try:
            set_window_topmost(self, enabled)
        except OSError as error:
            self.always_on_top_button.setChecked(not enabled)
            QMessageBox.warning(self, "置顶失败", str(error))

    def show_upload_dialog(self):
        import src.cEmojiDialogs as cEmojiDialogs

        cEmojiDialogs.show_upload_dialog(self)

    def show_manage_dialog(self):
        if self.app_config.delete_flag == 0:
            self.set_config_value("delete_flag", 1)
            self.emoji_view.set_manage_mode(True)
            self.manage_button.setText("退出管理")
        else:
            self.set_config_value("delete_flag", 0)
            self.emoji_view.set_manage_mode(False)
            self.manage_button.setText("管理")

    def clear_all_emojis(self):
        ret = QMessageBox.question(self, "确认清空", "确定要清空全部表情包吗？")
        if ret != QMessageBox.StandardButton.Yes:
            return

        removed = emoji_store.clear_emojis()
        self.display_emoji()
        QMessageBox.information(self, "清空完成", f"已删除 {removed} 个文件")

    def set_config_value(self, key, value):
        self.config_service.set_value(key, value)
        self.app_config = self.config_service.load()

    def save_hotkey(self):
        hotkey_text = self.hotkey_edit.keySequence().toString(QKeySequence.SequenceFormat.NativeText)
        if not hotkey_text:
            self.hotkey_status_label.setText("快捷键不能为空")
            self.hotkey_edit.setKeySequence(QKeySequence(self.app_config.hotkey))
            return

        if not self.register_hotkey(hotkey_text):
            self.hotkey_status_label.setText("注册失败")
            self.hotkey_edit.setKeySequence(QKeySequence(self.app_config.hotkey))
            return

        self.set_config_value("hotkey", hotkey_text)
        self.hotkey_status_label.setText("已保存，可呼出/隐藏主界面")

    def register_hotkey(self, hotkey_text):
        if sys.platform != "win32":
            return True

        converted = hotkey_to_windows(hotkey_text)
        if converted is None:
            return False

        self.unregister_hotkey()
        modifiers, vk = converted
        hwnd = int(self.winId())
        if not user32.RegisterHotKey(hwnd, HOTKEY_ID, modifiers, vk):
            return False

        self._hotkey_registered = True
        return True

    def unregister_hotkey(self):
        if sys.platform == "win32" and self._hotkey_registered:
            user32.UnregisterHotKey(int(self.winId()), HOTKEY_ID)
            self._hotkey_registered = False

    def nativeEvent(self, event_type, message):
        if sys.platform == "win32":
            msg = MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.toggle_main_window()
                return True, 0

        return super().nativeEvent(event_type, message)

    def apply_system_theme(self):
        resolved_mode = "dark" if self.is_system_dark() else "light"
        if resolved_mode == "dark":
            self.apply_dark_theme()
        else:
            self.apply_light_theme()
        self.emoji_view.apply_theme(resolved_mode)

    def is_system_dark(self):
        palette = QApplication.palette()
        return palette.color(QPalette.ColorRole.Window).lightness() < 128

    def apply_light_theme(self):
        self.setStyleSheet("""
            QWidget { background: #f7f8fa; color: #1f2328; }
            QPushButton, QKeySequenceEdit { background: #ffffff; border: 1px solid #c7ccd1; border-radius: 4px; padding: 4px 8px; }
            QPushButton:checked { background: #ddefff; border-color: #5aa4e8; }
            QLineEdit { background: #ffffff; border: 1px solid #c7ccd1; border-radius: 4px; padding: 5px 8px; color: #1f2328; }
            QFrame { background: transparent; }
        """)

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QWidget { background: #16181c; color: #eef1f4; }
            QPushButton, QKeySequenceEdit { background: #24272d; border: 1px solid #3a3f47; border-radius: 4px; padding: 4px 8px; color: #eef1f4; }
            QPushButton:checked { background: #24476b; border-color: #66a8e8; }
            QLineEdit { background: #202329; border: 1px solid #3a3f47; border-radius: 4px; padding: 5px 8px; color: #eef1f4; }
            QFrame { background: transparent; }
        """)

    def display_emoji(self):
        self.emoji_view.set_emojis(emoji_store.list_emojis(self.search_bar.text()))
        self.update_search_placeholder()

    def schedule_display_emoji(self):
        self.search_timer.start()

    def update_search_placeholder(self):
        search_message = "输入表情标题搜索(当前表情数量: " + str(emoji_store.count_emojis()) + ")"
        self.search_bar.setPlaceholderText(search_message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    QPixmapCache.setCacheLimit(65536)
    lock = QLockFile(str(Path(tempfile.gettempdir()) / "cEmoji.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, "提示", "cEmoji 已经在运行中")
        sys.exit(0)

    try:
        image_viewer = ImageViewer()
        image_viewer.show()
        sys.exit(app.exec())
    finally:
        lock.unlock()