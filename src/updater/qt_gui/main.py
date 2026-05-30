"""Qt/QML updater progress GUI entrypoint."""

import os
import sys
from pathlib import Path

from PySide6.QtCore import Property, QCoreApplication, QObject, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from updater.qt_gui.progress_client import (
    fetch_progress,
    merge_progress_update,
    request_return_to_system,
)


class ProgressModel(QObject):
    """QML-facing progress model."""

    changed = Signal()

    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self._stage = "waiting"
        self._progress = 0
        self._message = "Waiting for updater..."
        self._error = ""
        self._terminal = False
        self._countdown_seconds = 60

    @Property(str, notify=changed)
    def stage(self):
        return self._stage

    @Property(int, notify=changed)
    def progress(self):
        return self._progress

    @Property(str, notify=changed)
    def message(self):
        return self._message

    @Property(str, notify=changed)
    def error(self):
        return self._error

    @Property(bool, notify=changed)
    def terminal(self):
        return self._terminal

    @Property(int, notify=changed)
    def countdownSeconds(self):
        return self._countdown_seconds

    @Slot()
    def refresh(self):
        if self._terminal:
            return
        data = fetch_progress(self.url)
        data = merge_progress_update(
            {
                "stage": self._stage,
                "progress": self._progress,
                "message": self._message,
                "error": self._error,
                "terminal": self._terminal,
            },
            data,
        )
        self._stage = data["stage"]
        self._progress = data["progress"]
        self._message = data["message"]
        self._error = data["error"]
        self._terminal = bool(data["terminal"])
        if self._terminal:
            self._countdown_seconds = 60
        self.changed.emit()

    @Slot()
    def tickTerminalCountdown(self):
        if not self._terminal:
            return
        self._countdown_seconds = max(0, self._countdown_seconds - 1)
        self.changed.emit()
        if self._countdown_seconds <= 0:
            self.confirmExit()

    @Slot()
    def confirmExit(self):
        request_return_to_system(self.url)
        app = QCoreApplication.instance()
        if app is not None:
            app.quit()


def main() -> int:
    app = QGuiApplication(sys.argv)
    url = os.environ.get(
        "TOPE_UPDATER_PROGRESS_URL",
        "http://127.0.0.1:12315/api/v1.0/progress",
    )
    model = ProgressModel(url)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("progressModel", model)
    qml_path = Path(__file__).parent / "qml" / "UpdaterWindow.qml"
    engine.load(str(qml_path))

    if not engine.rootObjects():
        return 1

    timer = QTimer()
    timer.setInterval(500)
    timer.timeout.connect(model.refresh)
    timer.start()
    model.refresh()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
