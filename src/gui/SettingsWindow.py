from PyQt6.QtWidgets import QDialog, QPushButton, QVBoxLayout, QHBoxLayout, QLineEdit, QDoubleSpinBox, QWidget, QScrollArea, QLabel, QSizePolicy, QCheckBox, QComboBox, QGridLayout, QDialogButtonBox
from PyQt6.QtCore import Qt
import copy
from os import path
from src.tools.fileIO import saveSettings
from src.gui.Core import QFileDialog
from src.tools.Dialogs import ConfirmRemoveDialog, GetTestInformationDialog


class SettingBox(QDialog):
    """
    Settings menu to the app in a "QDialog" box.
    """

    def __init__(self, mainSettings):
        """
        Create the settings dialog.\n
        :param mainSettings: Settings dictionary used by the main window.
        """
        super().__init__()
        self.setFixedSize(1000, 800)

        # Flags
        self.addParticipantFlag = None

        # Keep a temporary copy until the user saves
        settings = copy.deepcopy(mainSettings)
        self.participants = []
        self.tests = []
        self.testsDicts = []

        # Create the close button
        QButton = (QDialogButtonBox.StandardButton.Save |
                   QDialogButtonBox.StandardButton.Cancel)
        self.buttonBox = QDialogButtonBox(QButton)
        self.buttonBox.accepted.connect(
            lambda: self.saveAndClose(settings, mainSettings))
        self.buttonBox.rejected.connect(self.reject)

        closeButton = QPushButton("Save and close")
        closeButton.clicked.connect(
            lambda: self.saveAndClose(settings, mainSettings))
        closeButton.setMaximumSize(100, 40)

        # Create the settings list layout
        layout = QVBoxLayout()

        # Code name of the patient
        scroll = self._getParticipantNamesWidget(settings)
        layout.addLayout(self._addSetting("Code name of the test subject",
                                          "Set the code name under which the recorded files will be saved",
                                          scroll), 1)

        # Test to use
        #test = self._getCurrentTestWidget(settings)
        #layout.addLayout(self._addSetting("Default test to use",
        #                                  "Set the default test to use when using a script",
        #                                  test), 1)

        # Path to the recording directory
        self.dirInput = QLineEdit()
        self.dirInput.setPlaceholderText("Path to the directory")
        self.dirInput.setText(settings["pathToWorkingDir"])
        self.dirInput.textChanged.connect(
            lambda text: settings.__setitem__("pathToWorkingDir", text))

        # Browse button for the save directory
        browseButton = QPushButton("Browse")
        browseButton.clicked.connect(self.findDir)

        # Create the directory input layout
        dirInputLayout = QHBoxLayout()
        dirInputLayout.setContentsMargins(0, 0, 0, 0)
        dirInputLayout.addWidget(self.dirInput, 0)
        dirInputLayout.addWidget(browseButton, 0)
        dirInputLayout.addStretch()

        # Create the directory input widget
        dirChoice = QWidget()
        dirChoice.setLayout(dirInputLayout)
        dirChoice.setMinimumSize(600, 40)

        layout.addLayout(self._addSetting("Path to the save directory",
                                          "Set the set the path to the directory where the different test subject files will be saved",
                                          dirChoice), 0)

        # Choice of the detection confidence
        detectionConfidence = QDoubleSpinBox()
        detectionConfidence.setValue(settings["detectionConfidence"])
        detectionConfidence.setMaximum(1.0)
        detectionConfidence.setMinimum(0.0)
        detectionConfidence.setDecimals(2)
        detectionConfidence.setSingleStep(0.05)
        detectionConfidence.valueChanged.connect(
            lambda value: settings.__setitem__("detectionConfidence", value))

        layout.addLayout(self._addSetting("Detection Confidence for the algorithm",
                                          "Set the detection confidence score requiered for the palm detection model to identify a hand",
                                          detectionConfidence), 0)

        # Choice of the tracking confidence
        trackingConfidence = QDoubleSpinBox()
        trackingConfidence.setValue(settings["trackingConfidence"])
        trackingConfidence.setMaximum(1.0)
        trackingConfidence.setMinimum(0.0)
        trackingConfidence.setDecimals(2)
        trackingConfidence.setSingleStep(0.05)
        trackingConfidence.valueChanged.connect(
            lambda value: settings.__setitem__("trackingConfidence", value))

        layout.addLayout(self._addSetting("Tracking Confidence for the algorithm",
                                          "Set the traquing confidence score requiered for the palm detection model to maintain the hand between frames",
                                          trackingConfidence), 0)

        # Choice of the presence confidence
        presenceConfidence = QDoubleSpinBox()
        presenceConfidence.setValue(settings["presenceConfidence"])
        presenceConfidence.setMaximum(1.0)
        presenceConfidence.setMinimum(0.0)
        presenceConfidence.setDecimals(2)
        presenceConfidence.setSingleStep(0.05)
        presenceConfidence.valueChanged.connect(
            lambda value: settings.__setitem__("presenceConfidence", value))

        layout.addLayout(self._addSetting("Presence Confidence for the algorithm",
                                          "Set the presence confidence score requiered for the palm detection model to find the hand if it is partialy covered or on the edge of the screen",
                                          presenceConfidence), 0)

        # Depth camera options
        self.checkZed(settings, layout)

        # Add participants to the scroll bar
        for participant in settings["participantNames"]:
            self._addParticipant(self.participantscroll, participant)

        # Add tests to the scroll bar
        for test in settings["testNames"]:
            self._addTest(self.testscroll, test)

        # Add empty space at the bottom of the settings
        layout.addStretch()

        # Create the settings scroll area
        settingList = QScrollArea()
        settingList.setWidgetResizable(True)
        container = QWidget()
        container.setLayout(layout)
        settingList.setWidget(container)

        # Create the main layout
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(settingList, 1)
        mainLayout.addWidget(self.buttonBox, 0)
        self.setLayout(mainLayout)

    # ---------------------------------------------------
    # Setting widget creation
    # ---------------------------------------------------

    @staticmethod
    def _addSetting(name: str, description: str, widget: QWidget) -> QVBoxLayout:
        """
        Add a setting to the list and does its styling.\n
        :param `str` name: Name of the setting.
        :param `str` description: Description of the setting.
        :param `QWidget` widget: Widget used to edit the setting.
        :returns: Returns the layout containing the setting.
        :rtype: `QVBoxLayout`
        """
        # Create the setting layout
        layout = QVBoxLayout()

        # Create the setting name label
        nameLabel = QLabel(name)
        nameLabel.setObjectName("nameLabel")
        nameLabel.setStyleSheet("""
                                QLabel#nameLabel {
                                    color :  #FFFF00;
                                    font-size: 18px;
                                    font-weight : bold;
                                }                                
        """)
        descriptionLabel = QLabel(description)

        # Add setting widgets to the layout
        layout.addWidget(nameLabel, 0)
        layout.addWidget(descriptionLabel, 0)
        widget.setSizePolicy(QSizePolicy.Policy.Fixed,
                             QSizePolicy.Policy.MinimumExpanding)
        widget.setMaximumSize(650, 500)
        layout.addWidget(widget, 1)
        layout.setContentsMargins(0, 10, 0, 10)

        return layout

    # ---------------------------------------------------
    # Depth camera settings
    # ---------------------------------------------------

    def checkZed(self, settings, layout) -> None:
        """
        Options for the Zed depth camera.\n
        :param settings: Settings dictionary to update.
        :param layout: Layout where the Zed settings will be added.
        """
        # Check if the depth camera module is available
        settings["depthCameraAvailable"] = self._checkPyzed()

        # Guard clause if the depth camera module is not available
        if not settings["depthCameraAvailable"]:
            return

        # Enabling the depth camera
        zedCheckBox = QCheckBox("Make the depth camera available")
        zedCheckBox.setChecked(settings["depthCameraAvailable"])
        zedCheckBox.stateChanged.connect(
            lambda checked: settings.__setitem__("depthCameraAvailable", bool(checked)))

        layout.addLayout(self._addSetting("Use depth cameras",
                                          "Make the use of Zed depth camera available when recording",
                                          zedCheckBox), 1)
 
        # Minimum depth
        zedMinDepth = QDoubleSpinBox()
        zedMinDepth.setValue(settings["zedDepthMin"])
        zedMinDepth.setMaximum(1.0)
        zedMinDepth.setMinimum(0.2)
        zedMinDepth.setDecimals(2)
        zedMinDepth.setSingleStep(0.01)
        zedMinDepth.valueChanged.connect(
            lambda value: settings.__setitem__("zedDepthMin", value))

        layout.addLayout(self._addSetting("Minimum depth",
                                          "Set the minimum depth for the Zed depth camera",
                                          zedMinDepth), 0)

        # Maximum depth
        zedMaxDepth = QDoubleSpinBox()
        zedMaxDepth.setValue(settings["zedDepthMax"])
        zedMaxDepth.setMaximum(10.0)
        zedMaxDepth.setMinimum(1.0)
        zedMaxDepth.setDecimals(2)
        zedMaxDepth.setSingleStep(0.01)
        zedMaxDepth.valueChanged.connect(
            lambda value: settings.__setitem__("zedDepthMax", value))

        layout.addLayout(self._addSetting("Maximum depth",
                                          "Set the maximum depth for the Zed depth camera",
                                          zedMaxDepth), 0)

        # Choice of resolution (vga to 2k)
        zedResolution = QComboBox()
        zedResolution.addItems(["VGA", "HD720", "HD1080", "HD2K"])
        zedResolution.setCurrentText(
            settings["zedResolution"] if settings["zedResolution"] is not None else "HD1080")
        zedResolution.currentTextChanged.connect(
            lambda: self._updateComboBox(zedResolution.currentText(), settings))

        layout.addLayout(self._addSetting("Resolution",
                                          "Set the resolution for the zed depth camera",
                                          zedResolution), 0)

        # Choice of Fps to use
        self.zedFps = QComboBox()
        self._updateComboBox(zedResolution.currentText(), settings)
        self.zedFps.setCurrentText(f"{str(settings["zedFps"])}FPS")
        self.zedFps.currentTextChanged.connect(lambda: settings.__setitem__("zedFps", int(
            self.zedFps.currentText().removesuffix("FPS"))) if self.zedFps.currentText() else 0)

        layout.addLayout(self._addSetting("Frame rate",
                                          "Set the maximum frame rate for the zed depth camera",
                                          self.zedFps), 0)

        # Choice of mode to use
        zedMode = QComboBox()
        zedMode.addItems(["Neural_Light", "Neural", "Neural_Complete"])
        zedMode.currentTextChanged.connect(
            lambda: settings.__setitem__("zedMode", zedMode.currentText()))
        zedMode.setCurrentText(
            settings["zedMode"] if settings["zedMode"] is not None else "Neural_Light")

        layout.addLayout(self._addSetting("Mode",
                                          "Set the mode for the depth camera neural network",
                                          zedMode), 0)

    def _updateComboBox(self, value: str, settings) -> None:
        """
        Update the "zedFps" combo box to only contain the supported Fps for the chosen resolution.\n
        :param `str` value: Selected Zed resolution.
        :param settings: Settings dictionary to update.
        """
        # Save the selected resolution
        settings["zedResolution"] = value

        # Get current settings and resolution options
        fps = settings["zedFps"]
        options = ["VGA", "HD720", "HD1080", "HD2K"]

        # Reset the FPS combo box
        self.zedFps.clear()
        self.zedFps.addItems(["15FPS", "30FPS", "60FPS", "100FPS"])

        # Remove unsupported FPS values for the selected resolution
        for i in range(0, self.zedFps.count()):
            if value == options[i]:
                maxFps = int(self.zedFps.itemText(
                    self.zedFps.count() - 1).removesuffix("FPS"))
                self.zedFps.setCurrentText(f"{min(fps, maxFps)}FPS")
                settings["zedFps"] = min(fps, maxFps)
                return
            else:
                self.zedFps.removeItem(self.zedFps.count() - 1)

        # Clear the FPS setting if no valid option was found
        self.zedFps.setCurrentText("")
        self.zedFps.removeItem(0)
        settings["zedFps"] = 0

    # ---------------------------------------------------
    # Settings saving
    # ---------------------------------------------------

    def saveAndClose(self, settings, mainSettings):
        """
        Saving the app settings and closing the settings dialog.\n
        :param settings: Temporary settings dictionary.
        :param mainSettings: Main settings dictionary to update.
        """
        # Save the temporary settings into the main settings
        settings["participantNames"] = [participant.text()
                                        for participant in self.participants]
        settings["participantName"] = self.participantName.text()

        testName = self.testName.text()

        settings["testName"] = ""
        for i, dict in enumerate(self.testsDicts):
            if dict["name"] == testName:
                settings["testName"] = self.testsDicts[i]
                break

        settings["testNames"] = [dict for dict in self.testsDicts]

        mainSettings.clear()
        mainSettings.update(settings)

        # Write the settings to file
        saveSettings()

        # Close the dialog
        self.accept()

    def findDir(self):
        """
        Get the user's chosen directory then set the input to its path.
        """
        # User chooses the save directory
        dirName = QFileDialog.getExistingDirectory(
            self,
            "Select a directory",
            "",
            QFileDialog.Option.ShowDirsOnly
        )

        # Update the directory input if a directory was chosen
        if dirName:
            self.dirInput.setText(str(path.abspath(dirName)))

    @staticmethod
    def _checkPyzed() -> bool:
        """
        Check if the pyzed module is installed.\n
        :returns: Returns `True` if pyzed can be imported, otherwise returns `False`.
        :rtype: `bool`
        """
        # Try to import the Zed module
        try:
            import pyzed.sl
        except ImportError:
            return False
        return True

    # -------------------------------------------------
    # Participant scroll area
    # -------------------------------------------------

    def _getParticipantNamesWidget(self, settings: dict) -> QVBoxLayout:
        """
        Get a widget containing the option to chose the participant.\n
        :param `dict` settings: Settings of the app in a dictionary.
        :returns: A widget containing the names of participants.
        :rtype: `QVBoxLayout`
        """

        self.participantscroll = QVBoxLayout()
        mainWidget = QWidget()

        # Container widget settings
        containerWidget = QWidget()
        containerWidget.setLayout(self.participantscroll)
        containerWidget.setMaximumWidth(540)

        # Create the scroll area and settings
        scrollArea = QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scrollArea.setWidget(containerWidget)
        scrollArea.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        # button to add a new participant
        addButton = QPushButton("Add")
        addButton.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        addButton.clicked.connect(
            lambda: self._addParticipant(self.participantscroll))

        # Button to remove the selected participant
        removeButton = QPushButton("Remove")
        removeButton.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        removeButton.clicked.connect(self._removeParticipant)

        # Label for the selected participant
        self.participantName = QLabel(settings["participantName"])
        self.participantName.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Create the participant layout and set settings
        participantLayout = QGridLayout()
        participantLayout.setColumnStretch(0, 1)
        participantLayout.setColumnStretch(1, 1)
        participantLayout.setRowStretch(0, 0)
        participantLayout.setRowStretch(1, 1)
        participantLayout.setRowStretch(2, 1)

        # Add the widget to the layout
        participantLayout.addWidget(self.participantName, 0, 1, 1, 1)
        participantLayout.addWidget(scrollArea, 1, 1, 2, 1)
        participantLayout.addWidget(addButton, 1, 0, 1, 1)
        participantLayout.addWidget(removeButton, 2, 0, 1, 1)

        # Set the scroll area settings
        scrollArea.setSizePolicy(QSizePolicy.Policy.Fixed,
                                 QSizePolicy.Policy.MinimumExpanding)
        scrollArea.setMinimumSize(550, 300)

        # return a layout
        mainWidget.setLayout(participantLayout)
        return mainWidget

    def _addParticipant(self, layout: QVBoxLayout, name: str = "") -> None:
        """
        Add a participant to the list available.\n
        :param `QVBoxLayout` layout: Layout to add the created layout to.
        :param `str` name: Name of the participant to add directly.
        """
        # Guard clause if the button is clicked twice
        if self.addParticipantFlag:
            layout.removeWidget(self.addParticipantFlag)
            self.addParticipantFlag = None
            return

        # Set the settings for the layout.
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Guard clause for if the name is given. Directly add the label
        if name:
            self._addParticipantLabel(layout, name)
            return

        # Inputs for the name input.
        addButton = QPushButton("Add")
        inputLineEdit = QLineEdit()
        addButton.clicked.connect(
            lambda: self._addParticipantLabel(layout, inputLineEdit.text()))

        # layout for the inputs
        addLayout = QHBoxLayout()
        addLayout.addWidget(inputLineEdit, 0)
        addLayout.addWidget(addButton, 0)

        # Container widget for the layout
        container = QWidget()
        container.setLayout(addLayout)

        layout.insertWidget(0, container)

        self.addParticipantFlag = container

    def _addParticipantLabel(self, layout: QVBoxLayout, name: str) -> None:
        """
        Add a label to the `layout` parameter with the `name` text.\n
        :param `QVBoxLayout` layout: Layout to which the label will be added.
        :param `str` name: Name to add to the list.
        """
        # Remove the add layout if it already exist.
        if self.addParticipantFlag:
            layout.removeWidget(self.addParticipantFlag)
            self.addParticipantFlag = None

        # If the name is empty, returns
        if not name:
            return

        # Create and set the label's settings
        nameLabel = QLabel(name)
        nameLabel.setObjectName("nameLabel")
        nameLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nameLabel.setStyleSheet("""
                                QLabel#nameLabel {
                                border-width: 1px;
                                border-style : solid;
                                font-weight : bold;
                                }""")
        nameLabel.mousePressEvent = lambda _: self._updateChosenName(nameLabel)

        # Add the label to the list
        layout.addWidget(nameLabel)
        self.participants.append(nameLabel)

        # If the list is empty, set the name as chosen
        if not self.participantName.text():
            self.participantName.setText(name)

    def _updateChosenName(self, label: QLabel) -> None:
        """
        Update the chosen name's label.
        :param `QLabel` label: Label to add to the list.
        """
        self.participantName.setText(label.text())

    def _removeParticipant(self) -> None:
        """
        Remove the chosen participant's label.
        """
        current_name = self.participantName.text()

        # Remove the label with the same name as chosen
        for label in self.participants:
            if label.text() == current_name:

                # Ask for confirmation before deleting
                dialog = ConfirmRemoveDialog(current_name)
                result = dialog.exec()

                if result:
                    self.participantscroll.removeWidget(label)
                    label.setParent(None)
                    label.deleteLater()
                    self.participants.remove(label)
                elif dialog.rejected:
                    return

                break

        # Change the chosen name
        if self.participants:
            self.participantName.setText(self.participants[0].text())
        else:
            self.participantName.setText("")

    # -------------------------------------------------
    # Tests scroll area
    # -------------------------------------------------

    def _getCurrentTestWidget(self, settings):
        """
        Get a widget containing the option to chose the test to run.\n
        :param `dict` settings: Settings of the app in a dictionary.
        :returns: A widget containing the names of the test.
        :rtype: `QVBoxLayout`
        """

        self.testscroll = QVBoxLayout()
        mainWidget = QWidget()

        # Container widget settings
        containerWidget = QWidget()
        containerWidget.setLayout(self.testscroll)
        containerWidget.setMaximumWidth(540)

        # Create the scroll area and settings
        scrollArea = QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scrollArea.setWidget(containerWidget)
        scrollArea.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        # button to add a new test
        addButton = QPushButton("Add")
        addButton.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        addButton.clicked.connect(lambda: self._addTest(self.testscroll))

        # Button to remove the selected test
        removeButton = QPushButton("Remove")
        removeButton.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        removeButton.clicked.connect(self._removeTest)

        # Label for the selected test
        if "name" in settings["testName"]:
            self.testName = QLabel(settings["testName"]["name"])
        else:
            self.testName = QLabel("")
        self.testName.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Create the test layout and set settings
        testLayout = QGridLayout()
        testLayout.setColumnStretch(0, 1)
        testLayout.setColumnStretch(1, 1)
        testLayout.setRowStretch(0, 0)
        testLayout.setRowStretch(1, 1)
        testLayout.setRowStretch(2, 1)

        # Add the widget to the layout
        testLayout.addWidget(self.testName, 0, 1, 1, 1)
        testLayout.addWidget(scrollArea, 1, 1, 2, 1)
        testLayout.addWidget(addButton, 1, 0, 1, 1)
        testLayout.addWidget(removeButton, 2, 0, 1, 1)

        # Set the scroll area settings
        scrollArea.setSizePolicy(QSizePolicy.Policy.Fixed,
                                 QSizePolicy.Policy.MinimumExpanding)
        scrollArea.setMinimumSize(550, 300)

        # return a layout
        mainWidget.setLayout(testLayout)
        return mainWidget

    def _addTest(self, layout: QVBoxLayout, dict_: dict = {}) -> None:
        """
        Add a test to the list available.\n
        :param `QVBoxLayout` layout: Layout to add the created layout to.
        :param `dict` dict_: Ditionnary of the test to add directly.
        """
        # Set the settings for the layout.
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Guard clause for if the name is given. Directly add the label
        if dict_:
            self._addTestLabel(layout, dict_)
            return

        dict_ = {"name": "test1", "scriptPath": "",
                 "filesToInclude": ["", "", ""]}

        dialog = GetTestInformationDialog()
        result = dialog.exec()

        if result:
            self._addTest(layout, dialog.getDict())
        else:
            return

    def _addTestLabel(self, layout: QVBoxLayout, dict_: dict = {}) -> None:
        """
        Add a label to the `layout` parameter with the `dict_["name"]` text.\n
        :param `QVBoxLayout` layout: Layout to which the label will be added.
        :param `dict` dict_: Dictionnary with the test name to add to the list.
        """
        # If the name is empty, returns
        if not dict_:
            return
        else:
            self.testsDicts.append(dict_)

        # Create and set the label's settings
        nameLabel = QLabel(dict_["name"])
        nameLabel.setObjectName("nameLabel")
        nameLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nameLabel.setStyleSheet("""
                                QLabel#nameLabel {
                                border-width: 1px;
                                border-style : solid;
                                font-weight : bold;
                                }""")
        nameLabel.mousePressEvent = lambda _: self._updateChosentest(nameLabel)

        # Add the label to the list
        layout.addWidget(nameLabel)
        self.tests.append(nameLabel)

        # If the list is empty, set the name as chosen
        if not self.testName.text():
            self.testName.setText(dict_["name"])

    def _updateChosentest(self, label: QLabel) -> None:
        """
        Update the chosen test's label.
        :param `QLabel` label: Label to add to the list.
        """
        self.testName.setText(label.text())

    def _removeTest(self) -> None:
        """
        Remove the chosen test's label.
        """
        currentTest = self.testName.text()

        # Remove the label with the same name as chosen
        for label in self.tests:
            if label.text() == currentTest:

                # Ask for confirmation before deleting
                dialog = ConfirmRemoveDialog(currentTest)
                result = dialog.exec()

                if result:
                    self.testscroll.removeWidget(label)
                    label.setParent(None)
                    label.deleteLater()
                    self.tests.remove(label)
                else:
                    return

                break

        for test in self.testsDicts:
            if test["name"] == currentTest:
                self.testsDicts.remove(test)
                break

        # Change the chosen name
        if self.tests:
            self.testName.setText(self.tests[0].text())
        else:
            self.testName.setText("")