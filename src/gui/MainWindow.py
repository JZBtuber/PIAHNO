from PyQt6.QtWidgets import *
from PyQt6.QtGui import QAction, QIcon, QPixmap
from PyQt6.QtCore import Qt, QThread
from src.gui.layout_colorwidget import Color
from src.video.video import VideoFeed
from src.audio.midi import MidiFeed
import math

class WidgetData():
    def __init__(self, widget: QWidget = None, ID: int = 0):
        self.widget = widget
        self.ID = ID

    
    def setID(self, ID: int):
        self.ID = ID


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
        self.windows = [[WidgetData() for _ in range(4)] for _ in range(2)]

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
        self.dialog = WindowChoice(self)

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


        self.quickAccess[0].triggered.connect(self.dialog.exec)

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


    def addWindow(self, widgetClass):
        done = False
        for i, iData in enumerate(self.windows):
            for j, jData in enumerate(iData):
                if jData.widget is None:
                    widget = widgetClass(int((i * 4 + j + 1))) if isinstance(widgetClass, type) else widgetClass
                    jData.widget = widget
                    jData.setID(int(i * 4 + j + 1))
                    self.fondLayout.addWidget(widget, int(i), int(j))
                    done = True
                if done: break
            if done: break

            

    def startALL(self):
        for i in self.windows:
            for j in i:
                if not j.widget == None:
                    j.widget.start()
            
    def pauseALL(self):
        for i in self.windows:
            for j in i:
                if not j.widget == None:
                    j.widget.pause()
    
    def stopALL(self):
        for i in self.windows:
            for j in i:
                if not j.widget == None:
                    j.widget.stop()
        

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


class WindowChoice(QDialog):
    def __init__(self, MainWindow):
        super().__init__()
        self.mainWindow = MainWindow
        vert = QVBoxLayout()
        hor1 = QHBoxLayout()
        addWindowButtonVideo = QPushButton("Add a Video Feed")
        addWindowButtonVideo.clicked.connect(self.setVideo)
        addWindowButtonVideo.clicked.connect(self.addWindow)
        addWindowButtonMidi = QPushButton("Add a Midi Feed")
        addWindowButtonMidi.clicked.connect(self.setMidi)
        addWindowButtonMidi.clicked.connect(self.addWindow)
        hor1.addWidget(addWindowButtonVideo)
        hor1.addWidget(addWindowButtonMidi)
        vert.addLayout(hor1)
        self.setLayout(vert)
        self.widget = None

    def setVideo(self):
        self.widget = VideoFeed

    def setMidi(self):
        self.widget = MidiFeed

    def addWindow(self, checked = False):
        self.mainWindow.addWindow(self.widget)
        self.close()








        
    