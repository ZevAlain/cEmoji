import base64
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re
import sys
import tempfile

from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import QEvent, QLockFile, QTimer, Qt, QUrl, qVersion
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence, QPixmapCache
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QCheckBox,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QKeySequenceEdit,
    QSizePolicy,
    QSystemTrayIcon,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

import my_icon
import version
import src.cEmojiWidgets as cEmojiWidgets
from src import emoji_store
from src.app_paths import ensure_app_dirs
from src.config_service import ConfigService
from src import message_box
from src import theme


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
OFFICIAL_SITE_URL = "https://zevalain.github.io/cEmoji/"
LATEST_RELEASE_URL = "https://github.com/ZevAlain/cEmoji/releases/latest"
UPDATE_LINK_TEXT = '<a href="check-update">检查更新</a>'
UPDATE_CHECKING_TEXT = '<span style="color: gray;">检查中...</span>'


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


def configure_app_font(app):
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)


class ImageViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("ImageViewer")
        ensure_app_dirs()

        self.config_service = ConfigService()
        self.app_config = self.config_service.load()
        self._tmp_icon_path = None
        self._exiting = False
        self._hotkey_registered = False
        self._update_reply = None
        self.update_manager = QNetworkAccessManager(self)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self.display_emoji)
        self.emoji_filter = "static"

        self.setWindowTitle("cEmoji")
        self.setFixedSize(500, 690)

        icon = self.create_icon()
        self.setWindowIcon(icon)

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(14, 14, 14, 12)
        self.main_layout.setSpacing(10)
        self.setLayout(self.main_layout)

        self.setup_tray(icon)
        self.setup_search()
        self.setup_filter_tabs()
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
        self.more_button = QPushButton("更多")
        self.more_menu = QMenu(self)
        self.about_action = QAction("关于", self)
        self.clear_action = QAction("清空所有表情包", self)
        self.more_menu.addAction(self.about_action)
        self.more_menu.addSeparator()
        self.more_menu.addAction(self.clear_action)
        self.more_button.setMenu(self.more_menu)

        for button in (self.always_on_top_button, self.upload_button, self.manage_button, self.more_button):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.buttons_layout.addWidget(button)

        self.always_on_top_button.clicked.connect(self.toggle_always_on_top)
        self.upload_button.clicked.connect(self.show_upload_dialog)
        self.manage_button.clicked.connect(self.show_manage_dialog)
        self.about_action.triggered.connect(self.show_about_dialog)
        self.clear_action.triggered.connect(self.clear_all_emojis)

    def setup_search(self):
        self.search_bar = QLineEdit(self)
        self.search_bar.textChanged.connect(self.schedule_display_emoji)
        self.update_search_placeholder()
        self.main_layout.addWidget(self.search_bar)

    def setup_filter_tabs(self):
        self.filter_tabs = QTabBar(self)
        self.filter_tabs.setObjectName("EmojiFilterTabs")
        self.filter_tabs.setDrawBase(False)
        self.filter_tabs.addTab("表情包")
        self.filter_tabs.addTab("动态表情包")
        self.filter_tabs.currentChanged.connect(self.on_filter_tab_changed)
        self.main_layout.addWidget(self.filter_tabs)

    def setup_emoji_view(self):
        self.emoji_view = cEmojiWidgets.EmojiListWidget(self)
        self.emoji_view.emoji_deleted.connect(self.display_emoji)
        self.emoji_view.emoji_copied.connect(self.on_emoji_copied)
        self.main_layout.addWidget(self.emoji_view)

    def setup_footer(self):
        self.shortcut_frame = QFrame(self)
        self.shortcut_frame.setObjectName("ShortcutFrame")
        self.shortcut_layout = QHBoxLayout(self.shortcut_frame)
        self.shortcut_layout.setContentsMargins(10, 8, 10, 8)
        self.shortcut_layout.setSpacing(8)
        self.shortcut_label = QLabel("快捷呼出/隐藏", self)
        self.hotkey_edit = QKeySequenceEdit(QKeySequence(self.app_config.hotkey), self)
        self.hotkey_edit.setMaximumWidth(150)
        self.hotkey_edit.setToolTip("在这里输入快捷键，用于呼出或隐藏主界面")
        self.hotkey_edit.editingFinished.connect(self.save_hotkey)
        self.hotkey_status_label = QLabel("在这里输入快捷键来控制", self)
        self.hotkey_status_label.setObjectName("HotkeyStatusLabel")
        self.hide_after_copy_checkbox = QCheckBox("复制后隐藏", self)
        self.hide_after_copy_checkbox.setChecked(self.app_config.hide_after_copy)
        self.hide_after_copy_checkbox.toggled.connect(self.save_hide_after_copy)
        self.shortcut_layout.addWidget(self.shortcut_label)
        self.shortcut_layout.addWidget(self.hotkey_edit)
        self.shortcut_layout.addWidget(self.hotkey_status_label, stretch=1)
        self.shortcut_layout.addWidget(self.hide_after_copy_checkbox)
        self.main_layout.addWidget(self.shortcut_frame)

        self.footer_layout = QHBoxLayout()
        self.footer_layout.setSpacing(10)
        self.main_layout.addLayout(self.footer_layout)

        self.copy_tip_label = QLabel("鼠标左键单击图片可复制到剪切板，右键可置顶", self)
        self.copy_tip_label.setObjectName("CopyTipLabel")
        self.copy_tip_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.copy_tip_reset_timer = QTimer(self)
        self.copy_tip_reset_timer.setSingleShot(True)
        self.copy_tip_reset_timer.setInterval(1500)
        self.copy_tip_reset_timer.timeout.connect(self.reset_copy_tip)
        self.update_link = QLabel(UPDATE_LINK_TEXT, self)
        self.update_link.setObjectName("UpdateLink")
        self.update_link.setTextFormat(Qt.TextFormat.RichText)
        self.update_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_link.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.update_link.setFixedSize(72, 22)
        self.update_link.setOpenExternalLinks(False)
        self.update_link.linkActivated.connect(self.check_for_updates)
        self.version_label = QLabel("版本号：" + version.cEmojiversion, self)
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setFixedHeight(22)
        self.footer_meta_frame = QFrame(self)
        self.footer_meta_layout = QHBoxLayout(self.footer_meta_frame)
        self.footer_meta_layout.setContentsMargins(0, 0, 0, 0)
        self.footer_meta_layout.setSpacing(10)
        self.footer_meta_layout.addWidget(self.update_link)
        self.footer_meta_layout.addWidget(self.version_label)
        self.footer_layout.addWidget(self.copy_tip_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.footer_layout.addStretch(1)
        self.footer_layout.addWidget(self.footer_meta_frame, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def open_official_site(self, _url=None):
        QDesktopServices.openUrl(QUrl(OFFICIAL_SITE_URL))

    def show_about_dialog(self):
        message = QMessageBox(self)
        message.setWindowTitle("关于 cEmoji")
        message.setIcon(QMessageBox.Icon.Information)
        message.setText(f"cEmoji {version.cEmojiversion}")
        message.setInformativeText(
            "一个用于管理、搜索和复制表情包的桌面工具。\n\n"
            "本程序基于 PySide6 / Qt 构建，并按 GNU GPL v3 开源发布。\n\n"
            "许可证与声明\n"
            "- cEmoji：GNU General Public License v3.0。完整文本见 LICENSE。\n"
            "- PySide6：由 Qt for Python 项目提供，通常以 LGPLv3/GPLv3/商业许可发布。\n"
            "- Qt：Qt Company / Qt Project，通常以 LGPLv3/GPLv3/商业许可发布。\n"
            "- Pillow：Python Imaging Library fork，用于图片处理。\n\n"
            f"运行环境\n"
            f"- Python：{sys.version.split()[0]}\n"
            f"- PySide6：{PYSIDE_VERSION}\n"
            f"- Qt：{qVersion()}\n\n"
            f"项目主页\n{OFFICIAL_SITE_URL}"
        )
        open_button = message.addButton("打开官网", QMessageBox.ButtonRole.ActionRole)
        message.addButton("确定", QMessageBox.ButtonRole.AcceptRole)
        message.exec()
        if message.clickedButton() == open_button:
            self.open_official_site()

    def check_for_updates(self, _url=None):
        if self._update_reply is not None:
            return

        self.update_link.setText(UPDATE_CHECKING_TEXT)
        self.update_link.setToolTip("正在检查更新...")
        request = QNetworkRequest(QUrl(LATEST_RELEASE_URL))
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute, QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        request.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "cEmoji")
        self._update_reply = self.update_manager.get(request)
        self._update_reply.finished.connect(self.on_update_check_finished)

    def on_update_check_finished(self):
        reply = self._update_reply
        self._update_reply = None
        self.update_link.setText(UPDATE_LINK_TEXT)
        self.update_link.setToolTip("")

        if reply is None:
            return

        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                message_box.warning(self, "检查更新", f"检查更新失败：{reply.errorString()}")
                return

            response_text = bytes(reply.readAll()).decode("utf-8", errors="replace")
            release_url = self.extract_release_url(response_text) or reply.url().toString()
            release = {
                "version": self.extract_release_version(release_url),
                "html_url": release_url or LATEST_RELEASE_URL,
            }
            latest_version = release.get("version", "").strip()
            current_version = version.cEmojiversion
            if not latest_version:
                message_box.warning(self, "检查更新", "没有找到发布版本。")
                return

            if not self.is_newer_version(latest_version, current_version):
                message_box.information(self, "检查更新", f"当前已是最新版本：{current_version}")
                return

            self.show_update_available(release, latest_version, current_version)
        except Exception as error:
            message_box.warning(self, "检查更新", f"检查更新失败：{error}")
        finally:
            reply.deleteLater()

    @staticmethod
    def extract_release_version(text):
        match = re.search(r"[vV]?\d+(?:\.\d+){1,3}", text)
        return match.group(0) if match else ""

    @staticmethod
    def extract_release_url(text):
        absolute_match = re.search(r"https://github\.com/ZevAlain/cEmoji/releases/tag/[^\"'<>\s]+", text)
        if absolute_match:
            return absolute_match.group(0)

        relative_match = re.search(r"/ZevAlain/cEmoji/releases/tag/[^\"'<>\s]+", text)
        if relative_match:
            return "https://github.com" + relative_match.group(0)

        return ""

    @staticmethod
    def is_newer_version(latest_version, current_version):
        latest = ImageViewer.parse_version(latest_version)
        current = ImageViewer.parse_version(current_version)
        if latest is None or current is None:
            return latest_version and latest_version != current_version
        return latest > current

    @staticmethod
    def parse_version(version_text):
        version_text = version_text.strip().lstrip("vV")
        parts = version_text.split(".")
        numbers = []
        for part in parts:
            if not part.isdigit():
                break
            numbers.append(int(part))

        if not numbers:
            return None

        while len(numbers) < 3:
            numbers.append(0)
        return tuple(numbers[:3])

    def show_update_available(self, release, latest_version, current_version):
        message = QMessageBox(self)
        message.setWindowTitle("检查更新")
        message.setIcon(QMessageBox.Icon.Information)
        message.setText(f"发现新版本：{latest_version}")
        message.setInformativeText(f"当前版本：{current_version}")

        open_button = message.addButton("打开下载页面", QMessageBox.ButtonRole.AcceptRole)
        message.addButton("稍后", QMessageBox.ButtonRole.RejectRole)
        message.exec()

        if message.clickedButton() == open_button:
            QDesktopServices.openUrl(QUrl(release.get("html_url", OFFICIAL_SITE_URL)))

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
            message_box.warning(self, "置顶失败", str(error))

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

    def on_emoji_copied(self, filename):
        self.copy_tip_label.setText(f"已复制：{emoji_store.display_title_for_filename(filename)}")
        self.copy_tip_reset_timer.start()
        if self.app_config.hide_after_copy:
            QTimer.singleShot(120, self.hide_to_tray)

    def reset_copy_tip(self):
        self.copy_tip_label.setText("鼠标左键单击图片可复制到剪切板，右键可置顶")

    def save_hide_after_copy(self, checked):
        self.set_config_value("hide_after_copy", checked)

    def clear_all_emojis(self):
        if not message_box.question(self, "确认清空", "确定要清空全部表情包吗？"):
            return

        removed = emoji_store.clear_emojis()
        self.display_emoji()
        message_box.information(self, "清空完成", f"已删除 {removed} 个文件")

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
        resolved_mode = theme.system_theme_mode(QApplication.palette())
        self.setStyleSheet(theme.window_stylesheet(resolved_mode))
        self.emoji_view.apply_theme(resolved_mode)

    def display_emoji(self):
        search_text = self.search_bar.text()
        image_paths = self.filtered_emojis(search_text)
        total_count = len(self.filtered_emojis())
        if emoji_store.count_emojis() == 0:
            self.emoji_view.set_empty_message("还没有表情，点击“上传”导入图片或 ZIP")
        elif total_count == 0:
            self.emoji_view.set_empty_message("当前分类还没有表情")
        elif search_text and not image_paths:
            self.emoji_view.set_empty_message("没有找到匹配的表情")
        else:
            self.emoji_view.set_empty_message("")
        self.emoji_view.set_emojis(image_paths)
        self.update_search_placeholder()

    def filtered_emojis(self, search_text=""):
        image_paths = emoji_store.list_emojis(search_text)
        if self.emoji_filter == "animated":
            return [path for path in image_paths if path.suffix.lower() == ".gif"]

        return [path for path in image_paths if path.suffix.lower() != ".gif"]

    def on_filter_tab_changed(self, index):
        self.emoji_filter = "animated" if index == 1 else "static"
        self.display_emoji()

    def schedule_display_emoji(self):
        self.search_timer.start()

    def update_search_placeholder(self):
        count = len(self.filtered_emojis())
        label = "动态表情数量" if self.emoji_filter == "animated" else "表情数量"
        search_message = f"输入表情标题搜索(当前{label}: {count})"
        self.search_bar.setPlaceholderText(search_message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    configure_app_font(app)
    QPixmapCache.setCacheLimit(65536)
    lock = QLockFile(str(Path(tempfile.gettempdir()) / "cEmoji.lock"))
    if not lock.tryLock(100):
        message_box.information(None, "提示", "cEmoji 已经在运行中")
        sys.exit(0)

    try:
        image_viewer = ImageViewer()
        image_viewer.show()
        sys.exit(app.exec())
    finally:
        lock.unlock()