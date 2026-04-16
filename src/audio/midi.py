from mido import MidiFile
from PyQt6.QtWidgets import QCheckBox, QWidget, QHBoxLayout, QVBoxLayout, QListWidgetItem, QLabel, QListWidget, QPushButton, QLineEdit
from PyQt6.QtCore import QObject, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QColor
import time
import math
import numpy as np
import pyaudio


class MidiWorker(QObject):
    noteOn = pyqtSignal(int, int)
    noteOff = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, midiPath: str, sample_rate: int = 44100, chunk: int = 512):
        super().__init__()
        self.midiPath = midiPath
        self.sample_rate = sample_rate
        self.chunk = chunk

        self.running = False
        self.paused = False
        self.muted = True

        self.p = None
        self.stream = None

        self.active_notes = {}   # note -> velocity
        self._phase = {}         # note -> phase in radians

    def midi_note_freq(self, note: int) -> float:
        return 440.0 * (2.0 ** ((note - 69) / 12.0))

    def make_chunk(self, frames: int) -> bytes:
        if self.muted or not self.active_notes:
            samples = np.zeros(frames, dtype=np.float32)
        else:
            t = np.arange(frames, dtype=np.float32) / self.sample_rate
            samples = np.zeros(frames, dtype=np.float32)

            for note, velocity in list(self.active_notes.items()):
                freq = self.midi_note_freq(note)
                phase = self._phase.get(note, 0.0)

                # simple sine wave
                wave = np.sin((2.0 * np.pi * freq * t) + phase)

                # scale by velocity
                amp = (velocity / 127.0) * 0.15
                samples += wave * amp

                # store phase continuity
                phase_advance = 2.0 * np.pi * freq * frames / self.sample_rate
                self._phase[note] = (phase + phase_advance) % (2.0 * np.pi)

            # prevent clipping
            samples = np.clip(samples, -1.0, 1.0)

        # convert float32 mono PCM
        return samples.astype(np.float32).tobytes()

    def open_audio(self):
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self.sample_rate,
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

        if self.p is not None:
            try:
                self.p.terminate()
            except Exception:
                pass
            self.p = None

    @pyqtSlot()
    def run(self):
        self.running = True
        self.paused = False
        self.active_notes.clear()
        self._phase.clear()

        midi = MidiFile(self.midiPath, clip=True)
        events = list(midi)  # raw messages, use msg.time yourself

        try:
            self.open_audio()

            event_index = 0
            next_event_time = events[0].time if events else None
            song_time = 0.0

            while self.running:
                if self.paused:
                    time.sleep(0.01)
                    continue
                
                audio = self.make_chunk(self.chunk)
                self.stream.write(audio)

                self.stream.write(audio)

                chunk_duration = self.chunk / self.sample_rate

                # process all midi events that fall into this chunk
                elapsed_in_chunk = 0.0
                while (
                    event_index < len(events)
                    and next_event_time is not None
                    and next_event_time <= chunk_duration - elapsed_in_chunk + 1e-9
                ):
                    msg = events[event_index]

                    if msg.type == "note_on" and msg.velocity > 0:
                        self.active_notes[msg.note] = msg.velocity
                        self.noteOn.emit(msg.note, msg.velocity)

                    elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                        self.active_notes.pop(msg.note, None)
                        self._phase.pop(msg.note, None)
                        self.noteOff.emit(msg.note)

                    elapsed_in_chunk += msg.time
                    event_index += 1

                    if event_index < len(events):
                        next_event_time = events[event_index].time
                    else:
                        next_event_time = None
                        break

                audio = self.make_chunk(self.chunk)
                self.stream.write(audio)
                song_time += chunk_duration

                # subtract this chunk from the next event delay
                if next_event_time is not None:
                    next_event_time -= chunk_duration
                    if next_event_time < 0:
                        next_event_time = 0.0

                # stop automatically when song is done and no notes are ringing
                if event_index >= len(events) and not self.active_notes:
                    break

        finally:
            self.close_audio()
            self.finished.emit()

    @pyqtSlot(bool)
    def setMuted(self, muted: bool):
        self.muted = muted

    @pyqtSlot()
    def pause(self):
        self.paused = True

    @pyqtSlot()
    def resume(self):
        self.paused = False

    @pyqtSlot()
    def stop(self):
        self.running = False


