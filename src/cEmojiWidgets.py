import subprocess

from PySide6.QtCore import QAbstractListModel, QEvent, QMimeData, QModelIndex, QPersistentModelIndex, QRect, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QMovie, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QInputDialog, QListView, QMenu, QStyle, QStyledItemDelegate, QToolTip

from src import emoji_store
from src import message_box
from src import theme


ImagePathRole = Qt.ItemDataRole.UserRole + 1


class EmojiListModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_paths = []
        self.pixmap_cache = {}

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self.image_paths)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        image_path = self.image_paths[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return emoji_store.display_title_for_thumbnail(image_path)
        if role == Qt.ItemDataRole.ToolTipRole:
            return emoji_store.display_title_for_thumbnail(image_path)
        if role == Qt.ItemDataRole.UserRole:
            return emoji_store.display_name_for_thumbnail(image_path)
        if role == ImagePathRole:
            return str(image_path)
        return None

    def set_paths(self, image_paths):
        self.beginResetModel()
        self.image_paths = list(image_paths)
        live_paths = {str(path) for path in self.image_paths}
        self.pixmap_cache = {key: pixmap for key, pixmap in self.pixmap_cache.items() if key in live_paths}
        self.endResetModel()

    def filename_at(self, index):
        if not index.isValid():
            return None
        return emoji_store.display_name_for_thumbnail(self.image_paths[index.row()])

    def pixmap_at(self, index):
        if not index.isValid():
            return QPixmap()
        image_path = self.image_paths[index.row()]
        cache_key = str(image_path)
        pixmap = self.pixmap_cache.get(cache_key)
        if pixmap is None:
            pixmap = QPixmap(cache_key)
            self.pixmap_cache[cache_key] = pixmap
        return pixmap


class EmojiItemDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(150, 132)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.paint_background(painter, option)
        self.paint_image(painter, option, index)
        self.paint_text(painter, option, index)
        self.paint_pinned_badge(painter, option, index)
        self.paint_gif_badge(painter, option, index)
        view = self.parent()
        if not getattr(view, "manage_mode", False):
            painter.restore()
            return

        rect = delete_button_rect(option.rect)
        painter.setBrush(QColor(30, 34, 38, 210))
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QPen(QColor(255, 255, 255), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        margin = 6
        painter.drawLine(rect.left() + margin, rect.top() + margin, rect.right() - margin, rect.bottom() - margin)
        painter.drawLine(rect.right() - margin, rect.top() + margin, rect.left() + margin, rect.bottom() - margin)
        painter.restore()

    def paint_background(self, painter, option):
        view = self.parent()
        color = theme.colors(getattr(view, "theme_mode", "light"))
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setBrush(QColor(color["item_selected"]))
            painter.setPen(QPen(QColor(color["accent"]), 1))
            painter.drawRoundedRect(option.rect.adjusted(2, 2, -2, -2), 7, 7)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.setBrush(QColor(color["item_hover"]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(option.rect.adjusted(2, 2, -2, -2), 7, 7)

    def paint_image(self, painter, option, index):
        model = index.model()
        view = self.parent()
        pixmap = view.animated_pixmap_for_index(index) if hasattr(view, "animated_pixmap_for_index") else QPixmap()
        if pixmap.isNull():
            pixmap = model.pixmap_at(index) if hasattr(model, "pixmap_at") else QPixmap(index.data(ImagePathRole))
        if pixmap.isNull():
            return

        image_rect = QRect(option.rect.left() + 25, option.rect.top() + 8, 100, 100)
        draw_size = pixmap.size()
        if draw_size.width() > image_rect.width() or draw_size.height() > image_rect.height():
            draw_size.scale(image_rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
        draw_rect = QRect(0, 0, draw_size.width(), draw_size.height())
        draw_rect.moveCenter(image_rect.center())
        painter.drawPixmap(draw_rect, pixmap)

    def paint_text(self, painter, option, index):
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        text_rect = QRect(option.rect.left() + 6, option.rect.top() + 108, option.rect.width() - 12, 20)
        metrics = painter.fontMetrics()
        view = self.parent()
        color = theme.colors(getattr(view, "theme_mode", "light"))
        painter.setPen(QColor(color["text"]))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, metrics.elidedText(text, Qt.TextElideMode.ElideMiddle, text_rect.width()))

    def paint_gif_badge(self, painter, option, index):
        image_path = index.data(ImagePathRole) or ""
        if not image_path.lower().endswith(".gif"):
            return
        rect = QRect(option.rect.right() - 42, option.rect.top() + 10, 34, 18)
        painter.setBrush(QColor(22, 143, 122, 230))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 5, 5)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "GIF")

    def paint_pinned_badge(self, painter, option, index):
        filename = index.data(Qt.ItemDataRole.UserRole) or ""
        if not emoji_store.is_pinned(filename):
            return
        rect = QRect(option.rect.left() + 8, option.rect.top() + 10, 38, 18)
        painter.setBrush(QColor(188, 122, 18, 235))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 5, 5)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "置顶")


