from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal
from src.tools.ScriptReader import getScore
from src.tools.fileIO import saveScripts, loadScripts
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from src.tools.setting import GlobalSettings
from src.gui.Core import FileDropLineEdit
from matplotlib import pyplot as plt
import pickle
import os

PYTHON_TEMPLATE_SCRIPT = """#Minimum imports
import sys
import pickle
import matplotlib.pyplot as plt
import datetime
import os


files = sys.argv    #Array containing the PATH to the input files

#Get the live or file time for analitics over time
if len(files) > 1:
    fileDate = str(datetime.datetime.fromtimestamp(os.path.getctime(files[1])))[:19].replace(" ", "_").replace(":", "-")
else:
    fileDate = str(datetime.datetime.now())[:19].replace(" ", "_").replace(":", "-")

#EXEMPLE of plot
figure, ax = plt.subplots()
ax.bar([1,2,3,4,5,6,7,8,9,10], [1,2,3,4,5,5,4,3,2,1])

#ONLY way to send data to the app!!
array = {"Score" : 512, # <-- "Score" must be the key to the score variable
         "Value1" : 256, # <-- "Every thing else will go into the table...
         "Plot1" : figure, # <-- ...execpt "Plot" wich will go in a figure
         "Time" : fileDate
         }

#Send data to the app
data = pickle.dumps(array)
sys.stdout.buffer.write(data)"""


