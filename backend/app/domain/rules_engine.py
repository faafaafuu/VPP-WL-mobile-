from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


RULE_SET_VERSION = "v2026.06.12"
RULE_SET_BASE_URL = "https://rules.vpn.example.com/sing-box"


@dataclass(frozen=True)
class RuleSetArtifact:
    tag: str
    filename: str
    sha256: str
    version: str = RULE_SET_VERSION
    format: str = "binary"
    download_detour: str = "direct"
    update_interval: str = "24h"

    def to_remote_rule_set(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "type": "remote",
            "format": self.format,
            "url": f"{RULE_SET_BASE_URL}/{self.version}/{self.filename}?sha256={self.sha256}",
            "download_detour": self.download_detour,
            "update_interval": self.update_interval,
        }


@dataclass(frozen=True)
class RuleCategory:
    name: str
    domains: list[str] = field(default_factory=list)
    domain_suffixes: list[str] = field(default_factory=list)
    rule_sets: list[str] = field(default_factory=list)
    outbound: str = "direct"

    def to_route_rules(self) -> list[dict[str, Any]]:
        rules: list[dict[str, Any]] = []
        if self.domain_suffixes:
            rules.append({"domain_suffix": self.domain_suffixes, "outbound": self.outbound})
        if self.domains:
            rules.append({"domain": self.domains, "outbound": self.outbound})
        if self.rule_sets:
            rules.append({"rule_set": self.rule_sets, "outbound": self.outbound})
        return rules

    def to_dns_rules(self, server: str) -> list[dict[str, Any]]:
        rules: list[dict[str, Any]] = []
        if self.domain_suffixes:
            rules.append({"domain_suffix": self.domain_suffixes, "server": server})
        if self.domains:
            rules.append({"domain": self.domains, "server": server})
        return rules


@dataclass(frozen=True)
class RulesEngine:
    direct: RuleCategory = field(default_factory=lambda: DEFAULT_DIRECT)
    proxy: RuleCategory = field(default_factory=lambda: DEFAULT_PROXY)
    remote_rule_set_artifacts: list[RuleSetArtifact] = field(
        default_factory=lambda: list(DEFAULT_REMOTE_RULE_SET_ARTIFACTS)
    )

    @property
    def remote_rule_sets(self) -> list[dict[str, Any]]:
        return [artifact.to_remote_rule_set() for artifact in self.remote_rule_set_artifacts]

    def route_rules(self) -> list[dict[str, Any]]:
        return [
            {"protocol": "dns", "outbound": "direct"},
            *self.direct.to_route_rules(),
            *self.proxy.to_route_rules(),
        ]

    def dns_rules(self, direct_server: str = "ru-dns") -> list[dict[str, Any]]:
        return self.direct.to_dns_rules(direct_server)


DEFAULT_DIRECT = RuleCategory(
    name="direct",
    outbound="direct",
    domain_suffixes=[
        "ru",
        "su",
        "рф",
        "xn--p1ai",
    ],
    domains=[
        # Government and public services.
        "gosuslugi.ru",
        "nalog.gov.ru",
        "cbr.ru",
        "mos.ru",
        "esia.gosuslugi.ru",
        # Banks and fintech.
        "sberbank.ru",
        "sber.ru",
        "vtb.ru",
        "tbank.ru",
        "tinkoff.ru",
        "alfabank.ru",
        "gazprombank.ru",
        "raiffeisen.ru",
        "pochtabank.ru",
        # Russian ecosystem services.
        "yandex.ru",
        "ya.ru",
        "vk.com",
        "vk.ru",
        "mail.ru",
        "ok.ru",
        "ozon.ru",
        "wildberries.ru",
        "wb.ru",
        "avito.ru",
    ],
    rule_sets=["geosite-ru", "geoip-ru"],
)


DEFAULT_PROXY = RuleCategory(
    name="proxy",
    outbound="auto",
    domains=[
        "telegram.org",
        "t.me",
        "instagram.com",
        "cdninstagram.com",
        "youtube.com",
        "youtu.be",
        "googlevideo.com",
        "openai.com",
        "chatgpt.com",
        "x.com",
        "twitter.com",
        "discord.com",
        "discord.gg",
        "github.com",
        "githubusercontent.com",
    ],
)


DEFAULT_REMOTE_RULE_SET_ARTIFACTS = [
    RuleSetArtifact(
        tag="geosite-ru",
        filename="geosite-ru.srs",
        sha256="1111111111111111111111111111111111111111111111111111111111111111",
    ),
    RuleSetArtifact(
        tag="geoip-ru",
        filename="geoip-ru.srs",
        sha256="2222222222222222222222222222222222222222222222222222222222222222",
    ),
]
