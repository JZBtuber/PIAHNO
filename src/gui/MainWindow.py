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
from src.tools.fileIO import saveSettings, loadSettings
from src.tools.setting import GlobalSettings
from src.gui.ScriptWindow import ScriptBox
from src.gui.ScriptWindow import ResultLoader
import copy
from os import path


class WidgetData():
    """
    Storage of the ID and the widget of each window.
    """

    def __init__(self, widget: QWidget = None, ID: int = 0):
        """
        Create the widget data object.\n
        :param `QWidget` widget: Widget linked to this data object, defaults to `None`.
        :param `int` ID: ID of the widget in the main window, defaults to `0`.
        """
        self.widget = widget
        self.ID = ID

    def setID(self, ID: int) -> None:
        """
        Set the ID of the widget.\n
        :param `int` ID: New ID to give to the widget.
        """
        self.ID = ID

    def getID(self) -> int:
        """
        Get the ID of the widget.\n
        :returns: Returns the widget ID.
        :rtype: `int`
        """
        return self.ID

    def getWidget(self) -> QWidget:
        """
        Get a reference to the widget object.\n
        :returns: Returns the saved widget.
        :rtype: `QWidget`
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
        """
        Create the main application window.\n
        :param `str` workingPath: Path to the working directory of the app.
        """
        super().__init__()

        # Set the window defaults
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenu)
        self.setWindowTitle("Data Colector")
        self.setMinimumSize(QSize(600, 400))
        self.showMaximized()

        # Set default variables
        self.windowNumber = 0
        self.windows = [[WidgetData() for _ in range(4)] for _ in range(2)]
        self.clock = None
        self.localPath = workingPath

        # Create the base widget
        self.addBaseWidget()

        # Load the global settings
        loadSettings()

        self.settings = GlobalSettings

    # ---------------------------------------------------
    # Main window setup
    # ---------------------------------------------------

    def addBaseWidget(self) -> None:
        """
        Makes the basic widget for the background of the window.
        """
        # Create the central widget and layout
        fond = QWidget()
        self.fondLayout = QGridLayout()
        self.fondLayout.setSpacing(10)
        fond.setLayout(self.fondLayout)

        # Create the window choice dialog
        self.dialog = WindowChoice(self, self.windows)

        # Add the menus
        self._addTopMenu()
        self._addMenuBar()

        # Set the central widget
        self.setCentralWidget(fond)

    def _addTopMenu(self) -> None:
        """
        Add the top - Quick access - menu to the main window.
        """
        # Create the toolbar
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        # Create the quick access actions
        quickAccess = [QAction("Add/Remove a window", self),
                       QAction("Remove All windows", self),
                       QAction("Start", self),
                       QAction("Pause/Resume", self),
                       QAction("Stop", self),
                       QAction("Record", self)
                       ]

        # Set action descriptions
        quickAccess[0].setStatusTip("Add or remove an observation window")
        quickAccess[1].setStatusTip("Remove all observation windows")
        quickAccess[2].setStatusTip("Start all video/audio")
        quickAccess[3].setStatusTip("Pause and resume all video/audio")
        quickAccess[4].setStatusTip("Stop all video/audio")
        quickAccess[5].setStatusTip("Recording all windows")

        # Connect actions to their functions
        quickAccess[0].triggered.connect(self.dialog.exec)
        quickAccess[1].triggered.connect(self.removeAllWindow)
        quickAccess[2].triggered.connect(self.startALL)
        quickAccess[3].triggered.connect(self.pauseALL)
        quickAccess[4].triggered.connect(self.stopALL)
        quickAccess[5].triggered.connect(self.chooseRecording)

        # Set the recording action as checkable
        quickAccess[5].setCheckable(True)

        # Add the actions to the toolbar
        toolbar.addActions(quickAccess)

        # Add separators and actions to the toolbar
        for i, action in enumerate(quickAccess):
            if i == 2 or i == 5:
                toolbar.addSeparator()
            toolbar.addAction(action)

    def _addMenuBar(self) -> None:
        """
        Add the different options to the menu bar.
        """
        # Create the menu bar categories
        menu = self.menuBar()
        fileMenu = menu.addMenu("&Files")
        editMenu = menu.addMenu("&Edit")
        toolMenu = menu.addMenu("&Tools")

        # Add file menu actions
        fileMenu.addActions([QAction("Save", self),
                             QAction("Load", self),
                             QAction("Export", self)
                             ])

        # Add edit menu actions
        editMenu.addActions([QAction("Settings", self),
                             QAction("Add and remove windows", self),
                             ])

        # Connect edit menu actions
        editMenu.actions()[0].triggered.connect(self.setSettings)
        editMenu.actions()[1].triggered.connect(self.dialog.exec)

        # Add tool menu actions
        toolMenu.addActions([QAction("Sync Midi", self),
                             QAction("Sync Video", self)
                             ])
        toolMenu.addSeparator()
        toolMenu.addActions([QAction("Preload Video", self),
                             QAction("Export Key Frames", self)
                             ])
        toolMenu.addSeparator()
        toolMenu.addActions([QAction("Load script", self),
                             QAction("Load results", self)
                             ])

        # Connect tool menu actions
        toolMenu.actions()[0].triggered.connect(self.midiSync)
        toolMenu.actions()[1].triggered.connect(self.videoSync)
        toolMenu.actions()[3].triggered.connect(self.preload)
        toolMenu.actions()[4].triggered.connect(self.exportKeyFrames)
        toolMenu.actions()[6].triggered.connect(self.loadScript)
        toolMenu.actions()[7].triggered.connect(self.loadResults)

    # ---------------------------------------------------
    # Window management
    # ---------------------------------------------------

    def addWindow(self, widgetClass):
        """
        Add a new widget to the first empty position in the main grid.\n
        :param widgetClass: Widget class or widget object to add to the main window.
        """
        # Look for the first empty window slot
        for i, iData in enumerate(self.windows):
            for j, jData in enumerate(iData):
                if jData.widget is None:
                    # Create the widget if a class was given
                    widget = widgetClass(int(
                        (i * 4 + j + 1)), self.localPath) if isinstance(widgetClass, type) else widgetClass

                    # Save the widget data
                    jData.widget = widget
                    jData.setID(int(i * 4 + j + 1))

                    # Add the widget to the layout
                    self.fondLayout.addWidget(widget, int(i), int(j))

                    # Send the new widget to the other widgets
                    self.windowAdded.connect(jData.widget.addWidget)
                    self.windowAdded.emit(jData.widget)
                    return

    def removeWindow(self, ID: int):
        """
        Remove a window from the main grid by its ID.\n
        :param `int` ID: ID of the window to remove.
        """
        # Look for the widget with the requested ID
        for row in self.windows:
            for window in row:
                if window.getID() == ID:
                    widget = window.getWidget()

                    # Stop and remove the widget if it exists
                    if widget is not None:
                        widget.stop()
                        self.fondLayout.removeWidget(widget)
                        widget.setParent(None)

                    # Reset the window data
                    window.setID(0)
                    window.widget = None
                    return

    def removeAllWindow(self):
        """
        Remove all windows from the main grid.
        """
        # Remove every possible window ID
        for i in range(1, 9):
            self.removeWindow(i)

    def getWidgetByID(self, ID: int = 0) -> QWidget:
        """
        Get a widget from its ID.\n
        :param `int` ID: ID of the widget to get, defaults to `0`.
        :returns: Returns the widget if it exists, otherwise returns `None`.
        :rtype: `QWidget`
        """
        # Look for the widget with the requested ID
        for i in self.windows:
            for j in i:
                if j.ID == ID and j.widget is not None:
                    return j.widget
        return None

    # ---------------------------------------------------
    # Playback controls
    # ---------------------------------------------------

    def startALL(self):
        """
        Start all windows with a shared master clock.
        """
        # Create the master clock for the current windows
        self.clock = MasterClock(self.windows)

        # Start every existing widget
        for row in self.windows:
            for widgetData in row:
                if widgetData.widget is not None:
                    widgetData.widget.start(
                        masterClock=self.clock, delayed=True)

    def pauseALL(self):
        """
        Pause or resume all windows.
        """
        # Update the master clock pause state
        if self.clock is not None:
            new_state = not self.clock.paused
            self.clock.setPaused(new_state)

        # Pause or resume every existing widget
        for i in self.windows:
            for j in i:
                if j.widget is not None:
                    j.widget.pause()

    def stopALL(self):
        """
        Stop all windows and clear the master clock.
        """
        # Clear the master clock
        self.clock = None

        # Stop every existing widget
        for i in self.windows:
            for j in i:
                if not j.widget == None:
                    j.widget.stop()

    # ---------------------------------------------------
    # Recording controls
    # ---------------------------------------------------

    def chooseRecording(self, s):
        """
        Start or stop recording depending on the action state.\n
        :param s: Checked state of the recording action.
        """
        # Start or stop recording from the checked state
        if s:
            self.startRecordingAll()
        else:
            self.stopRecordingALL()

    def startRecordingAll(self):
        """
        Start recording on every running widget that supports recording.
        """
        # Look through every widget
        for i in self.windows:
            for j in i:
                if not j.widget == None:
                    # Guard clauses for widgets that cannot record
                    if hasattr(j.widget, "setRecord"):
                        if hasattr(j.widget, "worker"):
                            if hasattr(j.widget.worker, "running"):
                                if j.widget.worker.running:
                                    j.widget.setRecord(True)

    def stopRecordingALL(self):
        """
        Stop recording on every running widget that supports recording.
        """
        # Look through every widget
        for i in self.windows:
            for j in i:
                if not j.widget == None:
                    # Guard clauses for widgets that cannot record
                    if hasattr(j.widget, "setRecord"):
                        if hasattr(j.widget, "worker"):
                            if hasattr(j.widget.worker, "running"):
                                if j.widget.worker.running:
                                    j.widget.setRecord(False)

    # ---------------------------------------------------
    # Context menu
    # ---------------------------------------------------

    def contextMenu(self):
        """
        Context menu event for the main window.
        """
        print("")
        # make context menu here

    # ---------------------------------------------------
    # Tool dialogs
    # ---------------------------------------------------

    def preload(self):
        """
        Open the video preload dialog.
        """
        # Create and execute the loader dialog
        loader = VideoLoader()
        loader.exec()
        loader = None

    def midiSync(self):
        """
        Open the midi synchronization dialog.
        """
        # Create and execute the sync dialog
        sync = MidiSync(self.localPath)
        sync.exec()
        sync = None

    def videoSync(self):
        """
        Open the video synchronization dialog.
        """
        # Create and execute the sync dialog
        sync = VideoSync(self.localPath)
        sync.exec()
        sync = None

    def loadScript(self):
        """
        Open the script loader dialog.
        """
        # Create and execute the script dialog
        loader = ScriptBox()
        loader.exec()
        loader = None

    def loadResults(self):
        """
        Open the result loader dialog.
        """
        # Create and execute the result loader dialog
        resultsLoader = ResultLoader()
        resultsLoader.exec()
        resultsLoader = None

    def exportKeyFrames(self):
        """
        Open the key frame export dialog.
        """
        # Create and execute the key frame export dialog
        keyFrameLoader = KeyFrameExporter()
        keyFrameLoader.exec()
        keyFrameLoader = None

    def setSettings(self):
        """
        Open the settings dialog.
        """
        # Create and execute the setting dialog
        settingbox = SettingBox(self.settings)
        settingbox.exec()
        settingbox = None


class topMenu(QToolBar):
    """
    Toolbar containing basic menu buttons.
    """

    def __init__(self):
        """
        Create the toolbar and its actions.
        """
        super().__init__()

        # Create menu buttons
        self.menuButtons = [QAction("Files", self), QAction("Edit", self)]

        # Set menu button descriptions
        self.menuButtons[0].setStatusTip("Manage files and systems")
        self.menuButtons[1].setStatusTip(
            "Edit and control the virtual environment")

        # Connect menu buttons
        self.menuButtons[0].triggered.connect(self.fileButtonClicked)
        self.menuButtons[1].triggered.connect(self.editButtonClicked)

        # Set buttons as checkable
        for m in self.menuButtons:
            m.setCheckable(True)

        # Add actions to the toolbar
        self.addActions(self.menuButtons)


class WindowChoice(QDialog):
    """
    Dialog used to add or remove feed windows from the main window.
    """

    def __init__(self, MainWindow, windows=[]):
        """
        Create the window choice dialog.\n
        :param MainWindow: Main window that will receive the add and remove requests.
        :param windows: Current window data grid, defaults to `[]`.
        """
        super().__init__()

        # Save the main window reference
        self.mainWindow = MainWindow

        # Create the main layouts
        vert = QVBoxLayout()

        self.hor0 = QGridLayout()
        self.hor0.rowStretch(0)
        self.hor0.columnStretch(0)

        # Add remove section label
        self.hor0.addWidget(QLabel("Remove a window:"), 0, 0)

        # Create add window layout
        hor1 = QHBoxLayout()
        self.buttons = []
        self.windows = windows

        # Create add window buttons
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

        # Add buttons to the layout
        hor1.addWidget(addWindowButtonVideo)
        hor1.addWidget(addWindowButtonAudio)
        hor1.addWidget(addWindowButtonMidi)
        hor1.addWidget(addWindowButtonKeyFrames)

        # Add layouts to the dialog
        vert.addLayout(self.hor0)
        vert.addLayout(hor1)
        self.setLayout(vert)

        # Set default widget to add
        self.widget = None

    # ---------------------------------------------------
    # Feed selection
    # ---------------------------------------------------

    def setVideo(self):
        """
        Set the next widget to add as a video feed.
        """
        self.widget = VideoFeed

    def setMidi(self):
        """
        Set the next widget to add as a midi feed.
        """
        self.widget = MidiFeed

    def setAudio(self):
        """
        Set the next widget to add as an audio feed.
        """
        self.widget = AudioFeed

    def setKeyFrames(self):
        """
        Set the next widget to add as a key frame feed.
        """
        self.widget = KeyFeed

    # ---------------------------------------------------
    # Window actions
    # ---------------------------------------------------

    def addWindow(self, checked=False):
        """
        Add the selected widget type to the main window.\n
        :param checked: Checked state from the button signal, defaults to `False`.
        """
        # Add the selected window and close the dialog
        self.mainWindow.addWindow(self.widget)
        self.close()

    def removeWindow(self, ID):
        """
        Remove the selected window from the main window.\n
        :param ID: ID of the window to remove.
        """
        # Remove the selected window and close the dialog
        self.mainWindow.removeWindow(ID)
        self.close()

    def exec(self):
        """
        Refresh the remove buttons and execute the dialog.
        """
        # Clear the old remove buttons
        for button in self.buttons:
            self.hor0.removeWidget(button)
            button.setParent(None)
            button.deleteLater()

        self.buttons = []

        # Create one remove button for each existing window
        for row in self.windows:
            for window in row:
                if isinstance(window, WidgetData):
                    if isinstance(window.widget, (VideoFeed, AudioFeed, MidiFeed, KeyFeed)):
                        id = window.getID()
                        button = QPushButton(f"{id}")
                        button.setMaximumSize(20, 20)
                        button.clicked.connect(
                            lambda checked=False, id=id: self.removeWindow(id))
                        self.hor0.addWidget(
                            button, 0 if id < 5 else 1, ((id - 1) % 4) + 1)

                        self.buttons.append(button)

        super().exec()


class SettingBox(QDialog):
    """
    Settings menu to the app in a "QDialog" box.
    """

    def __init__(self, mainSettings):
        """
        Create the settings dialog.\n
        :param mainSettings: Settings dictionary used by the main window.
        """
        super().__init__()
        self.setFixedSize(1000, 800)

        # Keep a temporary copy until the user saves
        settings = copy.deepcopy(mainSettings)

        # Create the close button
        closeButton = QPushButton("Save and close")
        closeButton.clicked.connect(
            lambda: self.saveAndClose(settings, mainSettings))
        closeButton.setMaximumSize(100, 40)

        # Create the settings list layout
        layout = QVBoxLayout()

        # Code name of the patient
        nameInput = QLineEdit()
        nameInput.setPlaceholderText("Code name")
        nameInput.setText(settings["participantName"])
        nameInput.textChanged.connect(
            lambda text: settings.__setitem__("participantName", text))

        layout.addLayout(self._addSetting("Code name of the test subject",
                                          "Set the code name under which the recorded files will be saved",
                                          nameInput), 0)

        # Path to the recording directory
        self.dirInput = QLineEdit()
        self.dirInput.setPlaceholderText("Path to the directory")
        self.dirInput.setText(settings["pathToWorkingDir"])
        self.dirInput.textChanged.connect(
            lambda text: settings.__setitem__("pathToWorkingDir", text))

        # Browse button for the save directory
        browseButton = QPushButton("Browse")
        browseButton.clicked.connect(self.findDir)

        # Create the directory input layout
        dirInputLayout = QHBoxLayout()
        dirInputLayout.setContentsMargins(0, 0, 0, 0)
        dirInputLayout.addWidget(self.dirInput, 0)
        dirInputLayout.addWidget(browseButton, 0)
        dirInputLayout.addStretch()

        # Create the directory input widget
        dirChoice = QWidget()
        dirChoice.setLayout(dirInputLayout)
        dirChoice.setMinimumSize(600, 40)

        layout.addLayout(self._addSetting("Path to the save directory",
                                          "Set the set the path to the directory where the different test subject files will be saved",
                                          dirChoice), 0)

        # Choice of the detection confidence
        detectionConfidence = QDoubleSpinBox()
        detectionConfidence.setValue(settings["detectionConfidence"])
        detectionConfidence.setMaximum(1.0)
        detectionConfidence.setMinimum(0.0)
        detectionConfidence.setDecimals(2)
        detectionConfidence.setSingleStep(0.05)
        detectionConfidence.valueChanged.connect(
            lambda value: settings.__setitem__("detectionConfidence", value))

        layout.addLayout(self._addSetting("Detection Confidence for the algorithm",
                                          "Set the detection confidence score requiered for the palm detection model to identify a hand",
                                          detectionConfidence), 0)

        # Choice of the tracking confidence
        trackingConfidence = QDoubleSpinBox()
        trackingConfidence.setValue(settings["trackingConfidence"])
        trackingConfidence.setMaximum(1.0)
        trackingConfidence.setMinimum(0.0)
        trackingConfidence.setDecimals(2)
        trackingConfidence.setSingleStep(0.05)
        trackingConfidence.valueChanged.connect(
            lambda value: settings.__setitem__("trackingConfidence", value))

        layout.addLayout(self._addSetting("Tracking Confidence for the algorithm",
                                          "Set the traquing confidence score requiered for the palm detection model to maintain the hand between frames",
                                          trackingConfidence), 0)

        # Choice of the presence confidence
        presenceConfidence = QDoubleSpinBox()
        presenceConfidence.setValue(settings["presenceConfidence"])
        presenceConfidence.setMaximum(1.0)
        presenceConfidence.setMinimum(0.0)
        presenceConfidence.setDecimals(2)
        presenceConfidence.setSingleStep(0.05)
        presenceConfidence.valueChanged.connect(
            lambda value: settings.__setitem__("presenceConfidence", value))

        layout.addLayout(self._addSetting("Presence Confidence for the algorithm",
                                          "Set the presence confidence score requiered for the palm detection model to find the hand if it is partialy covered or on the edge of the screen",
                                          presenceConfidence), 0)

        # Depth camera options
        self.checkZed(settings, layout)

        # Add empty space at the bottom of the settings
        layout.addStretch()

        # Create the settings scroll area
        settingList = QScrollArea()
        settingList.setWidgetResizable(True)
        container = QWidget()
        container.setLayout(layout)
        settingList.setWidget(container)

        # Create the main layout
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(settingList, 1)
        mainLayout.addWidget(closeButton, 0)
        self.setLayout(mainLayout)

    # ---------------------------------------------------
    # Setting widget creation
    # ---------------------------------------------------

    @staticmethod
    def _addSetting(name: str, description: str, widget: QWidget) -> QVBoxLayout:
        """
        Add a setting to the list and does its styling.\n
        :param `str` name: Name of the setting.
        :param `str` description: Description of the setting.
        :param `QWidget` widget: Widget used to edit the setting.
        :returns: Returns the layout containing the setting.
        :rtype: `QVBoxLayout`
        """
        # Create the setting layout
        layout = QVBoxLayout()

        # Create the setting name label
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

        # Add setting widgets to the layout
        layout.addWidget(nameLabel, 0)
        layout.addWidget(descriptionLabel, 0)
        widget.setSizePolicy(QSizePolicy.Policy.Fixed,
                             QSizePolicy.Policy.Fixed)
        widget.setMinimumSize(100, 25)
        widget.setMaximumSize(600, 40)
        layout.addWidget(widget, 0)
        layout.setContentsMargins(0, 10, 0, 10)

        return layout

    # ---------------------------------------------------
    # Depth camera settings
    # ---------------------------------------------------

    def checkZed(self, settings, layout) -> None:
        """
        Options for the Zed depth camera.\n
        :param settings: Settings dictionary to update.
        :param layout: Layout where the Zed settings will be added.
        """
        # Check if the depth camera module is available
        settings["depthCameraAvailable"] = self._checkPyzed()

        # Guard clause if the depth camera module is not available
        if not settings["depthCameraAvailable"]:
            return

        # Enabling the depth camera
        zedCheckBox = QCheckBox("Make the depth camera available")
        zedCheckBox.setChecked(settings["depthCameraAvailable"])
        zedCheckBox.stateChanged.connect(
            lambda checked: settings.__setitem__("depthCameraAvailable", bool(checked)))

        layout.addLayout(self._addSetting("Use depth cameras",
                                          "Make the use of Zed depth camera available when recording",
                                          zedCheckBox), 0)

        # Minimum depth
        zedMinDepth = QDoubleSpinBox()
        zedMinDepth.setValue(settings["zedDepthMin"])
        zedMinDepth.setMaximum(1.0)
        zedMinDepth.setMinimum(0.2)
        zedMinDepth.setDecimals(2)
        zedMinDepth.setSingleStep(0.01)
        zedMinDepth.valueChanged.connect(
            lambda value: settings.__setitem__("zedDepthMin", value))

        layout.addLayout(self._addSetting("Minimum depth",
                                          "Set the minimum depth for the Zed depth camera",
                                          zedMinDepth), 0)

        # Maximum depth
        zedMaxDepth = QDoubleSpinBox()
        zedMaxDepth.setValue(settings["zedDepthMax"])
        zedMaxDepth.setMaximum(10.0)
        zedMaxDepth.setMinimum(1.0)
        zedMaxDepth.setDecimals(2)
        zedMaxDepth.setSingleStep(0.01)
        zedMaxDepth.valueChanged.connect(
            lambda value: settings.__setitem__("zedDepthMax", value))

        layout.addLayout(self._addSetting("Maximum depth",
                                          "Set the maximum depth for the Zed depth camera",
                                          zedMaxDepth), 0)

        # Choice of resolution (vga to 2k)
        zedResolution = QComboBox()
        zedResolution.addItems(["VGA", "HD720", "HD1080", "HD2K"])
        zedResolution.setCurrentText(
            settings["zedResolution"] if settings["zedResolution"] is not None else "HD1080")
        zedResolution.currentTextChanged.connect(
            lambda: self._updateComboBox(zedResolution.currentText(), settings))

        layout.addLayout(self._addSetting("Resolution",
                                          "Set the resolution for the zed depth camera",
                                          zedResolution), 0)

        # Choice of Fps to use
        self.zedFps = QComboBox()
        self._updateComboBox(zedResolution.currentText(), settings)
        self.zedFps.setCurrentText(f"{str(settings["zedFps"])}FPS")
        self.zedFps.currentTextChanged.connect(lambda: settings.__setitem__("zedFps", int(
            self.zedFps.currentText().removesuffix("FPS"))) if self.zedFps.currentText() else 0)

        layout.addLayout(self._addSetting("Frame rate",
                                          "Set the maximum frame rate for the zed depth camera",
                                          self.zedFps), 0)

        # Choice of mode to use
        zedMode = QComboBox()
        zedMode.addItems(["Neural_Light", "Neural", "Neural_Complete"])
        zedMode.currentTextChanged.connect(
            lambda: settings.__setitem__("zedMode", zedMode.currentText()))
        zedMode.setCurrentText(
            settings["zedMode"] if settings["zedMode"] is not None else "Neural_Light")

        layout.addLayout(self._addSetting("Mode",
                                          "Set the mode for the depth camera neural network",
                                          zedMode), 0)

    def _updateComboBox(self, value: str, settings) -> None:
        """
        Update the "zedFps" combo box to only contain the supported Fps for the chosen resolution.\n
        :param `str` value: Selected Zed resolution.
        :param settings: Settings dictionary to update.
        """
        # Save the selected resolution
        settings["zedResolution"] = value

        # Get current settings and resolution options
        fps = settings["zedFps"]
        options = ["VGA", "HD720", "HD1080", "HD2K"]

        # Reset the FPS combo box
        self.zedFps.clear()
        self.zedFps.addItems(["15FPS", "30FPS", "60FPS", "100FPS"])

        # Remove unsupported FPS values for the selected resolution
        for i in range(0, self.zedFps.count()):
            if value == options[i]:
                maxFps = int(self.zedFps.itemText(
                    self.zedFps.count() - 1).removesuffix("FPS"))
                self.zedFps.setCurrentText(f"{min(fps, maxFps)}FPS")
                settings["zedFps"] = min(fps, maxFps)
                return
            else:
                self.zedFps.removeItem(self.zedFps.count() - 1)

        # Clear the FPS setting if no valid option was found
        self.zedFps.setCurrentText("")
        self.zedFps.removeItem(0)
        settings["zedFps"] = 0

    # ---------------------------------------------------
    # Settings saving
    # ---------------------------------------------------

    def saveAndClose(self, settings, mainSettings):
        """
        Saving the app settings and closing the settings dialog.\n
        :param settings: Temporary settings dictionary.
        :param mainSettings: Main settings dictionary to update.
        """
        # Save the temporary settings into the main settings
        mainSettings.clear()
        mainSettings.update(settings)

        # Write the settings to file
        saveSettings()

        # Close the dialog
        self.accept()

    def findDir(self):
        """
        Get the user's chosen directory then set the input to its path.
        """
        # User chooses the save directory
        dirName = QFileDialog.getExistingDirectory(
            self,
            "Select a directory",
            "",
            QFileDialog.Option.ShowDirsOnly
        )

        # Update the directory input if a directory was chosen
        if dirName:
            self.dirInput.setText(str(path.abspath(dirName)))

    @staticmethod
    def _checkPyzed() -> bool:
        """
        Check if the pyzed module is installed.\n
        :returns: Returns `True` if pyzed can be imported, otherwise returns `False`.
        :rtype: `bool`
        """
        # Try to import the Zed module
        try:
            import pyzed.sl
        except ImportError:
            return False
        return True
