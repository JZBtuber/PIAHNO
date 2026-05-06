from src.gui.gui import Application
import os
import faulthandler

#----------------------------------------------------------------#
# This code was writen by Justin Boileau
# for the PIAHNO reseach project at the "Université de Montreal".
# This code is free to use to anyone as said by the License.
# This is the main .py file of the app.
#----------------------------------------------------------------#

faulthandler.enable()
localPath = os.path.dirname(os.path.realpath(__file__))

app = Application(localPath)