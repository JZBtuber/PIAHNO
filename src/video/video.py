import cv2
from PyQt6.QtCore import pyqtSignal, QThread, pyqtSlot, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (QLabel, QVBoxLayout, QCheckBox, QSizePolicy, QHBoxLayout)
from src.tools.mediapipe.algorithms import mediaWork
from src.tools.setting import GlobalSettings
from src.video.Zed import Zed
import numpy as np
import time
import os
from src.gui.Core import *



class VideoWorker(basicWorker):
    """
    Worker used to read video frames from file, live camera, or Zed depth camera.
    """
    frameReady = pyqtSignal(QImage)
    fpsReady = pyqtSignal(float)

    def __init__(self, path, isLive):
        """
        Create the video worker.\n
        :param path: Path to the video file or live device identifier.
        :param isLive: If `True`, the worker uses a live camera input.
        """
        super().__init__(path, isLive)

        # Set default variables
        self.cameraNumber = 0
        self.useAlgorithm = False
        self.useOnlyAlgorithm = False
        self.target_dt = 1.0 / 60.0
        self.algorithm = mediaWork()
        self.useDepthCamera = False
        self.Zed = None
        self.videoFrame = None
        self.lastFrame = np.empty([])
        self.hasDepthCamera = False
        self.frameNumber = 0
        self.lastRecordedFrame = -1

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------

    def beforeLoop(self):
        """
        Prepare the video source before the main worker loop starts.
        """
        # Get the input path and save the current depth mode
        path = self.path
        self._depthMode = self.useDepthCamera

        # Open a normal OpenCV capture if depth camera is not used
        if not self.useDepthCamera:
            self.capture = cv2.VideoCapture(
                path, (cv2.CAP_DSHOW if self.isLive else None))

            # Get the source FPS
            src_fps = self.capture.get(cv2.CAP_PROP_FPS)
            self.src_fps = src_fps if src_fps > 0 else 30.0
            self.fpsReady.emit(self.src_fps)

            # Set frame timing
            self.target_dt = 1.0 / self.src_fps

            self.prevTime = time.perf_counter()
            self.smoothedFps = 0.0

            # Create file frame events for synchronized playback
            if not self.isLive:
                total_frames = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
                self.events = [
                    (int(i * 1000.0 / self.src_fps), i)
                    for i in range(total_frames)
                ]
                self.event_index = 0

        # Open a Zed camera if depth camera is used
        else:
            try:
                self.Zed = Zed(path, self.isLive)
            except:
                self.finished.emit()
                return

            # Get the Zed source FPS
            src_fps = self.Zed.getFps()
            self.src_fps = src_fps if src_fps > 0 else 30
            self.target_dt = 1.0 / self.src_fps

            self.prevTime = time.perf_counter()
            self.smoothedFps = 0.0

            # Create file frame events for synchronized playback
            if not self.isLive:
                total_frames = int(self.Zed.getFrameCount())
                self.events = [
                    (int(i * 1000.0 / self.src_fps), i)
                    for i in range(total_frames)
                ]
                self.event_index = 0

    def loop(self):
        """
        Run one video loop step.
        """
        # Choose live or file playback
        if self.isLive:
            self._loop_live()
        else:
            self._loop_file()

    def afterLoop(self):
        """
        Release the video source after the worker loop stops.
        """
        # Close the depth camera if it was used
        if self.useDepthCamera:
            if self.Zed is not None:
                self.Zed.close()

        # Release the OpenCV capture if it was used
        else:
            if hasattr(self, "capture") and self.capture is not None:
                self.capture.release()

    def _loop_live(self):
        """
        Read and emit one frame from a live source.
        """
        # Save loop start time for pacing
        loop_start = time.perf_counter()

        # Read frame from Zed or OpenCV
        if self._depthMode:
            ret, frame = self.Zed.read()
        else:
            ret, frame = self.capture.read()

        # Stop the worker if the frame could not be read
        if not ret:
            self.running = False
            return

        # Emit frame and update timing
        self._emit_frame(frame)
        self._pace(loop_start)
        self._update_fps()

    def _loop_file(self):
        """
        Read and emit frames from a video file according to the master time.
        """
        # Stop if there are no frames left
        if self.event_index >= len(self.events):
            self.running = False
            return

        # Get current synchronized time
        nowMs = self.getMasterTimeMs()

        # Read every frame that should already be shown
        while self.event_index < len(self.events):
            frameTimeMs, frameIndex = self.events[self.event_index]

            if frameTimeMs > nowMs:
                break

            # Seek to the exact frame by timestamp
            self.capture.set(cv2.CAP_PROP_POS_MSEC, frameTimeMs)
            ret, frame = self.capture.read()

            # Stop if the frame could not be read
            if not ret:
                self.running = False
                return

            # Emit frame and move to the next event
            self._emit_frame(frame)
            self._update_fps()
            self.event_index += 1

        QThread.msleep(1)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _emit_frame(self, frame):
        """
        Convert, process and emit a frame to the GUI.\n
        :param frame: Frame to emit.
        """
        # Guard clause for invalid frames
        if frame is None:
            return

        # ZED returns BGRA, OpenCV returns BGR.
        if self._depthMode:
            if frame.shape[2] == 4:
                bgr_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            else:
                bgr_frame = frame
        else:
            bgr_frame = frame

        # Apply hand algorithm if enabled
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

        # Convert normal OpenCV frame to RGB
        else:
            rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)

        # Save the current frame for recording
        self.videoFrame = rgb
        self.frameNumber += 1

        # Create the Qt image
        h, w, ch = rgb.shape
        qimg = QImage(
            rgb.data,
            w,
            h,
            ch * w,
            QImage.Format.Format_RGB888
        ).copy()

        # Send the frame to the GUI
        self.frameReady.emit(qimg)

    def _pace(self, loop_start: float):
        """
        Busy-wait until at least one frame-period has elapsed (live only).\n
        :param `float` loop_start: Time when the current loop started.
        """
        # Calculate target time for the next frame
        target = loop_start + self.target_dt
        remaining = target - time.perf_counter()

        # Sleep most of the remaining time
        if remaining > 0.0005:                          # sleep off the bulk
            QThread.usleep(int((remaining - 0.0005) * 1_000_000))

        # Spin for the last fraction of time
        while time.perf_counter() < target:             # tiny spin: < 0.5ms, negligible GIL pressure
            pass

    def _update_fps(self):
        """
        Update and emit the smoothed FPS value.
        """
        # Calculate time between frames
        now = time.perf_counter()
        dt = now - self.prevTime
        self.prevTime = now

        # Calculate and emit smoothed FPS
        if dt > 0:
            inst = 1.0 / dt
            self.smoothedFps = (self.smoothedFps * 0.9 + inst * 0.1
                                if self.smoothedFps else inst)
            self.fpsReady.emit(self.smoothedFps)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def initRecording(self):
        """
        Initialize video recording data and output paths.
        """
        # Set recording defaults
        self.recordStarTime = time.perf_counter()
        self.recordedFrames = []
        self.lastRecordedFrame = -1

        # Only used for ZED / depth camera recording
        self.recordedPointClouds = []

        # Create the recording directory
        path = self.getRecordingPath()

        os.makedirs(path, exist_ok=True)

        # Create the video output path
        self.newPath = os.path.join(
            path,
            f"Video_{self.ID}.mp4"
        )

        # Create depth camera output paths
        if self.useDepthCamera:
            self.newHandPointCloudPath = os.path.join(
                path,
                f"Video_{self.ID}_PointCloud.npz"
            )

            self.newCameraParametersPath = os.path.join(
                path,
                f"Video_{self.ID}_CameraParameters.json"
            )

    def recordloop(self):
        """
        Save the current video frame and point cloud if recording.
        """
        if self.videoFrame is None:
            return

        # Do not record the same source frame twice
        if self.frameNumber == self.lastRecordedFrame:
            return

        t = time.perf_counter() - self.recordStarTime

        self.recordedFrames.append(
            (t, self.videoFrame.copy())
        )

        self.lastRecordedFrame = self.frameNumber

        if self.useDepthCamera and self.Zed is not None:
            if self.Zed.point_cloud_img is not None:
                self.recordedPointClouds.append(
                    self.Zed.point_cloud_img[..., :3]
                    .astype(np.float16)
                    .copy()
                )

    def stopRecording(self):
        """
        Save the recorded frames and point cloud data to files.
        """
        # Guard clause if no frames were recorded
        if not self.recordedFrames:
            return

        real_fps = self.src_fps

        # Create the video writer
        height, width = self.recordedFrames[0][1].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')

        output = cv2.VideoWriter(self.newPath, fourcc,
                                 real_fps, (width, height))

        # Write the recorded frames
        for _, frame in self.recordedFrames:
            output.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

        output.release()

        # Save depth camera data if available
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
        """
        Set whether the Mediapipe algorithm should be used.\n
        :param `bool` value: New algorithm state.
        """
        self.useAlgorithm = value

    @pyqtSlot(bool)
    def setOnlyAlgorithm(self, value: bool):
        """
        Set whether only the algorithm output should be shown.\n
        :param `bool` value: New only-algorithm state.
        """
        self.useOnlyAlgorithm = value

    @pyqtSlot(bool)
    def setUseDepthCamera(self, value: bool):
        """
        Set whether the Zed depth camera should be used.\n
        :param `bool` value: New depth camera state.
        """
        self.useDepthCamera = value


