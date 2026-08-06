import cv2
from PyQt6.QtCore import pyqtSignal, QThread, pyqtSlot, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QCheckBox,
    QSizePolicy,
    QHBoxLayout
)

from src.tools.mediapipe.algorithms import mediaWork
from src.tools.setting import GlobalSettings
from src.video.Zed import Zed
from src.video.RealSens import RealSens
from src.gui.Core import *

import numpy as np
import time
import os
import ctypes
import csv
import threading
import serial

from bisect import bisect_left
import queue


class VideoWorker(basicWorker):
    """
    Worker used to read video frames from a file, live camera,
    ZED camera, or RealSense camera.
    """

    frameReady = pyqtSignal(object)
    fpsReady = pyqtSignal(float)

    def __init__(self, path, isLive):
        """
        Create the video worker.

        :param path: Video path or live camera identifier.
        :param isLive: True when using a live camera.
        """
        super().__init__(path, isLive)

        # --------------------------------------------------------------
        # Video state
        # --------------------------------------------------------------

        self.cameraNumber = 0

        self.useAlgorithm = False
        self.useOnlyAlgorithm = False

        self.useDepthCamera = False
        self._depthMode = False

        self.depth = None
        self.capture = None

        self.src_fps = 30.0
        self.target_dt = 1.0 / self.src_fps

        self.algorithm = mediaWork()

        self.videoFrame = None
        self.lastFrame = np.empty([])

        self.frameNumber = 0
        self.lastRecordedFrame = -1

        self.prevTime = time.perf_counter()
        self.smoothedFps = 0.0

        self.events = []
        self.event_index = 0

        # --------------------------------------------------------------
        # Recording state
        # --------------------------------------------------------------

        self.filepath = ""
        self.recordStartTime = 0.0

        self.recordedFrames = []
        self.recordedFrameTimes = []
        self.recordedPointClouds = []

        # --------------------------------------------------------------
        # TTL state
        # --------------------------------------------------------------

        self.ttl = []

        # Thread-safe queue used to move serial events from the TTL
        # thread to the video worker thread.
        self.ttlQueue = queue.SimpleQueue()

        # Allows the TTL thread to be stopped cleanly.
        self.ttlStopEvent = threading.Event()

        self.ttlThread = None
        self.ttlSerial = None

    # ==================================================================
    # Worker lifecycle
    # ==================================================================

    def beforeLoop(self):
        """
        Prepare the video source before the main loop starts.
        """
        self._set_high_res_timer()

        path = self.path
        provider = GlobalSettings["depthCameraProvider"]

        # Only enable depth mode when both the checkbox and a valid
        # provider are configured.
        self._depthMode = bool(
            self.useDepthCamera and provider is not None
        )

        # --------------------------------------------------------------
        # Open regular OpenCV source
        # --------------------------------------------------------------

        if not self._depthMode:
            if self.isLive:
                self.capture = cv2.VideoCapture(
                    int(path),
                    cv2.CAP_DSHOW
                )
            else:
                self.capture = cv2.VideoCapture(path)

            if not self.capture.isOpened():
                self.running = False
                self.pathError.emit()
                return

            src_fps = self.capture.get(cv2.CAP_PROP_FPS)

            if src_fps is None or src_fps <= 0:
                src_fps = 30.0

            self.src_fps = float(src_fps)
            self.target_dt = 1.0 / self.src_fps

            self.fpsReady.emit(self.src_fps)

            # Build the event list used for synchronized file playback.
            if not self.isLive:
                total_frames = int(
                    self.capture.get(cv2.CAP_PROP_FRAME_COUNT)
                )

                self.events = [
                    (
                        int(frame_index * 1000.0 / self.src_fps),
                        frame_index
                    )
                    for frame_index in range(total_frames)
                ]

                self.event_index = 0

        # --------------------------------------------------------------
        # Open depth camera source
        # --------------------------------------------------------------

        else:
            try:
                if provider == "Zed":
                    self.depth = Zed(path, self.isLive)
                elif provider == "Realsens":
                    self.depth = RealSens(path, self.isLive)
                else:
                    raise ValueError(
                        f"Unsupported depth camera provider: {provider}"
                    )

            except Exception as exc:
                print(f"Failed to open depth camera: {exc}")
                self.running = False
                self.pathError.emit()
                return

            src_fps = self.depth.getFps()

            if src_fps is None or src_fps <= 0:
                src_fps = 30.0

            self.src_fps = float(src_fps)
            self.target_dt = 1.0 / self.src_fps

            self.fpsReady.emit(self.src_fps)

            print(
                f"src_fps={self.src_fps:.2f}, "
                f"target_dt={self.target_dt * 1000:.2f} ms"
            )

        self.prevTime = time.perf_counter()
        self.smoothedFps = 0.0

        # Start TTL reading only after the video source opened
        # successfully.
        if self.isLive and GlobalSettings["enableTTL"]:
            print("TTLStart")
            self._startTTLReader()

    def loop(self):
        """
        Run one video loop iteration.
        """
        if self.isLive:
            self._loop_live()
        else:
            self._loop_file()

    def afterLoop(self):
        """
        Stop background work and release the video source.
        """
        self._stopTTLReader()
        self._set_high_res_timer(release=True)

        if self._depthMode:
            if self.depth is not None:
                try:
                    self.depth.close()
                except Exception as exc:
                    print(f"Failed to close depth camera: {exc}")

                self.depth = None

        else:
            if self.capture is not None:
                self.capture.release()
                self.capture = None

    # ==================================================================
    # Video loops
    # ==================================================================

    def _loop_live(self):
        """
        Read and emit one frame from a live source.
        """
        loop_start = time.perf_counter()

        if self._depthMode:
            ret, frame = self.depth.read()
        else:
            ret, frame = self.capture.read()

        if not ret:
            self.running = False
            return

        self._emit_frame(frame)
        self._pace(loop_start)
        self._update_fps()

    def _loop_file(self):
        """
        Read video file frames according to the master clock.
        """
        if self.event_index >= len(self.events):
            self.running = False
            return

        now_ms = self.getMasterTimeMs()

        while self.event_index < len(self.events):
            frame_time_ms, frame_index = self.events[self.event_index]

            if frame_time_ms > now_ms:
                break

            self.capture.set(
                cv2.CAP_PROP_POS_MSEC,
                frame_time_ms
            )

            ret, frame = self.capture.read()

            if not ret:
                self.running = False
                return

            self._emit_frame(frame)
            self._update_fps()

            self.event_index += 1

        QThread.msleep(1)

    # ==================================================================
    # Shared video helpers
    # ==================================================================

    def _emit_frame(self, frame):
        """
        Convert, process, and emit one frame.

        :param frame: OpenCV image.
        """
        if frame is None:
            return

        if len(frame.shape) != 3:
            return

        # ZED may return BGRA while OpenCV normally returns BGR.
        if frame.shape[2] == 4:
            frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGRA2BGR
            )

        if self.useAlgorithm:
            frame = self.algorithm.draw2dHands(
                frame,
                self.src_fps,
                self.useOnlyAlgorithm
            )
        else:
            frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )

        self.videoFrame = frame
        self.frameNumber += 1

        self.frameReady.emit(frame)

    def _pace(self, loop_start: float):
        """
        Limit live playback to the source frame rate.
        """
        target = loop_start + self.target_dt
        remaining = target - time.perf_counter()

        # Use a normal sleep for the coarse part.
        if remaining > 0.003:
            QThread.usleep(
                int((remaining - 0.002) * 1_000_000)
            )

        # Busy-wait only for the final small interval.
        while time.perf_counter() < target:
            pass

    def _update_fps(self):
        """
        Emit the FPS measured between the last two displayed frames.
        """
        now = time.perf_counter()
        frame_time = now - self.prevTime
        self.prevTime = now

        if frame_time > 0:
            last_frame_fps = 1.0 / frame_time
            self.fpsReady.emit(last_frame_fps)

    # ==================================================================
    # Recording
    # ==================================================================

    def initRecording(self):
        """
        Initialize recording data and output paths.
        """
        self.recordStartTime = time.perf_counter()

        # Compatibility with code that may still use the old typo.
        self.recordStarTime = self.recordStartTime

        self.recordedFrames = []
        self.recordedFrameTimes = []
        self.recordedPointClouds = []

        self.lastRecordedFrame = -1
        self.ttl = []

        # Discard TTL events received before recording started.
        self._clearTTLQueue()

        self.filepath = self.getRecordingPath()
        os.makedirs(self.filepath, exist_ok=True)

        self.newPath = os.path.join(
            self.filepath,
            f"Video_{self.ID}.mp4"
        )

        if self._depthMode:
            self.newHandPointCloudPath = os.path.join(
                self.filepath,
                f"Video_{self.ID}_PointCloud.npz"
            )

            self.newCameraParametersPath = os.path.join(
                self.filepath,
                f"Video_{self.ID}_CameraParameters.json"
            )

    def recordloop(self):
        """
        Record the current frame and process pending TTL events.
        """
        if self.videoFrame is None:
            return

        # Prevent the same source frame from being recorded twice.
        if self.frameNumber == self.lastRecordedFrame:
            # TTL events may still have arrived since the last call.
            self._processTTLQueue()
            return

        frame_time = (
            time.perf_counter() - self.recordStartTime
        )

        self.recordedFrames.append(
            (
                frame_time,
                self.videoFrame.copy()
            )
        )

        self.recordedFrameTimes.append(frame_time)
        self.lastRecordedFrame = self.frameNumber

        if self._depthMode and self.depth is not None:
            point_cloud = getattr(
                self.depth,
                "point_cloud_img",
                None
            )

            if point_cloud is not None:
                self.recordedPointClouds.append(
                    point_cloud[..., :3]
                    .astype(np.float16)
                    .copy()
                )

        # Process serial events after adding the current frame. This
        # allows the TTL event to be matched against all frames
        # recorded up to this point.
        self._processTTLQueue()

    def stopRecording(self):
        """
        Save video, depth data, and TTL events.
        """
        # Capture any final serial events already waiting in the queue.
        self._processTTLQueue()

        if not self.recordedFrames:
            return

        real_fps = self.src_fps

        first_frame = self.recordedFrames[0][1]
        height, width = first_frame.shape[:2]

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        output = cv2.VideoWriter(
            self.newPath,
            fourcc,
            real_fps,
            (width, height)
        )

        if not output.isOpened():
            print(
                f"Failed to open video writer: {self.newPath}"
            )
            return

        for _, frame in self.recordedFrames:
            # Frames stored by this worker are RGB.
            bgr_frame = cv2.cvtColor(
                frame,
                cv2.COLOR_RGB2BGR
            )

            output.write(bgr_frame)

        output.release()

        # --------------------------------------------------------------
        # Save depth data
        # --------------------------------------------------------------

        if (
            self._depthMode
            and self.recordedPointClouds
            and self.depth is not None
        ):
            self.depth.saveCameraParameters(
                self.newCameraParametersPath
            )

            np.savez_compressed(
                self.newHandPointCloudPath,
                point_clouds=np.asarray(
                    self.recordedPointClouds
                )
            )

        # --------------------------------------------------------------
        # Save TTL data
        # --------------------------------------------------------------

        if self.ttl:
            ttl_path = os.path.join(
                self.filepath,
                "ttl.csv"
            )

            with open(
                ttl_path,
                "w",
                newline="",
                encoding="utf-8"
            ) as file:
                writer = csv.writer(file)

                writer.writerow([
                    "frame_index",
                    "ttl_time_seconds",
                    "frame_time_seconds",
                    "value"
                ])

                for event in self.ttl:
                    writer.writerow([
                        event["frame_index"],
                        f"{event['ttl_time']:.9f}",
                        f"{event['frame_time']:.9f}",
                        event["value"]
                    ])

    # ==================================================================
    # TTL handling
    # ==================================================================

    def _startTTLReader(self):
        """
        Start the non-blocking TTL serial reader thread.
        """
        if self.ttlThread is not None:
            if self.ttlThread.is_alive():
                return

        self.ttlStopEvent.clear()

        self.ttlThread = threading.Thread(
            target=self._checkTTL,
            name=f"TTLReader-{self.ID}",
            daemon=True
        )

        self.ttlThread.start()

    def _stopTTLReader(self):
        """
        Stop the TTL reader safely.

        The TTL thread exclusively owns and closes the serial port.
        """
        self.ttlStopEvent.set()

        ttl_thread = self.ttlThread

        if (
            ttl_thread is not None
            and ttl_thread.is_alive()
            and ttl_thread is not threading.current_thread()
        ):
            ttl_thread.join(timeout=1.0)

        if ttl_thread is not None and ttl_thread.is_alive():
            print("Warning: TTL reader thread did not stop cleanly")

        self.ttlThread = None

    def _checkTTL(self):
        """
        Read TTL serial messages in a background thread.

        This thread exclusively owns and closes the serial port.
        Received events are transferred through ttlQueue.
        """
        serial_port = None
        port = GlobalSettings["port"]

        try:
            serial_port = serial.Serial(
                port=port,
                baudrate=9600,
                timeout=0.1
            )

            self.ttlSerial = serial_port

            try:
                serial_port.reset_input_buffer()
            except serial.SerialException:
                pass

            print(f"TTL serial port opened: {port}")

            while not self.ttlStopEvent.is_set():
                try:
                    raw_data = serial_port.readline()

                except serial.SerialException as exc:
                    if not self.ttlStopEvent.is_set():
                        print(f"TTL serial read error: {exc}")
                    break

                except OSError as exc:
                    if not self.ttlStopEvent.is_set():
                        print(f"TTL serial operating-system error: {exc}")
                    break

                if not raw_data:
                    continue

                received_time = time.perf_counter()

                value = raw_data.decode(
                    "utf-8",
                    errors="replace"
                ).strip()

                if not value:
                    continue

                self.ttlQueue.put({
                    "received_time": received_time,
                    "value": value
                })

        except serial.SerialException as exc:
            if not self.ttlStopEvent.is_set():
                print(f"Failed to open TTL serial port {port}: {exc}")

        except Exception as exc:
            if not self.ttlStopEvent.is_set():
                print(f"Unexpected TTL reader error: {exc}")

        finally:
            if self.ttlSerial is serial_port:
                self.ttlSerial = None

            if serial_port is not None:
                try:
                    if serial_port.is_open:
                        serial_port.close()
                except (
                    serial.SerialException,
                    OSError,
                    AttributeError
                ):
                    pass

            print("TTL serial reader stopped")

    def _processTTLQueue(self):
        """
        Transfer pending TTL events into the recording data.

        This method runs in the video worker thread and therefore does
        not require a lock around recordedFrames or ttl.
        """
        while not self.ttlQueue.empty():
            try:
                event = self.ttlQueue.get_nowait()
            except queue.Empty:
                break

            if not self.isRecording:
                continue

            if not self.recordedFrameTimes:
                continue

            ttl_time = (
                event["received_time"] - self.recordStartTime
            )

            if ttl_time < 0:
                continue

            frame_index = self._findNearestFrameIndex(
                ttl_time
            )

            frame_time = self.recordedFrameTimes[
                frame_index
            ]

            self.ttl.append({
                "frame_index": frame_index,
                "ttl_time": ttl_time,
                "frame_time": frame_time,
                "value": event["value"]
            })

    def _findNearestFrameIndex(self, event_time):
        """
        Find the recorded frame closest to a TTL event time.

        :param event_time: Time since recording began.
        :returns: Zero-based recorded frame index.
        """
        times = self.recordedFrameTimes

        if not times:
            return 0

        position = bisect_left(times, event_time)

        if position <= 0:
            return 0

        if position >= len(times):
            return len(times) - 1

        previous_index = position - 1
        next_index = position

        previous_difference = abs(
            event_time - times[previous_index]
        )

        next_difference = abs(
            times[next_index] - event_time
        )

        if previous_difference <= next_difference:
            return previous_index

        return next_index

    def _clearTTLQueue(self):
        """
        Remove all currently queued TTL events.
        """
        while not self.ttlQueue.empty():
            try:
                self.ttlQueue.get_nowait()
            except queue.Empty:
                break

    def ttlNow(self, value="manual"):
        """
        Manually create a TTL event.

        This method may be called from other parts of the application.
        The event is placed in the same queue as serial TTL events.

        :param value: Value written to the TTL CSV.
        """
        self.ttlQueue.put({
            "received_time": time.perf_counter(),
            "value": str(value)
        })

    # ==================================================================
    # Algorithm settings
    # ==================================================================

    @pyqtSlot(bool)
    def setAlgorithm(self, value: bool):
        """
        Enable or disable MediaPipe processing.
        """
        self.useAlgorithm = value

    @pyqtSlot(bool)
    def setOnlyAlgorithm(self, value: bool):
        """
        Show only the algorithm output.
        """
        self.useOnlyAlgorithm = value

    @pyqtSlot(bool)
    def setUseDepthCamera(self, value: bool):
        """
        Enable or disable the configured depth camera.
        """
        self.useDepthCamera = value

    # ==================================================================
    # Windows timer resolution
    # ==================================================================

    def _set_high_res_timer(self, release: bool = False):
        """
        Request or release one-millisecond Windows timer resolution.
        """
        try:
            winmm = ctypes.WinDLL("winmm")

            if release:
                winmm.timeEndPeriod(1)
            else:
                winmm.timeBeginPeriod(1)

        except Exception:
            # Not running on Windows or winmm is unavailable.
            pass


