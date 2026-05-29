from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal
from src.tools.ScriptReader import getScore
from src.tools.fileIO import saveScripts, loadScripts
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from src.tools.setting import GlobalSettings
import pickle
import os

class ScriptBox(QDialog):
    """
    Dialog for the use of the outside scripts.
    """
    scriptChanged = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedSize(1200, 800)

        self.scriptChanged.connect(self.updateChosenScript)

        self.scriptPathsWidgets = []
        self.filePathsWidgets = []

        self.score = 0
        self.chosenScript = None
        self.loadedPlot = 0

        self.values = []
        self.figures = []

        self.data = None
        self.testName = ""


        gridLayout = QGridLayout()

        inputLayout = QGridLayout()
        inputLayout.setColumnStretch(0, 1)
        inputLayout.setColumnStretch(1, 1)
        
        controlLayout = QGridLayout()
        scriptLayout = QGridLayout()
        scriptLayout.setColumnStretch(0, 1)
        scriptLayout.setColumnStretch(1, 1)

        self.fillInput(inputLayout)
        self.fillControls(controlLayout)
        self.fillScript(scriptLayout)

        gridLayout.addLayout(inputLayout, 0, 0, 2, 1)
        gridLayout.addLayout(controlLayout, 0, 1, 2, 1)
        gridLayout.addLayout(scriptLayout, 0, 2, 2, 1)

        gridLayout.setColumnStretch(0, 1)
        gridLayout.setColumnStretch(1, 2)
        gridLayout.setColumnStretch(2, 1)

        gridLayout.setRowStretch(0, 1)
        gridLayout.setRowStretch(1, 1)

        self.setLayout(gridLayout)

        paths = loadScripts()

        if paths:
            for path in paths:
                self.addScript(path)

    #---------------------------------------------------
    #Files
    #---------------------------------------------------

    def fillInput(self, inputLayout: QGridLayout) -> None:
        """
        Fill the input layout.
        """
        inputLayout.setColumnStretch(0, 1)
        inputLayout.setColumnStretch(1, 1)
        inputLayout.setRowStretch(0, 0)
        inputLayout.setRowStretch(1, 1)
        inputLayout.setRowStretch(2, 9)

        topText = QLabel("Input files")
        topText.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        
        inputLayout.addWidget(topText, 0, 0, 1, 2)

        addButton = QPushButton("Add file")
        addButton.clicked.connect(self.browseFiles)

        removeButton = QPushButton("Remove file")
        removeButton.clicked.connect(lambda: self.removeFileWidget(self.filePathsWidgets[-1]) if self.filePathsWidgets else "")

        inputLayout.addWidget(addButton, 1, 0, 1, 1)
        inputLayout.addWidget(removeButton, 1, 1, 1, 1)

        self.fileContainer = QVBoxLayout()
        self.fileContainer.addStretch()

        fileContentWidget = QWidget()
        fileContentWidget.setLayout(self.fileContainer)

        fileScrollArea = QScrollArea()
        fileScrollArea.setWidgetResizable(True)
        fileScrollArea.setWidget(fileContentWidget)

        inputLayout.addWidget(fileScrollArea, 2, 0, 1, 2)

        


    def addFile(self, path) -> None:
        """
        Add a file to the list.
        """
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
        
        text.contextMenuEvent = lambda event, widget=text: self.fileContextMenuEvent(event, widget)
        
        self.filePathsWidgets.append(text)
        self.fileContainer.addWidget(text, 0, Qt.AlignmentFlag.AlignTop)

    
    def removeFileWidget(self, widget: QLabel) -> None:
        if widget in self.filePathsWidgets:
            self.filePathsWidgets.remove(widget)

        self.fileContainer.removeWidget(widget)
        widget.deleteLater()
    
    
    def browseFiles(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select an input files",
            "",
            "Input files (*.mp4 *.mov *.wav *.mid *.npy *.npz *.csv *.mat)"
        )
        if paths:
            for path in paths:
                self.addFile(path)


    def fileContextMenuEvent(self, event, widget: QLabel) -> None:
        contextMenu = QMenu(self)

        showAction = contextMenu.addAction("Show file")
        contextMenu.addSeparator()
        removeAction = contextMenu.addAction("Remove")

        action = contextMenu.exec(event.globalPos())

        if action == showAction:
            _, _ = QFileDialog.getOpenFileName(self,
            "Select an input file",
            widget.text(),
            "Input files (*.mp4 *.mov *.wav *.mid *.npy *.npz *.csv *.mat)"
        )
        elif action == removeAction:
            self.removeFileWidget(widget)
    
    #---------------------------------------------------
    #Scripts
    #---------------------------------------------------

    def fillScript(self, scriptLayout: QGridLayout) -> None:
        """
        Fill the script layout
        """

        scriptLayout.setColumnStretch(0, 1)
        scriptLayout.setColumnStretch(1, 1)
        scriptLayout.setRowStretch(0, 0)
        scriptLayout.setRowStretch(1, 1)
        scriptLayout.setRowStretch(2, 9)

        topText = QLabel("Scripts")
        topText.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        topText.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        scriptLayout.addWidget(topText, 0, 0, 1, 2)

        addButton = QPushButton("Add script")
        addButton.clicked.connect(self.browseScripts)

        removeButton = QPushButton("Remove script")
        removeButton.clicked.connect(lambda: self.removeScriptWidget(self.scriptPathsWidgets[-1]) if self.scriptPathsWidgets else "")

        scriptLayout.addWidget(addButton, 1, 0, 1, 1)
        scriptLayout.addWidget(removeButton, 1, 1, 1, 1)

        self.scriptContainer = QVBoxLayout()
        self.scriptContainer.addStretch()

        scriptContentWidget = QWidget()
        scriptContentWidget.setLayout(self.scriptContainer)

        scriptScrollArea = QScrollArea()
        scriptScrollArea.setWidgetResizable(True)
        scriptScrollArea.setWidget(scriptContentWidget)

        scriptLayout.addWidget(scriptScrollArea, 2, 0, 1, 2)


    def addScript(self, path) -> None:
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
        
        text.contextMenuEvent = lambda event, widget=text: self.scriptContextMenuEvent(event, widget)

        self.scriptPathsWidgets.append(text)
        self.scriptContainer.addWidget(text, 0, Qt.AlignmentFlag.AlignTop)


    def removeScriptWidget(self, widget: QLabel) -> None:
        if widget in self.scriptPathsWidgets:
            self.scriptPathsWidgets.remove(widget)

        self.scriptContainer.removeWidget(widget)
        widget.deleteLater()


    def browseScripts(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select an script files",
            "",
            "Script files (*.py)"
        )
        if paths:
            for path in paths:
                self.addScript(path)


    def scriptContextMenuEvent(self, event, widget: QLabel) -> None:
        contextMenu = QMenu(self)

        useAction = contextMenu.addAction("Use script")
        contextMenu.addSeparator()
        showAction = contextMenu.addAction("Show file")
        contextMenu.addSeparator()
        removeAction = contextMenu.addAction("Remove")

        action = contextMenu.exec(event.globalPos())

        if action == showAction:
            _, _ = QFileDialog.getOpenFileName(self,
            "Select an script file",
            widget.text(),
            "Script files (*.py)"
        )
        elif action == removeAction:
            self.removeScriptWidget(widget)
        elif action == useAction:
            self.scriptChanged.emit(widget.text())

    #---------------------------------------------------
    #Controls
    #---------------------------------------------------

    def fillControls(self, controlLayout: QGridLayout) -> None:

        controlLayout.setColumnStretch(0, 1)
        controlLayout.setColumnStretch(1, 1)


        topText = QLabel("Script controls")
        topText.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        topText.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        controlLayout.addWidget(topText, 0, 0, 1, 2)

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

        controlLayout.addWidget(self.scriptLabel, 1, 0, 1, 2)

        self.scoreLabel = QLabel(f"Score: \n {self.score}")
        self.scoreLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scoreLabel.setObjectName("scoreLabel")
        self.scoreLabel.setStyleSheet("""
                                      QLabel#scoreLabel {
                                      font-size : 20px;
                                      font-weight : bold;
                                      color :  #FFFF00;
                                      }
                                      """)

        controlLayout.addWidget(self.scoreLabel, 2, 0, 1, 2)

        startButton = QPushButton("Start")
        startButton.clicked.connect(self.start)

        self.canvas = FigureCanvasQTAgg(Figure(figsize=(4, 4)))
        self.canvas.setFixedSize(300, 300)

        self.canvasContainer = QWidget()
        canvasLayout = QVBoxLayout(self.canvasContainer)
        canvasLayout.setContentsMargins(0, 0, 0, 0)
        canvasLayout.addWidget(self.canvas, alignment=Qt.AlignmentFlag.AlignCenter)

        controlLayout.addWidget(self.canvasContainer, 5, 0, 2, 2)
        controlLayout.setRowStretch(3, 8)

        controlLayout.addWidget(startButton, 10, 0, 2, 2)

        self.lastButton = QPushButton("Last figure")
        self.lastButton.setEnabled(False)
        self.lastButton.clicked.connect(lambda: self.loadPicture(True))

        self.nextButton = QPushButton("Next figure")
        self.nextButton.setEnabled(False)
        self.nextButton.clicked.connect(lambda: self.loadPicture(False))

        controlLayout.addWidget(self.lastButton, 9, 0, 1, 1)
        controlLayout.addWidget(self.nextButton, 9, 1, 1, 1)

        self.figureCounter = QLabel(f"Figure {self.loadedPlot}/{len(self.figures)}")
        controlLayout.addWidget(self.figureCounter, 7, 0, 1, 2, Qt.AlignmentFlag.AlignCenter)
        controlLayout.setRowStretch(7, 0)

        exportButton = QPushButton("Export figure as png")
        exportButton.clicked.connect(self.exportPGN)

        controlLayout.addWidget(exportButton, 8, 0, 1, 2)

        templateButton = QPushButton("Export python template")
        templateButton.clicked.connect(self.writeTemplate)

        controlLayout.addWidget(templateButton, 12, 0, 1, 2)

        self.createTable()

        controlLayout.addWidget(self.table, 3, 0, 2, 2)

        saveResultsButton = QPushButton("Save the test's results")
        saveResultsButton.clicked.connect(self.saveResults)

        controlLayout.addWidget(saveResultsButton, 13, 0, 1, 2)

            
    def start(self) -> None:

        self.lastButton.setEnabled(False)
        self.nextButton.setEnabled(False)

        filepaths = []
        for widget in self.filePathsWidgets:
            filepaths.append(widget.text())
        
        try:
            self.data = pickle.loads(getScore(self.chosenScript, filepaths).stdout)
            results = self.data
        except Exception as e:
            print(str(e))
            self.values = []
            self.figures = []
            self.table.clearContents()
            self.scoreLabel.setText("FAILED")
            return
        
        self.testName = os.path.basename(self.chosenScript)

        self.values = []

        self.figures = []
        for result in results:
            if result == "Score":
                self.score = results[result]
                self.scoreLabel.setText(f"Score: \n {self.score}")
            elif result.lower().startswith("plot"):
                self.figures.append(results[result])
            elif result.lower().startswith("time"):
                ""
            else:
                self.values.append((result, results[result]))


        self.loadedPlot = 0

        if self.figures:
            self.showFigure(0)

            self.lastButton.setEnabled(False)
            self.nextButton.setEnabled(len(self.figures) > 1)
            self.figureCounter.setText(f"Figure {self.loadedPlot + 1}/{len(self.figures)}")
        else:
            self.lastButton.setEnabled(False)
            self.nextButton.setEnabled(False)
            self.figureCounter.setText(f"Figure {self.loadedPlot}/{len(self.figures)}")

        if self.values:
            self.fillTable()
        else:
            self.table.clearContents()
        

    @pyqtSlot(str)
    def updateChosenScript(self, script) -> None:
        self.chosenScript = script
        self.scriptLabel.setText(os.path.basename(script))

    
    def hideEvent(self, a0):
        paths = []

        for widget in self.scriptPathsWidgets:
            paths.append(widget.text())

        saveScripts(paths)

        return super().hideEvent(a0)
    

    def loadPicture(self, back: bool = False) -> None:
        if not self.figures:
            self.lastButton.setEnabled(False)
            self.nextButton.setEnabled(False)
            return

        if back:
            self.loadedPlot -= 1
        else:
            self.loadedPlot += 1

        self.showFigure(self.loadedPlot)

        self.lastButton.setEnabled(self.loadedPlot > 0)
        self.nextButton.setEnabled(self.loadedPlot < len(self.figures) - 1)
        self.figureCounter.setText(f"Figure {self.loadedPlot + 1}/{len(self.figures)}")


    def showFigure(self, index: int) -> None:
        old_canvas = self.canvas

        fig = self.figures[index]
        fig.set_size_inches(3, 3)
        fig.set_dpi(100)
        fig.tight_layout(pad=0.5)

        self.canvas = FigureCanvasQTAgg(fig)
        self.canvas.setFixedSize(600, 350)

        layout = self.canvasContainer.layout()
        layout.removeWidget(old_canvas)
        old_canvas.deleteLater()

        layout.addWidget(self.canvas, alignment=Qt.AlignmentFlag.AlignCenter)
        self.canvas.draw()

    
    def exportPGN(self) -> None:
        
        figure = self.figures[self.loadedPlot]

        filePath, _ = QFileDialog.getSaveFileName(
            self,
            "Save plot",
            "",
            "Png Files (*.png)"
            )
        if filePath:
            figure.savefig(filePath)

    
    def writeTemplate(self) -> None:
        filePath = QFileDialog.getExistingDirectory(
            self,
            "Select a directory",
            "",
            QFileDialog.Option.ShowDirsOnly
            )
        if filePath:
            with  open(os.path.join(filePath, "PythonScriptTemplate.py"), "w", encoding='utf-8') as file:
                file.write(
"""#Minimum imports
import sys
import pickle
import matplotlib.pyplot as plt
import datetime
import os


files = sys.argv    #Array containing the PATH to the input files

#Get the live or file time for analitics over time
if len(files) > 1:
    fileDate = datetime.datetime.fromtimestamp(os.path.getctime(files[1]))[:19].replace(" ", "_").replace(":", "-")
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
sys.stdout.buffer.write(data)""")
                
    def createTable(self):
        self.table = QTableWidget()
        self.table.setRowCount(100)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Tests", "Score"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)      
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def fillTable(self):
        self.table.clearContents()
        for i, (key, value) in enumerate(self.values[:100]):
            self.table.setItem(i, 0, QTableWidgetItem(str(key)))
            self.table.setItem(i, 1, QTableWidgetItem(str(value)))


    def saveResults(self):
        if not self.data["Time"]:
            return
        self.data["TestName"] = self.testName
        
        pathToFile = GlobalSettings["pathToWorkingDir"] if GlobalSettings["pathToWorkingDir"] else os.path.join(os.getcwd(), "Tests")
        filepath = f"{GlobalSettings["participantName"]}\\Results" if GlobalSettings["participantName"] else f"Results"

        path = os.path.join(pathToFile, filepath)

        os.makedirs(path, exist_ok=True)

        with open(os.path.join(path, f"{self.testName}_{self.data["Time"]}_results.pkl"), "wb") as file:
            pickle.dump(self.data, file)


class overTimeBox(QDialog):
    def __init__(self):
        super().__init__()
        self.setFixedSize(1200, 800)

        mainLayout = QGridLayout()

        self.setLayout(mainLayout)

        self.chosenResults = ""

        self.dataSets = []


    def loadFiles(self):
        if self.chosenResults:
            testName = (pickle.loads(self.chosenResults))["TestName"]

        for file in os.listdir(os.path.dirname(self.chosenResults)):
            if os.path.isfile(os.join(os.path.dirname(self.chosenResults), file)):
                try:
                    data = pickle.loads(os.path.dirname(self.chosenResults), file)
                    if data["testName"] == testName:
                        self.dataSets.append(data)
                except:
                    continue