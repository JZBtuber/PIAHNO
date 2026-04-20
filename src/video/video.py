import cv2
from PyQt6.QtCore import QObject, pyqtSignal, QThread, pyqtSlot, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QWidget,QFileDialog, QVBoxLayout, QCheckBox, QSizePolicy, QHBoxLayout, QLineEdit, QPushButton, QSpinBox
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np
import time
from src.gui.Core import *


class VideoWorker(QObject):
    frameReady = pyqtSignal(QImage) #Signal to update a frame
    fpsReady = pyqtSignal(float)

    def __init__(self, path, isCamera = True, cameraNumber = 0):
        super().__init__()

        #Setting the worker's defalt settings
        self.path = path                    #Path to the video to load
        self.isCamera = isCamera            #Using a camera/loading a video
        self.cameraNumber = cameraNumber    #Default camera number for multile camera windows 
        self.useAlgorithm = False           #Use the Mediapipe algorithm
        self.useOnlyAlgorithm = False       #Use the Mediapipe algorithm and blackout everything else
        self.running = False                #Is running
        self.paused = False                 #Is paused
        self.target_dt = 1.0 / 60.0         #Target FPS

        self.setMediapipeSettings()


    def run(self):
        self.running = True

        capture = cv2.VideoCapture(self.cameraNumber if self.isCamera else self.path)

        if self.isCamera:
            source_fps = 60.0
        else:
            source_fps = capture.get(cv2.CAP_PROP_FPS)
            if source_fps <= 1 or source_fps > 240:
                source_fps = 60.0

        self.target_dt = 1.0 / source_fps
        print(f"Detected source FPS: {source_fps}")

        prev_time = time.perf_counter()
        smoothed_fps = 0.0

        while self.running and capture.isOpened():
            loop_start = time.perf_counter()

            if self.paused:
                time.sleep(0.05)
                prev_time = time.perf_counter()
                continue

            ret, frame = capture.read()
            if not ret:
                break

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            if not self.useAlgorithm:
                output = rgb_frame
            else:
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                result = self.detector.detect(mp_image)
                output = self.draw_landmarks_on_image(rgb_frame, result)

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
            dt = now - prev_time
            prev_time = now

            if dt > 0:
                instant_fps = 1.0 / dt
                if smoothed_fps == 0.0:
                    smoothed_fps = instant_fps
                else:
                    smoothed_fps = smoothed_fps * 0.9 + instant_fps * 0.1

                self.fpsReady.emit(smoothed_fps)

        capture.release()


    def setMediapipeSettings(self): #Setting the Mediapipe default settings
        base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
        options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=4)
        self.detector = vision.HandLandmarker.create_from_options(options)


    def stop(self): #Stop reading the frames
        self.running = False


    def pause(self): #Skips the loop until resumed
        if not self.isCamera:
            self.paused = True


    def resume(self): #Resumes the pause
        self.paused = False


    def setAlgorithm(self, value: bool): #Set if we use the mediapipe algorithm
        self.useAlgorithm = value

    def setOnlyAlgorithm(self, value: bool): #Set if we write the result on a black screen
        self.useOnlyAlgorithm = value

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
    

