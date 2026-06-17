from src.gui.gui import Application
import os
import faulthandler
import sys

#----------------------------------------------------------------#
# This code was writen by Justin Boileau
# for the PIAHNO reseach project at the "Université de Montreal".
# This code is free to use to anyone as said by the License.
# This is the main .py file of the app.
#----------------------------------------------------------------#

def main(): #Main App
    """
    Start the PIAHNO application.
    """
    #Enable fault handler for low-level crash debugging
    faulthandler.enable()

    #Get the path of the current file
    localPath = os.path.dirname(os.path.realpath(__file__))

    #Hide TensorFlow C++ warning and info logs
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

    #Create and start the application
    app = Application(localPath)

def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys.__excepthook__(exctype, value, traceback)
    sys.excepthook = exception_hook


if __name__ == "__main__":  #Do not run as module
    #Start the app only if this file is executed directly
    main()