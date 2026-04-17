import wave
import audioop
import pyaudio

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QThread, Qt
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import (
    QCheckBox, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QFileDialog
)
from src.gui.Core import *


class AudioWorker(QObject):
    finished = pyqtSignal()
    levelChanged = pyqtSignal(float)
    error = pyqtSignal(str)

    def __init__(self, wavPath: str, chunk: int = 1024):
        super().__init__()
        self.wavPath = wavPath
        self.chunk = chunk

        self.running = False
        self.paused = False
        self.muted = False

        self.p = None
        self.stream = None
        self.wf = None

    def open_audio(self):
        self.wf = wave.open(self.wavPath, "rb")

        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=self.p.get_format_from_width(self.wf.getsampwidth()),
            channels=self.wf.getnchannels(),
            rate=self.wf.getframerate(),
            output=True,
            frames_per_buffer=self.chunk
        )

    def close_audio(self):
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

    def compute_level(self, data: bytes) -> float:
        if not data or self.wf is None:
            return 0.0

        sample_width = self.wf.getsampwidth()
        max_possible = float((2 ** (8 * sample_width - 1)) - 1)

        try:
            rms = audioop.rms(data, sample_width)
        except Exception:
            return 0.0

        if max_possible <= 0:
            return 0.0

        level = rms / max_possible
        level *= 3.5
        return max(0.0, min(level, 1.0))

    @pyqtSlot()
    def run(self):
        self.running = True
        self.paused = False

        try:
            self.open_audio()

            while self.running:
                if self.paused:
                    QThread.msleep(20)
                    continue

                data = self.wf.readframes(self.chunk)
                if not data:
                    break

                if self.muted:
                    silent = b"\x00" * len(data)
                    self.stream.write(silent)
                    self.levelChanged.emit(0.0)
                else:
                    self.stream.write(data)
                    self.levelChanged.emit(self.compute_level(data))

        except Exception as e:
            self.error.emit(str(e))

        finally:
            self.close_audio()
            self.finished.emit()

    @pyqtSlot()
    def setMuted(self):
        self.muted = True

    @pyqtSlot()
    def resetMuted(self):
        self.muted = False

    @pyqtSlot()
    def pause(self):
        self.paused = True

    @pyqtSlot()
    def resume(self):
        self.paused = False

    @pyqtSlot()
    def stop(self):
        self.running = False


class AudioVisualizer(QWidget):
    def __init__(self, bars: int = 16):
        super().__init__()
        self.bars = bars
        self.levels = [0.0] * bars
        self.setMinimumHeight(200)

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

        margin = 10
        gap = 8
        usable_width = rect.width() - (2 * margin) - (gap * (self.bars - 1))
        bar_width = max(14, usable_width // self.bars)
        max_height = rect.height() - 16

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#4da3ff"))

        x = margin
        for level in self.levels:
            h = max(6, int(max_height * level))
            y = rect.height() - h - 8
            painter.drawRoundedRect(x, y, bar_width, h, 4, 4)
            x += bar_width + gap


class AudioFeed(QWidget):
    def __init__(self, ID: int = 0):
        super().__init__()

        self.ID = ID
        self.thread = None
        self.worker = None

        self.IDlabel = QLabel(str(self.ID))

        self.startButton = QPushButton("Start")
        self.pauseButton = QPushButton("Pause/Resume")
        self.stopButton = QPushButton("Stop")
        self.muteCheckBox = QCheckBox("Mute")
        self.muteCheckBox.setChecked(False)

        self.startButton.clicked.connect(self.start)
        self.pauseButton.clicked.connect(self.pause)
        self.stopButton.clicked.connect(self.stop)
        self.muteCheckBox.clicked.connect(self.muteChanged)

        controlsLayout = QHBoxLayout()
        controlsLayout.addWidget(self.startButton)
        controlsLayout.addWidget(self.pauseButton)
        controlsLayout.addWidget(self.stopButton)
        controlsLayout.addWidget(self.muteCheckBox)
        controlsLayout.addStretch()

        self.pathInput = FileDropLineEdit()
        self.pathInput.setPlaceholderText("Video path...")

        #Browse button
        self.browseButton = QPushButton("Browse")
        self.browseButton.clicked.connect(self.browseFile)

        #Path input layout
        self.pathLayout = QHBoxLayout()
        self.pathLayout.addWidget(self.pathInput, 1)
        self.pathLayout.addWidget(self.browseButton, 0)


        self.visualizer = AudioVisualizer()
        self.statusLabel = QLabel("Stopped")

        self.mainLayout = QVBoxLayout()
        self.mainLayout.addWidget(self.IDlabel, 0)
        self.mainLayout.addWidget(QLabel("Audio"), 0)
        self.mainLayout.addWidget(self.visualizer, 1)
        self.mainLayout.addLayout(controlsLayout, 0)
        self.mainLayout.addLayout(self.pathLayout, 0)
        self.mainLayout.addWidget(self.statusLabel, 0)
        self.mainLayout.addStretch()
        self.setLayout(self.mainLayout)

    def muteChanged(self, checked):
        if self.worker:
            if checked:
                self.worker.setMuted()
                self.statusLabel.setText("Muted")
            else:
                self.worker.resetMuted()
                self.statusLabel.setText("Playing")

    def start(self):
        if not self.checkPath():
            Message = MessageBox("Path Error!", "The path is empty and needs a file!")
            return

        if self.thread is not None:
            return

        path = self.pathInput.text().strip()
        if not path:
            return

        self.visualizer.clear()
        self.statusLabel.setText("Playing")

        self.thread = QThread()
        self.worker = AudioWorker(path)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)

        if self.muteCheckBox.isChecked():
            self.thread.started.connect(self.worker.setMuted)
        else:
            self.thread.started.connect(self.worker.resetMuted)

        self.worker.levelChanged.connect(self.visualizer.pushLevel)
        self.worker.error.connect(self.onError)
        self.worker.finished.connect(self.onPlaybackFinished)
        self.worker.finished.connect(self.thread.quit)

        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def pause(self):
        if self.worker:
            if self.worker.paused:
                self.worker.resume()
                if self.muteCheckBox.isChecked():
                    self.statusLabel.setText("Muted")
                else:
                    self.statusLabel.setText("Playing")
            else:
                self.worker.pause()
                self.statusLabel.setText("Paused")

    def stop(self):
        if self.worker:
            self.worker.stop()

        if self.thread:
            self.thread.quit()
            self.thread.wait()

        self.worker = None
        self.thread = None
        self.statusLabel.setText("Stopped")
        self.visualizer.clear()

    def onPlaybackFinished(self):
        self.worker = None
        self.thread = None
        self.statusLabel.setText("Finished")

    def onError(self, message: str):
        self.statusLabel.setText(f"Error: {message}")


    def browseFile(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "WAV Files (*.wav);;All Files (*)"
        )
        if path:
            self.pathInput.setText(path)


    def checkPath(self):
        if self.pathInput.text():
            return True
        else:
            return False