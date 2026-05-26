import time
from PyQt6.QtCore import pyqtSlot, QObject
from src.gui.Core import basicWindowWidget


class MasterClock(QObject):

    def __init__(self, windows):
        super().__init__()
        self.windows = windows
        self.widgets: list[basicWindowWidget] = []
        self.ready: list[int] = []
        self.released_ids: dict[int, int] = {}

        self.startTime        = None
        self.pauseTime        = None
        self.totalPausedTime  = 0.0
        self.paused           = False

        # Collect all live widgets
        for row in self.windows:
            for widgetData in row:
                widget = widgetData.widget
                if isinstance(widget, basicWindowWidget) and widget is not None:
                    self.widgets.append(widget)

        self.sortedWidgets = self._bubbleSort(self.widgets[:])

    # ------------------------------------------------------------------
    # Ready / release handshake
    # ------------------------------------------------------------------

    @pyqtSlot(int)
    def setReady(self, ID: int):
        if ID not in self.ready:
            self.ready.append(ID)

        if len(self.ready) == len(self.widgets):
            self.releaseAll()

    def releaseAll(self):
        # Build a filename → widget lookup so we can follow parent links
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

        for w in self.sortedWidgets:
            shifted = abs_delays[w.ID] - min_delay
            self.released_ids[w.ID] = shifted

        self.startTime       = time.perf_counter()
        self.totalPausedTime = 0.0
        self.pauseTime       = None
        self.paused          = False

    # ------------------------------------------------------------------
    # Delay chain resolver
    # ------------------------------------------------------------------

    def _resolveAbsoluteDelay(
        self,
        widget: basicWindowWidget,
        by_filename: dict[str, basicWindowWidget],
        visited: set,
    ) -> int:
        wid = widget.ID

        if wid in visited:
            # Circular dependency – break the cycle and treat this node
            # as if it has no further parent.
            return int(widget.syncDelay)

        visited = visited | {wid}   # immutable update – don't mutate caller's set

        parent_name = getattr(widget, "syncParentName", "")
        if not parent_name:
            # Root widget – its syncDelay is the absolute offset from t=0
            # (typically 0 for the audio master, non-zero if the whole
            # session has a global pre-roll).
            return int(widget.syncDelay)

        parent = by_filename.get(parent_name)
        if parent is None:
            # Parent not present in this session – treat as root
            return int(widget.syncDelay)

        parent_abs = self._resolveAbsoluteDelay(parent, by_filename, visited)
        return int(widget.syncDelay) + parent_abs

    # ------------------------------------------------------------------
    # Sorting (by raw syncDelay – used only to decide release order,
    # which doesn't matter much now that we resolve absolute delays, but
    # kept for compatibility)
    # ------------------------------------------------------------------

    @staticmethod
    def _bubbleSort(arr: list) -> list:
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
        if self.startTime is None:
            return 0

        now = self.pauseTime if (self.paused and self.pauseTime is not None) \
              else time.perf_counter()

        return int((now - self.startTime - self.totalPausedTime) * 1000)

    def setPaused(self, paused: bool):
        if paused and not self.paused:
            self.pauseTime = time.perf_counter()
            self.paused    = True

        elif not paused and self.paused:
            self.totalPausedTime += time.perf_counter() - self.pauseTime
            self.pauseTime = None
            self.paused    = False
