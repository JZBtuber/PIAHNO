from PyQt6.QtCore import QObject, QThread, pyqtSlot, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, 
                             QPushButton, QFileDialog,
                             QHBoxLayout, QProgressBar,
                             QComboBox
                             )
from src.tools.mediapipe.algorithms import mediaWork

import numpy as np
import scipy.io
import cv2
import os

from src.gui.Core import FileDropLineEdit, MessageBox


class HandTrack:
    """
    Data object used to store one tracked hand position.
    """
    def __init__(self, trackID, position, frame_index):
        """
        Create the hand track object.\n
        :param trackID: ID of the tracked hand.
        :param position: Last known position of the hand.
        :param frame_index: Frame index where the hand was last seen.
        """
        #Set tracking data
        self.id = trackID
        self.position = position
        self.lastSeenFrame = frame_index
        self.missedFrames = 0


class KeyFrameWorker(QObject):
    """
    Worker used to export hand key frames from a video file.
    """
    frameCount = pyqtSignal(int)
    frameDone = pyqtSignal()
    finished = pyqtSignal()
    

    def __init__(self):
        """
        Create the key frame export worker.
        """
        super().__init__()

        #Set default paths and options
        self.pathToVideo = ""
        self.pathToPoint = ""
        self.fileFormat = ""
        self.algorithm = mediaWork()
        self.pcl = None
        self.cameraParameters = None
        self.pathToCameraParameters = ""

    
    def run(self):
        """
        Run the key frame export loop.
        """

        #Open the video file
        capture = cv2.VideoCapture(self.pathToVideo)

        #Guard clause if the video cannot be opened
        if not capture.isOpened():
            MessageBox("Error!", "Failed to open video file")
            self.finished.emit()
            return
        
        #Get video information
        frameNumber = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = capture.get(cv2.CAP_PROP_FPS)
        
        #Send the frame count to the dialog
        self.frameCount.emit(frameNumber)
        

        #Load camera parameters if a path was selected
        if self.pathToCameraParameters != "":
            self.cameraParameters = self.loadCameraParameters(self.pathToCameraParameters)
        

        #Set default export variables
        framesDone = 0

        newPath = os.path.join(os.path.dirname(self.pathToVideo), f"{os.path.splitext(os.path.basename(self.pathToVideo))[0]}_KeyFrames")

        allRows = {}

        self.pointFrames = None

        #Load point cloud data if it was selected
        if self.pathToPoint != "" and os.path.exists(self.pathToPoint):
            loaded = np.load(self.pathToPoint, allow_pickle=False)
            pointData = loaded[loaded.files[0]]
        else:
            pointData = None

        #Process every frame
        while framesDone < frameNumber and capture.isOpened():

            ret, frame = capture.read()

            #Stop if the frame could not be read
            if not ret:
                break

            #Calculate the current timestamp
            timestamp_ms = int(framesDone * 1000 / fps)

            #Get the current point cloud frame if available
            if pointData:
                currentPcl = pointData[framesDone] if framesDone < len(pointData) else None
            else:
                currentPcl = None

            #Get 3D points from the algorithm
            data = self.algorithm.get3dpoints(frame, fps, currentPcl if currentPcl is not None else None, self.cameraParameters if self.cameraParameters is not None else None)

            leftHand, rightHand = data

            #Group hands by name
            hands = {
                "left": leftHand,
                "right": rightHand
            }

            #Add all valid hand points to the output rows
            for handName, handData in hands.items():
                if len(handData) != 21:
                    continue

                if handName not in allRows:
                    allRows[handName] = []

                for landmarkId, point in enumerate(handData):
                    
                    if len(point) >= 5:
                        x3d = point[2] if point[2] is not None else np.nan
                        y3d = point[3] if point[3] is not None else np.nan
                        z3d = point[4] if point[4] is not None else np.nan

                        allRows[handName].append([
                            framesDone,
                            timestamp_ms,
                            landmarkId,
                            x3d,
                            y3d,
                            z3d
                                    ])

            #Update progress
            framesDone += 1
            self.frameDone.emit()

        #Release the video file
        capture.release()

        #Save each hand track to the selected file format
        for trackId, rows in allRows.items():
            array = np.array(rows, dtype=np.float32)

            if self.fileFormat == ".npy":
                np.save(f"{newPath}_{trackId}.npy", array)
            elif self.fileFormat == ".csv":
                np.savetxt(f"{newPath}_{trackId}.csv", array, delimiter=',')
            elif self.fileFormat == ".mat":
                arraymat = {"array": array}
                scipy.io.savemat(f"{newPath}_{trackId}.mat", arraymat)

        #Signal that the worker is finished
        self.finished.emit()


    def setPathToVideo(self, str):
        """
        Set the video path.\n
        :param str: Path to the video file.
        """
        self.pathToVideo = str


    def setFileFormat(self, str):
        """
        Set the export file format.\n
        :param str: File format to use.
        """
        self.fileFormat = str


    def setPathToPoints(self, str):
        """
        Set the point cloud path.\n
        :param str: Path to the point cloud file.
        """
        self.pathToPoint = str


    def setPathToCameraParameters(self, str):
        """
        Set the camera parameters path.\n
        :param str: Path to the camera parameters file.
        """
        self.pathToCameraParameters = str


    def loadCameraParameters(self, path):
        """
        Load camera parameters from a JSON file.\n
        :param path: Path to the camera parameters file.
        :returns: Returns the loaded camera parameters or `None`.
        """
        import json

        #Guard clause if the path is empty or invalid
        if path == "" or not os.path.exists(path):
            return None

        #Load and return the camera parameters
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)


