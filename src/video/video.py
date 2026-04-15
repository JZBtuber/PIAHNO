import cv2
from PyQt6.QtCore import QObject, pyqtSignal, QThread, pyqtSlot, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout, QCheckBox, QSizePolicy, QHBoxLayout, QLineEdit, QPushButton, QSpinBox
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np


class VideoWorker(QObject):
    frameReady = pyqtSignal(QImage)

    def __init__(self, path, isCamera = True, cameraNumber = 0):
        super().__init__()
        self.path = path
        self.isCamera = isCamera
        self.cameraNumber = cameraNumber
        self.useAlgorithm = False


        base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
        options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=4)
        self.detector = vision.HandLandmarker.create_from_options(options)

        self.running = False
        self.paused = False


    def run(self):
        capture = cv2.VideoCapture(self.cameraNumber if self.isCamera else self.path)

        self.running = True

        while self.running and capture.isOpened():

            if self.paused:
                QThread.msleep(50)
                continue

            ret, frame = capture.read()
            if not ret:
                break

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            if not self.useAlgorithm:
                h, w, ch = rgb_frame.shape

                qimg = QImage(
                    rgb_frame.data,
                    w,
                    h,
                    ch * w,
                    QImage.Format.Format_RGB888
                    ).copy()

                self.frameReady.emit(qimg)
                continue

            mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_frame)

            result = self.detector.detect(mp_image)
            print("hands detected:", len(result.hand_landmarks))
            annotated = self.draw_landmarks_on_image(rgb_frame, result)

            h, w, ch = annotated.shape

            qimg = QImage(
                annotated.data,
                w,
                h,
                ch * w,
                QImage.Format.Format_RGB888).copy()

            self.frameReady.emit(qimg)

        capture.release()
    
    def stop(self):
        self.running = False

    def pause(self):
        if not self.isCamera:
            self.paused = True

    def resume(self):
        self.paused = False

    def setAlgorithm(self, value: bool):
        self.useAlgorithm = value

    def draw_landmarks_on_image(self, rgb_image, detection_result):

        mp_hands = mp.tasks.vision.HandLandmarksConnections
        mp_drawing = mp.tasks.vision.drawing_utils
        mp_drawing_styles = mp.tasks.vision.drawing_styles

        MARGIN = 10  # pixels
        FONT_SIZE = 1
        FONT_THICKNESS = 1
        HANDEDNESS_TEXT_COLOR = (88, 205, 54) # vibrant green



        hand_landmarks_list = detection_result.hand_landmarks
        handedness_list = detection_result.handedness
        annotated_image = np.copy(rgb_image)

        if not hand_landmarks_list:
            return annotated_image


            # Loop through the detected hands to visualize.
        for idx in range(len(hand_landmarks_list)):
            hand_landmarks = hand_landmarks_list[idx]
            handedness = handedness_list[idx]

            # Draw the hand landmarks.
            mp_drawing.draw_landmarks(
            annotated_image,
            hand_landmarks,
            mp_hands.HAND_CONNECTIONS,
            mp_drawing_styles.get_default_hand_landmarks_style(),
            mp_drawing_styles.get_default_hand_connections_style())

            # Get the top left corner of the detected hand's bounding box.
            height, width, _ = annotated_image.shape
            x_coordinates = [landmark.x for landmark in hand_landmarks]
            y_coordinates = [landmark.y for landmark in hand_landmarks]
            text_x = int(min(x_coordinates) * width)
            text_y = int(min(y_coordinates) * height) - MARGIN

            label = handedness[0].category_name if handedness else "?"

            # Draw handedness (left or right hand) on the image.
            cv2.putText(
                annotated_image,
                label,
                (text_x, text_y),
                cv2.FONT_HERSHEY_DUPLEX,
                FONT_SIZE,
                HANDEDNESS_TEXT_COLOR,
                FONT_THICKNESS,
                cv2.LINE_AA
            )

        return annotated_image
    

