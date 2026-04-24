import wave
import audioop
import pyaudio
import os
from datetime import datetime

from PyQt6.QtCore import pyqtSignal, QThread
from PyQt6.QtWidgets import QFileDialog
from src.gui.Core import *

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import QWidget
from PyQt6.QtWidgets import QSizePolicy


class AudioWorker(basicWorker):
    levelChanged = pyqtSignal(float)

    def __init__(self, path, isLive, chunk: int = 1024):
        super().__init__(path, isLive)

        self.chunk = chunk
        self.p = None
        self.stream = None
        self.wf = None
        self.frames = None
        self.visualPeak = 0.05
        self.peakDecay = 0.995

        # file-mode info
        self.sample_width = None
        self.channels = 1
        self.rate = 44100

    def beforeLoop(self):
        self.p = pyaudio.PyAudio()

        

        if self.isLive:
            self.wf = None

            deviceInfo = self.p.get_device_info_by_index(self.path)
            FORMAT = pyaudio.paInt16

            self.sample_width = self.p.get_sample_size(FORMAT)
            self.rate = int(deviceInfo.get('defaultSampleRate'))

            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=int(self.path),
                frames_per_buffer=self.chunk
            )
        else:
            if not self.path:
                print("No file path")
                self.running = False
                return

            try:
                self.wf = wave.open(self.path, "rb")
            except Exception as e:
                print("Failed to open file:", e)
                self.running = False
                return

            self.sample_width = self.wf.getsampwidth()
            self.rate = self.wf.getframerate()

            self.stream = self.p.open(
                format=self.p.get_format_from_width(self.sample_width),
                channels=self.channels,
                rate=self.rate,
                output=True,
                frames_per_buffer=self.chunk
            )

    def loop(self):
        if self.paused:
            QThread.msleep(20)
            return

        if self.isLive:
            try:
                self.data = self.stream.read(self.chunk, exception_on_overflow=False)
            except Exception:
                self.running = False
                return

            if not self.data:
                QThread.msleep(5)
                return

            if self.muted:
                self.levelChanged.emit(0.0)
            else:
                self.levelChanged.emit(self.compute_level(self.data, self.sample_width))

        else:
            data = self.wf.readframes(self.chunk)

            if not data:
                self.running = False
                return

            if self.muted:
                silent = b"\x00" * len(data)
                self.stream.write(silent)
                self.levelChanged.emit(0.0)
            else:
                self.stream.write(data)
                self.levelChanged.emit(self.compute_level(data, self.sample_width))

    def afterLoop(self):
        if self.stream is not None:
            try:
                self.stream.stop_stream()
            except Exception:
                pass
            try:
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        if self.wf is not None:
            try:
                self.wf.close()
            except Exception:
                pass
            self.wf = None

        if self.p is not None:
            try:
                self.p.terminate()
            except Exception:
                pass
            self.p = None


    def initRecording(self):
        self.frames = []

    
    def recordloop(self):
        self.frames.append(self.data)


    def stopRecording(self):

        time: str = str(datetime.now()).replace(" ", "_").replace(":", "-")[0:16]


        os.makedirs(os.path.join(os.getcwd(), f"Tests\\{time}_Test"), exist_ok=True)

        newPath = os.path.join(os.getcwd(), f"Tests\\{time}_Test\\Audio_{self.ID}.wav")

        wf = wave.open(newPath, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.sample_width)
        wf.setframerate(self.rate)
        wf.writeframes(b''.join(self.frames))
        wf.close()



    def compute_level(self, data: bytes, sample_width: int) -> float:
        if not data:
            return 0.0

        try:
            # Convert stereo/multichannel to mono for visualization
            if self.channels > 1:
                data = audioop.tomono(data, sample_width, 0.5, 0.5)

            rms = audioop.rms(data, sample_width)
        except Exception:
            return 0.0

        max_possible = float((2 ** (8 * sample_width - 1)) - 1)
        if max_possible <= 0:
            return 0.0

        raw_level = rms / max_possible

        # gentler display curve, without peak normalization
        level = raw_level * (4.0 if self.isLive else 35)   # tune this
        return max(0.0, min(level, 1.0))


class AudioVisualizer(QWidget):
    def __init__(self, bars: int = 16):
        super().__init__()

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.bars = bars
        self.levels = [0.0] * bars

    def pushLevel(self, level: float):
        if self.levels:
            prev = self.levels[-1]
            level = prev * 0.45 + level * 0.55

        self.levels.pop(0)
        self.levels.append(level)
        self.update()

    def clear(self):
        self.levels = [0.0] * self.bars
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        painter.fillRect(rect, QColor("#111111"))

        margin = 4
        gap = 3
        usable_width = rect.width() - (2 * margin) - (gap * (self.bars - 1))
        bar_width = max(3, usable_width // self.bars)
        max_height = rect.height() - 16

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#4da3ff"))

        x = margin
        for level in self.levels:
            h = max(1, int(max_height * level))
            y = rect.height() - h - 8
            painter.drawRoundedRect(x, y, bar_width, h, 4, 4)
            x += bar_width + gap


class AudioFeed(basicWindowWidget):
    def __init__(self, ID: int):
        super().__init__(AudioWorker, ID, True)

        self.visualizer = AudioVisualizer()
        self.mainWidget = self.visualizer
        self.mainWidget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.hasAudio = True
        self.isLiveFeed = True

        self.inputType = "audio"

        self.makeBasicWidget()


    def connectAll(self):
        self.worker.levelChanged.connect(self.visualizer.pushLevel)

    def browseFile(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "Wave Files (*.wav);;All Files (*)"
        )
        if path:
            self.pathInput.setText(path)
