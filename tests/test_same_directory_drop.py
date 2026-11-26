import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from ui.widgets import DropTreeView


class SameDirectoryDropTests(unittest.TestCase):
    def test_drop_in_source_directory_does_not_start_a_move(self):
        main_window = SimpleNamespace(
            _run_background=Mock(),
            adb_handler=SimpleNamespace(move_on_device=Mock()),
        )
        view = SimpleNamespace(main_window=main_window)

        DropTreeView._handle_internal_drop(
            view, ["/storage/emulated/0/report.txt"], "/storage/emulated/0"
        )

        main_window._run_background.assert_not_called()


if __name__ == "__main__":
    unittest.main()
