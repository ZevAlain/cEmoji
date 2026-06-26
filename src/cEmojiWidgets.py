import subprocess

from PySide6.QtCore import QAbstractListModel, QEvent, QModelIndex, QRect, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QListView, QMenu, QMessageBox, QStyledItemDelegate, QToolTip

from src import emoji_store
from src.app_paths import BIN_DIR


class EmojiListModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_paths = []
        self.icon_cache = {}

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self.image_paths)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        image_path = self.image_paths[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return image_path.name
        if role == Qt.ItemDataRole.DecorationRole:
            cache_key = str(image_path)
            icon = self.icon_cache.get(cache_key)
            if icon is None:
                icon = QIcon(cache_key)
                self.icon_cache[cache_key] = icon
            return icon
        if role == Qt.ItemDataRole.ToolTipRole:
            return image_path.name
        if role == Qt.ItemDataRole.UserRole:
            return image_path.name
        return None

    def set_paths(self, image_paths):
        self.beginResetModel()
        self.image_paths = list(image_paths)
        live_paths = {str(path) for path in self.image_paths}
        self.icon_cache = {key: icon for key, icon in self.icon_cache.items() if key in live_paths}
        self.endResetModel()

    def filename_at(self, index):
        if not index.isValid():
            return None
        return self.image_paths[index.row()].name


class EmojiItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        view = self.parent()
        if not getattr(view, "manage_mode", False):
            return

        rect = delete_button_rect(option.rect)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(QColor(30, 34, 38, 210))
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QPen(QColor(255, 255, 255), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        margin = 6
        painter.drawLine(rect.left() + margin, rect.top() + margin, rect.right() - margin, rect.bottom() - margin)
        painter.drawLine(rect.right() - margin, rect.top() + margin, rect.left() + margin, rect.bottom() - margin)
        painter.restore()


def delete_button_rect(item_rect):
    size = 24
    return QRect(item_rect.right() - size - 8, item_rect.top() + 8, size, size)


class EmojiListWidget(QListView):
    emoji_deleted = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manage_mode = False
        self.emoji_model = EmojiListModel(self)
        self.setModel(self.emoji_model)
        self.setItemDelegate(EmojiItemDelegate(self))
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setUniformItemSizes(True)
        self.setLayoutMode(QListView.LayoutMode.Batched)
        self.setBatchSize(128)
        self.setIconSize(QSize(100, 100))
        self.setGridSize(QSize(150, 132))
        self.setSpacing(6)
        self.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.clicked.connect(self.handle_index_clicked)
        self.customContextMenuRequested.connect(self.show_item_menu)
        self.apply_theme("light")

    def set_manage_mode(self, enabled):
        self.manage_mode = enabled
        self.viewport().update()

    def apply_theme(self, mode):
        if mode == "dark":
            self.setStyleSheet("""
                QListView { background: #101216; border: 1px solid #30343b; border-radius: 4px; outline: 0; }
                QListView::item { color: #eef1f4; padding: 5px; border-radius: 4px; }
                QListView::item:hover { background: #242830; }
                QListView::item:selected { background: #2e5f91; color: #ffffff; border: 1px solid #74b8ff; }
                QListView::item:selected:hover { background: #2e5f91; color: #ffffff; border: 1px solid #74b8ff; }
            """)
        elif mode == "light":
            self.setStyleSheet("""
                QListView { background: #ffffff; border: 1px solid #d0d5db; border-radius: 4px; outline: 0; }
                QListView::item { color: #1f2328; padding: 5px; border-radius: 4px; }
                QListView::item:hover { background: #eef5ff; }
                QListView::item:selected { background: #d8ebff; color: #0b3768; border: 1px solid #4d9de8; }
                QListView::item:selected:hover { background: #d8ebff; color: #0b3768; border: 1px solid #4d9de8; }
            """)
        else:
            self.setStyleSheet("""
                QListView { border: 1px solid palette(mid); border-radius: 4px; outline: 0; }
                QListView::item { padding: 5px; border-radius: 4px; }
                QListView::item:selected { background: palette(highlight); color: palette(highlighted-text); }
                QListView::item:selected:hover { background: palette(highlight); color: palette(highlighted-text); }
            """)

    def set_emojis(self, image_paths):
        self.setUpdatesEnabled(False)
        try:
            self.emoji_model.set_paths(image_paths)
        finally:
            self.setUpdatesEnabled(True)

    def handle_index_clicked(self, index):
        filename = self.emoji_model.filename_at(index)
        if filename is None:
            return

        if self.manage_mode:
            return

        image_path = emoji_store.original_image_path(filename)
        if image_path.suffix.lower() == ".gif":
            self.copy_gif(image_path)
        else:
            QApplication.clipboard().setPixmap(QPixmap(str(image_path)))

    def show_item_menu(self, position):
        index = self.indexAt(position)
        filename = self.emoji_model.filename_at(index)
        if filename is None:
            return

        menu = QMenu(self)
        delete_action = QAction("删除", self)
        menu.addAction(delete_action)
        action = menu.exec(self.mapToGlobal(position))
        if action == delete_action:
            self.delete_item(filename, confirm=True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(event.position().toPoint())
            if index.isValid():
                self.setCurrentIndex(index)

            if self.manage_mode:
                filename = self.emoji_model.filename_at(index)
                if filename is not None and delete_button_rect(self.visualRect(index)).contains(event.position().toPoint()):
                    self.delete_item(filename, confirm=False)
                    return

        super().mousePressEvent(event)

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.ToolTip and self.manage_mode:
            position = event.pos()
            index = self.indexAt(position)
            filename = self.emoji_model.filename_at(index)
            button_rect = delete_button_rect(self.visualRect(index))
            if filename is not None and button_rect.contains(position):
                QToolTip.showText(event.globalPos(), "删除", self.viewport(), button_rect)
                return True

        return super().viewportEvent(event)

    def delete_item(self, filename, confirm):
        if confirm:
            ret = QMessageBox.question(self, "确认删除", "你确定要删除这个表情吗？")
            if ret != QMessageBox.StandardButton.Yes:
                return

        if emoji_store.delete_emoji(filename):
            self.emoji_deleted.emit()

    def copy_gif(self, image_path):
        command = BIN_DIR / "cpgif.exe"
        try:
            subprocess.Popen(
                [str(command), str(image_path)],
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            )
        except OSError as error:
            QMessageBox.warning(self, "复制失败", str(error))