# ======================================================================

class VideoFeed(basicWindowWidget):
    """
    Video feed widget used to show and control video input.
    """

    def __init__(self, ID: int, workingDir: str = ""):
        """
        Create the video feed widget.\n
        :param `int` ID: ID of the widget.
        :param `str` workingDir: Working directory of the app, defaults to `""`.
        """
        super().__init__(VideoWorker, ID, workingDir=workingDir)

        # Set default variables
        self.useAlgorithm = False
        self.useOnlyAlgorithm = False
        self.cameraNumber = 0
        self.inputType = "video"

        # Create the video display widget
        self.mainWidget = QLabel()
        self.mainWidget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mainWidget.setSizePolicy(QSizePolicy.Policy.Expanding,
                                      QSizePolicy.Policy.Expanding)

        # Create algorithm and depth camera controls
        self.Hands = QCheckBox("Use Mediapipe Algorithm")
        self.OnlyHands = QCheckBox("Use ONLY the Algorithm")
        self.depthCamera = QCheckBox("Use Depth Camera ")
        self.depthCamera.setEnabled(False
                                    )

        # Create FPS label
        self.FPSLabel = QLabel("0")

        # Create custom control layout
        self.controlLayout = QVBoxLayout()
        hbox = QHBoxLayout()
        hbox.setSpacing(5)
        hbox.addWidget(self.Hands)
        hbox.addWidget(self.OnlyHands)
        hbox.addWidget(self.depthCamera)
        hbox.addStretch()
        self.controlLayout.addLayout(hbox)
        self.controlLayout.addWidget(self.FPSLabel)

        # Create the base widget layout
        self.makeBasicWidget()

    def updateCameraNumber(self, n):
        """
        Update the selected camera number.\n
        :param n: New camera number.
        """
        self.cameraNumber = n

    def connectAll(self):
        """
        Connect the video worker signals and settings.
        """
        # Send current settings to the worker
        self.worker.setAlgorithm(self.Hands.isChecked())
        self.worker.setOnlyAlgorithm(self.OnlyHands.isChecked())
        self.worker.setUseDepthCamera(self.depthCamera.isChecked())

        # Connect worker signals
        self.worker.frameReady.connect(self.setImage)
        self.worker.fpsReady.connect(self.updateFpsLabel)

    @pyqtSlot(QImage)
    def setImage(self, image):
        """
        Set the displayed image from a QImage.\n
        :param image: Image to display.
        """
        # Create pixmap from image
        pixmap = QPixmap.fromImage(image)

        # Scale the image to the display widget
        scaled = pixmap.scaled(self.mainWidget.size(),
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.FastTransformation)

        # Show the image
        self.mainWidget.setPixmap(scaled)
        self.mainWidget.update()

    @pyqtSlot(float)
    def updateFpsLabel(self, fps):
        """
        Update the FPS label.\n
        :param fps: FPS value to display.
        """
        self.FPSLabel.setText(f"FPS: {fps:.1f}")

    def checkPath(self, path):
        """
        Check if the selected path is valid.\n
        :param path: Path to check.
        :returns: Returns `True` for live mode, otherwise returns the parent path check.
        """
        return True if self.isLive else super().checkPath(path)

    def setIsLive(self, s):
        """
        Set whether the video feed uses live input.\n
        :param s: New live input state.
        """
        # Update the parent live state
        super().setIsLive(s)

        # Disable depth camera in file mode
        if not s and GlobalSettings["depthCameraAvailable"]:
            self.depthCamera.setChecked(False)

        # Enable depth camera only in live mode if available
        self.depthCamera.setEnabled(
            s and GlobalSettings["depthCameraAvailable"])
