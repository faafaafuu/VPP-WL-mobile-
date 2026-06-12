from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


TOOL = Path("../tools/check_sing_box_config.py")


class SingBoxCheckToolTest(unittest.TestCase):
    def test_tool_skips_missing_binary_by_default(self) -> None:
        result = subprocess.run(
            [sys.executable, str(TOOL), "--binary", "sing-box-missing"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("binary check skipped", result.stdout)

    def test_tool_can_require_binary(self) -> None:
        result = subprocess.run(
            [sys.executable, str(TOOL), "--binary", "sing-box-missing", "--require-binary"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("binary check skipped", result.stdout)


if __name__ == "__main__":
    unittest.main()