# ======================================================================


class VideoFeed(basicWindowWidget):
    """
    Video feed widget used to show and control video input.
    """

    def __init__(self, ID: int, workingDir: str = ""):
        """
        Create the video feed widget.

        :param ID: Widget identifier.
        :param workingDir: Application working directory.
        """
        super().__init__(
            VideoWorker,
            ID,
            workingDir=workingDir
        )

        self.useAlgorithm = False
        self.useOnlyAlgorithm = False
        self.cameraNumber = 0
        self.inputType = "video"

        # --------------------------------------------------------------
        # Video display
        # --------------------------------------------------------------

        self.mainWidget = QLabel()
        self.mainWidget.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.mainWidget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        # --------------------------------------------------------------
        # Controls
        # --------------------------------------------------------------

        self.Hands = QCheckBox(
            "Use Mediapipe Algorithm"
        )

        self.OnlyHands = QCheckBox(
            "Use ONLY the Algorithm"
        )

        self.depthCamera = QCheckBox(
            "Use Depth Camera"
        )

        self.depthCamera.setEnabled(False)

        self.FPSLabel = QLabel("FPS: 0.0")

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

    def updateCameraNumber(self, number):
        """
        Update the selected camera number.
        """
        self.cameraNumber = number

    def connectAll(self):
        """
        Connect worker signals and apply the current settings.
        """
        self.worker.setAlgorithm(
            self.Hands.isChecked()
        )

        self.worker.setOnlyAlgorithm(
            self.OnlyHands.isChecked()
        )

        self.worker.setUseDepthCamera(
            self.depthCamera.isChecked()
        )

        self.worker.frameReady.connect(
            self.setImage
        )

        self.worker.fpsReady.connect(
            self.updateFpsLabel
        )

    @pyqtSlot(object)
    def setImage(self, image):
        """
        Display an RGB NumPy image.
        """
        if image is None:
            return

        if len(image.shape) != 3:
            return

        height, width, channels = image.shape

        qimg = QImage(
            image.data,
            width,
            height,
            channels * width,
            QImage.Format.Format_RGB888
        ).copy()

        pixmap = QPixmap.fromImage(qimg)

        scaled = pixmap.scaled(
            self.mainWidget.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation
        )

        self.mainWidget.setPixmap(scaled)
        self.mainWidget.update()

    @pyqtSlot(float)
    def updateFpsLabel(self, fps):
        """
        Update the displayed instantaneous FPS.
        """
        self.FPSLabel.setText(
            f"FPS: {fps:.1f}"
        )

    def checkPath(self, path):
        """
        Check whether the selected path is valid.
        """
        if self.isLive:
            return True

        return super().checkPath(path)

    def setIsLive(self, state):
        """
        Set whether the video feed uses a live source.
        """
        super().setIsLive(state)

        if (
            not state
            and GlobalSettings["depthCameraAvailable"]
        ):
            self.depthCamera.setChecked(False)

        self.depthCamera.setEnabled(
            state
            and GlobalSettings["depthCameraAvailable"]
        )