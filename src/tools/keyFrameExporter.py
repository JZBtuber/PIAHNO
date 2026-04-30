from PyQt6.QtCore import QObject, QThread, pyqtSlot, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, 
                             QPushButton, QFileDialog,
                             QHBoxLayout, QProgressBar)

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

import numpy as np
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


class HandTracker:
    def __init__(self, maxDistance = 0.20, maxMissedFrames = 300):
        self.tracks = []
        self.nextId = 0
        self.maxDistance = maxDistance
        self.maxMissedFrames = maxMissedFrames


    def getDistance(self, x, y):
        return math.sqrt((x[0] - y[0]) ** 2 + (x[1] - y[1]) ** 2)


    def getHandCentre(self, landmarks):
        x = sum(p.x for p in landmarks) / len(landmarks)
        y = sum(p.y for p in landmarks) / len(landmarks)
        return (x, y)


    def update(self, detected_hands, frame_index):
        """
        detected_hands = result.hand_landmarks
        returns: list of (track_id, landmarks)
        """

        assignments = []
        usedTracks = set()
        usedDetections = set()

        detections = [{
                "index" : i,
                "landmarks" : landmarks,
                "position" : self.getHandCentre(landmarks)
            }
            for i, landmarks in enumerate(detected_hands)
        ]

        candidates = []

        for detection in detections:
            for trackIndex, track in enumerate(self.tracks):
                distance = self.getDistance(detection["position"], track.position)

                if distance <= self.maxDistance:
                    candidates.append((distance, detection["index"], trackIndex))

        candidates.sort(key=lambda x: x[0])

        for dist, detectionIndex, trackIndex in candidates:
            if detectionIndex in usedDetections:
                continue

            if trackIndex in usedTracks:
                continue

            detection = detections[detectionIndex]
            track = self.tracks[trackIndex]

            track.position = detection["position"]
            track.lastSeenFrame = frame_index
            track.missedFrames = 0

            assignments.append((track.id, detection["index"], detection["landmarks"]))

            usedDetections.add(detectionIndex)
            usedTracks.add(trackIndex)

        for detection in detections:
            if detection["index"] in usedDetections:
                continue

            new_track = HandTrack(
                self.nextId,
                detection["position"],
                frame_index
            )

            self.tracks.append(new_track)

            assignments.append((new_track.id, detection["index"], detection["landmarks"]))

            self.nextId += 1

        # Increase missed count for tracks not seen this frame
        for track_index, track in enumerate(self.tracks):
            if track_index not in usedTracks:
                track.missedFrames += 1

        # Remove tracks that have been missing too long
        self.tracks = [
            track for track in self.tracks
            if track.missedFrames <= self.maxMissedFrames
        ]

        return assignments



class KeyFrameWorker(QObject):
    frameCount = pyqtSignal(int)
    frameDone = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.pathToVideo = ""
        self.handTracker = HandTracker()


        self.setMediapipeSettings()

    
    def run(self):

        capture = cv2.VideoCapture(self.pathToVideo)

        if not capture.isOpened():
            MessageBox("Error!", "Failed to open video file")
            self.finished.emit()
            return
        
        frameNumber = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = capture.get(cv2.CAP_PROP_FPS)
        

        self.frameCount.emit(frameNumber)

        framesDone = 0

        newPath = os.path.join(os.path.dirname(self.pathToVideo), f"{os.path.splitext(os.path.basename(self.pathToVideo))[0]}_KeyFrames")

        allRows = {}

        while framesDone < frameNumber and capture.isOpened():

            ret, frame = capture.read()
            if not ret:
                break

            timestamp_ms = int(framesDone * 1000 / fps)

            rgbFrame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgbFrame)

            result = self.detector.detect_for_video(mp_image, timestamp_ms)

            if result.hand_landmarks and result.hand_world_landmarks:
                trackedHands = self.handTracker.update(
                    result.hand_landmarks,
                    framesDone
                )

                for trackId, handIndex, landmarks in trackedHands:
                    world = result.hand_world_landmarks[handIndex]
                    wrist = world[0]

                    if trackId not in allRows:
                        allRows[trackId] = []

                    for landmarkId, point in enumerate(world):
                        allRows[trackId].append([
                            framesDone,
                            timestamp_ms,
                            landmarkId,
                            point.x - wrist.x,
                            point.y - wrist.y,
                            point.z - wrist.z
                        ])

            framesDone += 1
            self.frameDone.emit()

        capture.release()

        for trackId, rows in allRows.items():
            array = np.array(rows, dtype=np.float32)

            np.save(f"{newPath}_{trackId}.npy", array)

        self.finished.emit()


    def setMediapipeSettings(self): #Setting the Mediapipe default settings
        model_path = Path(f"{__file__}/../..").resolve().with_name("hand_landmarker.task")

        base_options = python.BaseOptions(model_asset_path=str(model_path))
        options = vision.HandLandmarkerOptions(base_options=base_options, running_mode=vision.RunningMode.VIDEO, num_hands=4)
        self.detector = vision.HandLandmarker.create_from_options(options)

    
    def setPathToVideo(self, str):
        self.pathToVideo = str


class KeyFrameExporter(QDialog):
    def __init__(self):
        super().__init__()

        self.pathToVideo = ""

        self.thread = None
        self.worker = None
        self.frameNumber = 0

        self.mainLayout = self.makeBasicLayout()

        self.setLayout(self.mainLayout)


    def makeBasicLayout(self):
        mainLayout = QVBoxLayout()

        inputLayout = QHBoxLayout()

        self.videoPathInput = FileDropLineEdit()
        self.videoPathInput.textChanged.connect(self.setPathToVideo)
        self.videoPathInput.setMinimumWidth(400)

        browseButton = QPushButton("Browse")
        browseButton.clicked.connect(self.browseFile)

        inputLayout.addWidget(self.videoPathInput)
        inputLayout.addWidget(browseButton)

        mainLayout.addLayout(inputLayout)

        startButton = QPushButton("Start")
        startButton.clicked.connect(self.start)

        mainLayout.addWidget(startButton)

        return mainLayout


    def start(self):
        if self.worker is not None:
            return

        self.thread = QThread()
        self.worker = KeyFrameWorker()

        self.worker.setPathToVideo(self.pathToVideo)

        #Connecting signals
        self.worker.frameCount.connect(self.getLoadingLayout)
        self.worker.frameDone.connect(self.updateLoading)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.close)

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

    def browseFile(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "MOV Files (*.MOV);;Mp4 Files (*.mp4);;All Files (*)"
        )
        if path:
            self.videoPathInput.setText(path)

        
    def setPathToVideo(self, str):
        self.pathToVideo = str


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

