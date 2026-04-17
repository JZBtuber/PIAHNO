from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLineEdit

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
                    self.event.acceptProposedAction()
                    return
        event.ignore()
