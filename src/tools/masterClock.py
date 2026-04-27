from datetime import datetime
from PyQt6.QtCore import pyqtSignal, pyqtSlot, QThread, QTimer, QObject
from src.gui.Core import basicWindowWidget

class MasterClock(QObject):
    def __init__(self, windows):
        super().__init__()
        self.windows = windows
        self.widgets = []
        self.ready = []
        self.released_ids = {}

        for row in self.windows:
            for widgetData in row:
                widget = widgetData.widget
                if isinstance(widget, basicWindowWidget) and widget is not None:
                    self.widgets.append(widget)

        self.sortedWidgets = self.bubbleSort(self.widgets[:])


    @pyqtSlot(int)
    def setReady(self, ID):
        if ID not in self.ready:
            self.ready.append(ID)

        if len(self.ready) == len(self.widgets):
            self.releaseAll()


    def releaseAll(self):
        delays_ms = [int(widget.syncDelay * 1000) for widget in self.sortedWidgets]
        min_delay = min(delays_ms)

        for widget, delay_ms in zip(self.sortedWidgets, delays_ms):
            shifted_delay = delay_ms - min_delay
            self.released_ids[widget.ID] = shifted_delay

    @staticmethod
    def bubbleSort(arr):
        n = len(arr)

        for i in range(n):
            swapped = False

            for j in range(0, n - i - 1):
                if arr[j].syncDelay > arr[j + 1].syncDelay:
                    arr[j], arr[j + 1] = arr[j + 1], arr[j]
                    swapped = True

            if not swapped:
                break
        
        return arr
    