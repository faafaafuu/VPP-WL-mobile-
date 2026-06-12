from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOL = Path("../tools/check_env_ready.py")


class EnvReadyToolTest(unittest.TestCase):
    def test_accepts_non_placeholder_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            env_file = Path(tempdir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "VPN_ROUTER_TOKEN_SECRET=token-secret-with-enough-length",
                        "VPN_ROUTER_ADMIN_TOKEN=admin-token-with-enough-length",
                        "VPN_ROUTER_HOST=127.0.0.1",
                        "VPN_ROUTER_PORT=8080",
                        "VPN_ROUTER_ALLOWED_PRODUCT_IDS=vpn.monthly,vpn.yearly",
                        "VPN_ROUTER_HSTS_ENABLED=true",
                    ]
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(TOOL), "--env-file", str(env_file), "--require-hsts"],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0)
        self.assertIn("env readiness ok", result.stdout)

    def test_rejects_placeholder_env_file(self) -> None:
        result = subprocess.run(
            [sys.executable, str(TOOL), "--env-file", "../.env.example"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("placeholder", result.stderr)


if __name__ == "__main__":
    unittest.main()
