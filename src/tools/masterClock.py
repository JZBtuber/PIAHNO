import time
from PyQt6.QtCore import pyqtSlot, QObject
from src.gui.Core import basicWindowWidget


class MasterClock(QObject):
    """
    Master clock used to synchronize all active widgets.\n
    It waits until every worker is ready, resolves sync delays, then releases all widgets.
    """

    def __init__(self, windows):
        """
        Create the master clock.\n
        :param windows: Grid containing the current window data objects.
        """
        super().__init__()

        #Set default variables
        self.windows = windows
        self.widgets: list[basicWindowWidget] = []
        self.ready: list[int] = []
        self.released_ids: dict[int, int] = {}

        #Set clock variables
        self.startTime = None
        self.pauseTime = None
        self.totalPausedTime = 0.0
        self.paused = False

        # Collect all live widgets
        for row in self.windows:
            for widgetData in row:
                widget = widgetData.widget
                if isinstance(widget, basicWindowWidget) and widget is not None:
                    self.widgets.append(widget)

        #Sort widgets by delay
        self.sortedWidgets = self._bubbleSort(self.widgets[:])

    # ------------------------------------------------------------------
    # Ready / release handshake
    # ------------------------------------------------------------------

    @pyqtSlot(int)
    def setReady(self, ID: int):
        """
        Mark a widget as ready and release all widgets when every one is ready.\n
        :param `int` ID: ID of the widget that is ready.
        """
        #Add the widget ID to the ready list
        if ID not in self.ready:
            self.ready.append(ID)

        #Release all widgets once every widget is ready
        if len(self.ready) == len(self.widgets):
            self.releaseAll()

    def releaseAll(self):
        """
        Resolve all widget delays and release every widget.
        """
        # Build a filename widget lookup so we can follow parent links
        by_filename: dict[str, basicWindowWidget] = {}
        for w in self.widgets:
            if w.fileName:
                by_filename[w.fileName] = w

        # Resolve the absolute (chained) delay for every widget
        abs_delays: dict[int, int] = {}
        for w in self.widgets:
            abs_delays[w.ID] = self._resolveAbsoluteDelay(w, by_filename, set())

        # Shift so the earliest widget starts at t=0
        min_delay = min(abs_delays.values())

        #Save shifted delays for every widget
        for w in self.sortedWidgets:
            shifted = abs_delays[w.ID] - min_delay
            self.released_ids[w.ID] = shifted

        #Start the master clock
        self.startTime = time.perf_counter()
        self.totalPausedTime = 0.0
        self.pauseTime = None
        self.paused = False

    # ------------------------------------------------------------------
    # Delay chain resolver
    # ------------------------------------------------------------------

    def _resolveAbsoluteDelay(
        self,
        widget: basicWindowWidget,
        by_filename: dict[str, basicWindowWidget],
        visited: set,
    ) -> int:
        """
        Resolve the absolute delay of a widget by following its sync parent chain.\n
        :param `basicWindowWidget` widget: Widget to resolve.
        :param `dict[str, basicWindowWidget]` by_filename: Dictionary linking filenames to widgets.
        :param `set` visited: Set of already visited widget IDs used to detect cycles.
        :returns: Returns the absolute delay of the widget.
        :rtype: `int`
        """
        #Get the widget ID
        wid = widget.ID

        #Guard clause for circular dependencies
        if wid in visited:
            return int(widget.syncDelay)

        #Add this widget to the visited set
        visited = visited | {wid}   

        #Get the parent name
        parent_name = getattr(widget, "syncParentName", "")

        #Guard clause if the widget has no parent
        if not parent_name:
            return int(widget.syncDelay)

        #Get the parent widget
        parent = by_filename.get(parent_name)

        #Guard clause if the parent is not present
        if parent is None:
            return int(widget.syncDelay)

        #Add the parent absolute delay to this widget delay
        parent_abs = self._resolveAbsoluteDelay(parent, by_filename, visited)
        return int(widget.syncDelay) + parent_abs

    @staticmethod
    def _bubbleSort(arr: list) -> list:
        """
        Sort widgets by their raw sync delay.\n
        :param `list` arr: List of widgets to sort.
        :returns: Returns the sorted widget list.
        :rtype: `list`
        """
        #Bubble sort by sync delay
        n = len(arr)
        for i in range(n):
            swapped = False
            for j in range(n - i - 1):
                if arr[j].syncDelay > arr[j + 1].syncDelay:
                    arr[j], arr[j + 1] = arr[j + 1], arr[j]
                    swapped = True
            if not swapped:
                break
        return arr

    # Keep the old camelCase name so nothing else breaks
    bubbleSort = _bubbleSort


    def elapsedMs(self) -> int:
        """
        Get the elapsed master clock time in milliseconds.\n
        :returns: Returns the elapsed time without paused time.
        :rtype: `int`
        """
        #Guard clause if the clock has not started
        if self.startTime is None:
            return 0

        #Use pause time if the clock is currently paused
        now = self.pauseTime if (self.paused and self.pauseTime is not None) \
              else time.perf_counter()

        #Return elapsed time without paused time
        return int((now - self.startTime - self.totalPausedTime) * 1000)

    def setPaused(self, paused: bool):
        """
        Set the pause state of the master clock.\n
        :param `bool` paused: New pause state.
        """
        #Start pause
        if paused and not self.paused:
            self.pauseTime = time.perf_counter()
            self.paused = True

        #End pause
        elif not paused and self.paused:
            self.totalPausedTime += time.perf_counter() - self.pauseTime
            self.pauseTime = None
            self.paused = False