from PyQt6.QtWidgets import (QDialog, QFileDialog, QPushButton, QLabel,
                             QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy)
from PyQt6.QtGui import QImage, QPixmap
from src.gui.Core import FileDropLineEdit, Qt
from src.tools.fileIO import setDelayForParent
from src.tools.audioSync import getMidiNotes          # reuse existing MIDI parser
import cv2


class VideoSync(QDialog):
    """
    Dialog used to synchronize a video file with a MIDI file.\n
    The user can scrub through the video, add landmarks, calculate the delay, and save it.
    """
    def __init__(self, workingPath):
        """
        Create the video synchronization dialog.\n
        :param workingPath: Working directory used to save the calculated delay.
        """
        super().__init__()

        #Set default paths
        self.pathToVideo = ""
        self.pathToMidi  = ""
        self.workingPath = workingPath

        #Set default sync variables
        self.capture   = None
        self.noteDelay = 0          # current scrub position in ms
        self.notes     = []         # list of {"timeMs": int} landmarks
        self.videoDelay = 0         # calculated offset (ms)

        #Create and set the main layout
        self.setLayout(self._makeMainLayout())

        

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _makeMainLayout(self):
        """
        Create the main dialog layout.\n
        :returns: Returns the main layout of the dialog.
        """
        #Create the main layout
        mainLayout = QVBoxLayout()

        # ── File paths ────────────────────────────────────────────────
        pathGrid = QGridLayout()

        #Create path labels
        videoLabel = QLabel("Input video path:")
        midiLabel  = QLabel("Input MIDI path:")

        #Create path inputs
        self.videoPathInput = FileDropLineEdit()
        self.midiPathInput  = FileDropLineEdit()
        self.videoPathInput.setMinimumWidth(400)
        self.midiPathInput.setMinimumWidth(400)
        self.videoPathInput.setPlaceholderText("Video File...")
        self.midiPathInput.setPlaceholderText("Midi file...")

        #Connect path input changes
        self.videoPathInput.textChanged.connect(self._setVideoPath)
        self.midiPathInput.textChanged.connect(self._setMidiPath)

        #Create browse buttons
        videoBrowseBtn = QPushButton("Browse video")
        midiBrowseBtn  = QPushButton("Browse MIDI")
        videoBrowseBtn.clicked.connect(self._browseVideo)
        midiBrowseBtn.clicked.connect(self._browseMidi)

        #Add path widgets to the grid
        pathGrid.addWidget(videoLabel, 1, 0)
        pathGrid.addWidget(self.videoPathInput, 2, 0)
        pathGrid.addWidget(videoBrowseBtn, 3, 0)

        pathGrid.addWidget(midiLabel, 1, 1)
        pathGrid.addWidget(self.midiPathInput, 2, 1)
        pathGrid.addWidget(midiBrowseBtn, 3, 1)

        mainLayout.addLayout(pathGrid)

        # ── Controls ──────────────────────────────────────────────────
        controlsGrid = QGridLayout()

        # Video preview label
        self.videoLabel = QLabel("")
        self.videoLabel.setMaximumSize(800,800)
        self.videoLabel.setMinimumSize(300,300)
        self.videoLabel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )


        # Scrub buttons row
        scrubLayout = QHBoxLayout()

        #Create scrub steps
        steps = [
            ("-1s", -1000), ("-500ms", -500), ("-100ms", -100),
            ("-50ms", -50),  ("-10ms", -10),
            ("+10ms", +10),  ("+50ms", +50), ("+100ms", +100),
            ("+500ms", +500),  ("+1s", +1000)
        ]

        #Create one scrub button for each step
        for label, delta in steps:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, d=delta: self._scrub(d))
            scrubLayout.addWidget(btn)

        scrubLayout.addStretch()

        # Action panel
        actionLayout = QVBoxLayout()

        #Create action buttons
        loadVideoBtn = QPushButton("Load video")
        addNoteBtn = QPushButton("Add landmark")
        clearNotesBtn = QPushButton("Clear landmarks")
        calcBtn = QPushButton("Calculate")
        saveBtn = QPushButton("Save")
        closeBtn = QPushButton("Close")

        #Create status labels
        self.delayLabel = QLabel("Delay: —")
        self.landmarkLabel = QLabel("Landmarks: 0")

        #Connect action buttons
        loadVideoBtn.clicked.connect(self._loadVideo)
        addNoteBtn.clicked.connect(self._addNote)
        clearNotesBtn.clicked.connect(self._clearNotes)
        calcBtn.clicked.connect(self._calculate)
        saveBtn.clicked.connect(self._save)
        closeBtn.clicked.connect(self.close)

        #Add actions to the action layout
        for w in (loadVideoBtn, addNoteBtn, clearNotesBtn,
                  calcBtn, self.delayLabel, self.landmarkLabel,
                  saveBtn, closeBtn):
            actionLayout.addWidget(w)
        actionLayout.addStretch()

        #Add controls to the grid
        controlsGrid.addWidget(self.videoLabel, 0, 0)
        controlsGrid.addLayout(scrubLayout, 2, 0)
        controlsGrid.addLayout(actionLayout, 0, 1, 3, 1)

        mainLayout.addLayout(controlsGrid)
        return mainLayout

    # ------------------------------------------------------------------
    # Browse / path helpers
    # ------------------------------------------------------------------

    def _browseVideo(self):
        """
        Open a file dialog and set the selected video path.
        """
        #User chooses the video file
        path, _ = QFileDialog.getOpenFileName(
            self, "Select video file", "",
            "MP4 Files (*.mp4);;All Files (*)")
        
        #Set the video path if a file was chosen
        if path:
            self.videoPathInput.setText(path)

    def _browseMidi(self):
        """
        Open a file dialog and set the selected MIDI path.
        """
        #User chooses the MIDI file
        path, _ = QFileDialog.getOpenFileName(
            self, "Select MIDI file", "",
            "MIDI Files (*.mid *.midi);;All Files (*)")
        
        #Set the MIDI path if a file was chosen
        if path:
            self.midiPathInput.setText(path)

    def _setVideoPath(self, path):
        """
        Set the video path.\n
        :param path: New video path.
        """
        self.pathToVideo = path

    def _setMidiPath(self,  path):
        """
        Set the MIDI path.\n
        :param path: New MIDI path.
        """
        self.pathToMidi  = path

    # ------------------------------------------------------------------
    # Video loading & scrubbing
    # ------------------------------------------------------------------

    def _loadVideo(self):
        """
        Load the selected video and show the first frame.
        """
        #Guard clause if there is no selected video
        if not self.pathToVideo:
            return
        
        #Open the video and reset the scrub position
        self.capture = cv2.VideoCapture(self.pathToVideo)
        self.noteDelay = 0
        self._showFrame(0)

    def _scrub(self, deltaMs: int):
        """
        Move the current video position by a time delta.\n
        :param `int` deltaMs: Time to move in milliseconds.
        """
        #Update the current scrub position
        self.noteDelay = max(0, self.noteDelay + deltaMs)

        #Show the frame at the new position
        self._showFrame(self.noteDelay)

    def _showFrame(self, posMs: int):
        """
        Show the video frame at a specific time.\n
        :param `int` posMs: Position in the video in milliseconds.
        """
        #Guard clause if the video is not loaded
        if self.capture is None:
            return
        
        #Seek to the requested video position
        self.capture.set(cv2.CAP_PROP_POS_MSEC, posMs)
        ret, frame = self.capture.read()

        #Guard clause if the frame could not be read
        if not ret:
            return
        
        #Convert the frame to RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        #Create the Qt image
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()

        #Scale and show the image
        self.videoLabel.setPixmap(QPixmap.fromImage(qimg).scaled(self.videoLabel.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    # ------------------------------------------------------------------
    # Landmark management
    # ------------------------------------------------------------------

    def _addNote(self):
        """
        Add a video landmark at the current scrub position.
        """
        #Save the current video position as a landmark
        self.notes.append({"timeMs": self.noteDelay})

        #Update the landmark label
        self.landmarkLabel.setText(f"Landmarks: {len(self.notes)}  (last: {self.noteDelay} ms)")

    def _clearNotes(self):
        """
        Clear all video landmarks.
        """
        #Clear the landmark list
        self.notes.clear()

        #Reset the landmark label
        self.landmarkLabel.setText("Landmarks: 0")

    # ------------------------------------------------------------------
    # Delay calculation  (video landmarks ↔ MIDI note-ons)
    # ------------------------------------------------------------------

    def _calculate(self):
        """
        Calculate the delay between the video landmarks and the MIDI note-on events.
        """
        #Guard clause if there is no MIDI file selected
        if not self.pathToMidi:
            self.delayLabel.setText("Delay: no MIDI file selected!")
            return

        #Load MIDI notes
        midiNotes = getMidiNotes(self.pathToMidi)

        #Guard clause if the MIDI file contains no notes
        if not midiNotes:
            self.delayLabel.setText("Delay: no MIDI notes found!")
            return
        
        #Guard clause if there is no video file selected
        if not self.pathToVideo:
            self.delayLabel.setText("Delay: no Video file selected!")
            return
        
        delay = 0

        #Guard clause if there are no video landmarks
        if self.notes == []:
            self.delayLabel.setText("Delay: no notes set!")
            return
        
        
        #Add each landmark delay
        for i, note in enumerate(self.notes):
            delay += midiNotes[i]["timeMs"] - note["timeMs"]

        #Calculate the average video delay
        self.videoDelay = (delay / len(self.notes))

        #Show the delay in seconds
        self.delayLabel.setText(f"Delay: {float(self.videoDelay) / 1000}s")


    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self):
        """
        Persist the computed delay so MasterClock can pick it up.
        """
        #Save the delay for the selected video and MIDI files
        setDelayForParent(
            self.pathToVideo,
            self.pathToMidi,
            self.workingPath,
            self.videoDelay
        )