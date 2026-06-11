from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "graphify-out"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for path in sorted((ROOT / "backend").rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        file_id = node_id(relative)
        nodes.append(
            {
                "id": file_id,
                "label": path.name,
                "source_file": relative,
                "file_type": "code",
                "kind": "file",
            }
        )

        tree = ast.parse(path.read_text(encoding="utf-8"))
        for item in ast.walk(tree):
            if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol_id = f"{file_id}_{node_id(item.name)}"
                nodes.append(
                    {
                        "id": symbol_id,
                        "label": f"{item.name}()"
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                        else item.name,
                        "source_file": relative,
                        "file_type": "code",
                        "kind": "symbol",
                        "line": item.lineno,
                    }
                )
                edges.append(
                    {
                        "source": file_id,
                        "target": symbol_id,
                        "relation": "contains",
                        "source_file": relative,
                    }
                )

        for item in tree.body:
            if isinstance(item, ast.ImportFrom) and item.module and item.module.startswith("app."):
                target = item.module.replace(".", "/") + ".py"
                edges.append(
                    {
                        "source": file_id,
                        "target": node_id(f"backend/{target}"),
                        "relation": "imports",
                        "source_file": relative,
                    }
                )

    graph = {
        "metadata": {
            "generator": "mini_graphify",
            "root": str(ROOT),
            "note": "Fallback AST graph generated because full graphify may be unavailable.",
        },
        "nodes": nodes,
        "edges": edges,
    }
    (OUT / "graph.json").write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / ".graphify_root").write_text(str(ROOT), encoding="utf-8")
    write_report(nodes, edges)
    print(f"mini graphify wrote {OUT / 'graph.json'}")


def write_report(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    files = [node for node in nodes if node.get("kind") == "file"]
    symbols = [node for node in nodes if node.get("kind") == "symbol"]
    lines = [
        "# Graph Report",
        "",
        "Fallback AST graph for the VPN Router MVP backend.",
        "",
        f"- Files: {len(files)}",
        f"- Symbols: {len(symbols)}",
        f"- Edges: {len(edges)}",
        "",
        "## Key Files",
        "",
    ]
    lines.extend(f"- `{file['source_file']}`" for file in files)
    (OUT / "GRAPH_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def node_id(value: str) -> str:
    return (
        value.lower()
        .replace("/", "_")
        .replace(".", "_")
        .replace("-", "_")
        .replace(" ", "_")
    )


if __name__ == "__main__":
    main()

