from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, Optional, Tuple

from PyQt5.QtCore import QObject, pyqtSignal


class TaskRunner(QObject):
    """Run blocking backend work off the GUI thread.

    Uses a QObject signal bridge rather than QRunnable signal ownership so the
    signal object always lives as long as the window.
    """

    _done = pyqtSignal(int, object)
    _failed = pyqtSignal(int, str, str)

    def __init__(self, parent: Optional[QObject] = None, max_threads: int = 6):
        super().__init__(parent)
        self._pool = ThreadPoolExecutor(max_workers=max_threads, thread_name_prefix="crafttune")
        self._callbacks: Dict[int, Tuple[Callable[[object], None], Optional[Callable[[str, str], None]]]] = {}
        self._next_id = 0
        self._done.connect(self._dispatch_done)
        self._failed.connect(self._dispatch_failed)

    def run(self, fn: Callable[[], object], on_result: Callable[[object], None], on_error: Optional[Callable[[str, str], None]] = None) -> None:
        self._next_id += 1
        task_id = self._next_id
        self._callbacks[task_id] = (on_result, on_error)

        def task() -> None:
            try:
                value = fn()
            except Exception as exc:  # pragma: no cover - UI boundary
                self._failed.emit(task_id, str(exc), traceback.format_exc())
                return
            self._done.emit(task_id, value)

        self._pool.submit(task)

    def _dispatch_done(self, task_id: int, value: object) -> None:
        callbacks = self._callbacks.pop(task_id, None)
        if callbacks:
            try:
                callbacks[0](value)
            except Exception:
                logging.error("UI callback failed", exc_info=True)

    def _dispatch_failed(self, task_id: int, message: str, trace: str) -> None:
        callbacks = self._callbacks.pop(task_id, None)
        if callbacks and callbacks[1] is not None:
            callbacks[1](message, trace)

    def wait(self, timeout_ms: int = 1500) -> bool:
        self._pool.shutdown(wait=False)
        return True
