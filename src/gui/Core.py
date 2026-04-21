from PyQt6.QtCore import pyqtSignal, QObject, pyqtSlot, QThread, Qt
from PyQt6.QtWidgets import QFileDialog, QCheckBox, QLineEdit, QMessageBox, QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QLabel
import time


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
    def __init__(self, path:str):
        super().__init__()

        #Defining default variables
        self.running = False
        self.paused = False
        self.muted = False
        self.path = path


    def run(self):
        self.running = True

        self.beforeLoop()

        while self.running :

            if self.paused:
                QThread.msleep(50)
                continue
            self.loop()

        self.afterLoop()



    def beforeLoop():
        print("Before the loop")
    
    def loop():
        print("Looping")

    def afterLoop():
        print("After the loop")

    @pyqtSlot()
    def pause(self):
        self.paused = not self.paused
        
    @pyqtSlot()
    def stop(self):
        self.running = False

    @pyqtSlot(bool)
    def mute(self, s):
        self.muted = s
    
class basicWindowWidget(QWidget):
    mute = pyqtSignal(bool)

    def __init__(self, workerClass, ID: int = 0, hasAudio = False):
        super().__init__()

        #Setting the default variables
        self.ID = ID
        self.path = ""
        self.mainWidget = None
        self.controlLayout = None
        self.hasAudio = hasAudio
        self.thread = None
        self.worker = None
        self.workerClass = workerClass

        

        
    def setControlLayout(self, layout):
        self.controlLayout = layout


    def setMainWidget(self, widget):
        self.mainWidget = widget


    def makeBasicWidget(self):

        #ID number
        IDLabel = QLabel(str(self.ID))

        #Control buttons
        startButton = QPushButton("Start")
        pauseButton = QPushButton("Pause/Resume")
        stopButton = QPushButton("Stop")
        startButton.clicked.connect(self.start)
        pauseButton.clicked.connect(self.pause)
        stopButton.clicked.connect(self.stop)
        if self.hasAudio:
            self.muteCheckBox = QCheckBox("Mute")
            self.muteCheckBox.clicked.connect(self.mute)
            
        #Control layout
        controlsLayout = QHBoxLayout()
        controlsLayout.addWidget(startButton)
        controlsLayout.addWidget(pauseButton)
        controlsLayout.addWidget(stopButton)
        if self.hasAudio:
            controlsLayout.addWidget(self.muteCheckBox)
        controlsLayout.addStretch()

        #Video path
        self.pathInput = FileDropLineEdit()
        self.pathInput.setPlaceholderText("Video path...")
        self.pathInput.textChanged.connect(self.updatePath)
        self.pathInput.fileDropped.connect(self.updatePath)

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
        windowLayout.addLayout(pathLayout, 0)
        self.setLayout(windowLayout)
        

    def start(self):
        #If the worker already exist
        if self.thread is not None:
            return

        #Check if the path is valid
        if not self.checkPath(self.path):
            Message = MessageBox("Path Error!", "The path is empty and needs a file!")
            return
        
        #Create and initialize the thread and worker
        self.thread = QThread()
        self.worker = self.workerClass(self.path)

        #Sends the worker to the thread
        self.worker.moveToThread(self.thread)

        #Starts the worker if the thread is started
        self.thread.started.connect(self.worker.run)

        if self.hasAudio and self.muteCheckBox.checkState():
            self.worker.mute(self.muteCheckBox.isChecked())

        self.worker.finished.connect(self.worker.stop)

        #Connections of specific windows
        self.connectAll()

        #Sets the thread garbage collection settings
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        #Start the thread and so, the worker
        self.thread.start()


    def pause(self):
        if self.worker is not None:
            self.worker.paused = not self.worker.paused


    def stop(self):
        if self.worker is not None:
            self.worker.stop()      #Stop the worker
        if self.thread is not None:
            self.thread.quit()      #Stop the thread
            self.thread.wait()

            self.worker = None      #Deletes them both
            self.thread = None

    def mute(self, s):
        if self.worker is not None:
            self.worker.mute(s)


    def updatePath(self, path):
        self.path = path


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

