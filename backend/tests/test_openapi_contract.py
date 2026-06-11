from __future__ import annotations

import unittest
from pathlib import Path


class OpenApiContractTest(unittest.TestCase):
    def test_openapi_contract_mentions_current_endpoints_and_security(self) -> None:
        contract = Path("../docs/openapi.yaml").read_text(encoding="utf-8")

        for path in [
            "/api/auth/init",
            "/api/auth/receipt",
            "/api/config",
            "/api/nodes",
            "/api/admin/nodes",
            "/api/admin/nodes/{node_id}/health",
            "/api/webhook/apple",
            "/api/webhook/google",
        ]:
            self.assertIn(path, contract)

        self.assertIn("bearerAuth:", contract)
        self.assertIn("adminToken:", contract)
        self.assertIn("X-Admin-Token", contract)
        self.assertIn("ServiceUnavailable", contract)


if __name__ == "__main__":
    unittest.main()

