from src.gui.Core import *
from PyQt6.QtWidgets import QProgressBar, QPushButton, QCheckBox, QDialog, QHBoxLayout, QVBoxLayout, QFileDialog
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from src.tools.mediapipe.algorithms import mediaWork
import os
import cv2


class VideoWorker(QObject):
    frameCount = pyqtSignal(int)
    frameDone = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.path: str                  #Path to the video to write the algorithm on
        self.useOnlyAlgorithm = False   #Use only the algorithm with a black background
        self.running = False
        self.frameNumber = 0

    def run(self):

        capture = cv2.VideoCapture(self.path)

        if not capture.isOpened():
            MessageBox("Error!", "Failed to open video file")
            self.finished.emit()
            return

        fourcc =cv2.VideoWriter_fourcc(*'mp4v')
        
        self.frameNumber = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = capture.get(cv2.CAP_PROP_FPS)   
        self.frameCount.emit(self.frameNumber)
        self.frameCountDone = 0

        newPath = os.path.join(os.path.dirname(self.path), f"{os.path.splitext(os.path.basename(self.path))[0]}_{'ONLYHAND' if self.useOnlyAlgorithm else 'HAND'}.mp4")

        output = cv2.VideoWriter(newPath, fourcc, fps, (width, height))
        
        algorithm = mediaWork()

        while self.frameCountDone < self.frameNumber and capture.isOpened():

            ret, frame = capture.read()
            if not ret:
                break
            
            frame = algorithm.draw2dHands(frame, fps, self.useOnlyAlgorithm)

            output.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

            self.frameCountDone += 1
            self.frameDone.emit()

        capture.release()
        output.release()
        
        if not self.frameCountDone == self.frameNumber:
            MessageBox("Error!", "The video loading didn't go correctly!")

        self.finished.emit()


    def setUseOnlyAlgorithm(self, bool: bool):
        self.useOnlyAlgorithm = bool


    def setPath(self, path: str):
        self.path = path


class VideoLoader(QDialog):
    def __init__(self):
        super().__init__()

        self.path: str = ""
        self.outputPath: str = ""
        self.useOnlyAlgorithm = False
        self.thread = None
        self.worker = None

        self.optionsLayout = self.getOptionsLayout()
        self.mainLayout = QVBoxLayout()
        self.mainLayout.addLayout(self.optionsLayout)
        self.setLayout(self.mainLayout)


    def start(self):
        if self.worker is not None:
            return

        if not self.checkPath():
            Message = MessageBox("Path Error!", "The path is empty and needs a file!")
            return
        
        #Create and initialize the thread and worker
        self.thread = QThread()
        self.worker = VideoWorker()

        self.worker.setUseOnlyAlgorithm(self.useOnlyAlgorithm)
        self.worker.setPath(self.path)

        #Connecting signals
        self.worker.frameCount.connect(self.getLoadingLayout)
        self.worker.frameDone.connect(self.updateLoading)
        self.worker.finished.connect(self.thread.quit)

        #Sends the worker to the thread
        self.worker.moveToThread(self.thread)

        #Starts the worker if the thread is started
        self.thread.started.connect(self.worker.run)

        #Sets the thread garbage collection settings
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.onThreadFinished)

        #Start the thread and so, the worker
        self.thread.start()

        

    def getOptionsLayout(self):
        #Path Input
        self.pathInput = FileDropLineEdit()
        self.pathInput.setPlaceholderText("Video path...")
        self.pathInput.textChanged.connect(self.pathChanged)
        self.pathInput.setMinimumWidth(300)

        #Browse button
        browseButton = QPushButton("Browse")
        browseButton.clicked.connect(self.browseFile)

        #Use only algorithm Checkbox
        self.useOnlyAlgorithmCheckBox = QCheckBox("Use Only The Algorithm")
        self.useOnlyAlgorithmCheckBox.stateChanged.connect(self.changeBlackOut)

        #Start button
        startButton = QPushButton("Start")
        startButton.clicked.connect(self.start)
        
        #Make Layouts
        horizontalLayout1 = QHBoxLayout()
        horizontalLayout1.addWidget(self.pathInput)
        horizontalLayout1.addWidget(browseButton)

        horizontalLayout2 = QHBoxLayout()
        horizontalLayout2.addWidget(self.useOnlyAlgorithmCheckBox)
        horizontalLayout2.addWidget(startButton)

        optionsLayout = QVBoxLayout()
        optionsLayout.addLayout(horizontalLayout1)
        optionsLayout.addLayout(horizontalLayout2)
        return optionsLayout
    

    @pyqtSlot(int)
    def getLoadingLayout(self, frameCount):

        self.loadingBar = QProgressBar()

        self.loadingBar.setRange(0, frameCount)
        self.loadingBar.setValue(0)
        self.frameDone = 0

        self.loadingLayout = QVBoxLayout()
        self.loadingLayout.addWidget(self.loadingBar)

        self.mainLayout.addLayout(self.loadingLayout)


    @pyqtSlot()
    def updateLoading(self):
        self.frameDone += 1
        self.loadingBar.setValue(self.frameDone)


    def pathChanged(self, str):
        self.path = str


    def checkPath(self):
        if not self.path == "":
            return True
        else:
            return False
        
    
    def changeBlackOut(self):
        if self.useOnlyAlgorithmCheckBox.isChecked():
            self.useOnlyAlgorithm = True
        else:
            self.useOnlyAlgorithm = False
 

    def browseFile(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "Video Files (*.MOV *.mp4);;All Files (*)"
        )
        if path:
            self.pathInput.setText(path)


    def onThreadFinished(self):
        self.worker = None
        self.thread = None
        self.close()


