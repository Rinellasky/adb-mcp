# CLAUDE.md — adb-mcp (Photoshop MCP Plugin) Project Context

This is a fork/working copy of adb-mcp (Mike Chambers) being extended per
`Technical_Roadmap.md` (in `C:\AppDev\ClaudeMCP\`). Phase 1 is COMPLETE and
live-tested against Photoshop 2026. Current work: Phase 2.

## Architecture (three processes, all must be running to test live)

1. **MCP server** (`mcp/ps-mcp.py`) — FastMCP, Python. Defines tools with
   `@mcp.tool()`, sends JSON commands via `createCommand(action, options)` +
   `sendCommand(cmd)` through `socket_client.py`.
2. **Proxy** (`adb-proxy-socket-win-x64.exe`, listens on localhost:3001) —
   relays commands between server and plugin.
3. **UXP plugin** (`uxp/ps/`) — runs inside Photoshop, executes commands via
   `batchPlay`. Command modules live in `uxp/ps/commands/*.js`; each exports
   `commandHandlers` merged in `commands/index.js`.

## CRITICAL conventions (violating these caused real bugs)

- **ps-mcp.py has NO `__main__` block.** It MUST be launched via the MCP CLI:
  `uv run --directory <repo>\mcp mcp run ps-mcp.py`. Running `python ps-mcp.py`
  imports the module and exits silently with code 0.
- **UXP JavaScript, NOT ExtendScript.** Use `batchPlay` with `_obj` descriptor
  objects. `ActionDescriptor`, `charIDToTypeID`, `executeAction` DO NOT EXIST
  in UXP. Follow the patterns in existing `commands/*.js` files (uses
  `execute()`, `findLayer()`, `selectLayer()` from `commands/utils.js`).
- **Python tool params:** plain `int`, `str`, `dict`, `list`, `float`, `bool`
  with docstring Args sections, matching existing tools.
- **RGBColor descriptors use `grain` (not `green`)** for the green channel in
  batchPlay color objects.

## Dev workflow / gotchas

- After editing `uxp/ps/commands/*.js`: reload the plugin in Adobe UXP
  Developer Tools (dev-loaded plugins DO NOT persist across Photoshop
  restarts — must re-Load each time Photoshop restarts).
- After editing `mcp/*.py`: restart the MCP client (Claude Desktop / Claude
  Code session) so the server relaunches.
- The old `.ccx`-installed "Photoshop MCP Agent" and the Claude Desktop `.dxt`
  extension were UNINSTALLED on 2026-07-04. If a stale plugin ever answers
  again (symptom: `TypeError: Cannot read properties of undefined (reading
  'batchPlay')` on even simple reads), check for a reinstalled ccx/dxt copy.
- `claude_desktop_config.json` entry `photoshop-mcp` uses:
  `uv run --directory C:\AppDev\ClaudeMCP\adb-mcp-main\mcp mcp run ps-mcp.py`
- `C:\AppDev\ClaudeMCP\adobe-mcp` is a DIFFERENT project (successor, used by
  the Illustrator/InDesign config entries). Do not modify it for this work.
- `*.OGjs` files are pre-Phase-1 backups of the originals. Leave them.
- No git history in this folder (downloaded as zip). Consider `git init` +
  initial commit before large changes.

## Phase 1 — DONE (2026-07-04, all 12 tools visually verified live)

Selection (`commands/selection.js`): select_color_range, magic_wand_select,
modify_selection (expand/contract/feather/smooth/border), grow_selection,
select_similar.
Color (`commands/adjustment_layers.js`): add_curves_adjustment_layer,
add_levels_adjustment_layer, add_hue_saturation_adjustment_layer,
add_selective_color_adjustment_layer.
Painting (`commands/painting.js`, new): paint_brush_stroke, eraser_stroke,
smudge_stroke — implemented as work-path-from-points + stroke-with-tool +
delete-path. Verified painting real pixels.

Bug fixed: `socket_client.py` had auto-reconnection enabled with the command
emit inside the `connect` handler → transient reconnects replayed commands
(observed: duplicate Levels layer). Fixed with `reconnection=False` + a
`command_sent` guard. Fix benefits ps/pr/ai servers (shared module).

## Phase 2 — DONE (2026-07-04, 83 tools registered; batch tools live-tested)

Batch processing (server-side Python only, no UXP changes): batch_process_layers,
create/play/list/delete_action_sequence. Operations dispatch existing UXP
actions per layer via the BATCH_OPERATIONS registry in ps-mcp.py; settings use
the same camelCase keys as the single-layer tool's command options. Sequences
persist to mcp/action_sequences.json (gitignored). Per-layer/per-step errors
are collected and processing continues; a lost connection aborts and marks the
rest SKIPPED. Live-verified: batch set_layer_visibility (incl. bad-ID error
path) and a two-step sequence replay.

Neural filters (EXPERIMENTAL, `commands/neural_filters.js` + 4 Python tools):
apply_neural_filter (generic envelope verified against Adobe's official
neural-filter-sample repo), neural_style_transfer (params verbatim from that
sample), start_neural_filter_capture / get_captured_neural_filters (records
`neuralGalleryFilters` notification events for exact replay via
raw_filter_stack). NOT yet live-tested: requires plugin reload in UXP Dev
Tools, the filter must be downloaded in Filter > Neural Filters first, and
per-filter spl:: value keys are version-sensitive — capture-then-replay is
the reliable path. "Super Zoom" outputs to a new document and is known
unreliable programmatically; no dedicated wrapper was built for it.

## Phase 3 — NEXT (see Technical_Roadmap.md; adapt roadmap code samples,
they use invalid ExtendScript APIs)

Priority order: vector/path tools, advanced layer styles (bevel/emboss,
glow, satin), animation timeline (low priority per roadmap matrix). Always
check existing tools in ps-mcp.py before adding.

## Testing

- Live smoke test: `get_documents` should return open docs. Then run a new
  tool and pull `get_document_image` to verify visually.
- Handshake test without Photoshop: pipe MCP initialize + tools/list JSON-RPC
  into `uv run --directory mcp mcp run ps-mcp.py` (keep stdin open).
- Direct tool enumeration: import ps-mcp.py via importlib and
  `asyncio.run(m.mcp.list_tools())`.
