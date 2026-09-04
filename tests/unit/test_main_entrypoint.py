import sys
import types


def test_main_starts_qapplication_and_main_window(monkeypatch) -> None:
    events: list[str] = []

    class FakeApplication:
        def __init__(self, argv):
            events.append(f"app:{argv[0]}")

        def exec(self) -> int:
            events.append("exec")
            return 123

    class FakeMainWindow:
        def __init__(self) -> None:
            events.append("window")

        def show(self) -> None:
            events.append("show")

    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtwidgets.QApplication = FakeApplication
    pyside = types.ModuleType("PySide6")
    pyside.QtWidgets = qtwidgets

    main_window_module = types.ModuleType("mtpdflogo.presentation.main_window")
    main_window_module.MainWindow = FakeMainWindow

    monkeypatch.setitem(sys.modules, "PySide6", pyside)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "mtpdflogo.presentation.main_window", main_window_module)

    from mtpdflogo.__main__ import main

    assert main() == 123
    assert events == [f"app:{sys.argv[0]}", "window", "show", "exec"]