def delete_button_rect(item_rect):
    size = 24
    return QRect(item_rect.right() - size - 8, item_rect.top() + 8, size, size)


class EmojiListWidget(QListView):
    emoji_deleted = Signal()
    emoji_copied = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manage_mode = False
        self.theme_mode = "light"
        self.empty_message = ""
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.setInterval(1000)
        self.hover_timer.timeout.connect(self.start_hover_movie)
        self.hover_gif_index = QPersistentModelIndex()
        self.hover_gif_path = None
        self.active_movie_index = QPersistentModelIndex()
        self.active_movie_path = None
        self.active_movie = None
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
        self.theme_mode = mode
        self.setStyleSheet(theme.emoji_view_stylesheet(mode))
        self.viewport().update()

    def set_emojis(self, image_paths):
        self.stop_hover_movie()
        self.setUpdatesEnabled(False)
        try:
            self.emoji_model.set_paths(image_paths)
        finally:
            self.setUpdatesEnabled(True)
            self.viewport().update()

    def set_empty_message(self, message):
        self.empty_message = message
        self.viewport().update()

    def handle_index_clicked(self, index):
        filename = self.emoji_model.filename_at(index)
        if filename is None:
            return

        if self.manage_mode:
            return

        image_path = emoji_store.original_image_path(filename)
        if image_path.suffix.lower() == ".gif":
            copied = self.copy_gif(image_path)
        else:
            pixmap = QPixmap(str(image_path))
            copied = not pixmap.isNull()
            if copied:
                QApplication.clipboard().setPixmap(pixmap)
        if copied:
            self.emoji_copied.emit(filename)

    def show_item_menu(self, position):
        index = self.indexAt(position)
        filename = self.emoji_model.filename_at(index)
        if filename is None:
            return

        menu = QMenu(self)
        pinned = emoji_store.is_pinned(filename)
        pin_action = QAction("取消置顶" if pinned else "置顶", self)
        rename_action = QAction("重命名", self)
        show_file_action = QAction("打开文件位置", self)
        delete_action = QAction("删除", self)
        menu.addAction(pin_action)
        menu.addAction(rename_action)
        menu.addAction(show_file_action)
        menu.addSeparator()
        menu.addAction(delete_action)
        action = menu.exec(self.mapToGlobal(position))
        if action == pin_action:
            self.toggle_pinned(filename, not pinned)
        elif action == rename_action:
            self.rename_item(filename)
        elif action == show_file_action:
            self.open_file_location(filename)
        elif action == delete_action:
            self.delete_item(filename, confirm=True)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.model() is None or self.model().rowCount() != 0 or not self.empty_message:
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QColor(theme.colors(self.theme_mode)["empty"]))
        painter.drawText(self.viewport().rect(), Qt.AlignmentFlag.AlignCenter, self.empty_message)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.update_hover_gif(event.position().toPoint())

    def leaveEvent(self, event):
        self.clear_hover_gif()
        super().leaveEvent(event)

    def update_hover_gif(self, position):
        index = self.indexAt(position)
        image_path = index.data(ImagePathRole) if index.isValid() else None
        if not image_path or not image_path.lower().endswith(".gif"):
            self.clear_hover_gif()
            return

        if image_path == self.hover_gif_path:
            return

        self.hover_timer.stop()
        self.stop_hover_movie()
        self.hover_gif_index = QPersistentModelIndex(index)
        self.hover_gif_path = image_path
        self.hover_timer.start()

    def clear_hover_gif(self):
        self.hover_timer.stop()
        self.hover_gif_index = QPersistentModelIndex()
        self.hover_gif_path = None
        self.stop_hover_movie()

    def start_hover_movie(self):
        if not self.hover_gif_index.isValid() or not self.hover_gif_path:
            return

        self.stop_hover_movie()
        self.active_movie_index = QPersistentModelIndex(self.hover_gif_index)
        self.active_movie_path = self.hover_gif_path
        self.active_movie = QMovie(self.active_movie_path)
        self.active_movie.frameChanged.connect(self.update_active_movie_frame)
        self.active_movie.start()
        self.update_active_movie_frame()

    def stop_hover_movie(self):
        if self.active_movie is not None:
            self.active_movie.stop()
            self.active_movie.deleteLater()
        self.active_movie = None
        active_index = QModelIndex(self.active_movie_index) if self.active_movie_index.isValid() else QModelIndex()
        self.active_movie_index = QPersistentModelIndex()
        self.active_movie_path = None
        if active_index.isValid():
            self.viewport().update(self.visualRect(active_index))

    def update_active_movie_frame(self):
        if self.active_movie_index.isValid():
            self.viewport().update(self.visualRect(QModelIndex(self.active_movie_index)))

    def animated_pixmap_for_index(self, index):
        image_path = index.data(ImagePathRole) if index.isValid() else None
        if self.active_movie is None or image_path != self.active_movie_path:
            return QPixmap()
        return self.active_movie.currentPixmap()

    def toggle_pinned(self, filename, enabled):
        emoji_store.set_pinned(filename, enabled)
        parent = self.parent()
        if hasattr(parent, "display_emoji"):
            parent.display_emoji()
        else:
            self.set_emojis(emoji_store.list_emojis())
        self.viewport().update()

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
            if not message_box.question(self, "确认删除", "你确定要删除这个表情吗？"):
                return

        if emoji_store.delete_emoji(filename):
            self.emoji_deleted.emit()

    def rename_item(self, filename):
        new_filename, accepted = QInputDialog.getText(self, "重命名", "新的文件名：", text=emoji_store.display_title_for_filename(filename))
        if not accepted:
            return

        renamed, message = emoji_store.rename_emoji(filename, new_filename)
        if not renamed:
            message_box.warning(self, "重命名失败", message)
            return

        self.emoji_deleted.emit()

    def open_file_location(self, filename):
        image_path = emoji_store.original_image_path(filename)
        if not image_path.exists():
            message_box.warning(self, "打开失败", "文件不存在")
            return

        try:
            subprocess.Popen(["explorer", f"/select,{image_path}"], creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError as error:
            message_box.warning(self, "打开失败", str(error))

    def copy_gif(self, image_path):
        if not image_path.exists():
            message_box.warning(self, "复制失败", "文件不存在")
            return False

        image_path = image_path.resolve()
        mime_data = QMimeData()
        mime_data.setUrls([QUrl.fromLocalFile(str(image_path))])
        try:
            mime_data.setData("image/gif", image_path.read_bytes())
        except OSError as error:
            message_box.warning(self, "复制失败", str(error))
            return False
        QApplication.clipboard().setMimeData(mime_data)
        return True

