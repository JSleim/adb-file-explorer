import logging
import subprocess
import unittest
from unittest.mock import patch

from handler import ADBHandler


class StreamEmptyDirectoryTests(unittest.TestCase):
    def test_stream_directory_creates_empty_destination_directory(self):
        handler = ADBHandler.__new__(ADBHandler)
        handler.logger = logging.getLogger("test-stream-empty-directory")
        handler._run_adb_command = lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, "", ""
        )

        with patch.object(ADBHandler, "_exec_mkdir") as mkdir:
            result = handler.stream_directory(
                "source-device", "/empty", "target-device", "/destination/empty"
            )

        self.assertTrue(result)
        mkdir.assert_any_call("target-device", "/destination/empty")


if __name__ == "__main__":
    unittest.main()