class VideoFeed(QWidget):
    def __init__(self, ID: int, defaultPath = 0, cameraNumber = 0):
        super().__init__()

        #Set the default values of variables
        self.ID = ID
        self.defaultPath = defaultPath
        self.cameraNumber = cameraNumber
        self.UseCamera = True
        self.UseAlgorithm = False
        self.OnlyAlgorithm = False #Not programmed yet, Should blackout everything but the handmarks

        #Creating the widgets
        #ID counter
        self.IDlabel = QLabel(f"{self.ID} Video   FPS: {0}")
        #Video feed
        self.video = QLabel()
        self.video.setMinimumSize(320, 240)
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        #Control buttons
        self.startButton = QPushButton("Start")
        self.pauseButton = QPushButton("Pause/Resume")
        self.stopButton = QPushButton("Stop")
        self.startButton.clicked.connect(self.start)
        self.pauseButton.clicked.connect(self.pause)
        self.stopButton.clicked.connect(self.stop)

        #Control layout
        controlsLayout = QHBoxLayout()
        controlsLayout.addWidget(self.startButton)
        controlsLayout.addWidget(self.pauseButton)
        controlsLayout.addWidget(self.stopButton)
        controlsLayout.addStretch()

        #Camera settings
        #Use the camera
        self.cameraCheckBox = QCheckBox("Use Camera")
        self.cameraCheckBox.setChecked(True)
        self.cameraCheckBox.stateChanged.connect(self.ChangeUse)

        #Camera ID number
        self.cameraNumberInput = QSpinBox()
        self.cameraNumberInput.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.cameraNumberInput.valueChanged.connect(self.updateCameraNumber)

        #Camera layout
        self.cameraControl = QHBoxLayout()
        self.cameraControl.setSpacing(5)
        self.cameraControl.addWidget(self.cameraCheckBox)
        self.cameraControl.addWidget(self.cameraNumberInput)
        self.cameraControl.addStretch()

        #Video path
        self.pathInput = FileDropLineEdit()
        self.pathInput.setPlaceholderText("Video path...")

        #Browse button
        self.browseButton = QPushButton("Browse")
        self.browseButton.clicked.connect(self.browseFile)

        #Path input layout
        self.pathLayout = QHBoxLayout()
        self.pathLayout.addWidget(self.pathInput, 1)
        self.pathLayout.addWidget(self.browseButton, 0)

        #Algorithm settings
        #Activate the Mediapipe algorithm
        self.Hands = QCheckBox("Use Mediapipe Algorithm")

        #Activate the blackout of everything BUT the algorithm
        self.OnlyHands = QCheckBox("Use ONLY the Algorithm")

        #Layout for the algorithms
        self.algorithm = QHBoxLayout()
        self.algorithm.addWidget(self.Hands)
        self.algorithm.addWidget(self.OnlyHands)
        self.algorithm.addStretch()

        #Main Layout of the widget
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.IDlabel)
        layout.addWidget(self.video, 1)
        layout.addLayout(controlsLayout, 0)
        layout.addLayout(self.cameraControl, 0)
        layout.addLayout(self.algorithm, 0)
        layout.addLayout(self.pathLayout, 0)
        layout.addStretch()

        #Defining the thread and worker
        self.thread = None
        self.worker = None


    def ChangeUse(self, s):
        self.UseCamera = bool(s)        #Sets if the worker uses the camera or the path


    def updateCameraNumber(self, n):    #Sets the ID of the camera to use (0 being default and the first camera)
        self.cameraNumber = n

    
    def start(self):
        #If the worker already exist, stops it.
        if self.thread is not None:
            return
        
        if not self.checkPath() and not self.UseCamera:
            Message = MessageBox("Path Error!", "The path is empty and needs a file!")
            return

        #Gives to the worker the camera ID or path to video depending on user choice
        path = self.cameraNumber if self.UseCamera else self.pathInput.text()

        #Create and initialize the thread and worker
        self.thread = QThread()
        self.worker = VideoWorker(path, self.UseCamera, self.cameraNumber)

        #Sets to use the algorithm if the checkbox is set
        self.worker.setAlgorithm(self.Hands.isChecked())
        self.worker.setOnlyAlgorithm(self.OnlyHands.isChecked())

        #Sends the worker to the thread
        self.worker.moveToThread(self.thread)

        #Starts the worker if the thread is started
        self.thread.started.connect(self.worker.run)
        

        #Sets the image when the worker finished making one
        self.worker.frameReady.connect(self.setImage)
        self.worker.fpsReady.connect(self.updateFpsLabel)
        #Sets the thread garbage collection settings
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        #Start the thread and so, the worker
        self.thread.start()


    def pause(self):
        if self.worker:
            if not self.UseCamera:
                if self.worker.paused:      #If the worker is paused, it resumes
                    self.worker.resume()
                else:                       #If the worker is not paused, it pauses
                    self.worker.pause()


    def stop(self):
        if self.worker:
            self.worker.stop()              #Stop the worker
        
        if self.thread:                     #Stop the thread
            self.thread.quit()
            self.thread.wait()

            self.worker = None              #Deletes them both
            self.thread = None

        self.IDlabel.setText(f"{self.ID} Video   FPS: {0}")


    @pyqtSlot(QImage)
    def setImage(self, image):
        #Creates a pixmap from the worker's image
        pixmap = QPixmap.fromImage(image) 

        #Scales the image to the usable space and keeps the aspect ratio              
        scaled = pixmap.scaled(self.video.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        
        self.video.setPixmap(scaled)
        self.video.update()
    
    
    def resizeEvent(self, event): #Event if the label is rescaled
        if self.video.pixmap():
            pixmap = self.video.pixmap()

            #Rescales the pixmap
            scaled = pixmap.scaled(self.video.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
            #Updates the label with the current image
            self.video.setPixmap(scaled)
            self.video.update()

        super().resizeEvent(event)


    def browseFile(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "MP4 Files (*.mp4);;MOV files (*.MOV);;All Files (*)"
        )
        if path:
            self.pathInput.setText(path)
            self.cameraCheckBox.setChecked(False)

    @pyqtSlot(float)
    def updateFpsLabel(self, fps):
        self.IDlabel.setText(f"{self.ID} Video   FPS: {fps:.1f}")


    def checkPath(self):
        if self.pathInput.text():
            return True
        else:
            return False
