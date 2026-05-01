import cv2
from PyQt6.QtCore import pyqtSignal, QThread, pyqtSlot, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (QLabel, QVBoxLayout,
                             QCheckBox, QSizePolicy, QHBoxLayout)
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
    frameReady = pyqtSignal(QImage)
    fpsReady   = pyqtSignal(float)

    def __init__(self, path, isLive):
        super().__init__(path, isLive)

        self.cameraNumber      = 0
        self.useAlgorithm      = False
        self.useOnlyAlgorithm  = False
        self.target_dt         = 1.0 / 60.0

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------
    def beforeLoop(self):
        path = self.path if not self.isLive else int(self.path)
        self.capture = cv2.VideoCapture(path)

        src_fps = self.capture.get(cv2.CAP_PROP_FPS)
        self.src_fps   = src_fps if src_fps > 0 else 60.0
        self.target_dt = 1.0 / self.src_fps

        self.prevTime    = time.perf_counter()
        self.smoothedFps = 0.0

        # Pre-build the frame timeline exactly like midi.py builds its
        # event list -- a list of (frameTimeMs, frameIndex) pairs.
        # The loop then just walks this list forward against the clock,
        # the same way the MIDI worker walks its event list.
        # This means we never seek during playback, so there is no drift.
        if not self.isLive:
            total_frames = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
            self.events = [
                (int(i * 1000.0 / self.src_fps), i)
                for i in range(total_frames)
            ]
            self.event_index = 0

        if self.useAlgorithm:
            self._setMediapipeSettings()

    def loop(self):
        if self.isLive:
            self._loop_live()
        else:
            self._loop_file()

    def afterLoop(self):
        self.capture.release()

    # ------------------------------------------------------------------
    # Live camera -- free-running, unchanged
    # ------------------------------------------------------------------
    def _loop_live(self):
        loop_start = time.perf_counter()

        ret, frame = self.capture.read()
        if not ret:
            self.running = False
            return

        self._emit_frame(frame)
        self._pace(loop_start)
        self._update_fps()

    # ------------------------------------------------------------------
    # File playback -- mirrors midi.py's loop_file exactly
    #
    # Walk the pre-built event list forward.  For every frame whose
    # timestamp is <= the master clock, read and display it.  Then
    # sleep 1 ms and return, just like the MIDI worker does.
    #
    # Because the capture was opened sequentially and we never seek,
    # read() always returns the next frame in order -- no pointer drift,
    # no keyframe snapping, no cumulative speedup.
    # ------------------------------------------------------------------
    def _loop_file(self):
        if self.event_index >= len(self.events):
            self.running = False
            return

        nowMs = self.getMasterTimeMs()

        while self.event_index < len(self.events):
            frameTimeMs, frameIndex = self.events[self.event_index]

            if frameTimeMs > nowMs:
                break

            ret, frame = self.capture.read()
            if not ret:
                self.running = False
                return

            self._emit_frame(frame)
            self._update_fps()
            self.event_index += 1

        QThread.msleep(1)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _emit_frame(self, bgr_frame):
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)

        if self.useAlgorithm:
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = self.detector.detect(mp_img)
            rgb    = self._draw_landmarks(rgb, result)

        self.videoFrame = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
        self.frameReady.emit(qimg)

    def _pace(self, loop_start: float):
        """Busy-wait until at least one frame-period has elapsed (live only)."""
        target = loop_start + self.target_dt
        while True:
            remaining = target - time.perf_counter()
            if remaining <= 0:
                break
            if remaining > 0.002:
                time.sleep(remaining - 0.001)

    def _update_fps(self):
        now = time.perf_counter()
        dt  = now - self.prevTime
        self.prevTime = now
        if dt > 0:
            inst = 1.0 / dt
            self.smoothedFps = (self.smoothedFps * 0.9 + inst * 0.1
                                if self.smoothedFps else inst)
            self.fpsReady.emit(self.smoothedFps)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------
    def initRecording(self):
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        width  = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self.recordStarTime = time.perf_counter()
        self.recordedFrames = []

        ts = str(datetime.now()).replace(" ", "_").replace(":", "-")[:16]
        os.makedirs(os.path.join(os.getcwd(), f"Tests\\{ts}_Test"), exist_ok=True)
        self.newPath = os.path.join(os.getcwd(), f"Tests\\{ts}_Test\\Video_{self.ID}.mp4")
       

    def recordloop(self):
        t = time.perf_counter() - self.recordStarTime
        self.recordedFrames.append((t, self.videoFrame.copy()))

    def stopRecording(self):
        if not self.recordedFrames:
            return

        duration = self.recordedFrames[-1][0] - self.recordedFrames[0][0]
        frame_count = len(self.recordedFrames)

        real_fps = frame_count / duration if duration > 0 else 30.0

        height, width = self.recordedFrames[0][1].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')

        output = cv2.VideoWriter(self.newPath, fourcc, real_fps, (width, height))

        for _, frame in self.recordedFrames:
            output.write(frame)

        output.release()

    # ------------------------------------------------------------------
    # Algorithm slots
    # ------------------------------------------------------------------
    @pyqtSlot(bool)
    def setAlgorithm(self, value: bool):
        self.useAlgorithm = value

    @pyqtSlot(bool)
    def setOnlyAlgorithm(self, value: bool):
        self.useOnlyAlgorithm = value

    def _setMediapipeSettings(self):
        model_path = Path(f"{__file__}/../..").resolve().with_name("hand_landmarker.task")
        base_options = python.BaseOptions(model_asset_path=str(model_path))
        options = vision.HandLandmarkerOptions(base_options=base_options,
                                               num_hands=4)
        self.detector = vision.HandLandmarker.create_from_options(options)

    def _draw_landmarks(self, rgb_image, detection_result):
        mp_hands          = mp.tasks.vision.HandLandmarksConnections
        mp_drawing        = mp.tasks.vision.drawing_utils
        mp_drawing_styles = mp.tasks.vision.drawing_styles
        hand_landmarks_list = detection_result.hand_landmarks
        handedness_list     = detection_result.handedness
        annotated = (np.copy(rgb_image) if not self.useOnlyAlgorithm
                     else np.zeros_like(rgb_image))

        MARGIN  = 10
        FONT_SZ = 1
        FONT_TH = 1
        COLOR   = (88, 205, 54)

        if not hand_landmarks_list:
            return annotated

        for idx in range(len(hand_landmarks_list)):
            hand_landmarks = hand_landmarks_list[idx]
            handedness     = handedness_list[idx]

            mp_drawing.draw_landmarks(
                annotated, hand_landmarks, mp_hands.HAND_CONNECTIONS,
                mp_drawing_styles.get_default_hand_landmarks_style(),
                mp_drawing_styles.get_default_hand_connections_style()
            )

            height, width, _ = annotated.shape
            xs    = [lm.x for lm in hand_landmarks]
            ys    = [lm.y for lm in hand_landmarks]
            tx    = int(min(xs) * width)
            ty    = int(min(ys) * height) - MARGIN
            label = handedness[0].category_name if handedness else "?"
            cv2.putText(annotated, label, (tx, ty),
                        cv2.FONT_HERSHEY_DUPLEX, FONT_SZ, COLOR, FONT_TH,
                        cv2.LINE_AA)

        return annotated


