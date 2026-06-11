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

## Backend Architecture Chain

The backend graph should expose this path:

```text
API service
  -> config generator
  -> rules engine
  -> node scoring
  -> sing-box config
```

Admin health updates and the health-check worker feed node metrics used by node scoring before configs are emitted.

## Mobile UI Chain

The mobile graph should expose this path:

```text
Expo UI
  -> config repository
  -> backend API client
  -> last-known-good secure storage
  -> VpnRouterNative boundary
  -> Android VpnService / iOS NEPacketTunnelProvider
```

Expo is a UI and orchestration layer only; privileged VPN runtime work remains native.
