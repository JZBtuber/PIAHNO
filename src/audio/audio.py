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


class AudioWorker(basicWorker):
    finished = pyqtSignal()
    levelChanged = pyqtSignal(float)
    
    def __init__(self, path, chunk: int = 1024):
        super().__init__(path)

        #Defining default variables and objects
        self.wavPath = path  #Path to the .wav file
        self.chunk = chunk      #Audio's chunks
        self.p = None           #Duturely Pyaudio
        self.stream = None      #Futurely the output stream
        self.wf = None          #Wave file once opended


    def beforeLoop(self):
        self.wf = wave.open(self.wavPath, "rb") #Opens the .wav file

        self.p = pyaudio.PyAudio()  #Creates the Pyaudio object
        self.stream = self.p.open(  #Creates the stream object
            format=self.p.get_format_from_width(self.wf.getsampwidth()),
            channels=self.wf.getnchannels(),
            rate=self.wf.getframerate(),
            output=True,
            frames_per_buffer=self.chunk
        )


    def loop(self):
        if self.paused: #Handling the pause
            QThread.msleep(20)
            return

        data = self.wf.readframes(self.chunk)   #Check if there is data to play
        if not data:
            return

        if self.muted:                          #Play silence if muted
            silent = b"\x00" * len(data)
            self.stream.write(silent)
            self.levelChanged.emit(0.0)
        else:                                   #Plays the audio if not muted
            self.stream.write(data)
            self.levelChanged.emit(self.compute_level(data))


    def afterLoop(self):
        #Closing the stream
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

        #Closing the .wav file
        if self.wf is not None:
            try:
                self.wf.close()
            except Exception:
                pass
            self.wf = None

        #Closing the Pyaudio instance
        if self.p is not None:
            try:
                self.p.terminate()
            except Exception:
                pass
            self.p = None

        self.finished.emit()


    def compute_level(self, data: bytes) -> float:
        if not data or self.wf is None:
            return 0.0

        #Gets the working variables
        sample_width = self.wf.getsampwidth()
        max_possible = float((2 ** (8 * sample_width - 1)) - 1)

        try:
            rms = audioop.rms(data, sample_width)
        except Exception:
            return 0.0

        #If note is 0 return 0
        if max_possible <= 0:
            return 0.0

        level = rms / max_possible
        level *= 35
        return max(0.0, min(level, 1.0))    #Gets the audio bar's height from the audio


class AudioVisualizer(QWidget):
    def __init__(self, bars: int = 16):
        super().__init__()  

        #Creates the bars
        self.bars = bars
        self.levels = [0.0] * bars
        self.setMinimumHeight(200)


    def pushLevel(self, level: float):      #Push the bars up when the audio plays
        if self.levels:
            prev = self.levels[-1]
            level = prev * 0.45 + level * 0.55

        self.levels.pop(0)
        self.levels.append(level)
        self.update()


    def clear(self):                        #Clear the bars
        self.levels = [0.0] * self.bars
        self.update()


    def paintEvent(self, event):            #Paints the bar when a note is played (most is only defining the style)
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
        for level in self.levels:   #Prints the levels the the hights
            h = max(6, int(max_height * level))
            y = rect.height() - h - 8
            painter.drawRoundedRect(x, y, bar_width, h, 4, 4)
            x += bar_width + gap


class AudioFeed(basicWindowWidget):
    def __init__(self, ID: int):
        super().__init__(AudioWorker, ID, True)

        self.visualizer = AudioVisualizer()
        self.mainWidget = self.visualizer
        self.hasAudio = True

        self.makeBasicWidget()


    def connectAll(self):
        self.worker.levelChanged.connect(self.visualizer.pushLevel)
        self.worker.finished.connect(self.onPlaybackFinished)
        
    def browseFile(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "Wave Files (*wav);;All Files (*)"
        )
        if path:
            self.pathInput.setText(path)
        

    def onPlaybackFinished(self):
        self.worker = None
        self.thread = None
