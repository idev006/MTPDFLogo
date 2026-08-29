"""Application entry point."""

from __future__ import annotations

import multiprocessing
import sys


def main() -> int:
    """Start the desktop application."""
    from PySide6.QtWidgets import QApplication

    from mtpdflogo.presentation.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
