from PyQt6.QtWidgets import *
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from src.video.video import VideoFeed
from src.audio.midi import MidiFeed
from src.audio.audio import AudioFeed
from src.tools.VideoLoader import VideoLoader
from src.tools.masterClock import MasterClock
from src.tools.midiSync import MidiSync
from src.tools.videoSync import VideoSync
from src.tools.keyFrameExporter import KeyFrameExporter
from src.video.keyFrames import KeyFeed
from src.tools.fileIO import saveSettings,loadSettings
from src.tools.setting import GlobalSettings
from src.gui.ScriptWindow import ScriptBox
import copy
from os import path

class WidgetData():
    """
    Storage of the ID and the widget of each window.
    """
    def __init__(self, widget: QWidget = None, ID: int = 0):
        self.widget = widget
        self.ID = ID

    
    def setID(self, ID: int) -> None:
        """
        Set the ID of the widget.
        """
        self.ID = ID

    
    def getID(self) -> int:
        """
        Get the ID of the widget.
        """
        return self.ID
    

    def getWidget(self) -> QWidget:
        """
        Get a reference to the wiget object.
        """
        return self.widget


class MainWindow(QMainWindow):
    """
    Main window of the app.\n
    It contains all the other widgets and feed.
    Most of the logic for adding, removing and managing windows is in this class.
    It's in charge of managing most of the other classes of the app.
    """
    windowAdded = pyqtSignal(QWidget)

    def __init__(self, workingPath: str):
        super().__init__()

        #Sets the window's defaults
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenu)
        self.setWindowTitle("Data Colector")
        self.setMinimumSize(QSize(600, 400))
        self.showMaximized()
        
        self.windowNumber = 0
        self.windows = [[WidgetData() for _ in range(4)] for _ in range(2)]
        self.clock = None
        self.localPath = workingPath
        self.addBaseWidget()

        loadSettings()

        self.settings = GlobalSettings


    def addBaseWidget(self) -> None:
        """
        Makes the basic widget for the background of the window.
        """
        fond = QWidget()
        self.fondLayout = QGridLayout()
        self.fondLayout.setSpacing(10)
        fond.setLayout(self.fondLayout)
        self.dialog = WindowChoice(self, self.windows)

        self._addTopMenu()
        self._addMenuBar()

        self.setCentralWidget(fond)


    def _addTopMenu(self) -> None:
        """
        Add the top - Quick access - menu to the main window.
        """
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        quickAccess = [QAction("Add/Remove a window", self),
                            QAction("Remove All windows", self),
                            QAction("Start", self),
                            QAction("Pause/Resume", self),
                            QAction("Stop", self),
                            QAction("Record", self)
                            ]
        
        quickAccess[0].setStatusTip("Add or remove an observation window")
        quickAccess[1].setStatusTip("Remove all observation windows")
        quickAccess[2].setStatusTip("Start all video/audio")
        quickAccess[3].setStatusTip("Pause and resume all video/audio")
        quickAccess[4].setStatusTip("Stop all video/audio")
        quickAccess[5].setStatusTip("Recording all windows")

        quickAccess[0].triggered.connect(self.dialog.exec)
        quickAccess[1].triggered.connect(self.removeAllWindow)
        quickAccess[2].triggered.connect(self.startALL)
        quickAccess[3].triggered.connect(self.pauseALL)
        quickAccess[4].triggered.connect(self.stopALL)
        quickAccess[5].triggered.connect(self.chooseRecording)

        quickAccess[5].setCheckable(True)

        toolbar.addActions(quickAccess)

        for i, action in enumerate(quickAccess):
            if i == 2 or i == 5:
                toolbar.addSeparator()
            toolbar.addAction(action)


    def _addMenuBar(self) -> None:
        """
        Add the differrent options to the menu bar.
        """
        filesOptions = [QAction("Save", self),
                        QAction("Load", self),
                        QAction("Export", self)
                        ]
        
        editOptions = [QAction("Settings", self),
                       QAction("Add and remove windows", self),
                        ]
        editOptions[0].triggered.connect(self.setSettings)
        editOptions[1].triggered.connect(self.dialog.exec)

        toolOptions1 = [QAction("Sync Midi", self),
                        QAction("Sync Video", self)]
        toolOptions1[0].triggered.connect(self.midiSync)
        toolOptions1[1].triggered.connect(self.videoSync)
        
        toolOptions2 = [QAction("Preload Video", self),
                        QAction("Export Key Frames", self),
                        QAction("Load script", self)]
        toolOptions2[0].triggered.connect(self.preload)
        toolOptions2[1].triggered.connect(self.exportKeyFrames)
        toolOptions2[2].triggered.connect(self.loadScript)

        menu = self.menuBar()
        fileMenu = menu.addMenu("&Files")
        editMenu = menu.addMenu("&Edit")
        toolMenu = menu.addMenu("&Tools")
        
        fileMenu.addActions(filesOptions)
        editMenu.addActions(editOptions)
        toolMenu.addActions(toolOptions1)
        toolMenu.addSeparator()
        toolMenu.addActions(toolOptions2)


    def addWindow(self, widgetClass):
        for i, iData in enumerate(self.windows):
            for j, jData in enumerate(iData):
                if jData.widget is None:
                    widget = widgetClass(int((i * 4 + j + 1)), self.localPath) if isinstance(widgetClass, type) else widgetClass
                    jData.widget = widget
                    jData.setID(int(i * 4 + j + 1))
                    self.fondLayout.addWidget(widget, int(i), int(j))
                    self.windowAdded.connect(jData.widget.addWidget)
                    self.windowAdded.emit(jData.widget)
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
        for i in range(1, 9):
            self.removeWindow(i)
                    

    def startALL(self):
        self.clock = MasterClock(self.windows)

        for row in self.windows:
            for widgetData in row:
                if widgetData.widget is not None:
                    widgetData.widget.start(masterClock=self.clock, delayed=True)
        
            
    def pauseALL(self):
        if self.clock is not None:
            new_state = not self.clock.paused
            self.clock.setPaused(new_state)

        for i in self.windows:
            for j in i:
                if j.widget is not None:
                    j.widget.pause()
    
    def stopALL(self):
        self.clock = None
        for i in self.windows:
            for j in i:
                if not j.widget == None:
                    j.widget.stop()
        

    def chooseRecording(self, s):
        if s:
            self.startRecordingAll()
        else:
            self.stopRecordingALL()
    
    def startRecordingAll(self):
        for i in self.windows:
            for j in i:
                if not j.widget == None:
                    if hasattr(j.widget, "setRecord"):
                        if hasattr(j.widget, "worker"):
                            if hasattr(j.widget.worker, "running"):
                                if j.widget.worker.running:
                                    j.widget.setRecord(True)

    def stopRecordingALL(self):
        for i in self.windows:
            for j in i:
                if not j.widget == None:
                    if hasattr(j.widget, "setRecord"):
                        if hasattr(j.widget, "worker"):
                            if hasattr(j.widget.worker, "running"):
                                if j.widget.worker.running:
                                    j.widget.setRecord(False)


    def contextMenu(self):
        print("")
        #make context menu here


    def preload(self):
        loader = VideoLoader()
        loader.exec()
        loader = None


    def midiSync(self):
        sync = MidiSync(self.localPath)
        sync.exec()
        sync = None


    def videoSync(self):
        sync = VideoSync(self.localPath)
        sync.exec()
        sync = None


    def loadScript(self):
        loader = ScriptBox()
        loader.exec()
        loader = None

    def getWidgetByID(self, ID: int = 0) -> QWidget:
        for i in self.windows:
            for j in i:
                if j.ID == ID and j.widget is not None:
                    return j.widget
        return None
    

    def exportKeyFrames(self):
        keyFrameLoader = KeyFrameExporter()
        keyFrameLoader.exec()
        keyFrameLoader = None

    
    def setSettings(self):
        settingbox = SettingBox(self.settings)
        settingbox.exec()
        settingbox = None


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
    def __init__(self, MainWindow, windows = []):
        super().__init__()
        self.mainWindow = MainWindow

        vert = QVBoxLayout()

        self.hor0 = QGridLayout()
        self.hor0.rowStretch(0)
        self.hor0.columnStretch(0)

        self.hor0.addWidget(QLabel("Remove a window:"), 0, 0)

        hor1 = QHBoxLayout()
        self.buttons = []
        self.windows = windows
               
        addWindowButtonVideo = QPushButton("Add a Video Feed")
        addWindowButtonVideo.clicked.connect(self.setVideo)
        addWindowButtonVideo.clicked.connect(self.addWindow)
        addWindowButtonMidi = QPushButton("Add a Midi Feed")
        addWindowButtonMidi.clicked.connect(self.setMidi)
        addWindowButtonMidi.clicked.connect(self.addWindow)
        addWindowButtonAudio = QPushButton("Add a Audio Feed")
        addWindowButtonAudio.clicked.connect(self.setAudio)
        addWindowButtonAudio.clicked.connect(self.addWindow)
        addWindowButtonKeyFrames = QPushButton("Add a KeyFrame Feed")
        addWindowButtonKeyFrames.clicked.connect(self.setKeyFrames)
        addWindowButtonKeyFrames.clicked.connect(self.addWindow)


        hor1.addWidget(addWindowButtonVideo)
        hor1.addWidget(addWindowButtonAudio)
        hor1.addWidget(addWindowButtonMidi)
        hor1.addWidget(addWindowButtonKeyFrames)
        

        vert.addLayout(self.hor0)
        vert.addLayout(hor1)
        self.setLayout(vert)
        self.widget = None

    def setVideo(self):
        self.widget = VideoFeed

    def setMidi(self):
        self.widget = MidiFeed

    def setAudio(self):
        self.widget = AudioFeed

    def setKeyFrames(self):
        self.widget = KeyFeed

    def addWindow(self, checked = False):
        self.mainWindow.addWindow(self.widget)
        self.close()


    def removeWindow(self, ID):
        self.mainWindow.removeWindow(ID)
        self.close()

    def exec(self):
        for button in self.buttons:
            self.hor0.removeWidget(button)
            button.setParent(None)
            button.deleteLater()

        self.buttons = []

        for row in self.windows:
            for window in row:
                if isinstance(window, WidgetData):
                    if isinstance(window.widget, (VideoFeed, AudioFeed, MidiFeed, KeyFeed)):
                        id = window.getID()
                        button = QPushButton(f"{id}")
                        button.setMaximumSize(20, 20)
                        button.clicked.connect(lambda checked = False, id=id: self.removeWindow(id))
                        self.hor0.addWidget(button, 0 if id < 5 else 1, ((id - 1) % 4) + 1)

                        self.buttons.append(button)
            
        super().exec()

