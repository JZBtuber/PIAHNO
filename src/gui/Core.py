from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLineEdit, QMessageBox

class FileDropLineEdit(QLineEdit):
    fileDropped = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self.setAcceptDrops(True)


    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls():
            urls = mime.urls()
            if urls and urls[0].isLocalFile():
                event.acceptProposedAction()
                return
        event.ignore()


    def dragLeaveEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls():
            urls = mime.urls()
            if urls and urls[0].isLocalFile():
                event.acceptProposedAction()
                return
        event.ignore()


    def dropEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls():
            urls = mime.urls()
            if urls:
                local_path = urls[0].toLocalFile()
                if local_path:
                    self.setText(local_path)
                    self.fileDropped.emit(local_path)
                    event.acceptProposedAction()
                    return
        event.ignore()


class MessageBox(QMessageBox):
    def __init__(self, Name: str, Message: str):
        super().__init__()

        self.setText(Message)
        self.setWindowTitle(Name)
        self.setStandardButtons(QMessageBox.StandardButton.Ok)
        self.setDefaultButton(QMessageBox.StandardButton.Ok)
        self.setIcon(QMessageBox.Icon.Warning)
        self.exec()

