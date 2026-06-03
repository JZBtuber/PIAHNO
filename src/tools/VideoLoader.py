from src.gui.Core import *
from PyQt6.QtWidgets import QProgressBar, QPushButton, QCheckBox, QDialog, QHBoxLayout, QVBoxLayout, QFileDialog
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from src.tools.mediapipe.algorithms import mediaWork
import os
import cv2


class VideoWorker(QObject):
    """
    Worker used to apply the Mediapipe algorithm to a full video file.
    """
    frameCount = pyqtSignal(int)
    frameDone = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self):
        """
        Create the video loader worker.
        """
        super().__init__()

        #Set default variables
        self.path: str                  #Path to the video to write the algorithm on
        self.useOnlyAlgorithm = False   #Use only the algorithm with a black background
        self.running = False
        self.frameNumber = 0

    def run(self):
        """
        Run the video processing loop.
        """
        #Open the selected video file
        capture = cv2.VideoCapture(self.path)

        #Guard clause if the video cannot be opened
        if not capture.isOpened():
            MessageBox("Error!", "Failed to open video file")
            self.finished.emit()
            return

        #Create the video writer settings
        fourcc =cv2.VideoWriter_fourcc(*'mp4v')
        
        #Get video information
        self.frameNumber = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = capture.get(cv2.CAP_PROP_FPS)   

        #Send the total frame count to the dialog
        self.frameCount.emit(self.frameNumber)
        self.frameCountDone = 0

        #Create the output video path
        newPath = os.path.join(os.path.dirname(self.path), f"{os.path.splitext(os.path.basename(self.path))[0]}_{'ONLYHAND' if self.useOnlyAlgorithm else 'HAND'}.mp4")

        #Create the output video writer
        output = cv2.VideoWriter(newPath, fourcc, fps, (width, height))
        
        #Create the Mediapipe algorithm object
        algorithm = mediaWork()

        #Process every video frame
        while self.frameCountDone < self.frameNumber and capture.isOpened():

            ret, frame = capture.read()

            #Stop if the frame could not be read
            if not ret:
                break
            
            #Apply the hand algorithm
            frame = algorithm.draw2dHands(frame, fps, self.useOnlyAlgorithm)

            #Write the processed frame
            output.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

            #Update progress
            self.frameCountDone += 1
            self.frameDone.emit()

        #Release video resources
        capture.release()
        output.release()
        
        #Show error if not every frame was processed
        if not self.frameCountDone == self.frameNumber:
            MessageBox("Error!", "The video loading didn't go correctly!")

        #Signal that the worker is finished
        self.finished.emit()


    def setUseOnlyAlgorithm(self, bool: bool):
        """
        Set whether only the algorithm output should be used.\n
        :param `bool` bool: New only-algorithm state.
        """
        self.useOnlyAlgorithm = bool


    def setPath(self, path: str):
        """
        Set the video path to process.\n
        :param `str` path: Path to the video file.
        """
        self.path = path


class VideoLoader(QDialog):
    """
    Dialog used to process a video with the Mediapipe algorithm.
    """
    def __init__(self):
        """
        Create the video loader dialog.
        """
        super().__init__()

        #Set default variables
        self.path: str = ""
        self.outputPath: str = ""
        self.useOnlyAlgorithm = False
        self.thread = None
        self.worker = None

        #Create and set the main layout
        self.optionsLayout = self.getOptionsLayout()
        self.mainLayout = QVBoxLayout()
        self.mainLayout.addLayout(self.optionsLayout)
        self.setLayout(self.mainLayout)


    def start(self):
        """
        Start the video processing thread.
        """
        #Guard clause if the worker is already running
        if self.worker is not None:
            return

        #Guard clause if the path is empty
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
        """
        Create the option layout.\n
        :returns: Returns the layout containing the path input and options.
        """
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
        """
        Create the loading bar layout.\n
        :param frameCount: Total number of frames to process.
        """
        #Create the progress bar
        self.loadingBar = QProgressBar()

        #Set loading bar defaults
        self.loadingBar.setRange(0, frameCount)
        self.loadingBar.setValue(0)
        self.frameDone = 0

        #Create and add the loading layout
        self.loadingLayout = QVBoxLayout()
        self.loadingLayout.addWidget(self.loadingBar)

        self.mainLayout.addLayout(self.loadingLayout)


    @pyqtSlot()
    def updateLoading(self):
        """
        Update the loading bar by one frame.
        """
        #Update progress
        self.frameDone += 1
        self.loadingBar.setValue(self.frameDone)


    def pathChanged(self, str):
        """
        Update the selected video path.\n
        :param str: New video path.
        """
        self.path = str


    def checkPath(self):
        """
        Check if a video path was selected.\n
        :returns: Returns `True` if the path is not empty, otherwise returns `False`.
        """
        #Check if the path is not empty
        if not self.path == "":
            return True
        else:
            return False
        
    
    def changeBlackOut(self):
        """
        Update the only-algorithm option from the checkbox.
        """
        #Set only-algorithm mode from the checkbox state
        if self.useOnlyAlgorithmCheckBox.isChecked():
            self.useOnlyAlgorithm = True
        else:
            self.useOnlyAlgorithm = False
 

    def browseFile(self):
        """
        Open a file dialog and set the selected video path.
        """
        #User chooses the video file
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "Video Files (*.MOV *.mp4);;All Files (*)"
        )

        #Set the path if a file was chosen
        if path:
            self.pathInput.setText(path)


    def onThreadFinished(self):
        """
        Clear worker and thread references when processing is finished.
        """
        #Reset thread variables and close the dialog
        self.worker = None
        self.thread = None
        self.close()