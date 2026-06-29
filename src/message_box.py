from PySide6.QtWidgets import QMessageBox


def information(parent, title, text):
    message = QMessageBox(parent)
    message.setIcon(QMessageBox.Icon.Information)
    message.setWindowTitle(title)
    message.setText(text)
    message.addButton("确定", QMessageBox.ButtonRole.AcceptRole)
    message.exec()


def warning(parent, title, text):
    message = QMessageBox(parent)
    message.setIcon(QMessageBox.Icon.Warning)
    message.setWindowTitle(title)
    message.setText(text)
    message.addButton("确定", QMessageBox.ButtonRole.AcceptRole)
    message.exec()


def question(parent, title, text):
    message = QMessageBox(parent)
    message.setIcon(QMessageBox.Icon.Question)
    message.setWindowTitle(title)
    message.setText(text)
    yes_button = message.addButton("是", QMessageBox.ButtonRole.YesRole)
    no_button = message.addButton("否", QMessageBox.ButtonRole.NoRole)
    message.setDefaultButton(no_button)
    message.exec()
    return message.clickedButton() == yes_button
