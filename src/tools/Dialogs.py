from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

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
    def __init__(self):
        super().__init__()
        self.dict = {}
        
        #Set window settings
        self.setWindowTitle("Input script settings")

        #Creating the buttons
        QButton = (QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttonBox = QDialogButtonBox(QButton)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self.buttonBox)

        



        self.setLayout(layout)


    def getDict(self) -> dict:
        return self.dict