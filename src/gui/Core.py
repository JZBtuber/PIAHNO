from PyQt6.QtCore import pyqtSignal, QObject, pyqtSlot, QThread, Qt
from PyQt6.QtWidgets import QFileDialog, QComboBox, QCheckBox, QLineEdit, QMessageBox, QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtMultimedia import QMediaDevices
import pyaudio
import cv2
import mido


class FileDropLineEdit(QLineEdit):
    fileDropped = pyqtSignal(str)   #Signal emitted when a file is dropped

    def __init__(self):
        super().__init__()

        self.setAcceptDrops(True)   #Allows drag and drop on the widget


    def dragEnterEvent(self, event):
        mime = event.mimeData()

        #Check if the dragged data contains file paths
        if mime.hasUrls():
            urls = mime.urls()

            #Check if the first url is a local file
            if urls and urls[0].isLocalFile():
                event.acceptProposedAction()  #Accept the drag
                return

        event.ignore()   #Reject if not valid


    def dragLeaveEvent(self, event):
        mime = event.mimeData()

        #Same logic as dragEnter, but for leaving event
        if mime.hasUrls():
            urls = mime.urls()
            if urls and urls[0].isLocalFile():
                event.acceptProposedAction()
                return

        event.ignore()


    def dropEvent(self, event):
        mime = event.mimeData()

        #Check if dropped data contains files
        if mime.hasUrls():
            urls = mime.urls()

            if urls:
                local_path = urls[0].toLocalFile()   #Get the file path

                if local_path:
                    self.setText(local_path)         #Update the line edit
                    self.fileDropped.emit(local_path) #Emit the signal
                    event.acceptProposedAction()
                    return

        event.ignore()   #Reject invalid drops


class MessageBox(QMessageBox):
    def __init__(self, Name: str, Message: str):
        super().__init__()

        #Set the main message text
        self.setText(Message)

        #Set the window title (top bar)
        self.setWindowTitle(Name)

        #Set the available buttons (only OK)
        self.setStandardButtons(QMessageBox.StandardButton.Ok)

        #Set default button
        self.setDefaultButton(QMessageBox.StandardButton.Ok)

        #Set the icon type (warning icon)
        self.setIcon(QMessageBox.Icon.Warning)

        #Show the message box (blocking)
        self.exec()


class basicWorker(QObject):
    finished = pyqtSignal()
    def __init__(self, path, isLive):
        super().__init__()

        #Defining default variables
        self.running = False
        self.paused = False
        self.muted = False
        self.isLive = isLive
        self.path = path
        self.record = False
        self.isRecording = False
        self.ID = 0


    def run(self):
        self.running = True

        try:
            self.beforeLoop()

            while self.running :

                if self.paused:
                    QThread.msleep(50)
                    continue
                self.loop()
                if self.record or self.isRecording:
                    self.recordSetUp()

        except Exception as e:
            print(f"{type(self).__name__} crashed: {e}")

        finally:
            try:
                self.afterLoop()
                
            except Exception as e:
                print(f"{type(self).__name__} crashed: {e}")
            finally:
                self.finished.emit()



    def beforeLoop(self):
        print("Before the loop")
    
    def loop(self):
        print("Looping")

    def afterLoop(self):
        print("After the loop")

    
    def recordSetUp(self):
        if not self.isRecording:
            self.initRecording()
            self.isRecording = True

        self.recordloop()


        if not self.record:
            self.stopRecording()
            self.isRecording = False
            

    
    def initRecording(self):
        print("Initiatiing Recording")


    def stopRecording(self):
        print("Stop recording")


    def recordloop(self):
        print("Recording")

    def setID(self, ID: int = 0):
        self.ID = ID

    @pyqtSlot()
    def pause(self):
            self.paused = not self.paused


    @pyqtSlot()
    def stop(self):
            self.running = False


    @pyqtSlot(bool)
    def mute(self, s):
            self.muted = s


    @pyqtSlot(bool)
    def setRecord(self, s):
            self.record = s
            
    
