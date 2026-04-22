from PyQt6.QtWidgets import *
from PyQt6.QtGui import QAction, QIcon, QPixmap
from PyQt6.QtCore import Qt, QSize
from src.video.video import VideoFeed
from src.audio.midi import MidiFeed
from src.audio.audio import AudioFeed
from src.tools.VideoLoader import VideoLoader

class WidgetData():
    def __init__(self, widget: QWidget = None, ID: int = 0):
        self.widget = widget
        self.ID = ID

    
    def setID(self, ID: int):
        self.ID = ID

    
    def getID(self):
        return self.ID
    

    def getWidget(self):
        return self.widget


class MainWindow(QMainWindow):

    def __init__(self, workingPath: str):
        super().__init__()

        #Sets the window's defaults
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenu)
        self.setWindowTitle("Data Colector")
        self.setMinimumSize(QSize(600, 400))
        self.showMaximized()
        
        self.addBaseWidget()
        self.windowNumber = 0
        self.windows = [[WidgetData() for _ in range(4)] for _ in range(2)]

    def addBaseWidget(self):
        self.fond = QWidget()
        self.fondLayout = QGridLayout()
        self.fondLayout.setSpacing(10)
        self.fond.setLayout(self.fondLayout)
        self.dialog = WindowChoice(self)
        self.videoTool = VideoLoader()

        self.addTopMenu()
        self.addMenuBar()


        self.setCentralWidget(self.fond)


    def addTopMenu(self):

        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)
        


        self.quickAccess = [QAction("Add/Remove a window", self),
                            QAction("Remove All windows"),
                            QAction("Save project", self),
                            QAction("Start", self),
                            QAction("Pause/Resume", self),
                            QAction("Stop",self),
                            QAction("Start Recording", self),
                            QAction("Stop Recording", self)
                            ]
        
        self.quickAccess[0].setStatusTip("Add or remove an observation window")
        self.quickAccess[1].setStatusTip("Remove all observation windows")
        self.quickAccess[2].setStatusTip("Save the current project setup")
        self.quickAccess[3].setStatusTip("Start all video/audio")
        self.quickAccess[4].setStatusTip("Pause and resume all video/audio")
        self.quickAccess[5].setStatusTip("Stop all video/audio")
        self.quickAccess[6].setStatusTip("Start recording all windows")
        self.quickAccess[7].setStatusTip("Stop recording all windows")

        self.quickAccess[0].triggered.connect(self.dialog.exec)
        self.quickAccess[1].triggered.connect(self.removeAllWindow)

        self.quickAccess[3].triggered.connect(self.startALL)
        self.quickAccess[4].triggered.connect(self.pauseALL)
        self.quickAccess[5].triggered.connect(self.stopALL)
        self.quickAccess[6].triggered.connect(self.startRecordingAll)
        self.quickAccess[7].triggered.connect(self.stopRecordingALL)

        self.toolbar.addActions(self.quickAccess)

        for i, action in enumerate(self.quickAccess):
            if i == 3 or i == 6:
                self.toolbar.addSeparator
            self.toolbar.addAction(action)


    def addMenuBar(self):
        self.filesOptions = [QAction("Save", self),
                             QAction("Load", self),
                             QAction("Export", self)
                            ]

        self.editOptions = [QAction("Settings", self),
                            QAction("Add and remove windows", self),
                            ]
        self.editOptions[1].triggered.connect(self.dialog.exec)

        self.toolOptions1 = [QAction("Sync Midi", self),
                              QAction("Sync Video", self),
                              QAction("Show Delays",self)]
        
        self.toolOptions2 = [QAction("Preload Video", self),
                             QAction("Export Key Frames",self)]
        self.toolOptions2[0].triggered.connect(self.videoTool.exec)

        self.menu = self.menuBar()
        self.fileMenu = self.menu.addMenu("&Files")
        self.editMenu = self.menu.addMenu("&Edit")
        self.toolMenu = self.menu.addMenu("&Tools")

        
        self.fileMenu.addActions(self.filesOptions)
        
        self.editMenu.addActions(self.editOptions)
        
        self.toolMenu.addActions(self.toolOptions1)
        self.toolMenu.addSeparator()
        self.toolMenu.addActions(self.toolOptions2)


    def addWindow(self, widgetClass):
        for i, iData in enumerate(self.windows):
            for j, jData in enumerate(iData):
                if jData.widget is None:
                    widget = widgetClass(int((i * 4 + j + 1))) if isinstance(widgetClass, type) else widgetClass
                    jData.widget = widget
                    jData.setID(int(i * 4 + j + 1))
                    self.fondLayout.addWidget(widget, int(i), int(j))
                    return

    
    def removeWindow(self, ID: int):
        for row in self.windows:
            for window in row:
                if window.getID() == ID:
                    widget = window.getWidget()
                    if widget is not None:
                        widget.stop()
                        self.fondLayout.removeWidget(widget)
                        widget.setParent(None)

                    window.setID(0)
                    window.widget = None
                    return
                

    def removeAllWindow(self):
        for row in self.windows:
            for window in row:
                widget = window.getWidget()
                if not widget == None:
                    widget.stop()
                    self.fondLayout.removeWidget(widget)
                    widget.setParent = None
                    window.setID(0)
                    window.widget = None
                    

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
        
    
    def startRecordingAll(self):
        for i in self.windows:
            for j in i:
                if not j.widget == None:
                    j.widget.setRecord(True)

    def stopRecordingALL(self):
        for i in self.windows:
            for j in i:
                if not j.widget == None:
                    j.widget.setRecord(False)


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
        hor0 = QHBoxLayout()
        hor1 = QHBoxLayout()

        removeWindowButton = QPushButton("Remove the window number:")
        self.removeWindowSpinBox = QSpinBox()
        removeWindowButton.clicked.connect(self.removeWindow)

        addWindowButtonVideo = QPushButton("Add a Video Feed")
        addWindowButtonVideo.clicked.connect(self.setVideo)
        addWindowButtonVideo.clicked.connect(self.addWindow)
        addWindowButtonMidi = QPushButton("Add a Midi Feed")
        addWindowButtonMidi.clicked.connect(self.setMidi)
        addWindowButtonMidi.clicked.connect(self.addWindow)
        addWindowButtonAudio = QPushButton("Add a Audio Feed")
        addWindowButtonAudio.clicked.connect(self.setAudio)
        addWindowButtonAudio.clicked.connect(self.addWindow)

        hor0.addWidget(removeWindowButton)
        hor0.addWidget(self.removeWindowSpinBox)

        hor1.addWidget(addWindowButtonVideo)
        hor1.addWidget(addWindowButtonMidi)
        hor1.addWidget(addWindowButtonAudio)

        vert.addLayout(hor0)
        vert.addLayout(hor1)
        self.setLayout(vert)
        self.widget = None

    def setVideo(self):
        self.widget = VideoFeed

    def setMidi(self):
        self.widget = MidiFeed

    def setAudio(self):
        self.widget = AudioFeed

    def addWindow(self, checked = False):
        self.mainWindow.addWindow(self.widget)
        self.close()


    def removeWindow(self):
        self.mainWindow.removeWindow(self.removeWindowSpinBox.value())
        self.close()








        
    