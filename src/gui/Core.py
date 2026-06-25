from PyQt6.QtCore import pyqtSignal, QObject, pyqtSlot, QThread, Qt
from PyQt6.QtWidgets import QFileDialog, QComboBox, QCheckBox, QLineEdit, QMessageBox, QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QLabel
from src.tools.fileIO import getDelayFromParent
from pygrabber.dshow_graph import FilterGraph
from datetime import datetime
from src.tools.setting import GlobalSettings
import pyaudio
import mido
import os
import time


# Error message box to communicate with the user.
class MessageBox(QMessageBox):
    """
    Message box used to show errors to the user.
    """
    def __init__(self, Name: str, Message: str):
        """
        Create and show a warning message box.\n
        :param `str` Name: Title of the message box.
        :param `str` Message: Message to show in the box.
        """
        super().__init__()

        self.setWindowTitle(Name)  # Set the window title (top bar)
        self.setText(Message)  # Set the main message text

        # Set the available buttons (only OK)
        self.setStandardButtons(QMessageBox.StandardButton.Ok)

        self.setIcon(QMessageBox.Icon.Warning)  # Set the icon type

        self.exec()  # Enable the message box


class FileDropLineEdit(QLineEdit):
    """
    Line edit that accepts file paths by drag and drop.
    """
    fileDropped = pyqtSignal(str)  # Signal emitted when a file is dropped

    def __init__(self):
        """
        Create the file drop line edit.
        """
        super().__init__()

        self.setAcceptDrops(True)  # Allows drag and drop on the widget
        self.textChanged.connect(lambda: self.setText(self.text()))

    # -----------------------------------------------------------
    # Events to drag and drop files
    # -----------------------------------------------------------

    def dragEnterEvent(self, event):
        """
        Accept the drag event if it contains a local file.\n
        :param event: Drag enter event.
        """
        mime = event.mimeData()

        # Check if the dragged data contains file paths
        if mime.hasUrls():
            urls = mime.urls()

            # Check if the first url is a local file
            if urls and urls[0].isLocalFile():
                event.acceptProposedAction()  # Accept the drag
                return

        event.ignore()  # Reject if not valid

    def dragLeaveEvent(self, event):
        """
        Accept the drag leave event if it contains a local file.\n
        :param event: Drag leave event.
        """
        mime = event.mimeData()

        # Same logic as dragEnter, but for leaving event
        if mime.hasUrls():
            urls = mime.urls()
            if urls and urls[0].isLocalFile():
                event.acceptProposedAction()
                return

        event.ignore()

    def dropEvent(self, event):
        """
        Set the line edit text when a local file is dropped.\n
        :param event: Drop event.
        """
        mime = event.mimeData()

        # Check if dropped data contains files
        if mime.hasUrls():
            urls = mime.urls()

            if urls:
                local_path = urls[0].toLocalFile()  # Get the file path

                if local_path:
                    self.setText(local_path)  # Update the line edit
                    self.fileDropped.emit(local_path)  # Emit the signal
                    event.acceptProposedAction()
                    return

        event.ignore()  # Reject invalid drops

    # ------------------------------------------------------------
    # Functions to change the text with path verification
    # ------------------------------------------------------------

    def setText(self, a0):
        """
        Set the text only if the path exists or if the text is empty.\n
        :param a0: Text or path to set in the line edit.
        """
        # Allow empty text
        if a0 == "":
            return super().setText(a0)

        # Only accept existing paths
        if os.path.exists(a0):
            return super().setText(a0)
        else:
            message = MessageBox("Path error!", "That path doesn't exist!")

    def text(self):
        """
        Get the current path only if it exists.\n
        :returns: Returns the current text if it is an existing path, otherwise returns an empty string.
        """
        # Only return valid paths
        if os.path.exists(super().text()):
            return super().text()
        else:
            return ""


class RecordingWorker(QObject):
    """
    Worker used to run recording in a separate thread.
    """
    finished = pyqtSignal()

    def __init__(self, initFunc, recordFunc, stopFunc):
        """
        Create the recording worker.\n
        :param initFunc: Function called before the recording loop starts.
        :param recordFunc: Function called repeatedly while recording.
        :param stopFunc: Function called when recording stops.
        """
        super().__init__()

        # Taking the functions defined in the different
        # feeds and using the in the right order
        self.initFunc = initFunc
        self.recordFunc = recordFunc
        self.stopFunc = stopFunc

        # Set default variables
        self.running = False

    @pyqtSlot()
    def run(self):
        """
        Start the recording loop.
        """
        self.running = True

        # Basic recording loop with init and closing
        try:
            self.initFunc()

            while self.running:
                self.recordFunc()
                QThread.msleep(1)

        finally:
            self.stopFunc()
            self.finished.emit()

    @pyqtSlot()
    def stop(self):
        """
        Stop the recording loop.
        """
        self.running = False


