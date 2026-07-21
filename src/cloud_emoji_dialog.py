from pathlib import Path
import tempfile

from PySide6.QtCore import QByteArray, QBuffer, QEvent, QIODevice, QObject, QRunnable, QSize, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QMovie, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QRadioButton,
    QProgressDialog,
    QPushButton,
    QComboBox,
    QScrollArea,
    QSizePolicy,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from src import cloud_emoji_service, collection_store, emoji_store, message_box, theme
from src.window_effects import apply_modern_window_effects


PREVIEW_BATCH_SIZE = 30
PREVIEW_SIZE = QSize(96, 96)
GIF_PLAY_DELAY_MS = 350
PACKAGE_NAME_ROLE = Qt.ItemDataRole.UserRole + 11
PACKAGE_STATS_ROLE = Qt.ItemDataRole.UserRole + 12


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(object)
    progress = Signal(int, int, str)


def emit_if_alive(signal, *args):
    try:
        signal.emit(*args)
    except RuntimeError:
        pass


class MarqueeLabel(QLabel):
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

    def available_width(self):
        return max(40, self.width() - 8)

    def needs_scroll(self):
        return self.fontMetrics().horizontalAdvance(self.full_text) > self.available_width()

    def stop_scroll(self):
        self.scroll_timer.stop()
        self.scroll_index = 0
        self.update_elided_text()

    def update_elided_text(self):
        self.setText(self.fontMetrics().elidedText(self.full_text, Qt.TextElideMode.ElideRight, self.available_width()))

    def scroll_text(self):
        if not self.needs_scroll():
            self.stop_scroll()
            return
        padded_text = f"{self.full_text}   {self.full_text}"
        visible_text = padded_text[self.scroll_index:] + padded_text[:self.scroll_index]
        while visible_text and self.fontMetrics().horizontalAdvance(visible_text) > self.available_width():
            visible_text = visible_text[:-1]
        self.setText(visible_text or self.full_text[:1])
        self.scroll_index = (self.scroll_index + 1) % (len(self.full_text) + 3)


class LoadIndexWorker(QRunnable):
    def __init__(self, force_refresh=False):
        super().__init__()
        self.setAutoDelete(False)
        self.force_refresh = force_refresh
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            index_data, source = cloud_emoji_service.fetch_index(self.force_refresh)
            packages = cloud_emoji_service.parse_index(index_data)
        except Exception as error:
            emit_if_alive(self.signals.failed, str(error))
            return
        emit_if_alive(self.signals.finished, (packages, source))


class PreviewWorker(QRunnable):
    def __init__(self, item, generation):
        super().__init__()
        self.setAutoDelete(False)
        self.item = item
        self.generation = generation
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            data = cloud_emoji_service.fetch_preview_bytes(self.item)
        except Exception as error:
            emit_if_alive(self.signals.failed, (self.item.download_url, f"{self.item.name}: {error}"))
            return
        emit_if_alive(self.signals.finished, (self.generation, self.item, data))


class ImportPackageWorker(QRunnable):
    def __init__(self, package, collection_id):
        super().__init__()
        self.setAutoDelete(False)
        self.package = package
        self.collection_id = collection_id
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            with tempfile.TemporaryDirectory(prefix="cEmoji_cloud_") as temp_dir:
                temp_path = Path(temp_dir)
                downloaded = []
                item_hashes = {}
                download_failed = 0
                total = len(self.package.items)
                for index, item in enumerate(self.package.items, start=1):
                    emit_if_alive(self.signals.progress, index - 1, total, item.name)
                    try:
                        downloaded_path = cloud_emoji_service.download_emoji_to(item, temp_path)
                        downloaded.append(downloaded_path)
                        item_hashes[item.path] = emoji_store.image_content_hash(downloaded_path)
                    except Exception:
                        download_failed += 1
                    emit_if_alive(self.signals.progress, index, total, item.name)
                summary = emoji_store.import_images(downloaded, collection_id=self.collection_id)
                summary.failed += download_failed
        except Exception as error:
            emit_if_alive(self.signals.failed, str(error))
            return
        emit_if_alive(self.signals.finished, (self.package, item_hashes, summary))


