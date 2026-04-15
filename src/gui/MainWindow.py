from PyQt6.QtWidgets import *
from PyQt6.QtGui import QAction, QIcon, QPixmap
from PyQt6.QtCore import Qt, QThread
from src.gui.layout_colorwidget import Color
from src.video.video import VideoFeed
import math


class MainWindow(QMainWindow):

    windows = []

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
        self.fondLayout.setSpacing(10)
        self.fond.setLayout(self.fondLayout)

        self.addTopMenu()



        self.setCentralWidget(self.fond)


    def addTopMenu(self):

        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)

        self.quickAccess = [QAction("Add a window", self),
                            QAction("Save project", self),
                            QAction("Start", self),
                            QAction("Pause/Resume", self),
                            QAction("Stop",self)]
        
        self.quickAccess[0].setStatusTip("Add an observation window")
        self.quickAccess[1].setStatusTip("Save the current project setup")
        self.quickAccess[2].setStatusTip("Start all video/audio")
        self.quickAccess[3].setStatusTip("Pause and resume all video/audio")
        self.quickAccess[4].setStatusTip("Stop all video/audio")


        self.quickAccess[0].triggered.connect(self.addWindow)

        self.quickAccess[2].triggered.connect(self.startALL)
        self.quickAccess[3].triggered.connect(self.pauseALL)
        self.quickAccess[4].triggered.connect(self.stopALL)

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

    def addWindow(self, widgetNumber = 0):
        if not self.windowNumber <8:
            match widgetNumber:
                case 0:
                    video = VideoFeed()
                    self.windows.append(video)
                    self.fondLayout.addWidget(video,
                                         math.floor((self.windowNumber / 4)),
                                        (self.windowNumber % 4))
            self.windowNumber += 1
            

    def startALL(self):
        for w in self.windows:
            if hasattr(w, "start"):
                w.start()
            
    def pauseALL(self):
        for w in self.windows:
            if hasattr(w, "pause"):
                w.pause()
    
    def stopALL(self):
        for w in self.windows:
            if hasattr(w, "stop"):
                w.stop()
        
        
        


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












        
    