class SettingBox(QDialog):
    """
    Settings menu to the app in a "QDialog" box.
    """
    def __init__(self, mainSettings):
        super().__init__()
        self.setFixedSize(1000, 800)

        settings = copy.deepcopy(mainSettings)

        closeButton = QPushButton("Save and close")
        closeButton.clicked.connect(lambda : self.saveAndClose(settings, mainSettings))
        closeButton.setMaximumSize(100, 40)

        layout = QVBoxLayout()
        
        #Code name of the patient
        nameInput = QLineEdit()
        nameInput.setPlaceholderText("Code name")
        nameInput.setText(settings["participantName"])
        nameInput.textChanged.connect(lambda text: settings.__setitem__("participantName", text))
        
        layout.addLayout(self._addSetting("Code name of the test subject",
                                         "Set the code name under which the recorded files will be saved",
                                         nameInput), 0)
        
        #Path to the recording directory
        self.dirInput = QLineEdit()
        self.dirInput.setPlaceholderText("Path to the directory")
        self.dirInput.setText(settings["pathToWorkingDir"])
        self.dirInput.textChanged.connect(lambda text: settings.__setitem__("pathToWorkingDir", text))

        browseButton = QPushButton("Browse")
        browseButton.clicked.connect(self.findDir)

        dirInputLayout = QHBoxLayout()
        dirInputLayout.setContentsMargins(0, 0, 0, 0)
        dirInputLayout.addWidget(self.dirInput, 0)
        dirInputLayout.addWidget(browseButton, 0)
        dirInputLayout.addStretch()

        dirChoice = QWidget()
        dirChoice.setLayout(dirInputLayout)
        dirChoice.setMinimumSize(600, 40)

        layout.addLayout(self._addSetting("Path to the save directory",
                                         "Set the set the path to the directory where the different test subject files will be saved",
                                         dirChoice), 0)
        
        #Choice of the detection confidence
        detectionConfidence = QDoubleSpinBox()
        detectionConfidence.setValue(settings["detectionConfidence"])
        detectionConfidence.setMaximum(1.0)
        detectionConfidence.setMinimum(0.0)
        detectionConfidence.setDecimals(2)
        detectionConfidence.setSingleStep(0.05)
        detectionConfidence.valueChanged.connect(lambda value: settings.__setitem__("detectionConfidence", value))
        
        layout.addLayout(self._addSetting("Detection Confidence for the algorithm",
                                         "Set the detection confidence score requiered for the palm detection model to identify a hand",
                                         detectionConfidence), 0)

        #Choice of the tracking confidence
        trackingConfidence = QDoubleSpinBox()
        trackingConfidence.setValue(settings["trackingConfidence"])
        trackingConfidence.setMaximum(1.0)
        trackingConfidence.setMinimum(0.0)
        trackingConfidence.setDecimals(2)
        trackingConfidence.setSingleStep(0.05)
        trackingConfidence.valueChanged.connect(lambda value: settings.__setitem__("trackingConfidence", value))
        
        layout.addLayout(self._addSetting("Tracking Confidence for the algorithm",
                                         "Set the traquing confidence score requiered for the palm detection model to maintain the hand between frames",
                                         trackingConfidence), 0)
        
        #Choice of the presence confidence
        presenceConfidence = QDoubleSpinBox()
        presenceConfidence.setValue(settings["presenceConfidence"])
        presenceConfidence.setMaximum(1.0)
        presenceConfidence.setMinimum(0.0)
        presenceConfidence.setDecimals(2)
        presenceConfidence.setSingleStep(0.05)
        presenceConfidence.valueChanged.connect(lambda value: settings.__setitem__("presenceConfidence", value))
        
        layout.addLayout(self._addSetting("Presence Confidence for the algorithm",
                                         "Set the presence confidence score requiered for the palm detection model to find the hand if it is partialy covered or on the edge of the screen",
                                         presenceConfidence), 0)

        #depth camera options
        self.checkZed(settings, layout)

        layout.addStretch()

        settingList = QScrollArea()
        settingList.setWidgetResizable(True)
        container = QWidget()
        container.setLayout(layout)
        settingList.setWidget(container)
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(settingList, 1)
        mainLayout.addWidget(closeButton, 0)
        self.setLayout(mainLayout)


    @staticmethod
    def _addSetting(name:str, description:str, widget:QWidget)-> QVBoxLayout:
        """
        Add a setting to the list and does its styling.
        """
        layout = QVBoxLayout()

        nameLabel = QLabel(name)
        nameLabel.setObjectName("nameLabel")
        nameLabel.setStyleSheet("""
                                QLabel#nameLabel {
                                    color :  #FFFF00;
                                    font-size: 18px;
                                    font-weight : bold;
                                }                                
        """)
        descriptionLabel = QLabel(description)

        layout.addWidget(nameLabel, 0)
        layout.addWidget(descriptionLabel, 0)
        widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        widget.setMinimumSize(100, 25)
        widget.setMaximumSize(600, 40)
        layout.addWidget(widget, 0)
        layout.setContentsMargins(0,10,0,10)

        return layout
    

    def checkZed(self, settings, layout) -> None:
        """
        Options for the Zed depth camera.
        """
        settings["depthCameraAvailable"] = self._checkPyzed()
        if not settings["depthCameraAvailable"]: return
        
        #Enabling the depth camera
        zedCheckBox = QCheckBox("Make the depth camera available")
        zedCheckBox.setChecked(settings["depthCameraAvailable"])
        zedCheckBox.stateChanged.connect(lambda checked: settings.__setitem__("depthCameraAvailable", bool(checked)))
        
        layout.addLayout(self._addSetting("Use depth cameras",
                                         "Make the use of Zed depth camera available when recording",
                                         zedCheckBox), 0)
        
        #Minimum depth
        zedMinDepth = QDoubleSpinBox()
        zedMinDepth.setValue(settings["zedDepthMin"])
        zedMinDepth.setMaximum(1.0)
        zedMinDepth.setMinimum(0.2)
        zedMinDepth.setDecimals(2)
        zedMinDepth.setSingleStep(0.01)
        zedMinDepth.valueChanged.connect(lambda value: settings.__setitem__("zedDepthMin", value))
        
        layout.addLayout(self._addSetting("Minimum depth",
                                         "Set the minimum depth for the Zed depth camera",
                                         zedMinDepth), 0)
        
        #Maximum depth
        zedMaxDepth = QDoubleSpinBox()
        zedMaxDepth.setValue(settings["zedDepthMax"])
        zedMaxDepth.setMaximum(10.0)
        zedMaxDepth.setMinimum(1.0)
        zedMaxDepth.setDecimals(2)
        zedMaxDepth.setSingleStep(0.01)
        zedMaxDepth.valueChanged.connect(lambda value: settings.__setitem__("zedDepthMax", value))
        
        layout.addLayout(self._addSetting("Maximum depth",
                                         "Set the maximum depth for the Zed depth camera",
                                         zedMaxDepth), 0)
        
        #Choice of resolution (vga to 2k)
        zedResolution = QComboBox()
        zedResolution.addItems(["VGA", "HD720", "HD1080", "HD2K"])
        zedResolution.setCurrentText(settings["zedResolution"] if settings["zedResolution"] is not None else "HD1080")
        zedResolution.currentTextChanged.connect(lambda: self._updateComboBox(zedResolution.currentText(), settings))
        

        layout.addLayout(self._addSetting("Resolution",
                                         "Set the resolution for the zed depth camera",
                                         zedResolution), 0)

        #Choice of Fps to use
        self.zedFps = QComboBox()
        self._updateComboBox(zedResolution.currentText(), settings)
        self.zedFps.setCurrentText(f"{str(settings["zedFps"])}FPS")
        self.zedFps.currentTextChanged.connect(lambda: settings.__setitem__("zedFps",int(self.zedFps.currentText().removesuffix("FPS"))) if self.zedFps.currentText() else 0)
        

        layout.addLayout(self._addSetting("Frame rate",
                                         "Set the maximum frame rate for the zed depth camera",
                                         self.zedFps), 0)
        
        #Choice of mode to use
        zedMode = QComboBox()
        zedMode.addItems(["Neural_Light", "Neural", "Neural_Complete"])
        zedMode.currentTextChanged.connect(lambda: settings.__setitem__("zedMode", zedMode.currentText()))
        zedMode.setCurrentText(settings["zedMode"] if settings["zedMode"] is not None else "Neural_Light")

        layout.addLayout(self._addSetting("Mode",
                                         "Set the mode for the depth camera neural network",
                                         zedMode), 0)
        


    def _updateComboBox(self, value:str, settings) -> None:
        """
        Update the "zedFps" combo box to only contain the supported Fps for the chosen resolution.
        """
        settings["zedResolution"] = value
        fps = settings["zedFps"]
        options = ["VGA", "HD720", "HD1080", "HD2K"]

        self.zedFps.clear()
        self.zedFps.addItems(["15FPS", "30FPS", "60FPS", "100FPS"])

        for i in range(0, self.zedFps.count()):
            if value == options[i]:
                maxFps = int(self.zedFps.itemText(self.zedFps.count() - 1).removesuffix("FPS"))
                self.zedFps.setCurrentText(f"{min(fps, maxFps)}FPS")
                settings["zedFps"] = min(fps, maxFps)
                return
            else:
                self.zedFps.removeItem(self.zedFps.count() - 1)

        self.zedFps.setCurrentText("")
        self.zedFps.removeItem(0)
        settings["zedFps"] = 0
        

    def saveAndClose(self, settings, mainSettings):
        """
        Saving the app settings and closing the sttings dialog.
        """
        mainSettings.clear()
        mainSettings.update(settings)
        saveSettings()
        self.accept()


    def findDir(self):
        """
        Get the user's chosen directory then set the input to its path.
        """
        dirName = QFileDialog.getExistingDirectory(
            self, 
            "Select a directory",
            "",
            QFileDialog.Option.ShowDirsOnly
        )

        if dirName:
            self.dirInput.setText(str(path.abspath(dirName)))

    @staticmethod
    def _checkPyzed() -> bool:
        """
        Check if the pyzed module is installed.
        """
        try:
            import pyzed.sl
        except ImportError:
            return False
        return True