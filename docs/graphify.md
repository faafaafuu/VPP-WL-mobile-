# Graphify Notes

Graphify is part of the workflow for architecture navigation.

## Current Policy

- Commit `graphify-out/graph.json`.
- Do not commit `graphify-out/cache/`, `graphify-out/.graphify_root`, or `graphify-out/manifest.json`.
- Run graphify after code changes when the command is available:

```bash
/root/job-agent/.venv/bin/graphify update . --force --no-cluster
```

- If the command is unavailable, use the fallback:

```bash
python3 tools/mini_graphify.py
```

## Intended Architecture Chain

The backend graph should expose this path after the next implementation steps:

```text
API service
  -> config generator
  -> rules engine
  -> node scoring
  -> sing-box config
```