# ======================================================================
class VideoFeed(basicWindowWidget):
    def __init__(self, ID: int, workingDir: str = ""):
        super().__init__(VideoWorker, ID, workingDir=workingDir)

        self.useAlgorithm     = False
        self.useOnlyAlgorithm = False
        self.cameraNumber     = 0
        self.inputType        = "video"

        self.mainWidget = QLabel()
        self.mainWidget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mainWidget.setSizePolicy(QSizePolicy.Policy.Expanding,
                                      QSizePolicy.Policy.Expanding)

        self.Hands     = QCheckBox("Use Mediapipe Algorithm")
        self.OnlyHands = QCheckBox("Use ONLY the Algorithm")
        self.FPSLabel  = QLabel("0")

        self.controlLayout = QVBoxLayout()
        hbox = QHBoxLayout()
        hbox.setSpacing(5)
        hbox.addWidget(self.Hands)
        hbox.addWidget(self.OnlyHands)
        hbox.addStretch()
        self.controlLayout.addLayout(hbox)
        self.controlLayout.addWidget(self.FPSLabel)

        self.makeBasicWidget()

    def updateCameraNumber(self, n):
        self.cameraNumber = n

    def connectAll(self):
        self.worker.setAlgorithm(self.Hands.isChecked())
        self.worker.setOnlyAlgorithm(self.OnlyHands.isChecked())
        self.worker.frameReady.connect(self.setImage)
        self.worker.fpsReady.connect(self.updateFpsLabel)

    @pyqtSlot(QImage)
    def setImage(self, image):
        pixmap = QPixmap.fromImage(image)
        scaled = pixmap.scaled(self.mainWidget.size(),
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        self.mainWidget.setPixmap(scaled)
        self.mainWidget.update()

    @pyqtSlot(float)
    def updateFpsLabel(self, fps):
        self.FPSLabel.setText(f"FPS: {fps:.1f}")

    def checkPath(self, path):
        return True if self.isLive else super().checkPath(path)
