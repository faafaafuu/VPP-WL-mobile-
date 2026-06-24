"""Import vless:// URLs (e.g. exported from 3x-ui) into the node repository.

Usage:
    # From a JSON file: [{"vless_url": "...", "label": "...", "priority": 1, "enabled": true}, ...]
    python3 -m app.cli.import_vless --file nodes.json

    # From a plain-text file with one vless:// per line (label taken from #fragment):
    python3 -m app.cli.import_vless --file nodes.txt --text

    # List current nodes:
    python3 -m app.cli.import_vless --list

The real vless:// URLs contain client UUIDs and Reality keys — keep that file out
of git. This CLI writes into the runtime SQLite DB only.
"""

from __future__ import annotations

import argparse
import json
import sys

from app.domain.vless_parser import VlessParseError, parse_vless_url
from app.repositories.factory import create_repository


def main() -> int:
    parser = argparse.ArgumentParser(description="Import vless:// URLs into the node repository.")
    parser.add_argument("--file", help="Path to a JSON or plain-text file of vless URLs.")
    parser.add_argument("--text", action="store_true", help="Treat --file as plain text (one vless:// per line).")
    parser.add_argument("--list", action="store_true", help="List current nodes and exit.")
    args = parser.parse_args()

    repository = create_repository()

    if args.list:
        _list_nodes(repository)
        return 0

    if not args.file:
        parser.error("provide --file or --list")

    entries = _load_entries(args.file, plain_text=args.text)
    imported = 0
    for entry in entries:
        url = str(entry.get("vless_url", "")).strip()
        if not url:
            continue
        try:
            node = parse_vless_url(
                url,
                node_id=entry.get("id"),
                label=entry.get("label"),
                priority=int(entry.get("priority", 100)),
                enabled=bool(entry.get("enabled", True)),
                country_code=str(entry.get("country_code", "XX") or "XX"),
                region=str(entry.get("region", "unknown") or "unknown"),
                source=str(entry.get("source", "3x-ui") or "3x-ui"),
                source_panel=str(entry.get("source_panel", "local-3x-ui") or "local-3x-ui"),
            )
        except (VlessParseError, ValueError) as exc:
            print(f"skip (invalid): {exc}", file=sys.stderr)
            continue
        repository.upsert_node(node)
        imported += 1
        print(f"imported: {node.id}  [{node.tag}]  {node.host}:{node.port}")

    print(f"\nimported {imported} node(s)")
    return 0


def _load_entries(path: str, *, plain_text: bool) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        content = fh.read()
    if plain_text:
        return [{"vless_url": line.strip()} for line in content.splitlines() if line.strip() and not line.startswith("#")]
    data = json.loads(content)
    if isinstance(data, dict):
        data = data.get("nodes", [])
    if not isinstance(data, list):
        raise ValueError("JSON must be a list of objects or {\"nodes\": [...]}")
    return data


def _list_nodes(repository) -> None:
    nodes = repository.list_nodes()
    if not nodes:
        print("(no nodes)")
        return
    for node in sorted(nodes, key=lambda n: n.priority):
        opts = node.options
        label = getattr(opts, "label", None) or node.tag
        source = getattr(opts, "source", "?")
        print(f"{node.priority:>3}  {node.status.value:<9} {node.id:<28} {label:<28} {node.host}:{node.port}  ({source})")


if __name__ == "__main__":
    raise SystemExit(main())
