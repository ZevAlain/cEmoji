import base64
import ctypes
from ctypes import wintypes
from datetime import datetime
import os
from pathlib import Path
import re
import sys
import tempfile

from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import QEvent, QLockFile, QTimer, Qt, QUrl, qVersion
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence, QPixmapCache
from PySide6.QtNetwork import QLocalServer, QLocalSocket, QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QKeySequenceEdit,
    QSizePolicy,
    QSystemTrayIcon,
    QTabBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import my_icon
import version
import src.cEmojiWidgets as cEmojiWidgets
from src import emoji_store
from src import collection_store
from src.app_paths import ensure_app_dirs
from src.config_service import ConfigService
from src import message_box
from src import theme
from src.window_effects import apply_modern_window_effects


HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040
SW_RESTORE = 9
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
LOCAL_SERVER_NAME = "cEmoji-single-instance"


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


class CollectionNameButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.full_text = ""
        self.scroll_index = 0
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(220)
        self.scroll_timer.timeout.connect(self.scroll_text)
        self.set_full_text(text)

    def set_full_text(self, text):
        self.full_text = str(text)
        self.setToolTip(self.full_text)
        self.stop_scroll()

    def enterEvent(self, event):
        super().enterEvent(event)
        if self.needs_scroll():
            self.scroll_index = 0
            self.scroll_timer.start()
            self.scroll_text()

    def leaveEvent(self, event):
        self.stop_scroll()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.scroll_timer.isActive():
            self.update_elided_text()

    def needs_scroll(self):
        available_width = max(12, self.width() - 28)
        return self.fontMetrics().horizontalAdvance(self.full_text) > available_width

    def stop_scroll(self):
        self.scroll_timer.stop()
        self.scroll_index = 0
        self.update_elided_text()

    def update_elided_text(self):
        available_width = max(12, self.width() - 28)
        self.setText(self.fontMetrics().elidedText(self.full_text, Qt.TextElideMode.ElideRight, available_width))

    def scroll_text(self):
        if not self.needs_scroll():
            self.stop_scroll()
            return
        padded_text = f"{self.full_text}   {self.full_text}"
        visible_text = padded_text[self.scroll_index:] + padded_text[:self.scroll_index]
        available_width = max(12, self.width() - 28)
        while visible_text and self.fontMetrics().horizontalAdvance(visible_text) > available_width:
            visible_text = visible_text[:-1]
        self.setText(visible_text or self.full_text[:1])
        self.scroll_index = (self.scroll_index + 1) % (len(self.full_text) + 3)


class ImageViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("ImageViewer")
        ensure_app_dirs()

        self.config_service = ConfigService()
        self.app_config = self.config_service.load()
        self._tmp_icon_path = None
        self._exiting = False
        self._tray_close_hint_shown = False
        self._local_server = None
        self._hotkey_registered = False
        self._update_reply = None
        self.update_manager = QNetworkAccessManager(self)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self.display_emoji)
        self.emoji_filter = "static"
        self.emoji_sort_mode = "time"
        self.emoji_sort_order = "desc"
        self.current_collection_id = collection_store.active_collection_id()

        self.setWindowTitle("cEmoji")
        self.setFixedSize(500, 690)

        icon = self.create_icon()
        self.setWindowIcon(icon)

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(14, 14, 14, 12)
        self.main_layout.setSpacing(10)
        self.setLayout(self.main_layout)

        self.setup_tray(icon)
        self.setup_local_server()
        self.setup_search()
        self.setup_top_bar()
        self.setup_filter_tabs()
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
        self.tray_icon.show()

    def setup_local_server(self):
        QLocalServer.removeServer(LOCAL_SERVER_NAME)
        self._local_server = QLocalServer(self)
        self._local_server.newConnection.connect(self.on_local_server_connection)
        self._local_server.listen(LOCAL_SERVER_NAME)

    def on_local_server_connection(self):
        while self._local_server and self._local_server.hasPendingConnections():
            connection = self._local_server.nextPendingConnection()
            connection.readyRead.connect(connection.deleteLater)
            connection.disconnected.connect(connection.deleteLater)
        self.show_main_window()

    def setup_top_bar(self):
        self.top_bar_layout = QHBoxLayout()
        self.top_bar_layout.setSpacing(6)
        self.main_layout.addLayout(self.top_bar_layout)
        self.setup_collection_tabs()
        self.top_bar_layout.addStretch(1)
        self.setup_buttons()

    def setup_buttons(self):
        self.upload_button = QPushButton("上传")
        self.upload_button.setObjectName("CompactButton")
        self.manage_button = QPushButton("管理")
        self.manage_button.setObjectName("CompactButton")
        self.manage_button.setCheckable(True)
        self.more_button = QPushButton("菜单⌄")
        self.more_button.setObjectName("CompactButton")
        self.more_menu = QMenu(self)
        self.always_on_top_action = QAction("始终置顶", self)
        self.always_on_top_action.setCheckable(True)
        self.about_action = QAction("关于", self)
        self.cloud_library_action = QAction("云端表情包库", self)
        self.export_current_action = QAction("导出当前合集", self)
        self.export_all_action = QAction("导出所有表情包", self)
        self.clear_current_action = QAction("清空当前合集", self)
        self.clear_all_action = QAction("清空所有表情包", self)
        self.more_menu.addAction(self.always_on_top_action)
        self.more_menu.addSeparator()
        self.more_menu.addAction(self.about_action)
        self.more_menu.addSeparator()
        self.more_menu.addAction(self.cloud_library_action)
        self.more_menu.addSeparator()
        self.more_menu.addAction(self.export_current_action)
        self.more_menu.addAction(self.export_all_action)
        self.more_menu.addSeparator()
        self.more_menu.addAction(self.clear_current_action)
        self.more_menu.addAction(self.clear_all_action)
        self.more_button.setMenu(self.more_menu)

        for button in (self.upload_button, self.manage_button, self.more_button):
            button.setFixedHeight(34)
            self.top_bar_layout.addWidget(button)

        self.always_on_top_action.triggered.connect(self.toggle_always_on_top)
        self.upload_button.clicked.connect(self.show_upload_dialog)
        self.manage_button.clicked.connect(self.show_manage_dialog)
        self.about_action.triggered.connect(self.show_about_dialog)
        self.cloud_library_action.triggered.connect(self.show_cloud_library)
        self.export_current_action.triggered.connect(self.export_current_collection)
        self.export_all_action.triggered.connect(self.export_all_emojis)
        self.clear_current_action.triggered.connect(self.clear_current_collection)
        self.clear_all_action.triggered.connect(self.clear_all_emojis)

    def setup_search(self):
        self.search_bar = QLineEdit(self)
        self.search_bar.setObjectName("SearchBar")
        self.search_bar.textChanged.connect(self.schedule_display_emoji)
        self.update_search_placeholder()

    def setup_collection_tabs(self):
        self.secondary_collection_id = None
        self.local_collection_button = QPushButton(collection_store.DEFAULT_COLLECTION_NAME, self)
        self.local_collection_button.setObjectName("CollectionButton")
        self.local_collection_button.setCheckable(True)
        self.local_collection_button.setFixedHeight(34)
        self.local_collection_button.setFixedWidth(76)
        self.local_collection_button.clicked.connect(lambda: self.select_collection(collection_store.DEFAULT_COLLECTION_ID))
        self.local_collection_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.local_collection_button.customContextMenuRequested.connect(lambda position: self.show_collection_actions_menu(collection_store.DEFAULT_COLLECTION_ID, self.local_collection_button.mapToGlobal(position)))
        self.top_bar_layout.addWidget(self.local_collection_button)

        self.secondary_collection_button = QPushButton(self)
        self.secondary_collection_button.setObjectName("CollectionButton")
        self.secondary_collection_button.setCheckable(True)
        self.secondary_collection_button.setFixedHeight(34)
        self.secondary_collection_button.setFixedWidth(126)
        self.secondary_collection_button.clicked.connect(lambda: self.select_collection(self.secondary_collection_id))
        self.secondary_collection_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.secondary_collection_button.customContextMenuRequested.connect(lambda position: self.show_collection_actions_menu(self.secondary_collection_id, self.secondary_collection_button.mapToGlobal(position)))
        self.top_bar_layout.addWidget(self.secondary_collection_button)

        self.collection_more_button = QPushButton("更多⌄", self)
        self.collection_more_button.setObjectName("CollectionButton")
        self.collection_more_button.setFixedHeight(34)
        self.collection_more_button.setFixedWidth(64)
        self.collection_more_menu = QMenu(self)
        self.collection_more_button.setMenu(self.collection_more_menu)
        self.top_bar_layout.addWidget(self.collection_more_button)
        self.refresh_collection_tabs()

    def refresh_collection_tabs(self):
        collections = collection_store.collections_snapshot()
        collection_ids = {collection.id for collection in collections}
        active_id = self.current_collection_id if self.current_collection_id in collection_ids else collection_store.active_collection_id_snapshot()
        self.current_collection_id = active_id
        non_local = [collection for collection in collections if collection.id != collection_store.DEFAULT_COLLECTION_ID]
        if active_id != collection_store.DEFAULT_COLLECTION_ID:
            self.secondary_collection_id = active_id
        elif self.secondary_collection_id not in {collection.id for collection in non_local}:
            self.secondary_collection_id = non_local[0].id if non_local else None

        self.local_collection_button.setText(collection_store.DEFAULT_COLLECTION_NAME)
        self.local_collection_button.setChecked(active_id == collection_store.DEFAULT_COLLECTION_ID)
        secondary = next((collection for collection in non_local if collection.id == self.secondary_collection_id), None)
        self.secondary_collection_button.setVisible(secondary is not None)
        if secondary is not None:
            self.secondary_collection_button.setText(secondary.name)
            self.secondary_collection_button.setChecked(active_id == secondary.id)

        self.collection_more_menu.clear()
        for collection in collections:
            action = QAction(collection.name, self)
            action.setCheckable(True)
            action.setChecked(collection.id == active_id)
            action.triggered.connect(lambda _checked=False, collection_id=collection.id: self.select_collection(collection_id))
            self.collection_more_menu.addAction(action)
        self.collection_more_menu.addSeparator()
        self.collection_more_menu.addAction("新建合集", self.create_collection)

    def create_collection(self):
        from PySide6.QtWidgets import QInputDialog

        name, accepted = QInputDialog.getText(self, "新建合集", "合集名称：")
        if not accepted:
            return
        name = name.strip()
        if not name:
            return
        self.current_collection_id = collection_store.create_collection(name)
        self.refresh_collection_tabs()
        self.display_emoji()

    def show_collection_actions_menu(self, collection_id, global_position):
        if not collection_id:
            return
        menu = QMenu(self)
        rename_action = QAction("重命名合集", self)
        delete_action = QAction("删除合集", self)
        menu.addAction(rename_action)
        if collection_id != collection_store.DEFAULT_COLLECTION_ID:
            menu.addAction(delete_action)
        action = menu.exec(global_position)
        if action == rename_action:
            self.rename_collection(collection_id)
        elif action == delete_action:
            self.delete_collection(collection_id)

    def rename_collection(self, collection_id):
        from PySide6.QtWidgets import QInputDialog

        current_name = collection_store.collection_name(collection_id)
        name, accepted = QInputDialog.getText(self, "重命名合集", "合集名称：", text=current_name)
        if not accepted:
            return
        if not collection_store.rename_collection(collection_id, name):
            message_box.warning(self, "重命名失败", "合集名称不能为空，或已存在同名合集")
            return
        self.refresh_collection_tabs()

    def delete_collection(self, collection_id):
        name = collection_store.collection_name(collection_id)
        filenames = collection_store.filenames_for_collection(collection_id)
        if not filenames:
            if not message_box.question(self, "删除合集", f"确定要删除合集“{name}”吗？"):
                return
        else:
            if not message_box.question(self, "删除合集", f"确定要删除合集“{name}”吗？\n独占表情会删除本地文件，属于其他合集的表情只会移除合集关系。"):
                return
        emoji_store.clear_collection_emojis(collection_id)
        collection_store.delete_collection(collection_id)
        self.current_collection_id = collection_store.active_collection_id()
        self.refresh_collection_tabs()
        self.display_emoji()

    def select_collection(self, collection_id):
        if not collection_id:
            return
        if collection_id == self.current_collection_id:
            return
        self.current_collection_id = collection_id
        collection_store.set_active_collection(collection_id)
        self.refresh_collection_tabs()
        self.display_emoji()

    def setup_filter_tabs(self):
        self.filter_bar_layout = QHBoxLayout()
        self.filter_bar_layout.setSpacing(8)
        self.main_layout.addLayout(self.filter_bar_layout)

        self.filter_tabs = QTabBar(self)
        self.filter_tabs.setObjectName("EmojiFilterTabs")
        self.filter_tabs.setDrawBase(False)
        self.filter_tabs.addTab("表情包")
        self.filter_tabs.addTab("GIF")
        self.filter_tabs.currentChanged.connect(self.on_filter_tab_changed)
        self.filter_bar_layout.addWidget(self.filter_tabs)

        self.filter_bar_layout.addWidget(self.search_bar, stretch=1)

        self.sort_button = QToolButton(self)
        self.sort_button.setObjectName("SortButton")
        self.sort_button.setFixedSize(86, 36)
        self.sort_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.sort_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.sort_menu = QMenu(self)
        self.sort_by_time_action = QAction("按时间排序", self)
        self.sort_by_time_action.setCheckable(True)
        self.sort_by_name_action = QAction("按名称排序", self)
        self.sort_by_name_action.setCheckable(True)
        self.sort_ascending_action = QAction("升序", self)
        self.sort_ascending_action.setCheckable(True)
        self.sort_descending_action = QAction("降序", self)
        self.sort_descending_action.setCheckable(True)
        self.sort_menu.addAction(self.sort_by_time_action)
        self.sort_menu.addAction(self.sort_by_name_action)
        self.sort_menu.addSeparator()
        self.sort_menu.addAction(self.sort_ascending_action)
        self.sort_menu.addAction(self.sort_descending_action)
        self.sort_button.setMenu(self.sort_menu)
        self.sort_by_time_action.triggered.connect(lambda: self.set_emoji_sort_mode("time"))
        self.sort_by_name_action.triggered.connect(lambda: self.set_emoji_sort_mode("name"))
        self.sort_ascending_action.triggered.connect(lambda: self.set_emoji_sort_order("asc"))
        self.sort_descending_action.triggered.connect(lambda: self.set_emoji_sort_order("desc"))
        self.update_sort_button()
        self.filter_bar_layout.addWidget(self.sort_button)

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
        self.shortcut_layout.addWidget(self.shortcut_label)
        self.shortcut_layout.addWidget(self.hotkey_edit)
        self.shortcut_layout.addWidget(self.hotkey_status_label, stretch=1)
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
        if self._exiting:
            self.cleanup()
            event.accept()
            return

        event.ignore()
        self.hide_to_tray(show_hint=True)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized() and not self._exiting:
            QTimer.singleShot(0, self.hide_to_tray)

    def hide_to_tray(self, show_hint=False):
        if self._exiting:
            return
        self.hide()
        self.tray_icon.show()
        if show_hint and not self._tray_close_hint_shown and self.tray_icon.supportsMessages():
            self.tray_icon.showMessage("cEmoji", "cEmoji 已最小化到托盘，可从托盘菜单退出。", QSystemTrayIcon.MessageIcon.Information, 2500)
            self._tray_close_hint_shown = True

    def on_exit(self):
        self._exiting = True
        self.cleanup()
        QApplication.quit()

    def cleanup(self):
        self.unregister_hotkey()
        if self._local_server is not None:
            self._local_server.close()
            QLocalServer.removeServer(LOCAL_SERVER_NAME)
            self._local_server = None
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
        enabled = self.always_on_top_action.isChecked()
        try:
            set_window_topmost(self, enabled)
        except OSError as error:
            self.always_on_top_action.setChecked(not enabled)
            message_box.warning(self, "置顶失败", str(error))

    def show_upload_dialog(self):
        import src.cEmojiDialogs as cEmojiDialogs

        cEmojiDialogs.show_upload_dialog(self)

    def show_cloud_library(self):
        from src.cloud_emoji_dialog import CloudEmojiDialog

        dialog = CloudEmojiDialog(self)
        dialog.exec()

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

    def reset_copy_tip(self):
        self.copy_tip_label.setText("鼠标左键单击图片可复制到剪切板，右键可置顶")

    def export_current_collection(self):
        self.export_emojis(collection_id=self.current_collection_id, scope_name=collection_store.collection_name(self.current_collection_id), title="导出当前合集")

    def export_all_emojis(self):
        self.export_emojis(collection_id=None, scope_name="全部表情包", title="导出所有表情包")

    def export_emojis(self, collection_id, scope_name, title):
        if collection_id is None:
            has_items = emoji_store.count_emojis() > 0
        else:
            has_items = bool(collection_store.filenames_for_collection_snapshot(collection_id))
        if not has_items:
            message_box.information(self, "导出表情包", "当前没有可导出的表情包")
            return

        safe_scope = re.sub(r"[\\/:*?\"<>|]+", "_", scope_name).strip() or "emojis"
        default_name = f"cEmoji_{safe_scope}_{datetime.now():%Y%m%d_%H%M%S}.zip"
        default_path = Path.home() / default_name
        archive_path, _ = QFileDialog.getSaveFileName(self, title, str(default_path), "ZIP files (*.zip)")
        if not archive_path:
            return

        archive_path = Path(archive_path)
        if archive_path.suffix.lower() != ".zip":
            archive_path = archive_path.with_suffix(".zip")

        try:
            exported = emoji_store.export_emojis(archive_path, collection_id)
        except OSError as error:
            message_box.warning(self, "导出失败", str(error))
            return

        if exported == 0:
            message_box.information(self, "导出表情包", "当前没有可导出的表情包")
            return

        message_box.information(self, "导出完成", f"已导出 {exported} 个表情包到：\n{archive_path}")

    def clear_current_collection(self):
        name = collection_store.collection_name(self.current_collection_id)
        count = len(collection_store.filenames_for_collection_snapshot(self.current_collection_id))
        if count == 0:
            message_box.information(self, "清空合集", "当前合集没有表情包")
            return
        if not message_box.question(self, "确认清空", f"确定要清空当前合集“{name}”中的 {count} 个表情包吗？\n属于其他合集的表情只会从当前合集移除。"):
            return

        removed_files, removed_from_collection = emoji_store.clear_collection_emojis(self.current_collection_id)
        self.display_emoji()
        message_box.information(self, "清空完成", f"已删除 {removed_files} 个本地文件\n已从当前合集移除 {removed_from_collection} 个共享表情")

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
        apply_modern_window_effects(self, resolved_mode)

    def display_emoji(self):
        search_text = self.search_bar.text()
        image_paths = self.filtered_emojis(search_text)
        total_count = len(image_paths) if not search_text else len(self.filtered_emojis())
        collection_count = len(collection_store.filenames_for_collection_snapshot(self.current_collection_id))
        if emoji_store.count_emojis() == 0:
            self.emoji_view.set_empty_message("还没有表情，点击“上传”导入图片或 ZIP")
        elif total_count == 0:
            self.emoji_view.set_empty_message("当前分类还没有表情")
        elif search_text and not image_paths:
            self.emoji_view.set_empty_message("没有找到匹配的表情")
        else:
            self.emoji_view.set_empty_message("")
        self.emoji_view.set_emojis(image_paths)
        self.update_search_placeholder(len(image_paths) if not search_text else total_count, collection_count)

    def filtered_emojis(self, search_text=""):
        image_paths = emoji_store.list_emojis(search_text, self.current_collection_id)
        if self.emoji_filter == "animated":
            return self.sorted_emojis([path for path in image_paths if path.suffix.lower() == ".gif"])

        return self.sorted_emojis([path for path in image_paths if path.suffix.lower() != ".gif"])

    def sorted_emojis(self, image_paths):
        pinned_paths = []
        normal_paths = []
        for image_path in image_paths:
            filename = emoji_store.display_name_for_thumbnail(image_path)
            if emoji_store.is_pinned(filename):
                pinned_paths.append(image_path)
            else:
                normal_paths.append(image_path)

        reverse = self.emoji_sort_order == "desc"
        if self.emoji_sort_mode == "name":
            return sorted(pinned_paths, key=self.emoji_name_sort_key, reverse=reverse) + sorted(normal_paths, key=self.emoji_name_sort_key, reverse=reverse)

        return sorted(pinned_paths, key=self.emoji_time_sort_key, reverse=reverse) + sorted(normal_paths, key=self.emoji_time_sort_key, reverse=reverse)

    @staticmethod
    def emoji_name_sort_key(image_path):
        return emoji_store.display_title_for_thumbnail(image_path).casefold()

    @staticmethod
    def emoji_time_sort_key(image_path):
        filename = emoji_store.display_name_for_thumbnail(image_path)
        original_path = emoji_store.original_image_path(filename)
        time_path = original_path if original_path.exists() else image_path
        return time_path.stat().st_ctime

    def set_emoji_sort_mode(self, mode):
        self.emoji_sort_mode = "name" if mode == "name" else "time"
        self.update_sort_button()
        self.display_emoji()

    def set_emoji_sort_order(self, order):
        self.emoji_sort_order = "asc" if order == "asc" else "desc"
        self.update_sort_button()
        self.display_emoji()

    def update_sort_button(self):
        ascending = self.emoji_sort_order == "asc"
        mode_label = "名称" if self.emoji_sort_mode == "name" else "时间"
        order_label = "升序" if ascending else "降序"
        self.sort_button.setIcon(QIcon())
        self.sort_button.setText(f"{mode_label}⌄")
        self.sort_button.setToolTip(f"排序：{mode_label}，{order_label}")
        self.sort_by_time_action.setChecked(self.emoji_sort_mode == "time")
        self.sort_by_name_action.setChecked(self.emoji_sort_mode == "name")
        self.sort_ascending_action.setChecked(ascending)
        self.sort_descending_action.setChecked(not ascending)

    def on_filter_tab_changed(self, index):
        self.emoji_filter = "animated" if index == 1 else "static"
        self.display_emoji()

    def schedule_display_emoji(self):
        self.search_timer.start()

    def update_search_placeholder(self, count=None, collection_count=None):
        if count is None:
            count = len(self.filtered_emojis())
        if collection_count is None:
            collection_count = len(collection_store.filenames_for_collection_snapshot(self.current_collection_id))
        label = "GIF" if self.emoji_filter == "animated" else "当前"
        search_message = f"搜标题｜合集 {collection_count}｜{label} {count}"
        self.search_bar.setPlaceholderText(search_message)


def notify_existing_instance():
    socket = QLocalSocket()
    socket.connectToServer(LOCAL_SERVER_NAME)
    if not socket.waitForConnected(800):
        return False
    socket.write(b"show")
    socket.flush()
    socket.waitForBytesWritten(800)
    socket.disconnectFromServer()
    return True


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    configure_app_font(app)
    QPixmapCache.setCacheLimit(65536)
    lock = QLockFile(str(Path(tempfile.gettempdir()) / "cEmoji.lock"))
    if not lock.tryLock(100):
        if not notify_existing_instance():
            message_box.information(None, "提示", "cEmoji 已经在运行中")
        sys.exit(0)

    try:
        image_viewer = ImageViewer()
        image_viewer.show()
        sys.exit(app.exec())
    finally:
        lock.unlock()