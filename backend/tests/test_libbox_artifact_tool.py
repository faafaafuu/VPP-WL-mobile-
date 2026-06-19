from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


TOOL = Path("../tools/check_libbox_artifacts.py")


class LibboxArtifactToolTest(unittest.TestCase):
    def test_android_check_accepts_minimal_valid_aar(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "libbox.aar"
            with zipfile.ZipFile(artifact, "w") as archive:
                archive.writestr("classes.jar", b"fake")
                archive.writestr("jni/armeabi-v7a/libbox.so", b"fake")
                archive.writestr("jni/arm64-v8a/libbox.so", b"fake")
                archive.writestr("jni/x86/libbox.so", b"fake")
                archive.writestr("jni/x86_64/libbox.so", b"fake")

            result = subprocess.run(
                [sys.executable, str(TOOL), "--android", "--android-path", str(artifact), "--require"],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0)
        self.assertIn("ok: Android libbox AAR", result.stdout)
        self.assertIn("sha256:", result.stdout)

    def test_android_check_skips_when_artifact_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_artifact = Path(tmpdir) / "missing-libbox.aar"
            result = subprocess.run(
                [sys.executable, str(TOOL), "--android", "--android-path", str(missing_artifact)],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0)
        self.assertIn("libbox artifact check skipped", result.stdout)

    def test_android_require_fails_when_artifact_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_artifact = Path(tmpdir) / "missing-libbox.aar"
            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--android",
                    "--android-path",
                    str(missing_artifact),
                    "--require",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("missing: Android libbox AAR", result.stdout)


if __name__ == "__main__":
    unittest.main()
