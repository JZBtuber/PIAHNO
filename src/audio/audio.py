import wave
import audioop
import pyaudio
import os
from PyQt6.QtCore import pyqtSignal, QThread, QTimer, Qt
from PyQt6.QtWidgets import QFileDialog, QWidget, QSizePolicy
from src.gui.Core import basicWindowWidget, basicWorker
from PyQt6.QtGui import QPainter, QColor


class AudioWorker(basicWorker):
    """
    Worker used to read audio from a file or live input.\n
    It also emits audio levels for the visualizer and can record audio data.
    """
    levelChanged = pyqtSignal(float)

    def __init__(self, path, isLive, chunk: int = 1024):
        """
        Create the audio worker.\n
        :param path: Path to the audio file or live device ID.
        :param isLive: If `True`, the worker uses a live audio input.
        :param `int` chunk: Number of audio frames to read at a time, defaults to `1024`.
        """
        super().__init__(path, isLive)

        # Default variables
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

    # -------------------------------------
    # Workers's lifetime
    # -------------------------------------

    def beforeLoop(self):
        """
        Open the audio input before the main worker loop starts.
        """
        # Open the PyAudio instance
        self.p = pyaudio.PyAudio()

        # Open live microphone input
        if self.isLive:
            self.wf = None

            # Get the selected input device information
            deviceInfo = self.p.get_device_info_by_index(int(self.path))
            FORMAT = pyaudio.paInt16

            # Set the settings for audio
            self.sample_width = self.p.get_sample_size(FORMAT)
            self.rate = int(deviceInfo.get('defaultSampleRate'))

            try:  # try opening the mic
                self.stream = self.p.open(
                    format=pyaudio.paInt16,
                    channels=self.channels,
                    rate=self.rate,
                    input=True,
                    input_device_index=int(self.path),
                    frames_per_buffer=self.chunk
                )
            except:  # Stops if fail
                self.running = False
                self.finished.emit()
                return

        # Open audio file input
        else:  # File reading
            try:  # Try opening the .wav file (waveForm: wf)
                self.wf = wave.open(self.path, "rb")
            except:
                self.running = False
                self.finished.emit()
                return

            # get Data from the file
            self.sample_width = self.wf.getsampwidth()
            self.rate = self.wf.getframerate()

            # starts the stream for the audio
            self.stream = self.p.open(
                format=self.p.get_format_from_width(self.sample_width),
                channels=self.channels,
                rate=self.rate,
                output=True,
                frames_per_buffer=self.chunk
            )

    def loop(self):
        """
        Read one chunk of audio and emit the current audio level.
        """

        # Read live audio data
        if self.isLive:  # read the audio data from the stream
            try:
                self.data = self.stream.read(
                    self.chunk, exception_on_overflow=False)
            except Exception:
                self.running = False
                return

            # Guard clause if no audio data was read
            if not self.data:
                QThread.msleep(5)
                return

            # Emit muted or computed level
            if self.muted:  # muted execption
                self.levelChanged.emit(0.0)
            else:
                self.levelChanged.emit(self.compute_level(
                    self.data, self.sample_width))

        # Read audio file data
        else:
            data = self.wf.readframes(self.chunk)

            # Stop if the file is finished
            if not data:
                self.running = False
                return

            # Write silent or real audio data
            if self.muted:
                silent = b"\x00" * len(data)
                self.stream.write(silent)
                self.levelChanged.emit(0.0)
            else:
                self.stream.write(data)  # write that audio to the stream
                self.levelChanged.emit(
                    self.compute_level(data, self.sample_width))

    def afterLoop(self):
        """
        Close the stream, audio file and PyAudio instance after the worker stops.
        """
        # Close the audio stream
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

        # Close the wave file
        if self.wf is not None:
            try:
                self.wf.close()
            except Exception:
                pass
            self.wf = None

        # Close the PyAudio instance
        if self.p is not None:
            try:
                self.p.terminate()
            except Exception:
                pass
            self.p = None

    def initRecording(self):
        """
        Initialize audio recording data and output path.
        """
        self.frames = []  # list for recording data

        # making the path for the files
        path = self.getRecordingPath()
        self.newPath = os.path.join(
            path, f"Audio_{self.ID}.wav")
        os.makedirs(path, exist_ok=True)

    def recordloop(self):
        """
        Save the current audio data chunk.
        """
        self.frames.append(self.data)  # adds audio data to list

    def stopRecording(self):  # Closes the recording and the file
        """
        Save the recorded audio data to a wave file.
        """

        # Create and write the wave file
        wf = wave.open(self.newPath, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.sample_width)
        wf.setframerate(self.rate)
        wf.writeframes(b''.join(self.frames))
        wf.close()

    def compute_level(self, data: bytes, sample_width: int) -> float:
        """
        Compute an audio level value for visualization.\n
        :param `bytes` data: Raw audio data.
        :param `int` sample_width: Width of one audio sample in bytes.
        :returns: Returns a normalized audio level between `0.0` and `1.0`.
        :rtype: `float`
        """
        # Guard clause if there is no audio data
        if not data:
            return 0.0

        # Calculate RMS level
        try:
            # Convert stereo/multichannel to mono for visualization
            if self.channels > 1:
                data = audioop.tomono(data, sample_width, 0.5, 0.5)

            rms = audioop.rms(data, sample_width)
        except Exception:
            return 0.0

        # Get maximum possible amplitude
        max_possible = float((2 ** (8 * sample_width - 1)) - 1)
        if max_possible <= 0:
            return 0.0

        # Normalize RMS level
        raw_level = rms / max_possible

        # gentler display curve, without peak normalization
        level = raw_level * (4.0 if self.isLive else 4)   # tune this
        return max(0.0, min(level, 1.0))