class KeyFrameExporter(QDialog):
    """
    Dialog used to export key frame hand points from a video file.
    """
    def __init__(self):
        """
        Create the key frame exporter dialog.
        """
        super().__init__()

        #Set default paths
        self.pathToVideo = ""
        self.pathToPoint = ""
        self.pathToCameraParameters = ""

        #Set default thread variables
        self.thread = None
        self.worker = None
        self.frameNumber = 0

        #Create and set the main layout
        self.mainLayout = self.makeBasicLayout()

        self.setLayout(self.mainLayout)


    def makeBasicLayout(self):
        """
        Create the main exporter layout.\n
        :returns: Returns the main layout.
        """
        #Create the main layout
        mainLayout = QVBoxLayout()

        #Create input layouts
        inputLayout1 = QHBoxLayout()
        inputLayout2 = QHBoxLayout()
        inputLayout3 = QHBoxLayout()

        #Create video path input
        self.videoPathInput = FileDropLineEdit()
        self.videoPathInput.textChanged.connect(self.setPathToVideo)
        self.videoPathInput.setMinimumWidth(400)
        self.videoPathInput.setPlaceholderText("Video path...")

        videoBrowseButton = QPushButton("Browse")
        videoBrowseButton.clicked.connect(self.browseVideoFile)

        #Create point cloud path input
        self.pointPathInput = FileDropLineEdit()
        self.pointPathInput.textChanged.connect(self.setPathToPoints)
        self.pointPathInput.setMinimumWidth(400)
        self.pointPathInput.setPlaceholderText("Point path...")

        pointBrowseButton = QPushButton("Browse")
        pointBrowseButton.clicked.connect(self.browsePointFile)

        #Create camera settings path input
        self.cameraPathInput = FileDropLineEdit()
        self.cameraPathInput.textChanged.connect(self.setPathToCamera)
        self.cameraPathInput.setMinimumWidth(400)
        self.cameraPathInput.setPlaceholderText("Camera settings path...")

        cameraBrowseButton = QPushButton("Browse")
        cameraBrowseButton.clicked.connect(self.browseCameraFile)

        #Add video input widgets
        inputLayout1.addWidget(self.videoPathInput)
        inputLayout1.addWidget(videoBrowseButton)

        #Add point cloud input widgets
        inputLayout2.addWidget(self.pointPathInput)
        inputLayout2.addWidget(pointBrowseButton)

        #Add camera parameter input widgets
        inputLayout3.addWidget(self.cameraPathInput)
        inputLayout3.addWidget(cameraBrowseButton)

        #Add input layouts to the main layout
        mainLayout.addLayout(inputLayout1)
        mainLayout.addLayout(inputLayout2)
        mainLayout.addLayout(inputLayout3)

        #Create start button
        startButton = QPushButton("Start")
        startButton.clicked.connect(self.start)

        #Create file type combo box
        self.fileTypeComboBox = QComboBox()
        self.fileTypeComboBox.addItems([".npy", ".csv", ".mat"])

        #Add controls to the main layout
        mainLayout.addWidget(self.fileTypeComboBox)
        mainLayout.addWidget(startButton)

        return mainLayout


    def start(self):
        """
        Start the key frame export thread.
        """
        #Guard clause if the worker is already running
        if self.worker is not None:
            return

        #Create the worker and thread
        self.thread = QThread()
        self.worker = KeyFrameWorker()

        #Send selected paths to the worker
        self.worker.setPathToVideo(self.pathToVideo)
        self.worker.setPathToPoints(self.pathToPoint)
        self.worker.setPathToCameraParameters(self.pathToCameraParameters)

        #Set the selected file format
        self.worker.setFileFormat(self.fileTypeComboBox.currentText() if self.fileTypeComboBox.currentText() != "" else ".npy")

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

    def browseVideoFile(self):
        """
        Open a file dialog and set the selected video path.
        """
        #User chooses the video file
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select video file",
            "",
            "video Files (*.MOV *.mp4);;All Files (*)"
        )

        #Set the path if a file was chosen
        if path:
            self.videoPathInput.setText(path)


    def browsePointFile(self):
        """
        Open a file dialog and set the selected point cloud path.
        """
        #User chooses the point cloud file
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select point file",
            "",
            "Point Files (*.npz);;All Files (*)"
        )

        #Set the path if a file was chosen
        if path:
            self.pointPathInput.setText(path)


    def browseCameraFile(self):
        """
        Open a file dialog and set the selected camera parameter path.
        """
        #User chooses the camera parameter file
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a camera file",
            "",
            "Camera Files (*.json);;All Files (*)"
        )

        #Set the path if a file was chosen
        if path:
            self.cameraPathInput.setText(path)

        
    def setPathToVideo(self, str):
        """
        Set the selected video path.\n
        :param str: New video path.
        """
        self.pathToVideo = str

    def setPathToPoints(self, str):
        """
        Set the selected point cloud path.\n
        :param str: New point cloud path.
        """
        self.pathToPoint = str

    def setPathToCamera(self, str):
        """
        Set the selected camera parameters path.\n
        :param str: New camera parameters path.
        """
        self.pathToCameraParameters = str


    @pyqtSlot(int)
    def getLoadingLayout(self, frameCount):
        """
        Create the loading bar layout.\n
        :param frameCount: Total number of frames to export.
        """

        #Create the loading bar
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

    
    def onThreadFinished(self):
        """
        Clear worker and thread references when export is finished.
        """
        #Reset thread variables and close the dialog
        self.worker = None
        self.thread = None
        self.close()