class basicWindowWidget(QWidget):
    mute = pyqtSignal(bool)

    def __init__(self, workerClass, ID: int = 0, hasAudio = False):
        super().__init__()

        #Setting the default variables
        self.ID = ID
        self.filePath: str = ""
        self.livePath: str = ""
        self.path: str = ""
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

        
    def setControlLayout(self, layout):
        self.controlLayout = layout


    def setMainWidget(self, widget):
        self.mainWidget = widget


    def makeBasicWidget(self):

        #ID number
        IDLabel = QLabel(str(self.ID))

        #Control buttons
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
            self.muteCheckBox.clicked.connect(self.mute)
            
        #Control layout
        controlsLayout = QHBoxLayout()
        controlsLayout.addWidget(self.startButton)
        controlsLayout.addWidget(self.pauseButton)
        controlsLayout.addWidget(stopButton)
        if self.hasAudio:
            controlsLayout.addWidget(self.muteCheckBox)
        controlsLayout.addStretch()

        #Device Control
        self.isLiveCheckbox = QCheckBox("Use live input")
        self.isLiveCheckbox.toggled.connect(self.setIsLive)

        reloadDevicesButton = QPushButton("Reload Devices")
        reloadDevicesButton.clicked.connect(self.reloadDevices)

        self.deviceComboBox = QComboBox()
        self.deviceComboBox.setPlaceholderText("Device to use")
        self.getDevices(self.inputType)

        for device in self.devices:
            self.deviceComboBox.addItem(device["name"], device["id"])

        self.deviceComboBox.currentIndexChanged.connect(self.updateLivePath)

        deviceControlLayout = QHBoxLayout()
        deviceControlLayout.addWidget(self.isLiveCheckbox)
        deviceControlLayout.addWidget(reloadDevicesButton)
        deviceControlLayout.addWidget(self.deviceComboBox)

        #Video path
        self.pathInput = FileDropLineEdit()
        self.pathInput.setPlaceholderText("Video path...")
        self.pathInput.textChanged.connect(self.updateFilePath)
        self.pathInput.fileDropped.connect(self.updateFilePath)

        #Browse button
        browseButton = QPushButton("Browse")
        browseButton.clicked.connect(self.browseFile)

        #Path input layout
        pathLayout = QHBoxLayout()
        pathLayout.addWidget(self.pathInput, 1)
        pathLayout.addWidget(browseButton, 0)
        

        #layout of the window
        windowLayout = QVBoxLayout()

        windowLayout.addStretch()
        windowLayout.addWidget(IDLabel, 0)
        if self.mainWidget is not None:
            windowLayout.addWidget(self.mainWidget, 1)
        windowLayout.addLayout(controlsLayout, 0)
        if self.controlLayout is not None:
            windowLayout.addLayout(self.controlLayout, 0)
        if self.isLiveFeed:
            windowLayout.addLayout(deviceControlLayout, 0)
        windowLayout.addLayout(pathLayout, 0)
        self.setLayout(windowLayout)
        

    def start(self):
        #If the worker already exist
        if self.thread is not None:
            return
        
        #Check if the path is valid
        self.setPathOptions(self.isLiveCheckbox.isChecked())
        if not self.checkPath(self.path):
            Message = MessageBox("Path Error!", "The path is empty and needs a file!")
            return

        #Create and initialize the thread and worker
        self.thread = QThread()
        
        self.worker = self.workerClass(self.path, self.isLive)

        #Sends the worker to the thread
        self.worker.moveToThread(self.thread)

        #Starts the worker if the thread is started
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.onWorkerFinished)

        self.worker.setID(self.ID)
        if self.hasAudio and self.muteCheckBox.checkState():
            self.worker.mute(self.muteCheckBox.isChecked())

        #Connections of specific windows
        self.connectAll()

        #Sets the thread garbage collection settings
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.onThreadFinished)

        #Start the thread and so, the worker
        self.thread.start()


    def pause(self):
        if self.worker is not None:
            self.worker.paused = not self.worker.paused


    def updateFilePath(self):
        self.filePath = self.pathInput.text()


    def setIsLive(self, s: bool):
        self.isLive = s

    
    def setRecord(self, s):
        self.worker.setRecord(s)


    def stop(self):
        self.startButton.setChecked(False)
        self.pauseButton.setChecked(False)

        if self.worker is not None:
            try:
                self.worker.stop()
            except Exception:
                pass

        if self.thread is not None:
            self.thread.quit()
            self.thread.wait()

    def mute(self, s):
        if self.worker is not None:
            self.worker.mute(s)

    
    def updateLivePath(self):
        self.livePath = self.deviceComboBox.currentData()
        

    def setPathOptions(self, s: bool):
        if s:
            self.path = self.livePath
        else:
            self.path = self.filePath


    def browseFile(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "MP4 Files (*.mp4);;MOV files (*.MOV);;All Files (*)"
        )
        if path:
            self.pathInput.setText(path)

    
    def checkPath(self, path):
        if path:
            return True
        else:
            return False
        

    def connectAll(self):
        print("Make all connections")


    def reloadDevices(self):
        self.getDevices(self.inputType)

        self.deviceComboBox.clear()

        for device in self.devices:
            self.deviceComboBox.addItem(device["name"], device["id"])



    def getDevices(self, backend: str):
        self.devices = []

        if backend == "video":
            self.devices = self.getVideoDevicesCV2()
        elif backend == "audio":
            self.devices = self.getAudioDevicesPyAudio()
        elif backend == "midi":
            self.devices = self.getMidiInputDevices()
        else:
            raise ValueError(f"Unknown backend: {backend}")


    def getVideoDevicesCV2(self, max_devices: int = 5):
        devices = []

        for i in range(max_devices):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                devices.append({
                    "id": i,
                    "name": f"Camera {i}"
                })
                cap.release()

        return devices
    

    def getAudioDevicesPyAudio(self):
        devices = []
        p = pyaudio.PyAudio()

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
        self.worker.setRecord(True)


    def stopRecording(self):
        self.worker.setRecord(False)
    

    def getMidiInputDevices(self):
        devices = []

        try:
            names = mido.get_input_names()
            for i, name in enumerate(names):
                devices.append({
                    "id": name,      # keep the actual port name
                    "name": name
                })
        except Exception as e:
            print("Failed to get MIDI devices:", e)

        return devices
    

    def onWorkerFinished(self):
        self.startButton.setChecked(False)
        self.pauseButton.setChecked(False)


    def onThreadFinished(self):
        self.worker = None
        self.thread = None