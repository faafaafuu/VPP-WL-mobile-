from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


TOOL = Path("../tools/check_mobile_build_ready.py")


class MobileBuildReadinessToolTest(unittest.TestCase):
    def test_reports_missing_unavailable_tool_without_crashing(self) -> None:
        result = subprocess.run(
            [sys.executable, str(TOOL), "--ios"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertIn("Xcode build tools", result.stdout)
        self.assertIn(result.returncode, {0, 1})

    def test_expo_check_mentions_node_and_eas(self) -> None:
        result = subprocess.run(
            [sys.executable, str(TOOL), "--expo"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertIn("Node.js", result.stdout)
        self.assertIn("EAS CLI", result.stdout)


if __name__ == "__main__":
    unittest.main()