class basicWorker(QObject):
    """
    Base worker class used by feed widgets.
    """
    finished = pyqtSignal()
    ready = pyqtSignal(int)
    stopRecord = pyqtSignal()
    pathError = pyqtSignal()

    def __init__(self, path: str, isLive: bool, delay: int= 0):
        """
        Create the base worker.\n
        :param path: File path or live device path used by the worker.
        :param isLive: If `True`, the worker uses a live input.
        :param delay: Delay before starting the loop, defaults to `0`.
        """
        super().__init__()

        # Defining default variables
        self.running = False
        self.paused = False
        self.muted = False
        self.isLive = isLive
        self.path = path
        self.record = False
        self.isRecording = False
        self.ID = 0
        self.delay = delay
        self.delayed = False
        self.released = False
        self.masterClock = None
        self.localStartTime = None
        self.recorder = None
        self.recordThread = None
        self.recordStopping = False
        self.recordSelf = False

    def run(self):
        """
        Run the worker setup, loop and cleanup cycle.
        """
        self.running = True

        # Workers default cycle with error managment
        try:
            # Send an error if the path is empty
            if not self.isLive and self.path == "":
                self.running = False
                self.pathError.emit()
                return

            # Initialise the feed
            self.beforeLoop()
            self.ready.emit(self.ID)

            # Delay management
            while self.running and self.delayed:
                if self.masterClock is not None and self.ID in self.masterClock.released_ids:
                    self.delay = self.masterClock.released_ids[self.ID]
                    break
                QThread.msleep(1)
            if self.delay > 0:
                QThread.msleep(self.delay)
            self.localStartTime = time.perf_counter()

            # Main loop
            while self.running:

                # Pause
                if self.paused:
                    QThread.msleep(50)
                    continue

                # Loop function
                self.loop()

                # Recording managment
                if self.record or self.isRecording:
                    if self.recordSelf:
                        self.selfRecordSetup()
                    else:
                        self._recordSetUp()

        except Exception as e:  # Execption managment
            print(f"{type(self).__name__} crashed: {e}")

        finally:
            try:  # Kills the sub processes
                self.afterLoop()
            except Exception as e:
                print(f"{type(self).__name__} crashed: {e}")
            finally:
                recordThread = self.recordThread
                if self.recordThread is not None and recordThread.isRunning():
                    self.recordThread.quit()
                    self.recordThread.wait()

                self.finished.emit()

    # -----------------------------------------------------------
    # Abstract functions to be filled by the feeds
    # -----------------------------------------------------------

    def beforeLoop(self):
        """
        Function called before the main loop starts.\n
        :raises: `NotImplementedError` if the child class does not implement this method.
        """
        raise NotImplementedError

    def loop(self):
        """
        Function called repeatedly while the worker is running.\n
        :raises: `NotImplementedError` if the child class does not implement this method.
        """
        raise NotImplementedError

    def afterLoop(self):
        """
        Function called after the main loop stops.\n
        :raises: `NotImplementedError` if the child class does not implement this method.
        """
        raise NotImplementedError

    def initRecording(self):
        """
        Function called before recording starts.\n
        :raises: `NotImplementedError` if the child class does not implement this method.
        """
        raise NotImplementedError

    def stopRecording(self):
        """
        Function called when recording stops.\n
        :raises: `NotImplementedError` if the child class does not implement this method.
        """
        raise NotImplementedError

    def recordloop(self):
        """
        Function called repeatedly while recording.\n
        :raises: `NotImplementedError` if the child class does not implement this method.
        """
        raise NotImplementedError

    # --------------------------------------------------------
    # Recording functions
    # --------------------------------------------------------

    def selfRecordSetup(self):
        """
        Manage recording directly in the worker thread.
        """
        if self.record and not self.isRecording:  # Init
            self.initRecording()
            self.isRecording = True

        if self.record and self.isRecording:  # Loop
            self.recordloop()

        if not self.record and self.isRecording:  # Closing/stop
            self.stopRecording()
            self.isRecording = False

    def _recordSetUp(self):
        # Replace the queued signal callback with direct polling
        if self.recordStopping and self.recordThread is not None and not self.recordThread.isRunning():
            self.recorder = None
            self.recordThread = None
            self.isRecording = False
            self.recordStopping = False

        # Start a new recording
        if self.record and not self.isRecording:
            self.recorder = RecordingWorker(
                self.initRecording,
                self.recordloop,
                self.stopRecording
            )
            self.recordThread = QThread()
            self.recorder.moveToThread(self.recordThread)

            self.recordThread.started.connect(self.recorder.run)
            self.recorder.finished.connect(self.recordThread.quit, Qt.ConnectionType.DirectConnection)
            self.recorder.finished.connect(self.recorder.deleteLater)
            self.recordThread.finished.connect(self.recordThread.deleteLater)

            self.stopRecord.connect(self.recorder.stop, Qt.ConnectionType.DirectConnection)

            self.recordThread.start()
            self.isRecording = True

        # Stop the recording
        elif not self.record and self.isRecording and not self.recordStopping:
            self.recordStopping = True
            if self.recorder is not None:
                self.stopRecord.emit()

    def setID(self, ID: int = 0):
        """
        Set the ID of the worker.\n
        :param `int` ID: ID to give to the worker, defaults to `0`.
        """
        self.ID = ID

    @pyqtSlot()
    def pause(self):
        """
        Toggle the worker pause state.
        """
        self.paused = not self.paused

    @pyqtSlot()
    def stop(self):
        """
        Stop the worker and stop recording if needed.
        """
        self.running = False
        self.record = False

        # Stop self recording
        if self.recordSelf:
            if self.isRecording:
                self.stopRecording()
                self.isRecording = False

        # Stop recording thread
        elif self.recorder is not None:
            self.stopRecord.emit()

    @pyqtSlot(bool)
    def mute(self, s: bool) -> None:
        """
        Set the mute state.\n
        :param `bool` s: New mute state.
        """
        self.muted = s

    @pyqtSlot(bool)
    def setRecord(self, s: bool) -> None:
        """
        Set the recording state.\n
        :param `bool` s: New recording state.
        """
        self.record = s

    def setDelayed(self, s: bool) -> None:
        """
        Set the delayed start state.\n
        :param `bool` s: New delayed start state.
        """
        self.delayed = s

    def setMasterClock(self, clock) -> None:
        """
        Set the master clock used for synchronization.\n
        :param clock: Master clock object.
        """
        self.masterClock = clock

    def getMasterTimeMs(self) -> int:
        """
        Get the current synchronized time in milliseconds.\n
        :returns: Returns the master clock time if available, otherwise local worker time.
        :rtype: `int`
        """
        # Use the master clock if available
        if self.masterClock is not None:
            return self.masterClock.elapsedMs() - self.delay

        # Guard clause if the local clock has not started
        if self.localStartTime is None:
            return 0

        # Use the local worker clock
        return int((time.perf_counter() - self.localStartTime) * 1000)

    @staticmethod
    def getRecordingPath() -> str:
        """
        Returns the path to the directory where the file should be saved.\n
        :returns: Returns the path to the current recording directory.
        :rtype: `str`
        """
        # Create the test folder name
        timeString = str(datetime.now()).replace(
            " ", "_").replace(":", "-")[0:19]

        # Get the base saving path
        pathToFile = GlobalSettings["pathToWorkingDir"] if GlobalSettings["pathToWorkingDir"] else os.path.join(
            os.getcwd(), "Tests")
        filepath = f"{GlobalSettings["participantName"]}\\{timeString}_Test" if GlobalSettings["participantName"] else f"{timeString}_Test"

        return os.path.join(pathToFile, filepath)


