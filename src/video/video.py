import cv2
from PyQt6.QtCore import QObject, pyqtSignal, QThread, pyqtSlot, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QWidget,QFileDialog, QVBoxLayout, QCheckBox, QSizePolicy, QHBoxLayout, QLineEdit, QPushButton, QSpinBox
from PyQt6.QtMultimedia import QMediaDevices
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np
import time
import os
from src.gui.Core import *
from datetime import datetime
from pathlib import Path


class VideoWorker(basicWorker):
    frameReady = pyqtSignal(QImage) #Signal to update a frame
    fpsReady = pyqtSignal(float)

    def __init__(self, path, isLive):
        super().__init__(path, isLive)

        self.cameraNumber = 0               #Default camera number for multile camera windows
        self.useAlgorithm = False           #Use the Mediapipe algorithm
        self.useOnlyAlgorithm = False       #Use the Mediapipe algorithm and blackout everything else
        self.target_dt = 1.0 / 60.0         #Target FPS


    def beforeLoop(self):
        path = self.path if not self.isLive else int(self.path)
        print("Path")
        self.capture = cv2.VideoCapture(path)
        self.target_dt = 1.0 / (self.capture.get(cv2.CAP_PROP_FPS) if not self.capture.get(cv2.CAP_PROP_FPS) == 0 else 60)
        self.prevTime = time.perf_counter()
        self.smoothedFps = 0.0
        if self.useAlgorithm:
            self.setMediapipeSettings()

    def loop(self):
        loop_start = time.perf_counter()

        ret, frame = self.capture.read()
        if not ret:
            self.running = False
            return

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if not self.useAlgorithm:
            output = rgb_frame
        else:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            result = self.detector.detect(mp_image)
            output = self.draw_landmarks_on_image(rgb_frame, result)
            self.videoFrame = cv2.cvtColor(output, cv2.COLOR_RGB2BGR)

        h, w, ch = output.shape
        qimg = QImage(output.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
        self.frameReady.emit(qimg)

        # pace to source fps
        target_time = loop_start + self.target_dt
        while True:
            remaining = target_time - time.perf_counter()
            if remaining <= 0:
                break
            if remaining > 0.002:
                time.sleep(remaining - 0.001)

        # actual delivered fps
        now = time.perf_counter()
        dt = now - self.prevTime
        self.prevTime = now

        if dt > 0:
            instant_fps = 1.0 / dt
            if self.smoothedFps == 0.0:
                self.smoothedFps = instant_fps
            else:
                self.smoothedFps = self.smoothedFps * 0.9 + instant_fps * 0.1

            self.fpsReady.emit(self.smoothedFps)


    def afterLoop(self):
        self.capture.release()


    def initRecording(self):
        fourcc =cv2.VideoWriter_fourcc(*'mp4v')
        width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = self.capture.get(cv2.CAP_PROP_FPS)


        time: str = str(datetime.now()).replace(" ", "_").replace(":", "-")[0:16]

        os.makedirs(os.path.join(os.getcwd(), f"Tests\\{time}_Test"), exist_ok=True)

        newPath = os.path.join(os.getcwd(), f"Tests\\{time}_Test\\Video_{self.ID}.mp4")

        self.output = cv2.VideoWriter(newPath, fourcc, fps, (width, height))


    def recordloop(self):
        self.output.write(self.videoFrame)


    def stopRecording(self):
        self.output.release()
        

    @pyqtSlot()
    def setAlgorithm(self, value: bool): #Set if we use the mediapipe algorithm
        self.useAlgorithm = value


    @pyqtSlot()
    def setOnlyAlgorithm(self, value: bool): #Set if we write the result on a black screen
        self.useOnlyAlgorithm = value


    def setMediapipeSettings(self): #Setting the Mediapipe default settings
        model_path = Path(__file__).resolve().with_name("hand_landmarker.task")

        base_options = python.BaseOptions(model_asset_path=str(model_path))
        options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=4)
        self.detector = vision.HandLandmarker.create_from_options(options)

    
    def draw_landmarks_on_image(self, rgb_image, detection_result): #This function was given by mediapipe themselves so i'm not 100% sufe of its inner workings.

        #Defining local variables for mediapipe to write the hands
        mp_hands = mp.tasks.vision.HandLandmarksConnections
        mp_drawing = mp.tasks.vision.drawing_utils
        mp_drawing_styles = mp.tasks.vision.drawing_styles
        hand_landmarks_list = detection_result.hand_landmarks
        handedness_list = detection_result.handedness
        annotated_image = np.copy(rgb_image) if not self.useOnlyAlgorithm else np.zeros_like(rgb_image)

        #Settings of the text
        MARGIN = 10  # pixels
        FONT_SIZE = 1
        FONT_THICKNESS = 1
        HANDEDNESS_TEXT_COLOR = (88, 205, 54) # vibrant green

        if not hand_landmarks_list:
            return annotated_image #Sends the image if no hands are detected

            # Loop through the detected hands to visualize.
        for idx in range(len(hand_landmarks_list)):
            hand_landmarks = hand_landmarks_list[idx]
            handedness = handedness_list[idx]

            # Draw the hand landmarks.      This big functions was created by mediapipe, no clue on its inner workings.
            mp_drawing.draw_landmarks(annotated_image, hand_landmarks, mp_hands.HAND_CONNECTIONS, mp_drawing_styles.get_default_hand_landmarks_style(), mp_drawing_styles.get_default_hand_connections_style())

            # Get the top left corner of the detected hand's bounding box.
            height, width, _ = annotated_image.shape
            x_coordinates = [landmark.x for landmark in hand_landmarks]
            y_coordinates = [landmark.y for landmark in hand_landmarks]
            text_x = int(min(x_coordinates) * width)
            text_y = int(min(y_coordinates) * height) - MARGIN
            label = handedness[0].category_name if handedness else "?"

            # Draw handedness (left or right hand) on the image.
            cv2.putText(annotated_image, label, (text_x, text_y), cv2.FONT_HERSHEY_DUPLEX, FONT_SIZE, HANDEDNESS_TEXT_COLOR, FONT_THICKNESS, cv2.LINE_AA)

        return annotated_image
    

