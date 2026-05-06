from PyQt6.QtCore import QObject, QThread, pyqtSlot, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, 
                             QPushButton, QFileDialog,
                             QHBoxLayout, QProgressBar,
                             QComboBox
                             )
from src.tools.mediapipe.algorithms import mediaWork

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

import numpy as np
import scipy.io
from pathlib import Path
import cv2
import os
import math

from src.gui.Core import FileDropLineEdit, MessageBox

class HandTrack:
    def __init__(self, trackID, position, frame_index):
        self.id = trackID
        self.position = position
        self.lastSeenFrame = frame_index
        self.missedFrames = 0


class KeyFrameWorker(QObject):
    frameCount = pyqtSignal(int)
    frameDone = pyqtSignal()
    finished = pyqtSignal()
    

    def __init__(self):
        super().__init__()

        self.pathToVideo = ""
        self.pathToPoint = ""
        self.fileFormat = ""
        self.algorithm = mediaWork()
        self.pcl = None
        self.cameraParameters = None
        self.pathToCameraParameters = ""

    
    def run(self):

        capture = cv2.VideoCapture(self.pathToVideo)

        if not capture.isOpened():
            MessageBox("Error!", "Failed to open video file")
            self.finished.emit()
            return
        
        frameNumber = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = capture.get(cv2.CAP_PROP_FPS)
        
        self.frameCount.emit(frameNumber)
        

        if self.pathToCameraParameters != "":
            self.cameraParameters = self.loadCameraParameters(self.pathToCameraParameters)
        

        framesDone = 0

        newPath = os.path.join(os.path.dirname(self.pathToVideo), f"{os.path.splitext(os.path.basename(self.pathToVideo))[0]}_KeyFrames")

        allRows = {}

        self.pointFrames = None

        if self.pathToPoint != "" and os.path.exists(self.pathToPoint):
            loaded = np.load(self.pathToPoint, allow_pickle=False)
            pointData = loaded[loaded.files[0]]


        while framesDone < frameNumber and capture.isOpened():

            ret, frame = capture.read()
            if not ret:
                break

            timestamp_ms = int(framesDone * 1000 / fps)

            currentPcl = pointData[framesDone] if framesDone < len(pointData) else None

            data = self.algorithm.get3dpoints(frame, 
                                              fps, 
                                              currentPcl if currentPcl is not None else None,
                                              self.cameraParameters if self.cameraParameters is not None else None)

            leftHand, rightHand = data

            hands = {
                "left": leftHand,
                "right": rightHand
            }

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

            framesDone += 1
            self.frameDone.emit()

        capture.release()

        for trackId, rows in allRows.items():
            array = np.array(rows, dtype=np.float32)

            if self.fileFormat == ".npy":
                np.save(f"{newPath}_{trackId}.npy", array)
            elif self.fileFormat == ".csv":
                np.savetxt(f"{newPath}_{trackId}.csv", array, delimiter=',')
            elif self.fileFormat == ".mat":
                arraymat = {"array": array}
                scipy.io.savemat(f"{newPath}_{trackId}.mat", arraymat)

        self.finished.emit()


    def setPathToVideo(self, str):
        self.pathToVideo = str


    def setFileFormat(self, str):
        self.fileFormat = str


    def setPathToPoints(self, str):
        self.pathToPoint = str


    def setPathToCameraParameters(self, str):
        self.pathToCameraParameters = str


    def loadCameraParameters(self, path):
        import json

        if path == "" or not os.path.exists(path):
            return None

        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

class KeyFrameExporter(QDialog):
    def __init__(self):
        super().__init__()

        self.pathToVideo = ""
        self.pathToPoint = ""
        self.pathToCameraParameters = ""

        self.thread = None
        self.worker = None
        self.frameNumber = 0

        self.mainLayout = self.makeBasicLayout()

        self.setLayout(self.mainLayout)


    def makeBasicLayout(self):
        mainLayout = QVBoxLayout()

        inputLayout1 = QHBoxLayout()
        inputLayout2 = QHBoxLayout()
        inputLayout3 = QHBoxLayout()

        self.videoPathInput = FileDropLineEdit()
        self.videoPathInput.textChanged.connect(self.setPathToVideo)
        self.videoPathInput.setMinimumWidth(400)
        self.videoPathInput.setPlaceholderText("Video path...")

        videoBrowseButton = QPushButton("Browse")
        videoBrowseButton.clicked.connect(self.browseVideoFile)

        self.pointPathInput = FileDropLineEdit()
        self.pointPathInput.textChanged.connect(self.setPathToPoints)
        self.pointPathInput.setMinimumWidth(400)
        self.pointPathInput.setPlaceholderText("Point path...")

        pointBrowseButton = QPushButton("Browse")
        pointBrowseButton.clicked.connect(self.browsePointFile)

        self.cameraPathInput = FileDropLineEdit()
        self.cameraPathInput.textChanged.connect(self.setPathToCamera)
        self.cameraPathInput.setMinimumWidth(400)
        self.cameraPathInput.setPlaceholderText("Camera settings path...")

        cameraBrowseButton = QPushButton("Browse")
        cameraBrowseButton.clicked.connect(self.browseCameraFile)

        inputLayout1.addWidget(self.videoPathInput)
        inputLayout1.addWidget(videoBrowseButton)

        inputLayout2.addWidget(self.pointPathInput)
        inputLayout2.addWidget(pointBrowseButton)

        inputLayout3.addWidget(self.cameraPathInput)
        inputLayout3.addWidget(cameraBrowseButton)

        mainLayout.addLayout(inputLayout1)
        mainLayout.addLayout(inputLayout2)
        mainLayout.addLayout(inputLayout3)

        startButton = QPushButton("Start")
        startButton.clicked.connect(self.start)

        self.fileTypeComboBox = QComboBox()
        self.fileTypeComboBox.addItems([".npy", ".csv", ".mat"])

        mainLayout.addWidget(self.fileTypeComboBox)
        mainLayout.addWidget(startButton)

        return mainLayout


    def start(self):
        if self.worker is not None:
            return

        self.thread = QThread()
        self.worker = KeyFrameWorker()

        self.worker.setPathToVideo(self.pathToVideo)
        self.worker.setPathToPoints(self.pathToPoint)
        self.worker.setPathToCameraParameters(self.pathToCameraParameters)

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
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select video file",
            "",
            "video Files (*.MOV *.mp4);;All Files (*)"
        )
        if path:
            self.videoPathInput.setText(path)


    def browsePointFile(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select point file",
            "",
            "Point Files (*.npz);;All Files (*)"
        )
        if path:
            self.pointPathInput.setText(path)


    def browseCameraFile(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a camera file",
            "",
            "Camera Files (*.json);;All Files (*)"
        )
        if path:
            self.cameraPathInput.setText(path)

        
    def setPathToVideo(self, str):
        self.pathToVideo = str

    def setPathToPoints(self, str):
        self.pathToPoint = str

    def setPathToCamera(self, str):
        self.pathToCameraParameters = str


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

    
    def onThreadFinished(self):
        self.worker = None
        self.thread = None
        self.close()