class basicWindowWidget(QWidget):
    """
    Base widget class used by feed windows.
    """
    mute = pyqtSignal(bool)
    stopWorker = pyqtSignal()

    def __init__(self, workerClass, ID: int = 0, hasAudio=False, workingDir: str = ""):
        """
        Create the base window widget.\n
        :param workerClass: Worker class used by this widget.
        :param `int` ID: ID of the widget, defaults to `0`.
        :param hasAudio: If `True`, the widget has audio controls, defaults to `False`.
        :param `str` workingDir: Working directory used by the widget, defaults to `""`.
        """
        super().__init__()

        # Setting the default variables

        self.windows = []

        self.ID = ID
        self.filePath: str = ""
        self.livePath: str = ""
        self.path: str = ""
        self.workingDir: str = workingDir
        self.mainWidget = None
        self.controlLayout = None
        self.hasAudio = hasAudio
        self.thread = None
        self.worker = None
        self.workerClass = workerClass
        self.inputType = None
        self.isLive = False
        self.devices = []
        self.isLiveFeed = True
        self.syncParentName: str = ""
        self.fileName: str = ""
        self.syncDelay: int = 0

    @pyqtSlot(QWidget)
    def addWidget(self, widget: QWidget):
        """
        Add a widget to the list of known windows and update the parent list.\n
        :param `QWidget` widget: Widget to add to the known windows.
        """
        # Add the widget and reset the parent combo box
        self.windows.append(widget)
        self.parentComboBox.clear()

        # Add possible parent widgets to the combo box
        for w in self.windows:
            if isinstance(w, basicWindowWidget) and (w.ID != self.ID) and (w.fileName != ""):
                self.parentComboBox.addItem(w.fileName)

    def reloadParents(self):
        """
        Reload the list of possible sync parents from the main window.
        """
        # Reset current parent list
        self.parentComboBox.clear()

        self.windows = []

        # Get all widgets from the main window
        for i in range(1, 9):
            window = self.window()
            if hasattr(window, "getWidgetByID"):
                self.windows.append(window.getWidgetByID(i))
            else:
                return

        # Add possible parent widgets to the combo box
        for w in self.windows:
            if isinstance(w, basicWindowWidget) and (w.ID != self.ID) and (w.fileName != ""):
                self.parentComboBox.addItem(w.fileName)

    def setSyncParentName(self, name: str):
        """
        Set the sync parent name and load the saved delay.\n
        :param `str` name: Name of the selected sync parent.
        """
        # Save the sync parent name
        self.syncParentName = name
        self.syncParentNameLabel.setText(f"Parent name: {self.syncParentName}")

        # Load the delay from the saved parent data
        self.syncDelay = getDelayFromParent(self.pathInput.text(),
                                            f"{os.path.dirname(self.pathInput.text())}/{self.syncParentName}",
                                            self.workingDir)
        self.syncDelayLabel.setText(f"Sync delay: {self.syncDelay}")

    def setControlLayout(self, layout):
        """
        Set the custom control layout.\n
        :param layout: Layout to add under the base controls.
        """
        self.controlLayout = layout

    def setMainWidget(self, widget):
        """
        Set the main content widget.\n
        :param widget: Widget to show in the main area.
        """
        self.mainWidget = widget

    def makeBasicWidget(self):
        """
        Create the basic feed window layout.
        """

        # ID number
        IDLabel = QLabel(f"{type(self).__name__}   ID: {self.ID}")

        # SyncParent
        self.parentComboBox = QComboBox()
        self.parentComboBox.setPlaceholderText("Sync Parent")
        self.parentComboBox.currentTextChanged.connect(self.setSyncParentName)

        reloadParentsButton = QPushButton("Reload")

        reloadParentsButton.clicked.connect(self.reloadParents)

        self.syncParentNameLabel = QLabel(
            f"Parent name: {self.syncParentName}")

        # Delay
        self.syncDelayLabel = QLabel(f"Sync delay: {self.syncDelay}")

        # Top layout
        hTopLayout1 = QHBoxLayout()
        hTopLayout2 = QHBoxLayout()
        topLayout = QVBoxLayout()

        hTopLayout1.addWidget(IDLabel)
        hTopLayout1.addWidget(self.parentComboBox)
        hTopLayout1.addWidget(reloadParentsButton)
        hTopLayout2.addWidget(self.syncParentNameLabel)
        hTopLayout2.addWidget(self.syncDelayLabel)
        hTopLayout1.addStretch()
        hTopLayout2.addStretch()

        topLayout.addLayout(hTopLayout1)
        topLayout.addLayout(hTopLayout2)

        # Control buttons
        self.startButton = QPushButton("Start")
        self.pauseButton = QPushButton("Pause/Resume")
        stopButton = QPushButton("Stop")

        self.startButton.setCheckable(True)
        self.pauseButton.setCheckable(True)

        self.startButton.clicked.connect(self.start)
        self.pauseButton.clicked.connect(self.pause)
        stopButton.clicked.connect(self.stop)

        if self.hasAudio:
            self.muteCheckBox = QCheckBox("Mute")
            self.muteCheckBox.setEnabled(False)
            self.muteCheckBox.clicked.connect(self.mute)

        # Control layout
        controlsLayout = QHBoxLayout()
        controlsLayout.addWidget(self.startButton)
        controlsLayout.addWidget(self.pauseButton)
        controlsLayout.addWidget(stopButton)
        if self.hasAudio:
            controlsLayout.addWidget(self.muteCheckBox)
        controlsLayout.addStretch()

        # Device Control
        self.isLiveCheckbox = QCheckBox("Use live input")
        self.isLiveCheckbox.stateChanged.connect(self.setIsLive)

        reloadDevicesButton = QPushButton("Reload Devices")
        reloadDevicesButton.clicked.connect(self.reloadDevices)

        self.deviceComboBox = QComboBox()
        self.deviceComboBox.setPlaceholderText("Device to use")
        self.deviceComboBox.currentIndexChanged.connect(
            lambda: self.isLiveCheckbox.setChecked(True))
        self.getDevices(self.inputType)

        for device in self.devices:
            self.deviceComboBox.addItem(device["name"], device["id"])

        self.deviceComboBox.currentIndexChanged.connect(self.updateLivePath)

        deviceControlLayout = QHBoxLayout()
        deviceControlLayout.addWidget(self.isLiveCheckbox)
        deviceControlLayout.addWidget(reloadDevicesButton)
        deviceControlLayout.addWidget(self.deviceComboBox)

        # Path Input
        self.pathInput = FileDropLineEdit()
        self.pathInput.setPlaceholderText("Path to the file...")
        self.pathInput.textChanged.connect(self.updateFilePath)
        self.pathInput.fileDropped.connect(self.updateFilePath)

        # Browse button
        browseButton = QPushButton("Browse")
        browseButton.clicked.connect(self.browseFile)

        # Path input layout
        pathLayout = QHBoxLayout()
        pathLayout.addWidget(self.pathInput, 1)
        pathLayout.addWidget(browseButton, 0)

        # layout of the window
        windowLayout = QVBoxLayout()

        windowLayout.addStretch()
        windowLayout.addLayout(topLayout, 0)
        if self.mainWidget is not None:
            windowLayout.addWidget(self.mainWidget, 1)
        windowLayout.addLayout(controlsLayout, 0)
        if self.controlLayout is not None:
            windowLayout.addLayout(self.controlLayout, 0)
        if self.isLiveFeed:
            windowLayout.addLayout(deviceControlLayout, 0)
        windowLayout.addLayout(pathLayout, 0)
        self.setLayout(windowLayout)

    def start(self, checked=False, masterClock=None, delayed=False):
        """
        Start the worker thread for this widget.\n
        :param checked: Checked state from the button signal, defaults to `False`.
        :param masterClock: Master clock used for synchronization, defaults to `None`.
        :param delayed: If `True`, the worker waits for the master clock release, defaults to `False`.
        """
        # Guard clause if the worker is already running
        if self.thread is not None:
            return

        # Set the input path to live or file mode
        self.setPathOptions(self.isLiveCheckbox.isChecked())

        # Create the worker and thread
        self.thread = QThread()
        self.worker = self.workerClass(self.path, self.isLive)
        self.worker.setID(self.ID)
        self.worker.setDelayed(delayed)

        # Move the worker to its thread
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)

        # Connect worker stop signals
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.onWorkerFinished)

        self.stopWorker.connect(
            self.worker.stop, Qt.ConnectionType.DirectConnection)

        # Connect path error signal
        self.worker.pathError.connect(
            self.showPathError,
            Qt.ConnectionType.QueuedConnection
        )

        # Connect master clock if needed
        if masterClock is not None:
            self.worker.ready.connect(masterClock.setReady)
            self.worker.setMasterClock(masterClock)

        # Connect child class signals
        self.connectAll()

        # Connect thread cleanup signals
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.onThreadFinished)

        # Start the thread
        self.thread.start()

    def pause(self):
        """
        Toggle the pause state of the worker.
        """
        # Toggle pause if the worker exists
        if self.worker is not None:
            self.worker.paused = not self.worker.paused

    def updateFilePath(self):
        """
        Update the file path from the path input.
        """
        # Switch to file mode
        self.isLiveCheckbox.setChecked(False)

        # Save the file path and file name
        self.filePath = self.pathInput.text()
        self.fileName = os.path.basename(self.filePath)

    def setIsLive(self, s: bool):
        """
        Set whether the widget uses a live input.\n
        :param `bool` s: New live input state.
        """
        # Save the live state
        self.isLive = s

        # Disable mute when leaving live mode
        if self.hasAudio and not s:
            self.muteCheckBox.setChecked(False)

        # Enable mute only if the widget has audio
        if self.hasAudio:
            self.muteCheckBox.setEnabled(s)

    def setRecord(self, s):
        """
        Set the worker recording state.\n
        :param s: New recording state.
        """
        # Send the record state to the worker
        if self.worker is not None:
            self.worker.setRecord(s)

    def stop(self):
        """
        Stop the worker.
        """
        # Reset button states
        self.startButton.setChecked(False)
        self.pauseButton.setChecked(False)

        # Stop the worker if it exists
        if self.worker is not None:
            self.stopWorker.emit()

    def mute(self, s):
        """
        Set the worker mute state.\n
        :param s: New mute state.
        """
        # Send the mute state to the worker
        if self.worker is not None:
            self.worker.mute(s)

    def updateLivePath(self):
        """
        Update the live device path from the selected device.
        """
        self.livePath = self.deviceComboBox.currentData()

    def setPathOptions(self, s: bool):
        """
        Select the active path from the live or file input.\n
        :param `bool` s: If `True`, use the live path. Otherwise, use the file path.
        """
        # Use live or file path
        if s:
            self.path = self.livePath
        else:
            self.path = self.filePath

    def getDelay(self):
        """
        Get the sync delay.\n
        :returns: Returns the sync delay.
        """
        return self.syncDelay

    def setDelay(self, delay: float = 0.0):
        """
        Set the sync delay.\n
        :param `float` delay: Sync delay to set, defaults to `0.0`.
        """
        self.syncDelay = delay

    def browseFile(self):
        """
        Open a file dialog and set the selected path.
        """
        # User chooses the input file
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "MP4 Files (*.mp4);;MOV files (*.MOV);;All Files (*)"
        )

        # Set the path if a file was chosen
        if path:
            self.pathInput.setText(path)

    def connectAll(self):
        """
        Function used by child classes to connect their custom signals.
        """

    def reloadDevices(self):
        """
        Reload the available live input devices.
        """
        # Reload the device list
        self.getDevices(self.inputType)

        self.deviceComboBox.clear()

        # Add devices to the combo box
        for device in self.devices:
            self.deviceComboBox.addItem(device["name"], device["id"])

    def getDevices(self, backend: str):
        """
        Get the available devices for the selected backend.\n
        :param `str` backend: Backend type to use.
        :raises: `ValueError` if the backend is unknown.
        """
        self.devices = []

        # Get devices from the selected backend
        if backend == "video":
            self.devices = self.getVideoDevicesCV2()
        elif backend == "audio":
            self.devices = self.getAudioDevicesPyAudio()
        elif backend == "midi":
            self.devices = self.getMidiInputDevices()
        elif backend == "keyFrame":
            self.devices = []
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def getVideoDevicesCV2(self):
        """
        Get the available video input devices.\n
        :returns: Returns the list of video devices.
        """
        devices = FilterGraph().get_input_devices()
        return [{"id": i, "name": name} for i, name in enumerate(devices)]

    def getAudioDevicesPyAudio(self):
        """
        Get the available audio input devices.\n
        :returns: Returns the list of audio input devices.
        """
        devices = []
        p = pyaudio.PyAudio()

        # Get every input audio device
        try:
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)

                if info.get("maxInputChannels", 0) > 0:
                    devices.append({
                        "id": i,
                        "name": info.get("name", f"Microphone {i}")
                    })
        finally:
            p.terminate()

        return devices

    def startRecording(self):
        """
        Start recording from this widget's worker.
        """
        self.worker.setRecord(True)

    def stopRecording(self):
        """
        Stop recording from this widget's worker.
        """
        self.worker.setRecord(False)

    def getMidiInputDevices(self):
        """
        Get the available MIDI input devices.\n
        :returns: Returns the list of MIDI input devices.
        """
        devices = []

        # Get all midi input devices
        try:
            names = mido.get_input_names()
            for _, name in enumerate(names):
                devices.append({
                    "id": name,      # keep the actual port name
                    "name": name
                })
        except Exception as e:
            print("Failed to get MIDI devices:", e)

        return devices

    def onWorkerFinished(self):
        """
        Reset button states when the worker finishes.
        """
        self.startButton.setChecked(False)
        self.pauseButton.setChecked(False)

    def onThreadFinished(self):
        """
        Clear worker and thread references when the thread finishes.
        """
        self.startButton.setChecked(False)
        self.worker = None
        self.thread = None

    @pyqtSlot()
    def showPathError(self):
        """
        Show an error when the selected path is invalid.
        """
        MessageBox("Path error!", "The path doesn't exist / is empty!")