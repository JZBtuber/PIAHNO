from src.gui.Core import *
from PyQt6.QtWidgets import QProgressBar, QWidget, QPushButton, QCheckBox, QLabel, QDialog, QHBoxLayout, QVBoxLayout, QFileDialog
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
import os
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np

class VideoWorker(QObject):
    frameCount = pyqtSignal(int)
    frameDone = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.path: str                  #Path to the video to write the algorithm on
        self.useOnlyAlgorithm = False   #Use only the algorithm with a black background
        self.running = False

        self.setMediapipeSettings()

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

        while self.frameCountDone < self.frameNumber and capture.isOpened():

            ret, frame = capture.read()
            if not ret:
                break
            
            rgbFrame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgbFrame)
            result = self.detector.detect(mp_image)
            bgrFrame = cv2.cvtColor(self.draw_landmarks_on_image(rgbFrame, result), cv2.COLOR_RGB2BGR)
            output.write(bgrFrame)

            self.frameCountDone += 1
            self.frameDone.emit()

        capture.release()
        output.release()
        
        if not self.frameCountDone == self.frameNumber:
            message = MessageBox("Error!", "The video loading didn't go correctly!")

        self.finished.emit()


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

            
            

    def setUseOnlyAlgorithm(self, bool: bool):
        self.useOnlyAlgorithm = bool


    def setPath(self, path: str):
        self.path = path


    def setMediapipeSettings(self): #Setting the Mediapipe default settings
        base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
        options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=4)
        self.detector = vision.HandLandmarker.create_from_options(options)


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
        self.worker.finished.connect(self.close)

        #Sends the worker to the thread
        self.worker.moveToThread(self.thread)

        #Starts the worker if the thread is started
        self.thread.started.connect(self.worker.run)

        #Sets the thread garbage collection settings
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

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
        print("Made progress bar")
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
            "MOV Files (*.MOV);;All Files (*)"
        )
        if path:
            self.pathInput.setText(path)

