"""
@file    ui.py
@project Scan Watcher
@company Nova Network
@date    Oktober 2026
@brief   Ein einziger Tk-Thread fuer alle Fenster. Tkinter ist nicht
         thread-sicher: mehrere Tk-Instanzen in verschiedenen Threads fuehren
         zu Haengern und Abstuerzen. Andere Threads (Tray, Watcher, Downloads)
         reichen Aufgaben per submit() ein.
"""

import logging
import queue
import threading
from typing import Any, Callable

from . import theme

log = logging.getLogger("scan_watcher.ui")

_POLL_MS = 50


class UiThread:
    def __init__(self, appearance_mode: str = "dark"):
        self._appearance_mode = appearance_mode
        self._queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="ui", daemon=True)
        self.root = None

    def start(self) -> None:
        self._thread.start()
        self._ready.wait()

    def _run(self) -> None:
        import customtkinter as ctk

        theme.apply_appearance(self._appearance_mode)
        ctk.set_default_color_theme("blue")
        theme.tune_default_theme()
        self.root = ctk.CTk()
        self.root.withdraw()
        self.root.after(_POLL_MS, self._poll)
        self._ready.set()
        self.root.mainloop()
        try:
            self.root.destroy()   # gibt tkinters Default-Root frei
        except Exception:
            pass

    def _poll(self) -> None:
        while True:
            try:
                fn = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:
                log.exception("UI-Aufgabe fehlgeschlagen")
        self.root.after(_POLL_MS, self._poll)

    def is_ui_thread(self) -> bool:
        return threading.current_thread() is self._thread

    def submit(self, fn: Callable[[], None]) -> None:
        """fn im UI-Thread ausfuehren (aus jedem Thread aufrufbar)."""
        if self.is_ui_thread():
            fn()
        else:
            self._queue.put(fn)

    def ask(self, build: Callable[[Any, Callable[[Any], None]], None]) -> Any:
        """Modales Fenster aus einem anderen Thread zeigen und auf das Ergebnis
        warten. build(root, finish) baut das Fenster und ruft finish(wert)."""
        if self.is_ui_thread():
            raise RuntimeError("ask() darf nicht im UI-Thread aufgerufen werden")
        done = threading.Event()
        box: list[Any] = [None]

        def finish(value: Any = None) -> None:
            if not done.is_set():
                box[0] = value
                done.set()

        def run() -> None:
            try:
                build(self.root, finish)
            except Exception:
                log.exception("Dialog konnte nicht geoeffnet werden")
                finish(None)

        self.submit(run)
        done.wait()
        return box[0]

    def stop(self, timeout: float = 5.0) -> None:
        """UI-Thread beenden und darauf warten."""
        if self.root is not None and self._thread.is_alive():
            self.submit(self.root.quit)
            if not self.is_ui_thread():
                self._thread.join(timeout)