class AudioVisualizer(QWidget):
    """
    Widget used to draw audio level bars.
    """

    def __init__(self, bars: int = 64):
        """
        Create the audio visualizer.\n
        :param `int` bars: Number of bars to draw, defaults to `64`.
        """
        super().__init__()

        # Set defaults
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.bars = bars
        self.levels = [0.0] * bars
        self._pendingLevel = 0.0

        # Timer to process at 30 fps
        self._timer = QTimer(self)
        self._timer.setInterval(33)       # repaint at 30 fps
        self._timer.timeout.connect(self.update)
        self._timer.start()

    def pushLevel(self, level: float):
        """
        Add a new audio level to the visualizer.\n
        :param `float` level: New level to add.
        """
        # Set the levels
        if self.levels:
            prev = self.levels[-1]
            level = prev * 0.45 + level * 0.55
        self.levels.pop(0)
        self.levels.append(level)

    def clear(self):
        """
        Clear all visualizer levels.
        """
        # Reset every bar level
        self.levels = [0.0] * self.bars

    def paintEvent(self, event):
        """
        Paint the audio bars on the widget.\n
        :param event: Paint event.
        """
        # Paint the bars on the screen
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fill the background
        rect = self.rect()
        painter.fillRect(rect, QColor("#111111"))

        # Calculate bar dimensions
        margin = 4
        gap = 3
        usable_width = rect.width() - (2 * margin) - (gap * (self.bars - 1))
        bar_width = max(3, usable_width // self.bars)
        max_height = rect.height() - 16

        # Set bar drawing options
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#4da3ff"))

        # Draw each audio level bar
        x = margin
        for level in self.levels:
            h = max(1, int(max_height * level))
            y = rect.height() - h - 8
            painter.drawRoundedRect(x, y, bar_width, h, 4, 4)
            x += bar_width + gap


class AudioFeed(basicWindowWidget):
    """
    Audio feed widget used to read, play, record and visualize audio.
    """

    def __init__(self, ID: int, workingDir: str = ""):
        """
        Create the audio feed widget.\n
        :param `int` ID: ID of the widget.
        :param `str` workingDir: Working directory of the app, defaults to `""`.
        """
        super().__init__(AudioWorker, ID, True, workingDir=workingDir)

        # set Default variables
        self.visualizer = AudioVisualizer()
        self.mainWidget = self.visualizer
        self.mainWidget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.hasAudio = True
        self.isLiveFeed = True
        self.inputType = "audio"

        # Create the base widget layout
        self.makeBasicWidget()

    def connectAll(self):
        """
        Connect the audio worker signals.
        """
        self.worker.levelChanged.connect(
            self.visualizer.pushLevel)  # Connections to the worker

    # file Browser
    def browseFile(self):
        """
        Open a file dialog and set the selected audio path.
        """
        # User chooses the audio file
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "Wave Files (*.wav);;All Files (*)"
        )
        if path:
            self.pathInput.setText(path)
