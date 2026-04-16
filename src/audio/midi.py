from mido import MidiFile
from PyQt6.QtWidgets import QCheckBox, QWidget, QHBoxLayout, QVBoxLayout, QListWidgetItem, QLabel, QListWidget, QPushButton, QLineEdit
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from PyQt6.QtGui import QColor
class MidiWorker(QObject):
    noteOn = pyqtSignal(int, int)
    noteOff = pyqtSignal(int)
    finished =pyqtSignal()


    def __init__(self, midiPath: str):
        super().__init__()
        self.midiPath = midiPath
        self.running = False
        self.paused = False
        self.muted = True

        self.audioPlayer = None

    def run(self):
        self.running = True
        midi = MidiFile(self.midiPath, clip=True)

        for msg in midi.play():
            if not self.running:
                break

            while self.paused:
                QThread.msleep(50)
                continue

            if msg.type == "note_on" and msg.velocity > 0:
                self.noteOn.emit(msg.note, msg.velocity)
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity <= 0):
                self.noteOff.emit(msg.note)

        self.finished.emit()


    def setMuted(self, muted: bool):
        self.muted = muted
        if self.audioPlayer is not None:
            # depends on what audio system you use later
            # self.audioPlayer.setMuted(muted)
            # or:
            # self.audioPlayer.setVolume(0 if muted else 100)
            pass


    def stop(self):
        self.running = False


    def pause(self):
        self.paused = True


    def resume(self):
        self.paused = False


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

        self.thread = QThread()
        self.worker = MidiWorker(self.pathInput.text())
        try:
            self.muteChanged.disconnect()
        except:
            pass

        self.muteChanged.connect(self.worker.setMuted)

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.noteOn.connect(self.handleNoteOn)
        self.worker.noteOff.connect(self.handleNoteOff)
        self.worker.finished.connect(self.thread.quit)

        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

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

        # Optional: clear active highlighting when stopped
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

        

        