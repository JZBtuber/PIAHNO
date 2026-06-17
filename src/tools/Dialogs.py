from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QLineEdit, QFileDialog, QPushButton, QHBoxLayout

class ConfirmRemoveDialog(QDialog):
    """
    Ask for the confirmation to delete an item.
    """
    def __init__(self, item: str) -> None:
        """
        Create a dialog for confirmation to remove an item.\n
        :param `str` item: Item that will be removed.
        """
        super().__init__()

        #Set window settings
        self.setWindowTitle("Please confirm.")

        #Creating the buttons
        QButton = (QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.Cancel)
        self.buttonBox = QDialogButtonBox(QButton)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        #Creating the question label
        label = QLabel(f"\"{item}\" will be removed, do you want to proceed?")

        #Set the layout
        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.buttonBox)
        self.setLayout(layout)


class GetTestInformationDialog(QDialog):
    """
    Get information for a test.
    """
    def __init__(self) -> None:
        super().__init__()
        self.dict = {}
        filesToLoad = []
        
        # Set window settings
        self.setWindowTitle("Input script settings")

        # Creating the buttons
        QButton = (QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttonBox = QDialogButtonBox(QButton)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        # Inputs
        nameLabel = QLabel("Name of the test")

        self.nameInput = QLineEdit()
        self.nameInput.setPlaceholderText("Name of the test...")

        scriptLayout = QHBoxLayout()

        self.scriptInput = QLineEdit()
        self.scriptInput.setPlaceholderText("ScriptFile...")
        self.scriptInput.setMinimumSize(400, 30)

        scriptBrowseButton = QPushButton("Browse scripts")
        scriptBrowseButton.clicked.connect(self.browseScripts)

        scriptLayout.addWidget(self.scriptInput)
        scriptLayout.addWidget(scriptBrowseButton)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(nameLabel)
        layout.addWidget(self.nameInput)
        layout.addLayout(scriptLayout)

        layout.addWidget(self.buttonBox)
        

        self.setLayout(layout)


    def getDict(self) -> dict:
        if not self.nameLabel.text():
            return
        
        self.dict = {"name" : self.nameLabel.text(),
                     "scriptPath" : self.scriptInput.text()}

        return self.dict
    


    def browseScripts(self):
        """
        Open a file dialog and set the selected script.
        """
        # User chooses the input file
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a script",
            "",
            "Python Files (*.py);;All Files (*)"
        )

        # Set the path if a file was chosen
        if path:
            self.scriptInput.setText(path)