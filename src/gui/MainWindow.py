from PyQt6.QtWidgets import *
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QSize, pyqtSignal
from src.video.video import VideoFeed
from src.audio.midi import MidiFeed
from src.audio.audio import AudioFeed
from src.tools.VideoLoader import VideoLoader
from src.tools.masterClock import MasterClock
from src.tools.midiSync import MidiSync
from src.tools.videoSync import VideoSync
from src.tools.keyFrameExporter import KeyFrameExporter
from src.video.keyFrames import KeyFeed
from src.tools.fileIO import loadSettings
from src.tools.setting import GlobalSettings
from src.gui.ScriptWindow import ScriptBox
from src.gui.ScriptWindow import ResultLoader
from src.gui.SettingsWindow import SettingBox

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
        editMenu = menu.addMenu("&Edit")
        toolMenu = menu.addMenu("&Tools")

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
                    widget = widgetClass(int((i * 4 + j + 1)), self.localPath) if isinstance(widgetClass, type) else widgetClass

                    # Save the widget data
                    jData.widget = widget
                    jData.setID(int(i * 4 + j + 1))

                    # Add the widget to the layout
                    self.fondLayout.addWidget(widget, int(i), int(j))

                    # Send the new widget to the other widgets
                    self.windowAdded.connect(jData.widget.addWidget)
                    self.windowAdded.emit(jData.widget)
                    return

    def removeWindow(self, ID: int = 0):
        """
        Remove a window from the main grid by its ID.\n
        :param `int` ID: ID of the window to remove, defaults to `0`.
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
                    widgetData.widget.start(masterClock=self.clock, delayed=True)

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
                if j.widget == None:
                    continue
                # Guard clauses for widgets that cannot record

                if not hasattr(j.widget, "setRecord"):
                    continue

                if not hasattr(j.widget, "worker"):
                    continue

                if not hasattr(j.widget.worker, "running"):
                    continue

                if j.widget.worker.running:
                    j.widget.setRecord(True)

    def stopRecordingALL(self):
        """
        Stop recording on every running widget that supports recording.
        """
        # Look through every widget
        for i in self.windows:
            for j in i:
                if j.widget == None:
                    continue
                # Guard clauses for widgets that cannot record

                if not hasattr(j.widget, "setRecord"):
                    continue

                if not hasattr(j.widget, "worker"):
                    continue

                if not hasattr(j.widget.worker, "running"):
                    continue
                
                if j.widget.worker.running:
                    j.widget.setRecord(False)

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
        self.menuButtons[1].setStatusTip("Edit and control the virtual environment")

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

    def __init__(self, MainWindow: MainWindow, windows: list):
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

    def addWindow(self, checked: bool=False):
        """
        Add the selected widget type to the main window.\n
        :param bool checked: Checked state from the button signal, defaults to `False`.
        """
        # Add the selected window and close the dialog
        self.mainWindow.addWindow(self.widget)
        self.close()

    def removeWindow(self, ID: int):
        """
        Remove the selected window from the main window.\n
        :param `int` ID: ID of the window to remove.
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
                        button.clicked.connect(lambda _=False, id=id: self.removeWindow(id))
                        self.hor0.addWidget(button, 0 if id < 5 else 1, ((id - 1) % 4) + 1)

                        self.buttons.append(button)

        super().exec()