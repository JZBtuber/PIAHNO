from PyQt6.QtWidgets import QApplication
from src.gui.MainWindow import MainWindow


class Application():
    """
    Main application wrapper.\n
    It creates the Qt application, creates the main window, then starts the event loop.
    """
    application = QApplication([])

    def __init__(self, localPath):
        """
        Create and start the application.\n
        :param localPath: Path to the local working directory.
        """
        # Create the main window
        self.window = MainWindow(localPath)

        # Show the main window
        self.window.show()

        # Start the Qt event loop
        self.application.exec()
