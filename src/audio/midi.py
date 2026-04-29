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
        self.inport = None


    def beforeLoop(self):
        self.msg = None
        self.record_msg = None
        self.active_notes.clear()

        if self.isLive:
            self.inport = mido.open_input(self.path)
            self.midi = None
            self.events = []
            self.event_index = 0
        else:
            self.midi = mido.MidiFile(self.path, clip=True)

            self.events = []
            currentTimeMs = 0.0

            for msg in self.midi:
                currentTimeMs += msg.time * 1000.0
                self.events.append((currentTimeMs, msg))

            self.event_index = 0
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

        nowMs = self.getMasterTimeMs()

        while self.event_index < len(self.events):
            eventTimeMs, msg = self.events[self.event_index]

            if eventTimeMs > nowMs:
                break

            self.msg = msg

            if msg.type == "note_on" and msg.velocity > 0:
                self.active_notes[msg.note] = msg.velocity
                self.noteOn.emit(msg.note, msg.velocity)

            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                self.active_notes.pop(msg.note, None)
                self.noteOff.emit(msg.note)

            self.event_index += 1

        QThread.msleep(1)

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
    def __init__(self, ID: int, workingDir:str = ""):
        super().__init__(MidiWorker, ID, False, workingDir=workingDir)

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
