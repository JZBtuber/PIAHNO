from mido import MidiFile
from PyQt6.QtWidgets import QCheckBox, QWidget, QFileDialog, QHBoxLayout, QVBoxLayout, QListWidgetItem, QLabel, QListWidget, QPushButton, QLineEdit
from PyQt6.QtCore import QObject, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QColor
from src.gui.Core import *
import time
import numpy as np
import pyaudio


class MidiWorker(basicWorker):
    noteOn = pyqtSignal(int, int)
    noteOff = pyqtSignal(int)

    def __init__(self, path, isLive, sample_rate: int = 44100, chunk: int = 512):
        super().__init__(path, isLive)

        self.sample_rate = sample_rate
        self.chunk = chunk
        self.p = None
        self.stream = None
        self.active_notes = {}
        self._phase = {}

        self.midi = None
        self.events = []
        self.event_index = 0
        self.next_event_time = None
        self.song_time = 0.0
        self.inport = None


    def midi_note_freq(self, note: int) -> float: #Returns the calculated frequency of the note
        return 440.0 * (2.0 ** ((note - 69) / 12.0))


    def make_chunk(self, frames: int) -> bytes:
        if self.muted or not self.active_notes:
            #If the worker is muted, the sample is empty
            samples = np.zeros(frames, dtype=np.float32)    

        else:
            t = np.arange(frames, dtype=np.float32) / self.sample_rate  #Numpy array for the audio
            samples = np.zeros(frames, dtype=np.float32)                #Numpy array of the samples  

            for note, velocity in list(self.active_notes.items()):      #Loop for each active note, plays the audio
                freq = self.midi_note_freq(note)    #Gets the frequency
                phase = self._phase.get(note, 0.0)  #Gets the phase of the note

                #Simple sine wave
                wave = np.sin((2.0 * np.pi * freq * t) + phase)

                #Scaled by velocity
                amp = (velocity / 127.0) * 0.15
                samples += wave * amp

                #Store phase's continuity
                phase_advance = 2.0 * np.pi * freq * frames / self.sample_rate
                self._phase[note] = (phase + phase_advance) % (2.0 * np.pi)

            #Prevent clipping by cutting samples too big
            samples = np.clip(samples, -1.0, 1.0)

        #Convert float32 mono PCM
        return samples.astype(np.float32).tobytes()


    def beforeLoop(self):
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self.sample_rate,
            output=True,
            frames_per_buffer=self.chunk
        )

        self.active_notes.clear()
        self._phase.clear()

        if self.isLive:
            self.inport = mido.open_input(self.path)
            self.midi = None
            self.events = []
            self.event_index = 0
            self.next_event_time = None
            self.song_time = 0.0
        else:
            self.midi = MidiFile(self.path, clip=True)
            self.events = list(self.midi)
            self.event_index = 0
            self.next_event_time = self.events[0].time if self.events else None
            self.song_time = 0.0
            self.inport = None

        

    def loop(self):
        if self.isLive:
            self.loop_live()
        else:
            self.loop_file()


    def loop_live(self):
        # read all pending midi messages
        for msg in self.inport.iter_pending():
            if msg.type == "note_on" and msg.velocity > 0:
                self.active_notes[msg.note] = msg.velocity
                self.noteOn.emit(msg.note, msg.velocity)

            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                self.active_notes.pop(msg.note, None)
                self._phase.pop(msg.note, None)
                self.noteOff.emit(msg.note)

        # continuously synthesize currently held notes
        audio = self.make_chunk(self.chunk)
        self.stream.write(audio)

        QThread.msleep(int(1000 * self.chunk / self.sample_rate))


    def loop_file(self):
        audio = self.make_chunk(self.chunk)
        self.stream.write(audio)

        chunk_duration = self.chunk / self.sample_rate
        elapsed_in_chunk = 0.0

        while (
            self.event_index < len(self.events)
            and self.next_event_time is not None
            and self.next_event_time <= chunk_duration - elapsed_in_chunk + 1e-9
        ):
            msg = self.events[self.event_index]

            if msg.type == "note_on" and msg.velocity > 0:
                self.active_notes[msg.note] = msg.velocity
                self.noteOn.emit(msg.note, msg.velocity)

            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                self.active_notes.pop(msg.note, None)
                self._phase.pop(msg.note, None)
                self.noteOff.emit(msg.note)

            elapsed_in_chunk += msg.time
            self.event_index += 1

            if self.event_index < len(self.events):
                self.next_event_time = self.events[self.event_index].time
            else:
                self.next_event_time = None
                break

        self.song_time += chunk_duration

        if self.next_event_time is not None:
            self.next_event_time -= chunk_duration
            if self.next_event_time < 0:
                self.next_event_time = 0.0

        if self.event_index >= len(self.events) and not self.active_notes:
            self.running = False


    def afterLoop(self):
        if self.inport is not None:
            try:
                self.inport.close()
            except Exception:
                pass
            self.inport = None

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

        self.finished.emit()


class MidiFeed(basicWindowWidget):
    def __init__(self, ID: int):
        super().__init__(MidiWorker, ID, True)

        self.activeNoteItems = {}
        self.mainWidget = QListWidget()
        self.inputType = "midi"

        self.makeBasicWidget()


    def midiNoteToName(self, note: int) -> str: #Gives a name to the note in int
        names = ["C", "C#", "D", "D#", "E", "F",
                 "F#", "G", "G#", "A", "A#", "B"]
        octave = (note // 12) - 1
        return f"{names[note % 12]}{octave}"
    

    def connectAll(self):
        self.worker.noteOn.connect(self.handleNoteOn)
        self.worker.noteOff.connect(self.handleNoteOff)


    def handleNoteOn(self, note: int, velocity: int):   #Prints the received note
        note_name = self.midiNoteToName(note)
        text = f"{note_name} ({note})  vel={velocity}"

        # If already active, refresh text/color and keep at top
        if note in self.activeNoteItems:
            item = self.activeNoteItems[note]
            item.setText(text)
            self.mainWidget.takeItem(self.mainWidget.row(item))
            self.mainWidget.insertItem(0, item)
        else:
            item = QListWidgetItem(text)
            self.activeNoteItems[note] = item
            self.mainWidget.insertItem(0, item)

        # Active = blue
        item.setForeground(QColor("blue"))


    def handleNoteOff(self, note: int):                 #Move the now non-active notes down
        if note in self.activeNoteItems:
            item = self.activeNoteItems.pop(note)

            # Make inactive notes black and move them below current active notes
            item.setForeground(QColor("black"))

            self.mainWidget.takeItem(self.mainWidget.row(item))
            self.mainWidget.insertItem(len(self.activeNoteItems), item)


    def browseFile(self):   #File managements
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "MID Files (*.mid);;All Files (*)"
        )
        if path:
            self.pathInput.setText(path)