class ImportItemWorker(QRunnable):
    def __init__(self, item, collection_id):
        super().__init__()
        self.setAutoDelete(False)
        self.item = item
        self.collection_id = collection_id
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            with tempfile.TemporaryDirectory(prefix="cEmoji_cloud_item_") as temp_dir:
                temp_path = Path(temp_dir)
                downloaded = cloud_emoji_service.download_emoji_to(self.item, temp_path)
                content_hash = emoji_store.image_content_hash(downloaded)
                summary = emoji_store.import_images([downloaded], collection_id=self.collection_id)
        except Exception as error:
            emit_if_alive(self.signals.failed, str(error))
            return
        emit_if_alive(self.signals.finished, (self.item, content_hash, summary))


class ImportItemsWorker(QRunnable):
    def __init__(self, items, collection_id):
        super().__init__()
        self.setAutoDelete(False)
        self.items = list(items)
        self.collection_id = collection_id
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            with tempfile.TemporaryDirectory(prefix="cEmoji_cloud_selected_") as temp_dir:
                temp_path = Path(temp_dir)
                downloaded = []
                item_hashes = {}
                download_failed = 0
                total = len(self.items)
                for index, item in enumerate(self.items, start=1):
                    emit_if_alive(self.signals.progress, index - 1, total, item.name)
                    try:
                        downloaded_path = cloud_emoji_service.download_emoji_to(item, temp_path)
                        downloaded.append(downloaded_path)
                        item_hashes[item.path] = emoji_store.image_content_hash(downloaded_path)
                    except Exception:
                        download_failed += 1
                    emit_if_alive(self.signals.progress, index, total, item.name)
                summary = emoji_store.import_images(downloaded, collection_id=self.collection_id)
                summary.failed += download_failed
        except Exception as error:
            emit_if_alive(self.signals.failed, str(error))
            return
        emit_if_alive(self.signals.finished, (self.items, item_hashes, summary))


class CloudEmojiDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("云端表情包库")
        self.setMinimumSize(860, 620)
        self.packages = []
        self.filtered_packages = []
        self.current_package = None
        self.current_items = []
        self.filter_mode = "all"
        self.preview_offset = 0
        self.preview_cache = {}
        self.preview_cards = {}
        self.pending_preview_urls = set()
        self.preview_generation = 0
        self.selected_preview_cards = set()
        self.downloaded_item_hashes = cloud_emoji_service.load_downloaded_item_hashes()
        self.local_image_hashes = emoji_store.existing_image_hashes() if self.downloaded_item_hashes else set()
        self.active_preview_workers = []
        self.active_workers = []
        self.theme_mode = theme.system_theme_mode(self.palette())
        self.hovered_package_item = None
        self.package_name_scroll_index = 0
        self.package_name_scroll_timer = QTimer(self)
        self.package_name_scroll_timer.setInterval(220)
        self.package_name_scroll_timer.timeout.connect(self.scroll_hovered_package_name)

        self.setup_ui()
        self.apply_theme()
        self.load_index()

    def setup_ui(self):
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(14, 14, 14, 14)
        self.root_layout.setSpacing(10)

        self.status_label = QLabel("正在加载云端索引...", self)
        self.status_label.setObjectName("CloudStatusLabel")
        self.status_label.setOpenExternalLinks(True)
        self.status_label.setWordWrap(True)
        self.root_layout.addWidget(self.status_label)

        self.content_layout = QHBoxLayout()
        self.content_layout.setSpacing(10)
        self.root_layout.addLayout(self.content_layout, stretch=1)

        self.left_panel = QVBoxLayout()
        self.left_panel.setSpacing(8)
        self.content_layout.addLayout(self.left_panel)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("搜索云端合集或图片")
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.apply_package_filter)
        self.search_input.textChanged.connect(self.schedule_package_filter)
        self.left_panel.addWidget(self.search_input)

        self.package_list = QListWidget(self)
        self.package_list.setObjectName("CloudPackageList")
        self.package_list.setFixedWidth(230)
        self.package_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.package_list.setMouseTracking(True)
        self.package_list.viewport().setMouseTracking(True)
        self.package_list.viewport().installEventFilter(self)
        self.package_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.package_list.itemEntered.connect(self.on_package_item_hovered)
        self.package_list.currentRowChanged.connect(self.on_package_selected)
        self.left_panel.addWidget(self.package_list, stretch=1)

        self.preview_panel = QFrame(self)
        self.preview_panel.setObjectName("CloudPreviewPanel")
        self.preview_layout = QVBoxLayout(self.preview_panel)
        self.preview_layout.setContentsMargins(10, 10, 10, 10)
        self.preview_layout.setSpacing(10)
        self.content_layout.addWidget(self.preview_panel, stretch=1)

        self.package_title = MarqueeLabel("选择一个云端合集", self)
        self.package_title.setObjectName("CloudPackageTitle")
        self.preview_layout.addWidget(self.package_title)

        self.filter_tabs = QTabBar(self)
        self.filter_tabs.setObjectName("CloudFilterTabs")
        self.filter_tabs.addTab("全部")
        self.filter_tabs.addTab("表情包")
        self.filter_tabs.addTab("动态表情包")
        self.filter_tabs.currentChanged.connect(self.on_filter_changed)
        self.preview_layout.addWidget(self.filter_tabs)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.preview_container = QWidget(self)
        self.grid_layout = QGridLayout(self.preview_container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(8)
        self.scroll_area.setWidget(self.preview_container)
        self.preview_layout.addWidget(self.scroll_area, stretch=1)

        self.preview_footer = QHBoxLayout()
        self.preview_layout.addLayout(self.preview_footer)
        self.preview_count_label = QLabel("已显示 0 / 0", self)
        self.preview_count_label.setObjectName("CloudStatusLabel")
        self.preview_footer.addWidget(self.preview_count_label)
        self.preview_footer.addStretch(1)
        self.load_more_button = QPushButton("加载更多", self)
        self.load_more_button.clicked.connect(self.load_more_previews)
        self.preview_footer.addWidget(self.load_more_button)

        self.button_layout = QHBoxLayout()
        self.root_layout.addLayout(self.button_layout)
        self.refresh_button = QPushButton("刷新索引", self)
        self.import_button = QPushButton("导入当前合集", self)
        self.download_selected_button = QPushButton("下载选中", self)
        self.close_button = QPushButton("关闭", self)
        self.refresh_button.clicked.connect(lambda: self.load_index(force_refresh=True))
        self.import_button.clicked.connect(self.import_current_package)
        self.download_selected_button.clicked.connect(self.download_selected_items)
        self.close_button.clicked.connect(self.close)
        self.button_layout.addWidget(self.refresh_button)
        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.download_selected_button)
        self.button_layout.addWidget(self.import_button)
        self.button_layout.addWidget(self.close_button)
        self.update_download_selected_button()

    def apply_theme(self):
        self.setStyleSheet(theme.window_stylesheet(self.theme_mode) + cloud_dialog_stylesheet(self.theme_mode))
        apply_modern_window_effects(self, self.theme_mode)

    def schedule_package_filter(self):
        self.search_timer.start(260)

    def load_index(self, force_refresh=False):
        self.status_label.setText("正在加载云端索引...")
        self.refresh_button.setEnabled(False)
        worker = LoadIndexWorker(force_refresh)
        worker.signals.finished.connect(self.on_index_loaded)
        worker.signals.failed.connect(self.on_index_failed)
        self.active_workers.append(worker)
        QThreadPool.globalInstance().start(worker)

    def on_index_loaded(self, result):
        self.cleanup_workers()
        packages, source = result
        self.packages = list(packages)
        self.refresh_button.setEnabled(True)
        source_label = {"remote": "远端", "cache": "缓存", "stale-cache": "缓存", "local": "本地"}.get(source, source)
        total_items = sum(package.count for package in self.packages)
        self.status_label.setText(
            f"已加载 {len(self.packages)} 个云端合集，共收集 {total_items} 个表情包（{source_label}索引）。"
            "欢迎向 <a href='https://github.com/ZevAlain/EmojiPackage/pulls'>EmojiPackage 提交 PR</a> 补充内容；"
            "如有不适内容，请提交 <a href='https://github.com/ZevAlain/EmojiPackage/issues'>Issue</a> 反馈。"
        )
        self.apply_package_filter()

    def on_index_failed(self, message):
        self.cleanup_workers()
        self.refresh_button.setEnabled(True)
        self.status_label.setText("云端索引加载失败")
        message_box.warning(self, "云端表情包库", f"云端索引加载失败：{message}")

    def on_package_selected(self, row):
        if row < 0 or row >= len(self.filtered_packages):
            self.current_package = None
            self.current_items = []
            return
        self.current_package = self.filtered_packages[row]
        self.refresh_current_items()

    def apply_package_filter(self):
        self.stop_package_name_scroll()
        query = self.search_input.text().strip().lower()
        if not query:
            self.filtered_packages = list(self.packages)
        else:
            self.filtered_packages = [
                package
                for package in self.packages
                if any(query in Path(item.name).stem.lower() for item in package.items)
            ]
        self.package_list.clear()
        for package in self.filtered_packages:
            item = QListWidgetItem()
            item.setData(PACKAGE_NAME_ROLE, package.name)
            item.setData(PACKAGE_STATS_ROLE, f"{package.count} 个 / GIF {package.gif_count}")
            item.setToolTip(package.name)
            self.update_package_item_text(item)
            self.package_list.addItem(item)
        if self.filtered_packages:
            self.package_list.setCurrentRow(0)
        else:
            self.current_package = None
            self.current_items = []
            self.clear_grid()
            self.package_title.set_full_text("没有匹配的云端合集")
            self.update_preview_count()

    def on_filter_changed(self, index):
        self.filter_mode = ["all", "static", "gif"][index] if 0 <= index <= 2 else "all"
        self.refresh_current_items()

    def refresh_current_items(self):
        if self.current_package is None:
            self.current_items = []
            self.clear_grid()
            self.update_preview_count()
            return
        if self.filter_mode == "gif":
            self.current_items = [item for item in self.current_package.items if item.is_gif]
            filter_label = "动态表情包"
        elif self.filter_mode == "static":
            self.current_items = [item for item in self.current_package.items if not item.is_gif]
            filter_label = "表情包"
        else:
            self.current_items = list(self.current_package.items)
            filter_label = "全部"
        query = self.search_input.text().strip().lower()
        if query:
            self.current_items = [
                item
                for item in self.current_items
                if query in Path(item.name).stem.lower()
            ]
        self.preview_offset = 0
        self.preview_cards = {}
        self.preview_generation += 1
        self.selected_preview_cards = set()
        self.update_download_selected_button()
        self.clear_grid()
        self.package_title.set_full_text(f"{self.current_package.name}  -  {filter_label} {len(self.current_items)} 个")
        self.load_more_previews()

    def eventFilter(self, watched, event):
        if watched == self.package_list.viewport() and event.type() == QEvent.Type.Leave:
            self.stop_package_name_scroll()
        return super().eventFilter(watched, event)

    def on_package_item_hovered(self, item):
        if item is self.hovered_package_item:
            return
        self.stop_package_name_scroll()
        self.hovered_package_item = item
        self.package_name_scroll_index = 0
        if self.package_item_needs_scroll(item):
            self.package_name_scroll_timer.start()
            self.scroll_hovered_package_name()

    def stop_package_name_scroll(self):
        self.package_name_scroll_timer.stop()
        if self.hovered_package_item is not None:
            self.update_package_item_text(self.hovered_package_item)
        self.hovered_package_item = None
        self.package_name_scroll_index = 0

    def package_item_needs_scroll(self, item):
        name = item.data(PACKAGE_NAME_ROLE) or ""
        return self.package_list.fontMetrics().horizontalAdvance(name) > self.package_name_available_width()

    def package_name_available_width(self):
        return max(40, self.package_list.viewport().width() - 28)

    def update_package_item_text(self, item, name=None):
        full_name = item.data(PACKAGE_NAME_ROLE) or ""
        stats = item.data(PACKAGE_STATS_ROLE) or ""
        visible_name = name or self.package_list.fontMetrics().elidedText(full_name, Qt.TextElideMode.ElideRight, self.package_name_available_width())
        item.setText(f"{visible_name}\n{stats}")

    def scroll_hovered_package_name(self):
        item = self.hovered_package_item
        if item is None or not self.package_item_needs_scroll(item):
            self.stop_package_name_scroll()
            return
        full_name = item.data(PACKAGE_NAME_ROLE) or ""
        padded_name = f"{full_name}   {full_name}"
        visible_name = padded_name[self.package_name_scroll_index:] + padded_name[:self.package_name_scroll_index]
        available_width = self.package_name_available_width()
        while visible_name and self.package_list.fontMetrics().horizontalAdvance(visible_name) > available_width:
            visible_name = visible_name[:-1]
        self.update_package_item_text(item, visible_name or full_name[:1])
        self.package_name_scroll_index = (self.package_name_scroll_index + 1) % (len(full_name) + 3)

    def clear_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def load_more_previews(self):
        if self.current_package is None:
            return
        items = self.current_items[self.preview_offset : self.preview_offset + PREVIEW_BATCH_SIZE]
        start = self.preview_offset
        self.preview_offset += len(items)
        for index, item in enumerate(items, start=start):
            card = PreviewCard(item, self.is_item_downloaded(item))
            card.selected.connect(self.select_preview_card)
            card.download_requested.connect(self.download_cloud_item)
            row = index // 4
            column = index % 4
            self.grid_layout.addWidget(card, row, column)
            self.preview_cards[item.download_url] = card
            cached = self.preview_cache.get(item.download_url)
            if cached is not None:
                pixmap, data = cached
                card.set_preview(pixmap, data)
            else:
                self.load_preview(item)
        self.update_preview_count()

    def load_preview(self, item):
        if item.download_url in self.pending_preview_urls:
            return
        self.pending_preview_urls.add(item.download_url)
        worker = PreviewWorker(item, self.preview_generation)
        worker.signals.finished.connect(self.on_preview_loaded)
        worker.signals.failed.connect(self.on_preview_failed)
        self.active_preview_workers.append(worker)
        QThreadPool.globalInstance().start(worker)

    def on_preview_loaded(self, result):
        self.cleanup_preview_workers()
        _generation, item, data = result
        self.pending_preview_urls.discard(item.download_url)
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return
        scaled = pixmap.scaled(PREVIEW_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        preview_data = data if item.is_gif else None
        self.preview_cache[item.download_url] = (scaled, preview_data)
        card = self.preview_cards.get(item.download_url)
        if card is not None:
            card.set_preview(scaled, preview_data)

    def on_preview_failed(self, result):
        self.cleanup_preview_workers()
        if isinstance(result, tuple) and result:
            self.pending_preview_urls.discard(result[0])
            card = self.preview_cards.get(result[0])
            if card is not None:
                card.set_error()

    def select_preview_card(self, card):
        if card in self.selected_preview_cards:
            self.selected_preview_cards.remove(card)
            card.set_selected(False)
        else:
            self.selected_preview_cards.add(card)
            card.set_selected(True)
        self.update_download_selected_button()

    def download_cloud_item(self, item):
        collection_id = self.choose_target_collection("下载云端表情", default_name=Path(item.name).stem, prefer_new=False)
        if not collection_id:
            return
        worker = ImportItemWorker(item, collection_id)
        worker.signals.finished.connect(self.on_item_import_finished)
        worker.signals.failed.connect(self.on_item_import_failed)
        self.active_workers.append(worker)
        QThreadPool.globalInstance().start(worker)

    def on_item_import_finished(self, result):
        self.cleanup_workers()
        item, content_hash, summary = result
        if summary.imported or summary.skipped:
            self.downloaded_item_hashes = cloud_emoji_service.mark_downloaded_items({item.path: content_hash})
            self.local_image_hashes = emoji_store.existing_image_hashes()
            card = self.preview_cards.get(item.download_url)
            if card is not None:
                card.set_downloaded(self.is_item_downloaded(item))
            parent = self.parent()
            if hasattr(parent, "display_emoji"):
                if hasattr(parent, "refresh_collection_tabs"):
                    parent.current_collection_id = collection_store.active_collection_id()
                    parent.refresh_collection_tabs()
                parent.display_emoji()
        message_box.information(self, "下载完成", f"成功导入：{summary.imported} 个\n已存在跳过：{summary.skipped} 个\n加入合集：{summary.added_to_collection} 个\n失败：{summary.failed} 个")

    def on_item_import_failed(self, message):
        self.cleanup_workers()
        message_box.warning(self, "下载失败", f"下载到本地表情库失败：{message}")

    def download_selected_items(self):
        items = [card.item for card in self.selected_preview_cards]
        if not items:
            return
        collection_id = self.choose_target_collection("下载选中表情", default_name="新合集", prefer_new=False)
        if not collection_id:
            return
        self.download_selected_button.setEnabled(False)
        self.progress_dialog = QProgressDialog("准备下载...", "后台导入中", 0, len(items), self)
        self.progress_dialog.setWindowTitle("下载选中表情")
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.show()
        worker = ImportItemsWorker(items, collection_id)
        worker.signals.progress.connect(self.on_import_progress)
        worker.signals.finished.connect(self.on_selected_import_finished)
        worker.signals.failed.connect(self.on_selected_import_failed)
        self.active_workers.append(worker)
        QThreadPool.globalInstance().start(worker)

    def on_selected_import_finished(self, result):
        self.cleanup_workers()
        items, item_hashes, summary = result
        self.download_selected_button.setEnabled(True)
        self.progress_dialog.close()
        self.mark_items_downloaded(items, item_hashes)
        parent = self.parent()
        if hasattr(parent, "display_emoji"):
            if hasattr(parent, "refresh_collection_tabs"):
                parent.current_collection_id = collection_store.active_collection_id()
                parent.refresh_collection_tabs()
            parent.display_emoji()
        message_box.information(self, "下载完成", f"成功导入：{summary.imported} 个\n已存在跳过：{summary.skipped} 个\n加入合集：{summary.added_to_collection} 个\n失败：{summary.failed} 个")

    def on_selected_import_failed(self, message):
        self.cleanup_workers()
        self.download_selected_button.setEnabled(True)
        self.progress_dialog.close()
        message_box.warning(self, "下载失败", f"下载选中表情失败：{message}")

    def mark_package_downloaded(self, package, item_hashes):
        self.mark_items_downloaded(package.items, item_hashes)

    def mark_items_downloaded(self, items, item_hashes):
        if item_hashes:
            self.downloaded_item_hashes = cloud_emoji_service.mark_downloaded_items(item_hashes)
        self.local_image_hashes = emoji_store.existing_image_hashes()
        for item in items:
            card = self.preview_cards.get(item.download_url)
            if card is not None:
                card.set_downloaded(self.is_item_downloaded(item))

    def update_download_selected_button(self):
        if hasattr(self, "download_selected_button"):
            self.download_selected_button.setEnabled(bool(self.selected_preview_cards))

    def update_preview_count(self):
        total = len(self.current_items)
        self.preview_count_label.setText(f"已显示 {min(self.preview_offset, total)} / {total}")
        self.load_more_button.setVisible(self.current_package is not None and self.preview_offset < total)

    def is_item_downloaded(self, item):
        content_hash = self.downloaded_item_hashes.get(item.path)
        return bool(content_hash and content_hash in self.local_image_hashes)

    def import_current_package(self):
        if self.current_package is None:
            return
        collection_id = self.choose_target_collection("导入云端合集", default_name=self.current_package.name, prefer_new=True)
        if not collection_id:
            return
        if self.current_package.count > 300:
            if not message_box.question(self, "导入云端合集", f"该合集包含 {self.current_package.count} 个文件，导入可能需要较长时间，是否继续？"):
                return
        self.import_button.setEnabled(False)
        self.progress_dialog = QProgressDialog("准备下载...", "后台导入中", 0, self.current_package.count, self)
        self.progress_dialog.setWindowTitle("导入云端表情包")
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.show()
        worker = ImportPackageWorker(self.current_package, collection_id)
        worker.signals.progress.connect(self.on_import_progress)
        worker.signals.finished.connect(self.on_import_finished)
        worker.signals.failed.connect(self.on_import_failed)
        self.active_workers.append(worker)
        QThreadPool.globalInstance().start(worker)

    def choose_target_collection(self, title, default_name, prefer_new):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        existing_radio = QRadioButton("合并到已有合集", dialog)
        existing_combo = QComboBox(dialog)
        for collection in collection_store.collections():
            existing_combo.addItem(collection.name, collection.id)
        current_parent = self.parent()
        current_id = getattr(current_parent, "current_collection_id", collection_store.active_collection_id())
        current_index = existing_combo.findData(current_id)
        if current_index >= 0:
            existing_combo.setCurrentIndex(current_index)

        new_radio = QRadioButton("新建合集", dialog)
        new_input = QLineEdit(dialog)
        new_input.setText(collection_store.unique_collection_name(default_name))

        if prefer_new:
            new_radio.setChecked(True)
        else:
            existing_radio.setChecked(True)

        button_row = QHBoxLayout()
        ok_button = QPushButton("确定", dialog)
        cancel_button = QPushButton("取消", dialog)
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        button_row.addStretch(1)
        button_row.addWidget(ok_button)
        button_row.addWidget(cancel_button)

        layout.addWidget(existing_radio)
        layout.addWidget(existing_combo)
        layout.addWidget(new_radio)
        layout.addWidget(new_input)
        layout.addLayout(button_row)
        dialog.setStyleSheet(theme.window_stylesheet(self.theme_mode))

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        if new_radio.isChecked():
            name = new_input.text().strip()
            if not name:
                return None
            return collection_store.create_collection(name)
        return existing_combo.currentData()

    def on_import_progress(self, current, total, name):
        self.progress_dialog.setMaximum(max(total, 1))
        self.progress_dialog.setValue(current)
        self.progress_dialog.setLabelText(f"正在下载：{name}")

    def on_import_finished(self, result):
        self.cleanup_workers()
        package, item_hashes, summary = result
        self.import_button.setEnabled(True)
        self.progress_dialog.close()
        self.mark_package_downloaded(package, item_hashes)
        parent = self.parent()
        if hasattr(parent, "display_emoji"):
            if hasattr(parent, "refresh_collection_tabs"):
                parent.current_collection_id = collection_store.active_collection_id()
                parent.refresh_collection_tabs()
            parent.display_emoji()
        message_box.information(self, "导入完成", f"成功导入：{summary.imported} 个\n已存在跳过：{summary.skipped} 个\n加入合集：{summary.added_to_collection} 个\n失败：{summary.failed} 个")

    def on_import_failed(self, message):
        self.cleanup_workers()
        self.import_button.setEnabled(True)
        self.progress_dialog.close()
        message_box.warning(self, "导入失败", message)

    def cleanup_workers(self):
        sender = self.sender()
        self.active_workers = [worker for worker in self.active_workers if worker.signals is not sender]

    def cleanup_preview_workers(self):
        sender = self.sender()
        self.active_preview_workers = [worker for worker in self.active_preview_workers if worker.signals is not sender]


class PreviewCard(QFrame):
    selected = Signal(object)
    download_requested = Signal(object)

    def __init__(self, item, downloaded=False, parent=None):
        super().__init__(parent)
        self.item = item
        self.static_pixmap = QPixmap()
        self.image_data = None
        self.movie = None
        self.movie_buffer = None
        self.movie_data = None
        self.gif_play_timer = QTimer(self)
        self.gif_play_timer.setSingleShot(True)
        self.gif_play_timer.timeout.connect(self.start_gif_movie)
        self.setObjectName("CloudPreviewCard")
        self.setProperty("selected", False)
        self.setFixedSize(122, 142)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)
        self.image_label = QLabel("加载中", self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(PREVIEW_SIZE)
        self.image_label.setObjectName("CloudPreviewImage")
        layout.addWidget(self.image_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.gif_badge = QLabel("GIF", self)
        self.gif_badge.setObjectName("CloudGifBadge")
        self.gif_badge.setVisible(item.is_gif)
        self.gif_badge.raise_()
        self.downloaded_badge = QLabel("已下载", self)
        self.downloaded_badge.setObjectName("CloudDownloadedBadge")
        self.downloaded_badge.setVisible(downloaded)
        self.downloaded_badge.raise_()
        self.position_badges()
        title = Path(item.name).stem
        if len(title) > 12:
            title = title[:10] + "..."
        self.name_label = QLabel(title, self)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setObjectName("CloudPreviewName")
        self.name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.name_label)

    def set_preview(self, pixmap, data=None):
        self.static_pixmap = pixmap
        self.image_data = data
        self.image_label.setText("")
        self.image_label.setPixmap(pixmap)

    def set_error(self):
        self.image_data = None
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText("加载失败")

    def set_selected(self, selected):
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_downloaded(self, downloaded):
        self.downloaded_badge.setVisible(downloaded)
        self.position_badges()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_badges()

    def position_badges(self):
        self.gif_badge.adjustSize()
        self.downloaded_badge.adjustSize()
        self.gif_badge.move(self.width() - self.gif_badge.width() - 10, 10)
        self.downloaded_badge.move(10, 10)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        self.selected.emit(self)
        menu = QMenu(self)
        download_action = QAction("下载到本地表情库", self)
        menu.addAction(download_action)
        if menu.exec(event.globalPos()) == download_action:
            self.download_requested.emit(self.item)

    def enterEvent(self, event):
        super().enterEvent(event)
        if not self.item.is_gif or not self.image_data:
            return
        self.gif_play_timer.start(GIF_PLAY_DELAY_MS)

    def start_gif_movie(self):
        if not self.item.is_gif or not self.image_data:
            return
        self.movie_data = QByteArray(self.image_data)
        self.movie_buffer = QBuffer(self)
        self.movie_buffer.setData(self.movie_data)
        self.movie_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self.movie = QMovie(self.movie_buffer, QByteArray(), self)
        if not self.static_pixmap.isNull():
            self.movie.setScaledSize(self.static_pixmap.size())
        self.image_label.setMovie(self.movie)
        self.movie.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.gif_play_timer.stop()
        if self.movie is not None:
            self.movie.stop()
            self.movie.deleteLater()
            self.movie = None
        if self.movie_buffer is not None:
            self.movie_buffer.close()
            self.movie_buffer.deleteLater()
            self.movie_buffer = None
        self.movie_data = None
        if not self.static_pixmap.isNull():
            self.image_label.setPixmap(self.static_pixmap)


def cloud_dialog_stylesheet(mode):
    color = theme.colors(mode)
    return f"""
        QListWidget#CloudPackageList, QFrame#CloudPreviewPanel {{
            background: {color["panel"]};
            border: 1px solid {color["border"]};
            border-radius: 11px;
            outline: 0;
        }}
        QListWidget#CloudPackageList {{
            outline: 0;
        }}
        QListWidget#CloudPackageList::item {{
            padding: 9px;
            border-radius: 7px;
            color: {color["text"]};
            outline: 0;
        }}
        QListWidget#CloudPackageList::item:selected {{
            background: {color["accent_soft"]};
            color: {color["accent_hover"]};
        }}
        QListWidget#CloudPackageList::item:focus {{
            outline: 0;
        }}
        QTabBar#CloudFilterTabs {{
            background: transparent;
        }}
        QTabBar#CloudFilterTabs::tab {{
            background: {color["panel"]};
            border: 1px solid {color["border"]};
            border-radius: 8px;
            color: {color["muted"]};
            margin-right: 6px;
            padding: 6px 14px;
            min-width: 76px;
        }}
        QTabBar#CloudFilterTabs::tab:selected {{
            background: {color["accent_soft"]};
            color: {color["accent_hover"]};
            border-color: {color["accent"]};
        }}
        QTabBar#CloudFilterTabs::tab:hover {{
            background: {color["panel_alt"]};
            color: {color["text"]};
            border-color: {color["border_strong"]};
        }}
        QFrame#CloudPreviewCard {{
            background: {color["panel_alt"]};
            border: 1px solid {color["border"]};
            border-radius: 8px;
        }}
        QFrame#CloudPreviewCard:hover {{
            border-color: {color["border_strong"]};
        }}
        QFrame#CloudPreviewCard[selected="true"] {{
            background: {color["accent_soft"]};
            border: 1px solid {color["accent"]};
        }}
        QLabel#CloudPreviewImage {{
            background: transparent;
            color: {color["muted"]};
        }}
        QLabel#CloudGifBadge {{
            background: rgba(22, 143, 122, 230);
            color: #ffffff;
            border-radius: 5px;
            padding: 2px 5px;
            font-size: 10px;
            font-weight: 700;
        }}
        QLabel#CloudDownloadedBadge {{
            background: {color["panel_solid"]};
            color: {color["accent_hover"]};
            border: 1px solid {color["accent"]};
            border-radius: 4px;
            padding: 2px 5px;
            font-size: 10px;
            font-weight: 700;
        }}
        QLabel#CloudStatusLabel, QLabel#CloudPreviewName {{
            color: {color["muted"]};
        }}
        QLabel#CloudPackageTitle {{
            color: {color["text"]};
        }}
        QScrollArea {{
            background: transparent;
        }}
    """
