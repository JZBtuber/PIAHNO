import time
from PyQt6.QtCore import pyqtSignal, pyqtSlot, QThread, QTimer, QObject
from src.gui.Core import basicWindowWidget


class MasterClock(QObject):
    def __init__(self, windows):
        super().__init__()
        self.windows = windows
        self.widgets = []
        self.ready = []
        self.released_ids = {}

        self.startTime = None
        self.pauseTime = None
        self.totalPausedTime = 0.0
        self.paused = False

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
        delays_ms = [int(widget.syncDelay) for widget in self.sortedWidgets]
        min_delay = min(delays_ms)

        for widget, delay_ms in zip(self.sortedWidgets, delays_ms):
            shifted_delay = delay_ms - min_delay
            self.released_ids[widget.ID] = shifted_delay

        self.startTime = time.perf_counter()
        self.totalPausedTime = 0.0
        self.pauseTime = None
        self.paused = False


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
    

    def elapsedMs(self):
        if self.startTime is None:
            return 0
        
        if self.paused and self.pauseTime is not None:
            now = self.pauseTime
        else:
            now = time.perf_counter()

        return int((now - self.startTime - self.totalPausedTime) * 1000)


    def setPaused(self, paused: bool):
        if paused and not self.paused:
            self.pauseTime = time.perf_counter()
            self.paused = True

        elif not paused and self.paused:
            self.totalPausedTime += time.perf_counter() - self.pauseTime
            self.pauseTime = None
            self.paused = False