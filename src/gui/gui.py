from PyQt6.QtWidgets import QApplication
from src.gui.MainWindow import MainWindow



class Application():
    application = QApplication([])

    def __init__(self, localPath):
        
        self.window = MainWindow(localPath)

        self.window.show()      #Shows the window
        self.application.exec() #Starts the window