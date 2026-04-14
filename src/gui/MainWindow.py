from PyQt6.QtWidgets import *
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        #Sets the window's defaults
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenu)
        self.setWindowTitle("Data Colector")
        self.showMaximized()

    def contextMenu(self, pos):
        context = QMenu(self)

        Actions = []

        context.addActions(Actions)
        context.exec(self.mapToGlobal(pos))


class VideoFeed(QLabel):
    def __init__(self):
        super().__init__()

        
    