class ScriptBox(QDialog):
    """
    Dialog for the use of the outside scripts.
    """
    scriptChanged = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedSize(1200, 800)

        self.scriptChanged.connect(self._updateChosenScript)

        # Default variables
        self.scriptPathsWidgets = []
        self.filePathsWidgets = []
        self.score = 0
        self.chosenScript = None
        self.loadedPlot = 0
        self.values = []
        self.figures = []
        self.data = None
        self.testName = ""

        # Working layouts
        mainLayout = QGridLayout()
        inputLayout = QGridLayout()
        controlLayout = QGridLayout()
        scriptLayout = QGridLayout()

        self.setLayout(mainLayout)

        # Fill layouts
        self._fillInput(inputLayout)
        self._fillControls(controlLayout)
        self._fillScript(scriptLayout)

        # Add layouts to main
        mainLayout.addLayout(inputLayout, 0, 0, 2, 1)
        mainLayout.addLayout(controlLayout, 0, 1, 2, 1)
        mainLayout.addLayout(scriptLayout, 0, 2, 2, 1)

        # Set stretch
        mainLayout.setColumnStretch(0, 1)
        mainLayout.setColumnStretch(1, 2)
        mainLayout.setColumnStretch(2, 1)

        # Load last scripts
        scripts = loadScripts()
        for script in scripts:
            self._addScript(script)

    # ---------------------------------------------------
    # Files
    # ---------------------------------------------------

    def _fillInput(self, inputLayout: QGridLayout) -> None:
        """
        Create all the different widgets to add inputs files to the script.\n
        :param `QGridLayout` inputLayout: Layout object that will be filled with the widgets.
        """
        # Set layout settings
        inputLayout.setRowStretch(0, 0)
        inputLayout.setRowStretch(1, 0)

        # Input Label
        topText = QLabel("Input files")
        topText.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Add file button
        addButton = QPushButton("Add file")
        addButton.clicked.connect(self._browseFiles)

        # Remove file button
        removeButton = QPushButton("Remove file")
        removeButton.clicked.connect(lambda: self._removeFileWidget(
            self.filePathsWidgets[-1]) if self.filePathsWidgets else "")

        # Scroll area
        self.fileContainer = QVBoxLayout()
        self.fileContainer.addStretch()
        fileContentWidget = QWidget()
        fileContentWidget.setLayout(self.fileContainer)
        fileScrollArea = QScrollArea()
        fileScrollArea.setWidgetResizable(True)
        fileScrollArea.setWidget(fileContentWidget)

        # Add all the widgets to the layout
        inputLayout.addWidget(topText, 0, 0, 1, 2)
        inputLayout.addWidget(addButton, 1, 0, 1, 1)
        inputLayout.addWidget(removeButton, 1, 1, 1, 1)
        inputLayout.addWidget(fileScrollArea, 2, 0, 1, 2)

    def _addFile(self, path: str) -> None:
        """
        Add a file to the list of file to give as arguments to the script.\n
        :param `str` path: Path to the file to add as argument.
        """
        # Set the text settings
        text = QLabel(path)
        text.setObjectName("text")
        text.setStyleSheet("""
                           QLabel#text {
                           border-style : solid;
                           border-width : 1px;
                           border-radius : 3px;
                           margin : 2px;
                           }""")
        text.contextMenuEvent = lambda event, widget=text: self.fileContextMenuEvent(
            event, widget)

        # Add the text widget to the scroll area and list
        self.filePathsWidgets.append(text)
        self.fileContainer.addWidget(text, 0, Qt.AlignmentFlag.AlignTop)

    def _removeFileWidget(self, widget: QLabel) -> None:
        """
        Remove a widget from the scroll area for files.\n
        :param `QLabel` widget: Label object that will be removed.\n
        :raises: `ValueError` if widget doesn't exist in the lists.
        """
        if widget not in self.filePathsWidgets:
            raise ValueError("widget is not in the saved widgets")

        # Remove the widget from the scroll area and the list
        self.filePathsWidgets.remove(widget)
        self.fileContainer.removeWidget(widget)
        widget.deleteLater()

    def _browseFiles(self) -> None:
        # Look for a tretable file type
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select an input files",
            "",
            "Input files (*.mp4 *.mov *.wav *.mid *.npy *.npz *.csv *.mat)"
        )
        for path in paths:
            self._addFile(path)

    def fileContextMenuEvent(self, event, widget: QLabel) -> None:
        """
        Event the the context menu of the path label,\n
        :param event: Event object of the context menu.\n
        :param `QLabel` widget: Label object that was interacted with.
        """
        contextMenu = QMenu(self)

        # Add options to the context menu
        showAction = contextMenu.addAction("Show file")
        contextMenu.addSeparator()
        removeAction = contextMenu.addAction("Remove")

        # Set the context menu position from the event
        action = contextMenu.exec(event.globalPos())

        # User's options on the context menu
        if action == showAction:
            _, _ = QFileDialog.getOpenFileName(self,
                                               "Select an input file",
                                               widget.text(),
                                               "Input files (*.mp4 *.mov *.wav *.mid *.npy *.npz *.csv *.mat)")
        elif action == removeAction:
            self._removeFileWidget(widget)

    # ---------------------------------------------------
    # Scripts
    # ---------------------------------------------------

    def _fillScript(self, scriptLayout: QGridLayout) -> None:
        """
        Create all the different widgets to add scripts to use.\n
        :param `QGridLayout` inputLayout: Layout object that will be filled with the widgets.
        """
        # Set layout settings
        scriptLayout.setRowStretch(0, 0)
        scriptLayout.setRowStretch(1, 0)

        # Script labal
        topText = QLabel("Scripts")
        topText.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Add script button
        addButton = QPushButton("Add script")
        addButton.clicked.connect(self._browseScripts)

        # Remove script button
        removeButton = QPushButton("Remove script")
        removeButton.clicked.connect(lambda: self._removeScriptWidget(
            self.scriptPathsWidgets[-1]) if self.scriptPathsWidgets else "")

        # Scroll area
        self.scriptContainer = QVBoxLayout()
        self.scriptContainer.addStretch()
        scriptContentWidget = QWidget()
        scriptContentWidget.setLayout(self.scriptContainer)
        scriptScrollArea = QScrollArea()
        scriptScrollArea.setWidgetResizable(True)
        scriptScrollArea.setWidget(scriptContentWidget)

        # Add all the widgets to the layout
        scriptLayout.addWidget(topText, 0, 0, 1, 2)
        scriptLayout.addWidget(addButton, 1, 0, 1, 1)
        scriptLayout.addWidget(removeButton, 1, 1, 1, 1)
        scriptLayout.addWidget(scriptScrollArea, 2, 0, 1, 2)

    def _addScript(self, path: str) -> None:
        """
        Add a script to the list of script that can be used.\n
        :param `str` path: Path to the script to run.
        """
        # Set the text settings
        text = QLabel(path)
        text.setObjectName("text")
        text.setStyleSheet("""
                           QLabel#text {
                           border-style : solid;
                           border-width : 1px;
                           border-radius : 3px;
                           margin : 2px;
                           }
                            """)
        text.contextMenuEvent = lambda event, widget=text: self._scriptContextMenuEvent(
            event, widget)

        # Add the text widget to the scroll area and list
        self.scriptPathsWidgets.append(text)
        self.scriptContainer.addWidget(text, 0, Qt.AlignmentFlag.AlignTop)

    def _removeScriptWidget(self, widget: QLabel) -> None:
        """
        Remove a widget from the scroll area for scripts.\n
        :param `QLabel` widget: Label object that will be removed.\n
        :raises: `ValueError` if widget doesn't exist in the lists.
        """
        if widget not in self.scriptPathsWidgets:
            raise ValueError("widget is not in the saved widgets")

        # Remove the widget from the scroll area and the list
        self.scriptPathsWidgets.remove(widget)
        self.scriptContainer.removeWidget(widget)
        widget.deleteLater()

    def _browseScripts(self) -> None:
        # Look for a usable script
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select an script files",
            "",
            "Script files (*.py)"
        )
        if paths:
            for path in paths:
                self._addScript(path)

    def _scriptContextMenuEvent(self, event, widget: QLabel) -> None:
        """
        Event the the context menu of the path label,\n
        :param event: Event object of the context menu.\n
        :param `QLabel` widget: Label object that was interacted with.
        """
        contextMenu = QMenu(self)

        # Add options to the context menu
        useAction = contextMenu.addAction("Use script")
        contextMenu.addSeparator()
        showAction = contextMenu.addAction("Show file")
        contextMenu.addSeparator()
        removeAction = contextMenu.addAction("Remove")

        # Set the context menu position from the event
        action = contextMenu.exec(event.globalPos())

        # User's options on the context menu
        if action == showAction:
            _, _ = QFileDialog.getOpenFileName(self,
                                               "Select an script file",
                                               widget.text(),
                                               "Script files (*.py)"
                                               )
        elif action == removeAction:
            self._removeScriptWidget(widget)
        elif action == useAction:
            self.scriptChanged.emit(widget.text())

    # ---------------------------------------------------
    # Controls
    # ---------------------------------------------------

    def _fillControls(self, controlLayout: QGridLayout) -> None:
        """
        Create all the different widgets to control the script interface. \n
        :param `QGridLayout` controlLayout: Layout object that will be filled with the control widgets.
        """

        # Set layout settings
        for i in range(14):
            if i == 3:
                controlLayout.setRowStretch(i, 3)
            elif i == 5:
                controlLayout.setRowStretch(i, 3)
            else:
                controlLayout.setRowStretch(i, 0)

        # Control label
        topText = QLabel("Script controls")
        topText.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        topText.setSizePolicy(QSizePolicy.Policy.Minimum,
                              QSizePolicy.Policy.Minimum)

        # Chosen script label
        self.scriptLabel = QLabel("")
        self.scriptLabel.setObjectName("scriptLabel")
        self.scriptLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scriptLabel.setStyleSheet("""
                                  QLabel#scriptLabel {
                                  background-color : #808080;
                                  border-radius : 2px;
                                  font-size : 18px;
                                  border-style : solid;
                                  border-width : 1px;
                                  border-radius : 2px;
                                  }""")

        # Score label
        self.scoreLabel = QLabel(f"Score:\n {self.score}")
        self.scoreLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scoreLabel.setObjectName("scoreLabel")
        self.scoreLabel.setStyleSheet("""
                                      QLabel#scoreLabel {
                                      font-size : 20px;
                                      font-weight : bold;
                                      color :  #FFFF00;
                                      }
                                      """)

        # Start script button
        startButton = QPushButton("Start")
        startButton.clicked.connect(self._start)

        # Figure canvas
        self.canvas = FigureCanvasQTAgg(Figure(figsize=(4, 4)))
        self.canvas.setFixedSize(600, 350)
        self.canvasContainer = QWidget()
        canvasLayout = QVBoxLayout(self.canvasContainer)
        canvasLayout.setContentsMargins(0, 0, 0, 0)
        canvasLayout.addWidget(
            self.canvas, alignment=Qt.AlignmentFlag.AlignCenter)

        # Last figure button
        self.lastButton = QPushButton("Last figure")
        self.lastButton.setEnabled(False)
        self.lastButton.clicked.connect(lambda: self._loadPicture(True))

        # Next figure button
        self.nextButton = QPushButton("Next figure")
        self.nextButton.setEnabled(False)
        self.nextButton.clicked.connect(lambda: self._loadPicture(False))

        # Figure counter label
        self.figureCounter = QLabel(
            f"Figure {self.loadedPlot}/{len(self.figures)}")

        # Export figure button
        exportButton = QPushButton("Export figure as png")
        exportButton.clicked.connect(self._exportPNG)

        # Export template button
        templateButton = QPushButton("Export python template")
        templateButton.clicked.connect(self._writeTemplate)

        # Create the value table
        self._createTable()

        # Save the result button
        saveResultsButton = QPushButton("Save the test's results")
        saveResultsButton.clicked.connect(self._saveResults)

        # Add all widgets to the layout
        controlLayout.addWidget(topText, 0, 0, 1, 2)
        controlLayout.addWidget(self.scriptLabel, 1, 0, 1, 2)
        controlLayout.addWidget(self.scoreLabel, 2, 0, 1, 2)
        controlLayout.addWidget(self.table, 3, 0, 2, 2)
        controlLayout.addWidget(self.canvasContainer, 5, 0, 2, 2)
        controlLayout.addWidget(self.figureCounter, 7,
                                0, 1, 2, Qt.AlignmentFlag.AlignCenter)
        controlLayout.addWidget(exportButton, 8, 0, 1, 2)
        controlLayout.addWidget(self.lastButton, 9, 0, 1, 1)
        controlLayout.addWidget(self.nextButton, 9, 1, 1, 1)
        controlLayout.addWidget(startButton, 10, 0, 2, 2)
        controlLayout.addWidget(templateButton, 12, 0, 1, 2)
        controlLayout.addWidget(saveResultsButton, 13, 0, 1, 2)

    def _start(self) -> None:
        """
        Start the script with the input files and gets the result.
        """
        # Reset default values
        self.values = []
        self.figures = []
        self.table.clearContents()
        self.testName = os.path.basename(self.chosenScript)
        self.loadedPlot = 0

        # Dissable figure control buttons
        self.lastButton.setEnabled(False)
        self.nextButton.setEnabled(False)

        # Gets all curent file paths
        filepaths = []
        for widget in self.filePathsWidgets:
            filepaths.append(widget.text())

        # Try to run the script and get the results
        try:
            self.data = pickle.loads(
                getScore(self.chosenScript, filepaths).stdout)
            results = self.data
        except Exception as e:
            # On failure, clean up and return
            print(str(e))
            self.scoreLabel.setText("FAILED")
            return

        # Puts the result in the right list by result type (score, value, plot or time)
        for result in results:
            if result == "Score":
                self.score = results[result]
                self.scoreLabel.setText(f"Score: \n {self.score}")
            elif result.lower().startswith("plot"):
                self.figures.append(results[result])
            elif not result.lower().startswith("time"):
                self.values.append((result, results[result]))

        # Show a plot if the results contain any
        if self.figures:
            self._showFigure(0)
            self.nextButton.setEnabled(len(self.figures) > 1)
            self.figureCounter.setText(
                f"Figure {self.loadedPlot + 1}/{len(self.figures)}")
        else:
            self.figureCounter.setText(
                f"Figure {self.loadedPlot}/{len(self.figures)}")

        # Show values if the results contain any
        if self.values:
            self._fillTable()
        else:
            self.table.clearContents()

    @pyqtSlot(str)
    def _updateChosenScript(self, script: str = "") -> None:
        """
        Set the `ChosenSript` variable to the input script.\n
        :param `str` script: Path to the chosen script, defaults to `""`
        """
        self.chosenScript = script
        self.scriptLabel.setText(os.path.basename(script))

    def hideEvent(self, a0):
        """
        Override of the hidding event.
        """
        # Save the cripts
        paths = [widget.text() for widget in self.scriptPathsWidgets]
        saveScripts(paths)

        return super().hideEvent(a0)

    def _loadPicture(self, back: bool = False) -> None:
        """
        Load the next/last plot to the canvas.\n
        :param `bool` back: Go backward through the list, defaults to `False`\n
        :raises: `ValueError` If there are no plots in `figures` to load.
        """
        # Guard clause for empty figures
        if not self.figures:
            raise ValueError("No figure to load!")

        # Load the next/last plot
        self.loadedPlot += -1 if back else 1
        self._showFigure(self.loadedPlot)

        # Button and label managment
        self.lastButton.setEnabled(self.loadedPlot > 0)
        self.nextButton.setEnabled(self.loadedPlot < len(self.figures) - 1)
        self.figureCounter.setText(
            f"Figure {self.loadedPlot + 1}/{len(self.figures)}")

    def _showFigure(self, index: int = 0) -> None:
        """
        Show the figure specified in `index`.\n
        :param `int` index: Index of the figure to show, defaults to `0`.\n
        :raises: `ValueError` if `figures` does not have this index.
        """
        # Guard clause if the index is too high
        if index > len(self.figures):
            raise ValueError("No figures at this index")

        # Backup the old canvas for future deletion
        old_canvas = self.canvas

        # Set figure defaults
        fig = self.figures[index]
        fig.set_size_inches(3, 3)
        fig.set_dpi(100)
        fig.tight_layout(pad=0.5)

        # Set canvas defaults
        self.canvas = FigureCanvasQTAgg(fig)
        self.canvas.setFixedSize(600, 350)

        # Removes the old canvas
        layout = self.canvasContainer.layout()
        layout.removeWidget(old_canvas)
        old_canvas.deleteLater()

        # Add the new canvas
        layout.addWidget(self.canvas, alignment=Qt.AlignmentFlag.AlignCenter)
        self.canvas.draw()

    def _exportPNG(self) -> None:
        """
        Export the current plos as a png file.
        """
        # Gets the current loaded plot
        figure = self.figures[self.loadedPlot]

        # User chooses the saving location
        filePath, _ = QFileDialog.getSaveFileName(
            self,
            "Save plot",
            "",
            "Png Files (*.png)"
        )
        if filePath:
            figure.savefig(filePath)

    def _writeTemplate(self) -> None:
        """
        Export the script template to files.
        """
        # User chooses the saving location
        filePath = QFileDialog.getExistingDirectory(
            self,
            "Select a directory",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        if filePath:
            with open(os.path.join(filePath, "PythonScriptTemplate.py"), "w", encoding='utf-8') as file:
                file.write(PYTHON_TEMPLATE_SCRIPT)

    def _createTable(self) -> None:
        """
        Create the table for values.
        """
        self.table = QTableWidget()
        self.table.setRowCount(100)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Tests", "Score"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def _fillTable(self) -> None:
        """
        Fill the table with the current results up to 100.
        """
        self.table.clearContents()
        for i, (key, value) in enumerate(self.values[:100]):
            self.table.setItem(i, 0, QTableWidgetItem(str(key)))
            self.table.setItem(i, 1, QTableWidgetItem(str(value)))

    def _saveResults(self) -> None:
        """
        Save the results of the script to a pickle file.\n
        :raises: `ValueError` if there is no time data in the results.
        """
        # Guard clause if there is no time data
        if "Time" not in self.data:
            raise ValueError("No time data in results")

        # Save the TestName to the results
        self.data["TestName"] = self.testName

        # Custom paths generation
        pathToFile = GlobalSettings["pathToWorkingDir"] if GlobalSettings["pathToWorkingDir"] else os.path.join(
            os.getcwd(), "Tests")
        filepath = f"{GlobalSettings["participantName"]}\\Results" if GlobalSettings["participantName"] else f"Results"
        path = os.path.join(pathToFile, filepath)

        os.makedirs(path, exist_ok=True)

        # Write the data to the file
        try:
            with open(os.path.join(path, f"{self.testName}_{self.data["Time"]}_results.pkl"), "wb") as file:
                pickle.dump(self.data, file)
        except Exception as e:
            print(e)


class ResultLoader(QDialog):
    """
    Dialog to load and plot the last results.
    """

    def __init__(self):
        super().__init__()
        self.setFixedSize(1200, 800)

        # Set default variables
        self.chosenResults = ""
        self.loadedPlot = 0
        self.figures = []
        self.dataSets = []

        # Create the widget
        self.makeWidget()

    def makeWidget(self) -> None:
        """
        Create the widget to populate the dialog.
        """
        self.mainLayout = QGridLayout()
        self.setLayout(self.mainLayout)
        self.canvas = FigureCanvasQTAgg(Figure(figsize=(4, 4)))

        # Counter
        self.figureCounter = QLabel(
            f"Figure {self.loadedPlot}/{len(self.figures)}")

        # Next and previous buttons
        self.lastButton = QPushButton("Last figure")
        self.lastButton.setEnabled(False)
        self.lastButton.clicked.connect(lambda: self._loadPicture(True))

        self.nextButton = QPushButton("Next figure")
        self.nextButton.setEnabled(False)
        self.nextButton.clicked.connect(lambda: self._loadPicture(False))

        # Calculate button
        calculateButton = QPushButton("Calculate")
        calculateButton.clicked.connect(self._calculate)

        # Path Input
        self.pathInput = FileDropLineEdit()
        self.pathInput.setPlaceholderText("Path to the file...")
        self.pathInput.textChanged.connect(self._updateResults)
        self.pathInput.fileDropped.connect(self._updateResults)

        # Browse button
        browseButton = QPushButton("Browse")
        browseButton.clicked.connect(self._browseFile)

        # Path input layout
        pathLayout = QHBoxLayout()
        pathLayout.addWidget(self.pathInput, 1)
        pathLayout.addWidget(browseButton, 0)
        pathLayout.addWidget(self.pathInput)
        pathLayout.addWidget(browseButton)

        # Add the widget to the main layout
        self.mainLayout.addWidget(self.canvas, 0, 0, 4, 2)
        self.mainLayout.addWidget(
            self.figureCounter, 4, 0, 1, 2, Qt.AlignmentFlag.AlignCenter)
        self.mainLayout.addWidget(self.lastButton, 5, 0, 1, 1)
        self.mainLayout.addWidget(self.nextButton, 5, 1, 1, 1)
        self.mainLayout.addWidget(calculateButton, 6, 0, 1, 2)
        self.mainLayout.addLayout(pathLayout, 7, 0, 1, 2)

    def _updateResults(self, path: str = "") -> None:
        """
        Update `chosenResults` to contain the `path` parameter.\n
        :param `str` path: Path to the chosen results.
        """
        self.chosenResults = path

    def _calculate(self) -> None:
        """
        Calculate and plot the difference between result sets.
        """
        # Guard clause if the chosen results are empty
        if not self.chosenResults:
            return

        # Get the dicts from the files and the files from the path
        pathToFile = os.path.dirname(self.chosenResults)
        files = [os.path.join(pathToFile, f) for f in os.listdir(pathToFile)]
        dicts = self._getDicts(files)

        # Index of the example file
        exempleIndex = 0

        # Get the index of a file with the same test as the chosen result
        try:
            with open(self.chosenResults, "rb") as file:
                testName = (pickle.load(file))["TestName"]
                for dict_ in dicts:
                    if dict_["TestName"] == testName:
                        exempleIndex = dicts.index(dict_)
                        break
        except Exception as e:
            print(e)

        # Removes useless dictionnaries
        dicts = self._getReleventDicts(dicts, exempleIndex)
        dicts = self._organizeDictsByTime(dicts)

        self._makePlots(dicts)

        # draw the figures if there is any
        if self.figures:
            self.loadedPlot = 0
            self._showFigure(0)

            self.lastButton.setEnabled(False)
            self.nextButton.setEnabled(len(self.figures) > 1)
            self.figureCounter.setText(f"Figure 1/{len(self.figures)}")

    def _browseFile(self) -> None:
        """
        User choses the pickle result file to load.
        """
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select result file",
            "",
            "Pickle Files (*.pkl)"
        )
        if path:
            self.pathInput.setText(path)

    def _showFigure(self, index: int = 0) -> None:
        """
        Show the figure specified in `index`.\n
        :param `int` index: Index of the figure to show, defaults to `0`.\n
        :raises: `ValueError` if `figures` does not have this index.
        """
        # Guard clause if the index is too high
        if index > len(self.figures):
            raise ValueError("No figures at this index")

        # Keep a copy of the old canvas for deletion
        old_canvas = self.canvas

        # Set the figure settings
        fig = self.figures[index]
        fig.set_size_inches(3, 3)
        fig.set_dpi(100)
        fig.tight_layout(pad=0.5)

        # Set canvas
        self.canvas = FigureCanvasQTAgg(fig)

        # Delete the old canvas
        self.mainLayout.removeWidget(old_canvas)
        old_canvas.deleteLater()

        # Add new canvas
        self.mainLayout.addWidget(self.canvas, 0, 0, 4, 2)
        self.canvas.draw()

    def _loadPicture(self, back: bool = False) -> None:
        """
        Load the next/last plot to the canvas.\n
        :param `bool` back: Go backward through the list, defaults to `False`\n
        :raises: `ValueError` If there are no plots in `figures` to load.
        """
        # Guard clause for empty figures
        if not self.figures:
            raise ValueError("No figure to load!")

        # Load the next/last plot
        self.loadedPlot += -1 if back else 1
        self._showFigure(self.loadedPlot)

        # Button and label managment
        self.lastButton.setEnabled(self.loadedPlot > 0)
        self.nextButton.setEnabled(self.loadedPlot < len(self.figures) - 1)
        self.figureCounter.setText(
            f"Figure {self.loadedPlot + 1}/{len(self.figures)}")

    @staticmethod
    def _getDicts(paths: list[str]) -> list[dict]:
        """
        Get the dictionnaries for a list of pickle path.\n
        :param `list[str]` paths: List of path to unpickle and get the dictionnary.\n
        :returns: Returns a list of dictionnaries containned in the files.\n
        :rtype: `list[dict]`
        """
        dicts = []

        for path in paths:
            try:
                with open(path, "rb") as file:
                    dicts.append(dict(pickle.load(file)))
            except Exception as e:
                print(e)

        return dicts

    @staticmethod
    def _getReleventDicts(dicts: list[dict], exempleIndex: int = 0) -> list[dict]:
        """
        Get the dictionnaries with the same `TestName` as the `exempleIndex`'s dictionnary.\n
        :param `list[dict]` dicts: List of dictionnaries to check.\n
        :param `int` exempleIndex: Index of the file to compare, defaults to `0`.\n
        :raises: `ValueError` if `dicts` has no dictionnaries.\n
        :raises: `ValueError` if `exempleIndex` is out of range for `dicts`.\n
        :returns: Returns a list of dictionnaries with the same `TestName` as the exemple one.\n
        :rtype: `list[dict]`
        """
        releventDicts = []

        # Guard clause if there is no dictionnary
        if not dicts:
            raise ValueError("No dictionnaries to check")

        # Guard clause if the exmpleIdex is out of range
        if exempleIndex > len(dicts) - 1:
            raise ValueError("ExempleIndex too high")

        # Get the text done
        exemple = dicts[exempleIndex]
        test = exemple["TestName"]

        # Compare the test done to all dicts
        for dict_ in dicts:
            if dict_["TestName"] == test:
                releventDicts.append(dict_)

        return releventDicts

    @staticmethod
    def _organizeDictsByTime(dicts: list[dict]) -> list[dict]:
        """
        Get the dictionnaries sorted by date.\n
        :param `list[dict]` dicts: Dictionnaries to sort.\n
        :returns: Returns the dictionnaries sorted.\n
        :rtype: `list[dict]`\n
        :raises: `ValueError` if `dicts` has no dictionnaries.\n
        """
        # Guard clause if there is no dictionnary
        if not dicts:
            raise ValueError("No dictionnaries to check")

        n = len(dicts)

        # Bubble sort by time
        for i in range(n):
            swapped = False
            for j in range(0, n - i - 1):
                if dicts[j]["Time"] > dicts[j + 1]["Time"]:
                    dicts[j], dict[j + 1] = dict[j + 1], dicts[j]
                    swapped == True
            if not swapped:
                break

        return dicts

    def _makePlots(self, dicts: list[dict]) -> None:
        """
        Draws the plots for the dicts.\n
        :param `list[dict]` dicts: Dictionnaries to plot.\n
        :raises: `ValueError` if `dicts` has no dictionnaries.\n
        """
        # Clear old plots
        plt.close("all")
        self.figures = []

        # Guard clause if there is no dictionnary
        if not dicts:
            raise ValueError("No dictionnaries to check")

        # Removes the "TestName" and "plot" keys
        for dict_ in dicts:
            keys = dict_.keys()
            keysToRemove = []
            for key in keys:
                if key == "TestName" or key.lower().startswith("plot") or key == "TestName":
                    keysToRemove.append(key)

            for key in keysToRemove:
                dict_.pop(key, None)

        # Draws the plots for each value
        for i in range(len(dicts[0]) - 1):
            figure, x = plt.subplots()
            nextKey = list(dicts[0].keys())[i]
            x.set_title(f"{nextKey} over time")

            xValues = []
            yValues = []

            for dict_ in dicts:
                if nextKey in dict_:
                    xValues.append(dict_["Time"])
                    yValues.append(dict_[nextKey])

            x.plot(xValues, yValues)
            x.tick_params(axis="x", labelrotation=45)
            figure.tight_layout(pad=0.5)

            self.figures.append(figure)