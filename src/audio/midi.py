import mido
import os
from PyQt6.QtWidgets import QFileDialog, QVBoxLayout, QListWidgetItem, QListWidget, QPushButton
from PyQt6.QtCore import pyqtSignal, QThread
from PyQt6.QtGui import QColor
from src.gui.Core import *
import time


class MidiWorker(basicWorker):
    """
    Worker used to read MIDI notes from a file or live MIDI input.\n
    It emits note-on and note-off signals and can record live MIDI data.
    """
    noteOn = pyqtSignal(int, int)
    noteOff = pyqtSignal(int)

    def __init__(self, path, isLive, sample_rate: int = 44100, chunk: int = 512):
        """
        Create the MIDI worker.\n
        :param path: Path to the MIDI file or live MIDI input name.
        :param isLive: If `True`, the worker uses a live MIDI input.
        :param `int` sample_rate: Sample rate value, defaults to `44100`.
        :param `int` chunk: Chunk size value, defaults to `512`.
        """
        super().__init__(path, isLive)

        # Set default MIDI variables
        self.active_notes = {}

        self.midi = None
        self.events = []
        self.event_index = 0
        self.next_event_time = None
        self.inport = None

    def beforeLoop(self):
        """
        Prepare the MIDI input before the main worker loop starts.
        """
        # Reset current messages and active notes
        self.msg = None
        self.record_msg = None
        self.active_notes.clear()

        # Open live MIDI input
        if self.isLive:
            self.inport = mido.open_input(self.path)
            self.midi = None
            self.events = []
            self.event_index = 0

        # Load MIDI file events
        else:
            self.midi = mido.MidiFile(self.path, clip=True)

            self.events = []
            currentTimeMs = 0.0

            # Convert MIDI event times to absolute milliseconds
            for msg in self.midi:
                currentTimeMs += msg.time * 1000.0
                self.events.append((currentTimeMs, msg))

            self.event_index = 0
            self.inport = None

    def loop(self):
        """
        Run one MIDI loop step.
        """
        # Choose live or file loop
        if self.isLive:
            self.loop_live()
        else:
            self.loop_file()

    def loop_live(self):
        """
        Read and process pending live MIDI messages.
        """
        # Set default message state
        had_message = False

        # Process all pending MIDI messages
        for self.msg in self.inport.iter_pending():
            had_message = True
            self.record_msg = self.msg

            # Handle note-on messages
            if self.msg.type == "note_on" and self.msg.velocity > 0:
                self.active_notes[self.msg.note] = self.msg.velocity
                self.noteOn.emit(self.msg.note, self.msg.velocity)

            # Handle note-off messages
            elif self.msg.type == "note_off" or (self.msg.type == "note_on" and self.msg.velocity == 0):
                self.active_notes.pop(self.msg.note, None)
                self.noteOff.emit(self.msg.note)

        # Sleep briefly if no MIDI message was received
        if not had_message:
            QThread.msleep(5)

    def loop_file(self):
        """
        Read and process MIDI file events according to the master time.
        """
        # Stop if there are no events left
        if self.event_index >= len(self.events):
            self.running = False
            return

        # Get current synchronized time
        nowMs = self.getMasterTimeMs()

        # Process every event that should already be played
        while self.event_index < len(self.events):
            eventTimeMs, msg = self.events[self.event_index]

            if eventTimeMs > nowMs:
                break

            self.msg = msg

            # Handle note-on messages
            if msg.type == "note_on" and msg.velocity > 0:
                self.active_notes[msg.note] = msg.velocity
                self.noteOn.emit(msg.note, msg.velocity)

            # Handle note-off messages
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                self.active_notes.pop(msg.note, None)
                self.noteOff.emit(msg.note)

            self.event_index += 1

        QThread.msleep(1)

    def afterLoop(self):
        """
        Close the live MIDI input after the worker stops.
        """
        # Close the MIDI input port if it is open
        if self.inport is not None:
            try:
                self.inport.close()
            except Exception:
                pass
            self.inport = None

    def initRecording(self):
        """
        Initialize MIDI recording data and output path.
        """
        # Create the recording path
        recordpath = self.getRecordingPath()

        self.newPath = os.path.join(recordpath, f"Midi_{self.ID}.mid")

        os.makedirs(recordpath, exist_ok=True)

        # Create the MIDI recording file and track
        self.midi_recording = mido.MidiFile(ticks_per_beat=480)
        self.track = mido.MidiTrack()
        self.midi_recording.tracks.append(self.track)

        # Set default tempo
        self.tempo = mido.bpm2tempo(120)   # 120 BPM default
        self.track.append(mido.MetaMessage(
            'set_tempo', tempo=self.tempo, time=0))

        # Set starting recording time
        self.last_record_time = time.time()

    def recordloop(self):
        """
        Save one live MIDI message if one is available.
        """
        # Record the last received MIDI message
        if self.record_msg is not None:
            now = time.time()
            delta_seconds = now - self.last_record_time
            self.last_record_time = now

            # Convert elapsed seconds to MIDI ticks
            delta_ticks = int(
                mido.second2tick(
                    delta_seconds,
                    self.midi_recording.ticks_per_beat,
                    self.tempo
                )
            )

            # Add the message to the MIDI track
            self.track.append(self.record_msg.copy(time=delta_ticks))
            self.record_msg = None

    def stopRecording(self):
        """
        Save the recorded MIDI file.
        """
        self.midi_recording.save(self.newPath)


