from __future__ import annotations

import unittest
from pathlib import Path


DOCS_ROOT = Path("../docs")


class LegalDocsTest(unittest.TestCase):
    def test_privacy_policy_draft_covers_vpn_data_minimization(self) -> None:
        policy = (DOCS_ROOT / "privacy-policy-draft.md").read_text(encoding="utf-8")

        self.assertIn("draft for legal review", policy)
        self.assertIn("We do not store browsing history", policy)
        self.assertIn("No traffic content logs are stored", policy)
        self.assertIn("Store receipts are sent to the backend only for validation", policy)
        self.assertIn("Access tokens are stored", policy)
        self.assertIn("deletion", policy.lower())
        self.assertIn("export", policy.lower())

    def test_terms_draft_covers_store_subscriptions_and_acceptable_use(self) -> None:
        terms = (DOCS_ROOT / "terms-draft.md").read_text(encoding="utf-8")

        self.assertIn("draft for legal review", terms)
        self.assertIn("Apple App Store", terms)
        self.assertIn("Google Play", terms)
        self.assertIn("renew automatically", terms)
        self.assertIn("Acceptable Use", terms)
        self.assertIn("does not store traffic content logs", terms)

    def test_store_readiness_covers_vpn_store_requirements(self) -> None:
        checklist = (DOCS_ROOT / "store-readiness.md").read_text(encoding="utf-8")

        self.assertIn("Network Extension", checklist)
        self.assertIn("BIND_VPN_SERVICE", checklist)
        self.assertIn("Privacy Policy URL", checklist)
        self.assertIn("Google Play Billing", checklist)
        self.assertIn("Apple IAP", checklist)
        self.assertIn("Data Safety", checklist)
        self.assertIn("sing-box/libbox distribution and license decision", checklist)

    def test_runtime_integration_plan_records_gpl_blocker(self) -> None:
        plan = (DOCS_ROOT / "runtime-integration-plan.md").read_text(encoding="utf-8")

        self.assertIn("blocked on product/legal decision", plan)
        self.assertIn("GPL-3.0-or-later", plan)
        self.assertIn("MissingSingBoxRunner", plan)
        self.assertIn("Android development build starts a real tunnel", plan)
        self.assertIn("iOS development build starts a real Packet Tunnel", plan)


if __name__ == "__main__":
    unittest.main()
