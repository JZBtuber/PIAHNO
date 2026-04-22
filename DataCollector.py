from src.gui.gui import Application
import os
#----------------------------------------------------------------#
# This code was writen by Justin Boileau
# for the PIAHNO reseach project at the "Université de Montreal".
# This code is free to use to anyone as said by the License.
# This is the main .py file of the app.
#----------------------------------------------------------------#

localPath = os.path.dirname(os.path.realpath(__file__))

app = Application(localPath)