class MidiFeed(basicWindowWidget):
    """
    MIDI feed widget used to display and control MIDI notes.
    """

    def __init__(self, ID: int, workingDir: str = ""):
        """
        Create the MIDI feed widget.\n
        :param `int` ID: ID of the widget.
        :param `str` workingDir: Working directory of the app, defaults to `""`.
        """
        super().__init__(MidiWorker, ID, False, workingDir=workingDir)

        # Set default variables
        self.activeNoteItems = {}
        self.mainWidget = QListWidget()
        self.inputType = "midi"

        # Create clear notes button
        self.clearNotesButton = QPushButton("Clear Notes")
        self.clearNotesButton.clicked.connect(self.clearNotes)

        # Create custom controls layout
        self.controlLayout = QVBoxLayout()
        self.controlLayout.addWidget(self.clearNotesButton)

        # Create the base widget layout
        self.makeBasicWidget()

    def clearNotes(self):
        """
        Clear all displayed MIDI notes.
        """
        # Clear active note tracking and the list widget
        self.activeNoteItems.clear()
        self.mainWidget.clear()

    def midiNoteToName(self, note: int) -> str:  # Gives a name to the note in int
        """
        Convert a MIDI note number to a note name.\n
        :param `int` note: MIDI note number.
        :returns: Returns the note name with octave.
        :rtype: `str`
        """
        # Convert note number to note name and octave
        names = ["C", "C#", "D", "D#", "E", "F",
                 "F#", "G", "G#", "A", "A#", "B"]
        octave = (note // 12) - 1
        return f"{names[note % 12]}{octave}"

    def connectAll(self):
        """
        Connect the MIDI worker signals.
        """
        # Connect note signals to display handlers
        self.worker.noteOn.connect(self.handleNoteOn)
        self.worker.noteOff.connect(self.handleNoteOff)

    def handleNoteOn(self, note: int, velocity: int):  # Prints the received note
        """
        Display a note-on MIDI event.\n
        :param `int` note: MIDI note number.
        :param `int` velocity: MIDI note velocity.
        """
        # Create the note text
        note_name = self.midiNoteToName(note)
        text = f"{note_name} ({note})  vel={velocity}"

        # If already active, refresh text/color and keep at top
        if note in self.activeNoteItems:
            item = self.activeNoteItems[note]
            item.setText(text)
            self.mainWidget.takeItem(self.mainWidget.row(item))
            self.mainWidget.insertItem(0, item)

        # Create a new note item
        else:
            item = QListWidgetItem(text)
            self.activeNoteItems[note] = item
            self.mainWidget.insertItem(0, item)

        # Active = blue
        item.setForeground(QColor("blue"))

    def handleNoteOff(self, note: int):  # Move the now non-active notes down
        """
        Display a note-off MIDI event.\n
        :param `int` note: MIDI note number.
        """
        # Move the note to the inactive section
        if note in self.activeNoteItems:
            item = self.activeNoteItems.pop(note)

            # Make inactive notes black and move them below current active notes
            item.setForeground(QColor("black"))

            self.mainWidget.takeItem(self.mainWidget.row(item))
            self.mainWidget.insertItem(len(self.activeNoteItems), item)

    def browseFile(self):  # File managements
        """
        Open a file dialog and set the selected MIDI path.
        """
        # User chooses the MIDI file
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "MID Files (*.mid);;All Files (*)"
        )

        # Set the path if a file was chosen
        if path:
            self.pathInput.setText(path)
