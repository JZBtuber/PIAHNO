from PyQt6.QtWidgets import QDialog, QFileDialog, QPushButton, QLabel, QVBoxLayout, QHBoxLayout
from src.gui.Core import FileDropLineEdit
from src.tools.audioSync import *
from src.tools.fileIO import setDelayForParent


class MidiSync(QDialog):
    """
    Dialog used to synchronize a MIDI file with an audio file.\n
    It calculates the delay between MIDI note-on events and detected audio peaks.
    """
    def __init__(self, workingPath):
        """
        Create the MIDI synchronization dialog.\n
        :param workingPath: Working directory used to save the calculated delay.
        """
        super().__init__()

        #Set default paths
        self.pathToAudio = ""
        self.pathToMidi = ""
        self.workingPath = workingPath

        #Set default delay
        self.MidiDelay = 0

        #Create and set the main layout
        self.mainLayout = self.makeMainLayout()

        self.setLayout(self.mainLayout)


    def makeMainLayout(self):
        """
        Create the main dialog layout.\n
        :returns: Returns the main layout of the dialog.
        """
        #Create the main layout
        mainLayout = QHBoxLayout()
        
        #Inputs

        #Create input layouts
        inputLayout = QVBoxLayout()
        midiLayout = QHBoxLayout()
        audioLayout = QHBoxLayout()


        #Create MIDI path input
        self.midiInput = FileDropLineEdit()
        self.midiInput.setMinimumWidth(400)
        midiBrouwseButton = QPushButton("Browse")
        midiBrouwseButton.clicked.connect(self.browseMidiFile)

        #Add MIDI path widgets
        inputLayout.addWidget(QLabel("Path to the Midi"))
        midiLayout.addWidget(self.midiInput)
        midiLayout.addWidget(midiBrouwseButton)
        inputLayout.addLayout(midiLayout)

        #Create audio path input
        self.audioInput = FileDropLineEdit()
        self.audioInput.setMinimumWidth(400)
        audioBrowseButton = QPushButton("Browse")
        audioBrowseButton.clicked.connect(self.browseAudioFile)
        
        #Add audio path widgets
        inputLayout.addWidget(QLabel("Path to the audio"))
        audioLayout.addWidget(self.audioInput)
        audioLayout.addWidget(audioBrowseButton)
        inputLayout.addLayout(audioLayout)

        mainLayout.addLayout(inputLayout)

        #Controls

        #Create control layout
        controlLayout = QVBoxLayout()

        #Create calculate button
        calculateButton = QPushButton("Calculate")
        calculateButton.clicked.connect(self.calculateDelay)

        #Create delay label
        self.delayLabel = QLabel("Delay: 0.0s")

        #Create save button
        saveButton = QPushButton("Save")
        saveButton.clicked.connect(self.saveDelay)

        #Create close button
        closeButton = QPushButton("Close")
        closeButton.clicked.connect(self.close)

        #Add control widgets
        controlLayout.addWidget(calculateButton)
        controlLayout.addWidget(self.delayLabel)
        controlLayout.addWidget(saveButton)
        controlLayout.addWidget(closeButton)

        mainLayout.addLayout(controlLayout)

        return mainLayout


    def calculateDelay(self):
        """
        Calculate the delay between the MIDI notes and the audio peaks.
        """

        #Guard clause if one of the input paths is empty
        if self.audioInput.text() == "" or self.midiInput.text() == "":
            return

        #Get audio peaks and MIDI notes
        audioPeaks = getAudioPeaks(self.audioInput.text())
        midiNotes = getMidiNotes(self.midiInput.text())

        #Guard clause if no audio peaks were found
        if not audioPeaks:
            self.delayLabel.setText("Delay: no audio peaks found")
            return

        #Guard clause if no MIDI notes were found
        if not midiNotes:
            self.delayLabel.setText("Delay: no midi notes found")
            return
        
        #Set default best score
        bestScore = -1

        #Try every MIDI/audio pair as a possible delay
        for midiNote in midiNotes:
            for audioPeak in audioPeaks:
                candidateDelay = audioPeak["timeMs"] - midiNote["timeMs"]

                score = 0

                #Score the candidate delay by matching notes to nearby peaks
                for note in midiNotes:
                    expectedAudioTime = note["timeMs"] + candidateDelay

                    for peak in audioPeaks:
                        if abs(peak["timeMs"] - expectedAudioTime) <= 15:
                            score += 1
                            break
                
                #Keep the best delay found
                if score > bestScore:
                    bestScore = score
                    self.midiDelay = int(candidateDelay)

        #Show the calculated delay in seconds
        self.delayLabel.setText(f"Delay: {float(self.midiDelay) / 1000}s")



    def saveDelay(self):
        """
        Save the calculated delay for the selected MIDI and audio files.
        """
        #Write the delay to the parent delay file
        setDelayForParent(self.midiInput.text(), self.audioInput.text(), self.workingPath, self.midiDelay)


    def browseMidiFile(self):
        """
        Open a file dialog and set the selected MIDI path.
        """
        #User chooses the MIDI file
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select midi file",
            "",
            "Midi Files (*.mid);;All Files (*)"
        )

        #Set the path if a file was chosen
        if path:
            self.midiInput.setText(path)


    def browseAudioFile(self):
        """
        Open a file dialog and set the selected audio path.
        """
        #User chooses the audio file
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "Wave Files (*.wav);;All Files (*)"
        )

        #Set the path if a file was chosen
        if path:
            self.audioInput.setText(path)