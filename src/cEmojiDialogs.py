from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QLabel, QMessageBox, QProgressDialog

from src import emoji_store


class ImportSignals(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)


class ImportWorker(QRunnable):
    def __init__(self, import_func, filenames):
        super().__init__()
        self.import_func = import_func
        self.filenames = filenames
        self.signals = ImportSignals()

    @Slot()
    def run(self):
        try:
            imported = self.import_func(self.filenames, self.signals.progress.emit)
        except Exception as error:
            self.signals.failed.emit(str(error))
            return
        self.signals.finished.emit(imported)


def show_upload_dialog(self):
    msg_box = QMessageBox(self)
    msg_box.setText("请选择上传类型:")
    msg_box.setWindowTitle("cEmoji")
    button_image = msg_box.addButton("图片", QMessageBox.ButtonRole.YesRole)
    button_zip = msg_box.addButton("压缩包", QMessageBox.ButtonRole.NoRole)
    clipboard_button = msg_box.addButton("读取剪切板内容", QMessageBox.ButtonRole.ActionRole)
    msg_box.addButton("取消上传", QMessageBox.ButtonRole.RejectRole)

    msg_box.exec()

    if msg_box.clickedButton() == button_image:
        upload_image(self)
    elif msg_box.clickedButton() == button_zip:
        upload_zip(self)
    elif msg_box.clickedButton() == clipboard_button:
        import_clipboard_image(self)


def upload_image(self):
    filenames, _ = QFileDialog.getOpenFileNames(self, "Select image", "", "Image files (*.jpg *.jpeg *.png *.gif)")
    if not filenames:
        return

    start_import(self, emoji_store.import_images, filenames)


def upload_zip(self):
    filenames, _ = QFileDialog.getOpenFileNames(self, "Select ZIP", "", "ZIP files (*.zip)")
    if not filenames:
        return

    start_import(self, emoji_store.import_zip_files, filenames)


def start_import(self, import_func, filenames):
    worker = ImportWorker(import_func, filenames)
    if not hasattr(self, "_active_imports"):
        self._active_imports = []
    self._active_imports.append(worker)
    self.upload_button.setEnabled(False)

    progress_dialog = QProgressDialog("准备导入...", "后台导入中", 0, max(len(filenames), 1), self)
    progress_dialog.setWindowTitle("导入进度")
    progress_dialog.setAutoClose(False)
    progress_dialog.setAutoReset(False)
    progress_dialog.setCancelButton(None)
    progress_dialog.setFixedWidth(460)
    progress_label = QLabel("准备导入...", progress_dialog)
    progress_label.setFixedWidth(380)
    progress_dialog.setLabel(progress_label)
    progress_dialog.show()
    center_dialog(progress_dialog, self)

    def update_progress(current, total, filename):
        progress_dialog.setMaximum(max(total, 1))
        progress_dialog.setValue(current)
        metrics = progress_label.fontMetrics()
        progress_label.setText("正在导入：" + metrics.elidedText(filename, Qt.TextElideMode.ElideMiddle, 300))

    def finish_import(summary):
        if worker in self._active_imports:
            self._active_imports.remove(worker)
        self.upload_button.setEnabled(True)
        progress_dialog.setValue(progress_dialog.maximum())
        progress_dialog.close()
        self.display_emoji()
        QMessageBox.information(
            self,
            "导入完成",
            f"成功导入：{summary.imported} 个\n已存在跳过：{summary.skipped} 个\n失败：{summary.failed} 个",
        )

    def fail_import(message):
        if worker in self._active_imports:
            self._active_imports.remove(worker)
        self.upload_button.setEnabled(True)
        progress_dialog.close()
        QMessageBox.warning(self, "导入失败", message)

    worker.signals.progress.connect(update_progress)
    worker.signals.finished.connect(finish_import)
    worker.signals.failed.connect(fail_import)
    QThreadPool.globalInstance().start(worker)


def center_dialog(dialog, parent):
    parent_geometry = parent.frameGeometry()
    dialog_geometry = dialog.frameGeometry()
    dialog_geometry.moveCenter(parent_geometry.center())
    dialog.move(dialog_geometry.topLeft())


def import_clipboard_image(self):
    from src import clipboard_service

    image = clipboard_service.read_clipboard_image()
    if image is None:
        QMessageBox.information(self, "提示", "剪切板中没有可读取的图片")
        return

    filename = clipboard_service.new_clipboard_filename()
    try:
        emoji_store.import_clipboard_image(image, filename)
    except Exception as error:
        QMessageBox.warning(self, "导入失败", str(error))
        return

    self.display_emoji()


def opt_image_dia(self):
    msg = QMessageBox(self)
    msg.setWindowTitle("提示")
    msg.setText("待实现")
    msg.exec()