class VideoFeed(basicWindowWidget):
    def __init__(self, ID: int):
        
        super().__init__(VideoWorker, ID)

        #Set the default values of variables
        self.useAlgorithm = False
        self.useOnlyAlgorithm = False
        self.cameraNumber = 0
        self.inputType = "video"


        #Main widget of the page
        self.mainWidget = QLabel()
        self.mainWidget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mainWidget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        #Algorithm settings
        #Activate the Mediapipe algorithm
        self.Hands = QCheckBox("Use Mediapipe Algorithm")

        #Activate the blackout of everything BUT the algorithm
        self.OnlyHands = QCheckBox("Use ONLY the Algorithm")

        #Fps counter
        self.FPSLabel = QLabel("0")
    
        #Camera layout
        self.controlLayout = QVBoxLayout()

        self.horizontalControlLayout = QHBoxLayout()
        self.horizontalControlLayout.setSpacing(5)
        self.horizontalControlLayout.addWidget(self.Hands)
        self.horizontalControlLayout.addWidget(self.OnlyHands)
        self.horizontalControlLayout.addStretch()

        self.controlLayout.addLayout(self.horizontalControlLayout)
        self.controlLayout.addWidget(self.FPSLabel)

        self.makeBasicWidget()


    def updateCameraNumber(self, n):    #Sets the ID of the camera to use (0 being default and the first camera)
        self.cameraNumber = n


    def connectAll(self):
        #Sets to use the algorithm if the checkbox is set
        self.worker.setAlgorithm(self.Hands.isChecked())
        self.worker.setOnlyAlgorithm(self.OnlyHands.isChecked())

        #Sets the image when the worker finished making one
        self.worker.frameReady.connect(self.setImage)
        self.worker.fpsReady.connect(self.updateFpsLabel)


    @pyqtSlot(QImage)
    def setImage(self, image):
        #Creates a pixmap from the worker's image
        pixmap = QPixmap.fromImage(image) 

        #Scales the image to the usable space and keeps the aspect ratio              
        scaled = pixmap.scaled(self.mainWidget.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        
        self.mainWidget.setPixmap(scaled)
        self.mainWidget.update()

    @pyqtSlot(float)
    def updateFpsLabel(self, fps):
        self.FPSLabel.setText(f"FPS: {fps:.1f}")

    def checkPath(self, path):
        return True if self.isLive else super().checkPath(path)
    