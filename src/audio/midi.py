import mido
import os
from PyQt6.QtWidgets import QCheckBox, QWidget, QFileDialog, QHBoxLayout, QVBoxLayout, QListWidgetItem, QLabel, QListWidget, QPushButton, QLineEdit
from PyQt6.QtCore import QObject, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QColor
from src.gui.Core import *
from datetime import datetime
import time
import numpy as np



class MidiWorker(basicWorker):
    noteOn = pyqtSignal(int, int)
    noteOff = pyqtSignal(int)

    def __init__(self, path, isLive, sample_rate: int = 44100, chunk: int = 512):
        super().__init__(path, isLive)

        self.active_notes = {}

        self.midi = None
        self.events = []
        self.event_index = 0
        self.next_event_time = None
        self.song_time = 0.0
        self.inport = None


    def midi_note_freq(self, note: int) -> float: #Returns the calculated frequency of the note
        return 440.0 * (2.0 ** ((note - 69) / 12.0))


    def make_chunk(self, frames: int) -> bytes:

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
        self.msg = None
        self.record_msg = None
        self.active_notes.clear()

        if self.isLive:
            self.inport = mido.open_input(self.path)
            self.midi = None
            self.events = []
            self.event_index = 0
            self.next_event_time = None
            self.song_time = 0.0
        else:
            self.midi = mido.MidiFile(self.path, clip=True)
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
        had_message = False

        for self.msg in self.inport.iter_pending():
            had_message = True
            self.record_msg = self.msg

            if self.msg.type == "note_on" and self.msg.velocity > 0:
                self.active_notes[self.msg.note] = self.msg.velocity
                self.noteOn.emit(self.msg.note, self.msg.velocity)

            elif self.msg.type == "note_off" or (self.msg.type == "note_on" and self.msg.velocity == 0):
                self.active_notes.pop(self.msg.note, None)
                self.noteOff.emit(self.msg.note)

        if not had_message:
            QThread.msleep(5)


    def loop_file(self):
        if self.event_index >= len(self.events):
            self.running = False
            return

        msg = self.events[self.event_index]

        if msg.time > 0:
            QThread.msleep(int(msg.time * 1000))

        self.msg = msg

        if msg.type == "note_on" and msg.velocity > 0:
            self.active_notes[msg.note] = msg.velocity
            self.noteOn.emit(msg.note, msg.velocity)

        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            self.active_notes.pop(msg.note, None)
            self.noteOff.emit(msg.note)

        self.event_index += 1


    def afterLoop(self):
        if self.inport is not None:
            try:
                self.inport.close()
            except Exception:
                pass
            self.inport = None



    def initRecording(self):

        time: str = str(datetime.now()).replace(" ", "_").replace(":", "-")[0:16]
        os.makedirs(os.path.join(os.getcwd(), f"Tests\\{time}_Test"), exist_ok=True)
        self.newPath = os.path.join(os.getcwd(), f"Tests\\{time}_Test\\Midi_{self.ID}.mid")
        
        self.midi_recording = mido.MidiFile(ticks_per_beat=480)
        self.track = mido.MidiTrack()
        self.midi_recording.tracks.append(self.track)

        self.tempo = mido.bpm2tempo(120)   # 120 BPM default
        self.track.append(mido.MetaMessage('set_tempo', tempo=self.tempo, time=0))

        self.last_record_time = time.time()


    def recordloop(self):
        if self.record_msg is not None:
            now = time.time()
            delta_seconds = now - self.last_record_time
            self.last_record_time = now

            delta_ticks = int(
                mido.second2tick(
                    delta_seconds,
                    self.midi_recording.ticks_per_beat,
                    self.tempo
                )
            )

            self.track.append(self.record_msg.copy(time=delta_ticks))
            self.record_msg = None

        
    def stopRecording(self):
        self.midi_recording.save(self.newPath)

class MidiFeed(basicWindowWidget):
    def __init__(self, ID: int):
        super().__init__(MidiWorker, ID, False)

        self.activeNoteItems = {}
        self.mainWidget = QListWidget()
        self.inputType = "midi"

        self.clearNotesButton = QPushButton("Clear Notes")
        self.clearNotesButton.clicked.connect(self.clearNotes)

        self.controlLayout = QVBoxLayout()
        self.controlLayout.addWidget(self.clearNotesButton)

        self.makeBasicWidget()

    def clearNotes(self):
        self.activeNoteItems.clear()
        self.mainWidget.clear()


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
