# MetaMatrix — Emergent Salvage

Working code rescued from MetaMatrix's original build on the Emergent.ai
platform, which was phased out in April 2026. The code was recovered from the
project's private archive, and **every piece marked "working" below was
test-run on 2026-11-11** — not just read.

This is the origin codebase of the [MetaMatrix](https://github.com/gowith133-rgb/Metamatrix_v_2)
project: the Kairos / AutoDream concepts developed here later informed the
design of Charlie, the model that runs on MetaMatrix's phone nodes.

## What's here

### `clawcode/` — the ClawCode engine ✅ working

`clawcode_engine.py` (632 lines) — a self-contained agent engine in **pure
Python, standard library only, zero dependencies**:

- **Kairos** — a background daemon that watches for the "right moment" to act,
  with a priority task queue and trigger conditions
- **AutoDream** — memory consolidation: memories carry importance scores and
  access counts, get pruned and merged during idle-time "dream" passes
- **Mythos** — a narrative layer that maintains project understanding across
  sessions as a story with chapters and extracted themes

Run the smoke test:

```bash
python3 clawcode/test_clawcode_smoke.py
```

### `cli/` — the MetaMatrix command-line interface ✅ working

A terminal-first node interface (Click + Rich): agent delegation, interactive
chat, context sync for local knowledge files, model switching (including local
models via Ollama / LM Studio with auto-detection), personas
(`default / critic / danger / research / sovereign`), and a session-closing
protocol that documents each session as it ends.

```bash
pip install click rich requests
python -m cli.metamatrix --help
python -m cli.metamatrix status
```

### `dashboard/` — Meshtastic T-Beam node dashboard ✅ working

`metamatrix_node_dashboard.html` — a single self-contained web page (no
external dependencies) that connects to a LilyGO T-Beam over **Web Bluetooth
or Web Serial** and shows mesh peers, signal strength (SNR/RSSI), GPS,
battery, and a live message log. Open it in Chrome and connect.

### `backend/` — the original API server ⚠️ real, but tethered

A 46-route FastAPI server (auth, chat threads, an MCP control panel, phone
integration, ClawCode endpoints). It is genuine working code from the
Emergent build, but it does not run as-is today — see `backend/README.md`
for exactly why and what revival takes.

## Provenance

Built by Mark Krzan on Emergent.ai (2025–April 2026), rescued from the
platform before its phase-out, archived privately, and published here after
hands-on verification. The React frontend and mobile app from the same build
fronted the tethered backend and are not included; the pieces above are the
ones that stand on their own.

## License

MIT — see `LICENSE`.
