from __future__ import annotations

import unittest

from app.domain.config_builder import ConfigBuilder
from app.domain.config_validation import ConfigValidationError, optional_sing_box_check, validate_config_shape
from app.domain.models import NodeStatus, Protocol, VlessOptions, VpnNode


class ConfigValidationTest(unittest.TestCase):
    def test_accepts_generated_config_shape(self) -> None:
        config = ConfigBuilder().build_client_config([_node()])

        self.assertIsInstance(config["route"]["rules"], list)
        validate_config_shape(config)

    def test_rejects_missing_required_sections(self) -> None:
        with self.assertRaises(ConfigValidationError):
            validate_config_shape({"outbounds": [], "route": {}})

    def test_rejects_route_final_without_outbound(self) -> None:
        config = ConfigBuilder().build_client_config([_node()])
        config["route"]["final"] = "missing"

        with self.assertRaises(ConfigValidationError):
            validate_config_shape(config)

    def test_optional_sing_box_check_skips_when_binary_is_missing(self) -> None:
        checked, message = optional_sing_box_check(ConfigBuilder().build_client_config([_node()]), binary="sing-box-missing")

        self.assertFalse(checked)
        self.assertIn("not found", message)


def _node() -> VpnNode:
    return VpnNode(
        id="node-1",
        tag="vless-eu-1",
        region="eu",
        country_code="DE",
        host="eu1.example.com",
        port=443,
        protocol=Protocol.VLESS,
        status=NodeStatus.ACTIVE,
        priority=10,
        options=VlessOptions(uuid="00000000-0000-4000-8000-000000000001", server_name="cdn.example.com"),
    )


if __name__ == "__main__":
    unittest.main()