class MidiFeed(QWidget):
    muteChanged = pyqtSignal(bool)

    def __init__(self, ID: int):
        super().__init__()

        #Set the default values of variables
        self.ID = ID
        self.mute = True

        #Active note being played in the recording
        self.activeNoteItems = {}

        #Creating the widgets
        #ID counter
        self.IDlabel = QLabel(str(self.ID))

        #Control buttons
        self.startButton = QPushButton("Start")
        self.pauseButton = QPushButton("Pause/Resume")
        self.stopButton = QPushButton("Stop")
        self.muteCheckBox = QCheckBox("Mute")
        self.muteCheckBox.setChecked(True)
        self.startButton.clicked.connect(self.start)
        self.pauseButton.clicked.connect(self.pause)
        self.stopButton.clicked.connect(self.stop)
        self.muteCheckBox.toggled.connect(self.muteChanged.emit)

        #Control layout
        controlsLayout = QHBoxLayout()
        controlsLayout.addWidget(self.startButton)
        controlsLayout.addWidget(self.pauseButton)
        controlsLayout.addWidget(self.stopButton)
        controlsLayout.addWidget(self.muteCheckBox)
        controlsLayout.addStretch()

        #Video path
        self.pathInput = QLineEdit()
        self.pathInput.setPlaceholderText("Midi path...")

        #Note lists
        self.noteList = QListWidget()


        #MainLayout of the widget
        self.mainLayout = QVBoxLayout()
        self.mainLayout.addWidget(self.IDlabel, 0)
        self.mainLayout.addWidget(QLabel("Notes"), 0)
        self.mainLayout.addWidget(self.noteList, 1)
        self.mainLayout.addLayout(controlsLayout, 0)
        self.mainLayout.addWidget(self.pathInput, 0)
        self.mainLayout.addStretch()
        self.setLayout(self.mainLayout)

        self.thread = None
        self.worker = None


    def midiNoteToName(self, note: int) -> str:
        names = ["C", "C#", "D", "D#", "E", "F",
                 "F#", "G", "G#", "A", "A#", "B"]
        octave = (note // 12) - 1
        return f"{names[note % 12]}{octave}"


    def start(self):
        if self.thread is not None:
            self.stop()

        path = self.pathInput.text().strip()
        if not path:
            return

        self.thread = QThread()
        self.worker = MidiWorker(path)

        self.worker.moveToThread(self.thread)

        self.muteChanged.connect(self.worker.setMuted)
        self.worker.setMuted(self.muteCheckBox.isChecked())

        self.thread.started.connect(self.worker.run)
        self.worker.noteOn.connect(self.handleNoteOn)
        self.worker.noteOff.connect(self.handleNoteOff)
        self.worker.finished.connect(self.onPlaybackFinished)
        self.worker.finished.connect(self.thread.quit)

        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.muteChanged.connect(self.worker.setMuted)
        self.worker.setMuted(self.muteCheckBox.isChecked())

        self.thread.start()


    def pause(self):
        if self.worker:
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

        for note in list(self.activeNoteItems.keys()):
            self.handleNoteOff(note)

    def onPlaybackFinished(self):
        self.worker = None
        self.thread = None


    def handleNoteOn(self, note: int, velocity: int):
        note_name = self.midiNoteToName(note)
        text = f"{note_name} ({note})  vel={velocity}"

        # If already active, refresh text/color and keep at top
        if note in self.activeNoteItems:
            item = self.activeNoteItems[note]
            item.setText(text)
            self.noteList.takeItem(self.noteList.row(item))
            self.noteList.insertItem(0, item)
        else:
            item = QListWidgetItem(text)
            self.activeNoteItems[note] = item
            self.noteList.insertItem(0, item)

        # Active = blue
        item.setForeground(QColor("blue"))

    def handleNoteOff(self, note: int):
        if note in self.activeNoteItems:
            item = self.activeNoteItems.pop(note)

            # Make inactive notes black and move them below current active notes
            item.setForeground(QColor("black"))

            self.noteList.takeItem(self.noteList.row(item))
            self.noteList.insertItem(len(self.activeNoteItems), item)

        

        