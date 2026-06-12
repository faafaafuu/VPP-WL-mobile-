from __future__ import annotations

import argparse
import contextlib
import io
import os
import unittest
from unittest.mock import patch

from app.cli.health_check import _retention_days


class HealthCheckCliTest(unittest.TestCase):
    def test_reads_audit_retention_days_from_env(self) -> None:
        parser = argparse.ArgumentParser()

        with patch.dict(os.environ, {"VPN_ROUTER_AUDIT_RETENTION_DAYS": "7"}):
            self.assertEqual(_retention_days(parser), 7)

    def test_rejects_negative_audit_retention_days(self) -> None:
        parser = argparse.ArgumentParser()

        with patch.dict(os.environ, {"VPN_ROUTER_AUDIT_RETENTION_DAYS": "-1"}):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    _retention_days(parser)


if __name__ == "__main__":
    unittest.main()