class VideoFeed(QWidget):
    def __init__(self, defaultPath = 0, cameraNumber = 0):
        super().__init__()

        self.defaultPath = defaultPath
        self.cameraNumber = cameraNumber
        self.UseCamera = True
        self.UseAlgorithm = False
        self.OnlyAlgorithm = False

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.video = QLabel()
        self.video.setMinimumSize(320, 240)
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.video)

        

        #Controls--------------------------------------

        controlsLayout = QHBoxLayout()

        self.startButton = QPushButton("Start")
        self.pauseButton = QPushButton("Pause/Resume")
        self.stopButton = QPushButton("Stop")

        controlsLayout.addWidget(self.startButton)
        controlsLayout.addWidget(self.pauseButton)
        controlsLayout.addWidget(self.stopButton)

        layout.addLayout(controlsLayout)


        self.cameraControl = QHBoxLayout()
        self.cameraControl.setSpacing(5)

        self.cameraNumberInput = QSpinBox()
        self.cameraNumberInput.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.cameraNumberInput.valueChanged.connect(self.updateCameraNumber)

        self.cameraCheckBox = QCheckBox("Use Camera")
        self.cameraCheckBox.setChecked(True)
        self.cameraCheckBox.stateChanged.connect(self.ChangeUse)

        self.pathInput = QLineEdit()
        self.pathInput.setPlaceholderText("Video path...")

        self.cameraControl.addWidget(self.cameraCheckBox)
        self.cameraControl.addWidget(self.cameraNumberInput)
        self.cameraControl.addStretch()

        self.Hands = QCheckBox("Use Mediapipe Algorithm")
        self.OnlyHands = QCheckBox("Use ONLY the Mediapipe Algorithm")

        self.algorithm = QHBoxLayout()

        self.algorithm.addWidget(self.Hands)
        self.algorithm.addWidget(self.OnlyHands)
        self.algorithm.addStretch()

        layout.addLayout(self.cameraControl)
        layout.addLayout(self.algorithm)
        layout.addWidget(self.pathInput)


        self.Hands.stateChanged.connect(self.ChangeAlgorithm)
        self.Hands.stateChanged.connect(self.ChangeAlgorithm)
        self.OnlyHands.stateChanged.connect(self.ChangeONLYAlgorithm)

        self.startButton.clicked.connect(self.start)
        self.pauseButton.clicked.connect(self.pause)
        self.stopButton.clicked.connect(self.stop)

        self.thread = None
        self.worker = None

    def ChangeAlgorithm(self, s):
        if self.worker:
            self.worker.setAlgorithm(bool(s))
    
    def ChangeUse(self, s):
        self.UseCamera = bool(s)


    def ChangeONLYAlgorithm(self, s):
        self.OnlyAlgorithm = bool(s)
        if self.worker:
            self.worker.setAlgorithm(self.OnlyAlgorithm)

    def start(self):
        if self.thread is not None:
            self.stop()

        path = self.cameraNumber if self.UseCamera else self.pathInput.text()

        self.thread = QThread()
        self.worker = VideoWorker(path, self.UseCamera, self.cameraNumber)


        self.worker.setAlgorithm(self.Hands.isChecked())

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.frameReady.connect(self.setImage)

        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def pause(self):
        if self.worker:
            if not self.UseCamera:
                if self.worker.paused:
                    self.worker.resume()
                else:
                    self.worker.pause()



    def stop(self):
        if self.worker:
            self.worker.stop()
        
        if self.thread:
            self.thread.quit()
            self.thread.wait()

            self.worker = None
            self.thread = None

    @pyqtSlot(QImage)
    def setImage(self, image):
        pixmap = QPixmap.fromImage(image)
        scaled = pixmap.scaled(
        self.video.size(),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation
        )
        self.video.setPixmap(scaled)
        self.video.update()

    def updateCameraNumber(self, n):
        self.cameraNumber = n

    
    
    def qimage_to_numpy(self, image: QImage):
        image = image.convertToFormat(QImage.Format.Format_RGB888)

        width = image.width()
        height = image.height()

        ptr = image.bits()
        ptr.setsize(image.height() * image.bytesPerLine())

        arr = np.frombuffer(ptr, np.uint8).reshape((height, image.bytesPerLine() // 3, 3))

        # remove padding (important!)
        arr = arr[:, :width, :]

        return arr
    
    def numpy_to_qimage(self, arr):
        h, w, ch = arr.shape
        return QImage(arr.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
