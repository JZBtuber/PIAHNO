from PyQt6.QtWidgets import QApplication
from src.gui.MainWindow import MainWindow


class Application():
    application = QApplication([])
    window = MainWindow()

    def __init__(self):
        self.window.show()      #Shows the window
        self.application.exec() #Starts the window