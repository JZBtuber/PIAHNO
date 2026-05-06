import cv2
from PyQt6.QtCore import pyqtSignal, QThread, pyqtSlot, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (QLabel, QVBoxLayout,
                             QCheckBox, QSizePolicy, QHBoxLayout)
from src.tools.mediapipe.algorithms import mediaWork
from src.video.Zed import Zed
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
        self.algorithm         = mediaWork()
        self.useDepthCamera    = False
        self.Zed               = None

        


    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------
    def beforeLoop(self):
        if self.isLive:
            if self.useDepthCamera:
                path = None
            else:
                path = int(self.path) if str(self.path).strip() != "" else 0
        else:
            path = self.path

        if not self.useDepthCamera:
            self.capture = cv2.VideoCapture(path)

            src_fps = self.capture.get(cv2.CAP_PROP_FPS)
            self.src_fps   = src_fps if src_fps > 0 else 60.0
            self.target_dt = 1.0 / self.src_fps

            self.prevTime    = time.perf_counter()
            self.smoothedFps = 0.0


            if not self.isLive:
                total_frames = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
                self.events = [
                    (int(i * 1000.0 / self.src_fps), i)
                    for i in range(total_frames)
                ]
                self.event_index = 0

        else:
                self.Zed = Zed(path, self.isLive)

                src_fps = self.Zed.getFps()
                self.src_fps   = src_fps if src_fps > 0 else 30
                self.target_dt = 1.0 / self.src_fps

                self.prevTime    = time.perf_counter()
                self.smoothedFps = 0.0

                if not self.isLive:
                    total_frames = int(self.Zed.getFrameCount())
                    self.events = [
                        (int(i * 1000.0 / self.src_fps), i)
                        for i in range(total_frames)
                    ]
                    self.event_index = 0

    def loop(self):
        if self.isLive:
            self._loop_live()
        else:
            self._loop_file()


    def afterLoop(self):
        if self.useDepthCamera:
            if self.Zed is not None:
                self.Zed.close()
        else:
            if hasattr(self, "capture") and self.capture is not None:
                self.capture.release()


    def _loop_live(self):
        loop_start = time.perf_counter()

        if self.useDepthCamera:
            ret, frame = self.Zed.read()
        else:
            ret, frame = self.capture.read()

        if not ret:
            self.running = False
            return

        self._emit_frame(frame)
        self._pace(loop_start)
        self._update_fps()


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
    def _emit_frame(self, frame):
        if frame is None:
            return

        # ZED returns BGRA, OpenCV returns BGR.
        if self.useDepthCamera:
            if frame.shape[2] == 4:
                bgr_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            else:
                bgr_frame = frame
        else:
            bgr_frame = frame

        if self.useAlgorithm:
            if not self.useDepthCamera:
                rgb = self.algorithm.draw2dHands(
                    bgr_frame,
                    self.src_fps,
                    self.useOnlyAlgorithm
                )
            else:
                rgb = self.algorithm.draw3dHands(
                    bgr_frame,
                    self.src_fps,
                    self.Zed.point_cloud,
                    self.Zed.camera_params,
                    self.useOnlyAlgorithm
                )
        else:
            rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        self.videoFrame = rgb

        h, w, ch = rgb.shape
        qimg = QImage(
            rgb.data,
            w,
            h,
            ch * w,
            QImage.Format.Format_RGB888
        ).copy()

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
        self.recordStarTime = time.perf_counter()
        self.recordedFrames = []

        # Only used for ZED / depth camera recording
        self.recordedPointClouds = []

        ts = str(datetime.now()).replace(" ", "_").replace(":", "-")[0:19]
        os.makedirs(os.path.join(os.getcwd(), f"Tests\\{ts}_Test"), exist_ok=True)

        self.newPath = os.path.join(
            os.getcwd(),
            f"Tests\\{ts}_Test\\Video_{self.ID}.mp4"
        )

        if self.useDepthCamera:
            self.newHandPointCloudPath = os.path.join(
                os.getcwd(),
                f"Tests\\{ts}_Test\\Video_{self.ID}_PointCloud.npz"
            ) 

            self.newCameraParametersPath = os.path.join(
                os.getcwd(),
                f"Tests\\{ts}_Test\\Video_{self.ID}_CameraParameters.json"
            )

    def recordloop(self):
        t = time.perf_counter() - self.recordStarTime

        self.recordedFrames.append((t, self.videoFrame.copy()))

        if self.useDepthCamera and self.Zed is not None:
            if self.Zed.point_cloud_img is not None:
                self.recordedPointClouds.append(
                    self.Zed.point_cloud_img[..., :3].astype(np.float16).copy()
                    )
                
                
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
            output.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

        output.release()

        if self.useDepthCamera and self.recordedPointClouds:

            self.Zed.saveCameraParameters(self.newCameraParametersPath)
            
            np.savez(
                self.newHandPointCloudPath,
                self.recordedPointClouds
            )

    # ------------------------------------------------------------------
    # Algorithm slots
    # ------------------------------------------------------------------
    @pyqtSlot(bool)
    def setAlgorithm(self, value: bool):
        self.useAlgorithm = value

    @pyqtSlot(bool)
    def setOnlyAlgorithm(self, value: bool):
        self.useOnlyAlgorithm = value

    @pyqtSlot(bool)
    def setUseDepthCamera(self, value: bool):
        self.useDepthCamera = value


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
        self.depthCamera = QCheckBox("Use Depth Camera ")
        self.FPSLabel  = QLabel("0")

        self.controlLayout = QVBoxLayout()
        hbox = QHBoxLayout()
        hbox.setSpacing(5)
        hbox.addWidget(self.Hands)
        hbox.addWidget(self.OnlyHands)
        hbox.addWidget(self.depthCamera)
        hbox.addStretch()
        self.controlLayout.addLayout(hbox)
        self.controlLayout.addWidget(self.FPSLabel)

        self.makeBasicWidget()

    def updateCameraNumber(self, n):
        self.cameraNumber = n

    def connectAll(self):
        self.worker.setAlgorithm(self.Hands.isChecked())
        self.worker.setOnlyAlgorithm(self.OnlyHands.isChecked())
        self.worker.setUseDepthCamera(self.depthCamera.isChecked())
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
