from src.gui.Core import *
from PyQt6.QtWidgets import QProgressBar, QWidget, QPushButton, QCheckBox, QLabel, QDialog, QHBoxLayout, QVBoxLayout, QFileDialog
import os

class VideoLoader(QDialog):
    def __init__(self):
        super().__init__()

        self.path: str = ""
        self.outputPath: str = ""
        self.useOnlyAlgorithm = False

        optionsLayout = self.getOptionsLayout()

        self.setLayout(optionsLayout)


    def start(self):
        if not self.checkPath():
            Message = MessageBox("Path Error!", "The path is empty and needs a file!")
            return
        

    def getOptionsLayout(self):
        #Path Input
        pathInput = FileDropLineEdit()
        pathInput.setPlaceholderText("Video path...")
        pathInput.textChanged.connect(self.pathChanged)
        pathInput.setMinimumWidth(300)

        #Browse button
        browseButton = QPushButton("Browse")
        browseButton.clicked.connect(self.browseFile)

        #Use only algorithm Checkbox
        self.useOnlyAlgorithmCheckBox = QCheckBox("Use Only The Algorithm")
        self.useOnlyAlgorithmCheckBox.stateChanged.connect(self.changeBlackOut)

        #Start button
        startButton = QPushButton("Start")
        startButton.clicked.connect(self.start)
        
        #Make Layouts
        horizontalLayout1 = QHBoxLayout()
        horizontalLayout1.addWidget(pathInput)
        horizontalLayout1.addWidget(browseButton)

        horizontalLayout2 = QHBoxLayout()
        horizontalLayout2.addWidget(self.useOnlyAlgorithmCheckBox)
        horizontalLayout2.addWidget(startButton)

        optionsLayout = QVBoxLayout()
        optionsLayout.addLayout(horizontalLayout1)
        optionsLayout.addLayout(horizontalLayout2)
        return optionsLayout



    def pathChanged(self, str):
        self.path = str
        self.pathInput = os.path.dirname(str)



    def checkPath(self):
        if not self.path == "":
            return True
        else:
            return False
        
    
    def changeBlackOut(self):
        if self.useOnlyAlgorithmCheckBox.isChecked():
            self.useOnlyAlgorithm = True
        else:
            self.useOnlyAlgorithm = False

        

    def browseFile(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "MOV Files (*.MOV);;All Files (*)"
        )
        if path:
            self.pathInput.setText(path)
            self.cameraCheckBox.setChecked(False)

