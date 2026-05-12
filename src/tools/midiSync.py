from PyQt6.QtWidgets import QDialog, QFileDialog, QPushButton, QLabel, QVBoxLayout, QHBoxLayout
from src.gui.Core import FileDropLineEdit
from src.tools.audioSync import *
from src.tools.fileIO import setDelayForParent

class MidiSync(QDialog):
    def __init__(self, workingPath):
        super().__init__()

        self.pathToAudio = ""
        self.pathToMidi = ""
        self.workingPath = workingPath

        self.MidiDelay = 0

        self.mainLayout = self.makeMainLayout()

        self.setLayout(self.mainLayout)


    def makeMainLayout(self):
        
        mainLayout = QHBoxLayout()
        
        #Inputs

        inputLayout = QVBoxLayout()
        midiLayout = QHBoxLayout()
        audioLayout = QHBoxLayout()


        self.midiInput = FileDropLineEdit()
        self.midiInput.setMinimumWidth(400)
        midiBrouwseButton = QPushButton("Browse")
        midiBrouwseButton.clicked.connect(self.browseMidiFile)

        inputLayout.addWidget(QLabel("Path to the Midi"))
        midiLayout.addWidget(self.midiInput)
        midiLayout.addWidget(midiBrouwseButton)
        inputLayout.addLayout(midiLayout)

        self.audioInput = FileDropLineEdit()
        self.audioInput.setMinimumWidth(400)
        audioBrowseButton = QPushButton("Browse")
        audioBrowseButton.clicked.connect(self.browseAudioFile)
        
        inputLayout.addWidget(QLabel("Path to the audio"))
        audioLayout.addWidget(self.audioInput)
        audioLayout.addWidget(audioBrowseButton)
        inputLayout.addLayout(audioLayout)

        mainLayout.addLayout(inputLayout)

        #Controls

        controlLayout = QVBoxLayout()

        calculateButton = QPushButton("Calculate")
        calculateButton.clicked.connect(self.calculateDelay)

        self.delayLabel = QLabel("Delay: 0.0s")

        saveButton = QPushButton("Save")
        saveButton.clicked.connect(self.saveDelay)

        closeButton = QPushButton("Close")
        closeButton.clicked.connect(self.close)

        controlLayout.addWidget(calculateButton)
        controlLayout.addWidget(self.delayLabel)
        controlLayout.addWidget(saveButton)
        controlLayout.addWidget(closeButton)

        mainLayout.addLayout(controlLayout)

        return mainLayout


    def calculateDelay(self):

        if self.audioInput.text() == "" or self.midiInput.text() == "":
            return

        audioPeaks = getAudioPeaks(self.audioInput.text())
        midiNotes = getMidiNotes(self.midiInput.text())

        if not audioPeaks:
            self.delayLabel.setText("Delay: no audio peaks found")
            return

        if not midiNotes:
            self.delayLabel.setText("Delay: no midi notes found")
            return
        
        bestScore = -1

        for midiNote in midiNotes:
            for audioPeak in audioPeaks:
                candidateDelay = audioPeak["timeMs"] - midiNote["timeMs"]

                score = 0

                for note in midiNotes:
                    expectedAudioTime = note["timeMs"] + candidateDelay

                    for peak in audioPeaks:
                        if abs(peak["timeMs"] - expectedAudioTime) <= 15:
                            score += 1
                            break
                
                if score > bestScore:
                    bestScore = score
                    self.midiDelay = int(candidateDelay)

        self.delayLabel.setText(f"Delay: {float(self.midiDelay) / 1000}s")



    def saveDelay(self):
        setDelayForParent(self.midiInput.text(), self.audioInput.text(), self.workingPath, self.midiDelay)


    def browseMidiFile(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select midi file",
            "",
            "Midi Files (*.mid);;All Files (*)"
        )
        if path:
            self.midiInput.setText(path)


    def browseAudioFile(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "Wave Files (*.wav);;All Files (*)"
        )
        if path:
            self.audioInput.setText(path)