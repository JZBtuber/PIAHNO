from PyQt6.QtWidgets import *
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import Qt
from src.gui.layout_colorwidget import Color

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        #Sets the window's defaults
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenu)
        self.setWindowTitle("Data Colector")
        self.showMaximized()
        self.addBaseWidget()
        self.windowNumber = 0


    def addBaseWidget(self):
        self.fond = QWidget()
        self.fondLayout = QGridLayout()
        self.fond.setLayout(self.fondLayout)

        self.addTopMenu()



        self.setCentralWidget(self.fond)


    def addTopMenu(self):

        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)

        self.quickAccess = [QAction("Add a window", self), QAction("Save project", self)]
        self.quickAccess[0].setStatusTip("Add an observation window")
        self.quickAccess[1].setStatusTip("Save the current project setup")
        self.quickAccess[0].triggered.connect(self.addWindow)
        self.toolbar.addActions(self.quickAccess)
        


        self.filesOptions = [QAction("Save", self),
                             QAction("Load", self),
                             QAction("Export", self)
                            ]

        self.editOptions = [QAction("Settings", self),
                            QAction("Add and remove windows", self),
                            ]
        self.editOptions[1].triggered.connect(self.addWindow)


        self.menu = self.menuBar()
        self.fileMenu = self.menu.addMenu("&Files")
        self.editMenu = self.menu.addMenu("&Edit")

        for o in self.filesOptions:
            self.fileMenu.addSeparator
            self.fileMenu.addAction(o)

        for o in self.editOptions:
            self.editMenu.addSeparator
            self.editMenu.addAction(o)

    def addWindow(self):
        

        match self.windowNumber:

            case 0:
                self.fondLayout.addWidget(Color("Red"), 0, 0)
            case 1:
                self.fondLayout.addWidget(Color("Blue"), 0, 1)
            case 2:
                self.fondLayout.addWidget(Color("Green"), 1, 0)
            case 3:
                self.fondLayout.addWidget(Color("Orange"), 1, 1)
        self.windowNumber += 1
        


    def contextMenu(self):
        print("")
        #make context menu here


class topMenu(QToolBar):
    def __init__(self):
        super().__init__()

        self.menuButtons = [QAction("Files", self), QAction("Edit", self)]


        self.menuButtons[0].setStatusTip("Manage files and systems")
        self.menuButtons[1].setStatusTip("Edit and control the virtual environment")

        self.menuButtons[0].triggered.connect(self.fileButtonClicked)
        self.menuButtons[1].triggered.connect(self.editButtonClicked)

        for m in self.menuButtons:
            m.setCheckable(True)

        self.addActions(self.menuButtons)










class VideoFeed(QLabel):
    def __init__(self):
        super().__init__()
        self.setText("Hello, world!")

        
    