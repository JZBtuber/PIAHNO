import wave
import audioop
import pyaudio
import os
from datetime import datetime

from PyQt6.QtCore import pyqtSignal, QThread, QTimer, Qt
from PyQt6.QtWidgets import QFileDialog, QWidget, QSizePolicy
from src.gui.Core import basicWindowWidget, basicWorker
from PyQt6.QtGui import QPainter, QColor

class AudioWorker(basicWorker):
    levelChanged = pyqtSignal(float)

    def __init__(self, path, isLive, chunk: int = 1024):
        super().__init__(path, isLive)

        #Default variables
        self.chunk = chunk
        self.p = None
        self.stream = None
        self.wf = None
        self.frames = None
        self.visualPeak = 0.05
        self.peakDecay = 0.995       
        self.sample_width = None
        self.channels = 1
        self.rate = 44100
        self.recordSelf = True

    #-------------------------------------
    #Workers's lifetime
    #-------------------------------------    

    def beforeLoop(self):
        self.p = pyaudio.PyAudio() #Open the audio stream
        
        if self.isLive: #Live mic input
            self.wf = None

            deviceInfo = self.p.get_device_info_by_index(int(self.path)) # get the device from its id
            FORMAT = pyaudio.paInt16

            #Set the settings for audio
            self.sample_width = self.p.get_sample_size(FORMAT)
            self.rate = int(deviceInfo.get('defaultSampleRate'))

            try: #try opening the mic
                self.stream = self.p.open(
                    format=pyaudio.paInt16,
                    channels=self.channels,
                    rate=self.rate,
                    input=True,
                    input_device_index=int(self.path),
                    frames_per_buffer=self.chunk
                )
            except: #Stops if fail
                self.running = False
                self.finished.emit()
                return
            
        else:   #File reading
            try:    #Try opening the .wav file (waveForm: wf)
                self.wf = wave.open(self.path, "rb")
            except:
                self.running = False
                self.finished.emit()
                return
            
            #get Data from the file
            self.sample_width = self.wf.getsampwidth()
            self.rate = self.wf.getframerate()

            #starts the stream for the audio
            self.stream = self.p.open(
                format=self.p.get_format_from_width(self.sample_width),
                channels=self.channels,
                rate=self.rate,
                output=True,
                frames_per_buffer=self.chunk
            )

    def loop(self):

        if self.isLive: #read the audio data from the stream
            try:
                self.data = self.stream.read(self.chunk, exception_on_overflow=False)
            except Exception:
                self.running = False
                return

            if not self.data:
                QThread.msleep(5)
                return

            if self.muted: #muted execption
                self.levelChanged.emit(0.0)
            else:
                self.levelChanged.emit(self.compute_level(self.data, self.sample_width))

        else:
            data = self.wf.readframes(self.chunk)   #read the audio from the file

            if not data:
                self.running = False
                return

            if self.muted:  #if muted, write nothing
                silent = b"\x00" * len(data)    
                self.stream.write(silent)
                self.levelChanged.emit(0.0)
            else:
                self.stream.write(data) #write that audio to the stream
                self.levelChanged.emit(self.compute_level(data, self.sample_width))


    def afterLoop(self):
        if self.stream is not None: #closes the stream
            try:
                self.stream.stop_stream()
            except Exception:
                pass
            try:
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        if self.wf is not None: #closes the file
            try:
                self.wf.close()
            except Exception:
                pass
            self.wf = None

        if self.p is not None: #closes the pyaudio instance
            try:
                self.p.terminate()
            except Exception:
                pass
            self.p = None


    def initRecording(self):
        self.frames = [] #list for recording data
        
        #making the path for the files
        self.newPath = os.path.join(self.getRecordingPath(), f"Audio_{self.ID}.wav")

    
    def recordloop(self):
        self.frames.append(self.data) #adds audio data to list


    def stopRecording(self): #Closes the recording and the file

        wf = wave.open(self.newPath, 'wb')
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
        level = raw_level * (4.0 if self.isLive else 4)   # tune this
        return max(0.0, min(level, 1.0))


class AudioVisualizer(QWidget):
    def __init__(self, bars: int = 64):
        super().__init__()

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.bars = bars
        self.levels = [0.0] * bars
        self._pendingLevel = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(33)       # repaint at 30 fps
        self._timer.timeout.connect(self.update)
        self._timer.start()

    def pushLevel(self, level: float):
        if self.levels:
            prev = self.levels[-1]
            level = prev * 0.45 + level * 0.55
        self.levels.pop(0)
        self.levels.append(level)

    def clear(self):
        self.levels = [0.0] * self.bars

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
    def __init__(self, ID: int, workingDir:str = ""):
        super().__init__(AudioWorker, ID, True, workingDir=workingDir)

        #set Default variables
        self.visualizer = AudioVisualizer()
        self.mainWidget = self.visualizer
        self.mainWidget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.hasAudio = True
        self.isLiveFeed = True
        self.inputType = "audio"

        self.makeBasicWidget()


    def connectAll(self):
        self.worker.levelChanged.connect(self.visualizer.pushLevel) #Connections to the worker

    #file Browser
    def browseFile(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "Wave Files (*.wav);;All Files (*)"
        )
        if path:
            self.pathInput.setText(path)
