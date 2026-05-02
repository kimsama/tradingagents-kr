# Diagrams

Excalidraw source files (`.excalidraw` JSON) for the architecture documents in `../`.

## Files

| File | Purpose |
|---|---|
| `00-architecture.excalidraw` | Editable source ([Excalidraw scene format](https://github.com/excalidraw/excalidraw)) |
| `00-architecture.png` | Web-shareable rendering (4000 × 4480 px, ~450 KB) |
| `render_pillow.py` | Self-contained Pillow renderer (no browser, no network) |

The diagram is the visual companion to [`../00.Architecture.md`](../00.Architecture.md). It shows the full pipeline (CLI → orchestrator → analysts → research debate → trader → risk debate → portfolio manager → END) plus the three cross-cutting layers (LLM provider abstraction, data vendor routing, persistence).

## How to view

- **PNG (instant):** open `00-architecture.png` in any image viewer or paste into Slack / GitHub / Notion.
- **Editable scene:** drag `00-architecture.excalidraw` onto [excalidraw.com](https://excalidraw.com) (or open in VS Code with the `pomdtr.excalidraw-editor` extension).

## How to re-render after editing

Two renderers are available — pick whichever works in your environment.

### Option A: Pillow renderer (recommended — no external deps)

```bash
python3 docs/diagrams/render_pillow.py docs/diagrams/00-architecture.excalidraw
# → writes 00-architecture.png next to the source
# Optional: -s 3 for 3x scale, -o path/to/custom.png for a different output
```

Requires only Pillow (`pip install Pillow`) and a system monospace font at `/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf` (present on most Debian/Ubuntu/WSL2 systems).

### Option B: Skill's headless-Chromium renderer (richer styling, requires network)

```bash
cd ~/.claude/skills/excalidraw-diagram-skill/references
uv run python render_excalidraw.py /path/to/00-architecture.excalidraw
```

Uses the official `@excalidraw/excalidraw` library via Playwright. Higher fidelity (rounded corners, anti-aliasing match Excalidraw web), but needs a working headless Chromium and reliable access to `esm.sh`. First-time setup:

```bash
cd ~/.claude/skills/excalidraw-diagram-skill/references
uv sync
uv run playwright install chromium
```

## Conventions

- **Color semantics** match `~/.claude/skills/excalidraw-diagram-skill/references/color-palette.md`:
  - Orange — start / trigger (CLI)
  - Blue (primary) — orchestrator / data flow
  - Purple (AI/LLM) — agent nodes
  - Light blue (tertiary) — tool nodes
  - Yellow (decision) — Research Manager
  - Red (warning) — risk debators
  - Green (end/success) — Portfolio Manager / END
  - Dark slate (`#1e293b`) with green text — code/data evidence artifacts
- **Roughness `0`** — clean, modern edges (not hand-drawn)
- **Font family `3`** — monospace
- **Section IDs** are prefixed (`s1_`, `s2a_`, `s2b_`, …) so cross-section bindings stay readable when editing the JSON by hand
