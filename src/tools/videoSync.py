from PyQt6.QtWidgets import (QDialog, QFileDialog, QPushButton, QLabel,
                             QVBoxLayout, QHBoxLayout, QGridLayout)
from PyQt6.QtGui import QImage, QPixmap
from src.gui.Core import FileDropLineEdit
from src.tools.fileIO import setDelayForParent
from src.tools.audioSync import getMidiNotes          # reuse existing MIDI parser
import cv2


class VideoSync(QDialog):
    def __init__(self, workingPath):
        super().__init__()

        self.pathToVideo = ""
        self.pathToMidi  = ""
        self.workingPath = workingPath

        self.capture   = None
        self.noteDelay = 0          # current scrub position in ms
        self.notes     = []         # list of {"timeMs": int} landmarks
        self.videoDelay = 0         # calculated offset (ms)

        self.setLayout(self._makeMainLayout())

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _makeMainLayout(self):
        mainLayout = QVBoxLayout()

        # ── File paths ────────────────────────────────────────────────
        pathGrid = QGridLayout()

        videoLabel = QLabel("Input video path:")
        midiLabel  = QLabel("Input MIDI path:")

        self.videoPathInput = FileDropLineEdit()
        self.midiPathInput  = FileDropLineEdit()
        self.videoPathInput.setMinimumWidth(400)
        self.midiPathInput.setMinimumWidth(400)

        self.videoPathInput.textChanged.connect(self._setVideoPath)
        self.midiPathInput.textChanged.connect(self._setMidiPath)

        videoBrowseBtn = QPushButton("Browse video")
        midiBrowseBtn  = QPushButton("Browse MIDI")
        videoBrowseBtn.clicked.connect(self._browseVideo)
        midiBrowseBtn.clicked.connect(self._browseMidi)

        pathGrid.addWidget(videoLabel,          1, 0)
        pathGrid.addWidget(self.videoPathInput, 2, 0)
        pathGrid.addWidget(videoBrowseBtn,      3, 0)

        pathGrid.addWidget(midiLabel,           1, 1)
        pathGrid.addWidget(self.midiPathInput,  2, 1)
        pathGrid.addWidget(midiBrowseBtn,       3, 1)

        mainLayout.addLayout(pathGrid)

        # ── Controls ──────────────────────────────────────────────────
        controlsGrid = QGridLayout()

        # Video preview label
        self.videoLabel = QLabel("")

        # Scrub buttons row
        scrubLayout = QHBoxLayout()

        steps = [
            ("-1s",    -1000), ("-500ms", -500), ("-100ms", -100),
            ("-50ms",   -50),  ("-10ms",   -10),
            ("+10ms",   +10),  ("+50ms",   +50), ("+100ms", +100),
            ("+500ms", +500),  ("+1s",    +1000),
        ]
        for label, delta in steps:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, d=delta: self._scrub(d))
            scrubLayout.addWidget(btn)

        scrubLayout.addStretch()

        # Action panel
        actionLayout = QVBoxLayout()

        loadVideoBtn  = QPushButton("Load video")
        addNoteBtn    = QPushButton("Add landmark")
        clearNotesBtn = QPushButton("Clear landmarks")
        calcBtn       = QPushButton("Calculate")
        saveBtn       = QPushButton("Save")
        closeBtn      = QPushButton("Close")

        self.delayLabel     = QLabel("Delay: —")
        self.landmarkLabel  = QLabel("Landmarks: 0")

        loadVideoBtn.clicked.connect(self._loadVideo)
        addNoteBtn.clicked.connect(self._addNote)
        clearNotesBtn.clicked.connect(self._clearNotes)
        calcBtn.clicked.connect(self._calculate)
        saveBtn.clicked.connect(self._save)
        closeBtn.clicked.connect(self.close)

        for w in (loadVideoBtn, addNoteBtn, clearNotesBtn,
                  calcBtn, self.delayLabel, self.landmarkLabel,
                  saveBtn, closeBtn):
            actionLayout.addWidget(w)
        actionLayout.addStretch()

        controlsGrid.addWidget(self.videoLabel,  0, 0)
        controlsGrid.addLayout(scrubLayout,      2, 0)
        controlsGrid.addLayout(actionLayout,     0, 1, 3, 1)

        mainLayout.addLayout(controlsGrid)
        return mainLayout

    # ------------------------------------------------------------------
    # Browse / path helpers
    # ------------------------------------------------------------------
    def _browseVideo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select video file", "",
            "MP4 Files (*.mp4);;All Files (*)")
        if path:
            self.videoPathInput.setText(path)

    def _browseMidi(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select MIDI file", "",
            "MIDI Files (*.mid *.midi);;All Files (*)")
        if path:
            self.midiPathInput.setText(path)

    def _setVideoPath(self, path): self.pathToVideo = path
    def _setMidiPath(self,  path): self.pathToMidi  = path

    # ------------------------------------------------------------------
    # Video loading & scrubbing
    # ------------------------------------------------------------------
    def _loadVideo(self):
        if not self.pathToVideo:
            return
        self.capture = cv2.VideoCapture(self.pathToVideo)
        self.noteDelay = 0
        self._showFrame(0)

    def _scrub(self, deltaMs: int):
        self.noteDelay = max(0, self.noteDelay + deltaMs)
        self._showFrame(self.noteDelay)

    def _showFrame(self, posMs: int):
        if self.capture is None:
            return
        self.capture.set(cv2.CAP_PROP_POS_MSEC, posMs)
        ret, frame = self.capture.read()
        if not ret:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
        self.videoLabel.setPixmap(QPixmap.fromImage(qimg))

    # ------------------------------------------------------------------
    # Landmark management
    # ------------------------------------------------------------------
    def _addNote(self):
        self.notes.append({"timeMs": self.noteDelay})
        self.landmarkLabel.setText(f"Landmarks: {len(self.notes)}  (last: {self.noteDelay} ms)")

    def _clearNotes(self):
        self.notes.clear()
        self.landmarkLabel.setText("Landmarks: 0")

    # ------------------------------------------------------------------
    # Delay calculation  (video landmarks ↔ MIDI note-ons)
    # ------------------------------------------------------------------
    def _calculate(self):
        if not self.pathToMidi:
            self.delayLabel.setText("Delay: no MIDI file selected!")
            return

        midiNotes = getMidiNotes(self.pathToMidi)
        if not midiNotes:
            self.delayLabel.setText("Delay: no MIDI notes found!")
            return
        
        delay = 0
        
        for i, note in enumerate(self.notes):
            delay += midiNotes[i]["timeMs"] - note["timeMs"]

        self.videoDelay = (delay / len(self.notes))

        self.delayLabel.setText(f"Delay: {float(self.videoDelay) / 1000}s")


    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    def _save(self):
        """Persist the computed delay so MasterClock can pick it up."""
        setDelayForParent(
            self.pathToVideo,
            self.pathToMidi,
            self.workingPath,
            self.videoDelay
        )
