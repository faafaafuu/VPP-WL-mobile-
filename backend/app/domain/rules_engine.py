from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    remote_rule_sets: list[dict[str, Any]] = field(default_factory=lambda: list(DEFAULT_REMOTE_RULE_SETS))

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


DEFAULT_REMOTE_RULE_SETS = [
    {
        "tag": "geosite-ru",
        "type": "remote",
        "format": "binary",
        "url": "https://example.invalid/rules/geosite-ru.srs",
        "download_detour": "direct",
    },
    {
        "tag": "geoip-ru",
        "type": "remote",
        "format": "binary",
        "url": "https://example.invalid/rules/geoip-ru.srs",
        "download_detour": "direct",
    },
]

