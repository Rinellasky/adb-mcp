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

Neural filters (`commands/neural_filters.js` + 8 Python tools). KEY FINDING
(verified live on PS 2026 by pixel-diff): descriptors built from NF_UI_DATA
alone (the 2021 Adobe sample format used by neural_style_transfer and the
filter_id/values form) are ACCEPTED but SILENTLY NO-OP — modern Photoshop
requires the compiled NF_SPL_GRAPH that only a real captured descriptor
contains. The working flow is capture -> preset -> replay:
start_neural_filter_capture, apply the filter once manually in Photoshop,
save_captured_neural_filter("name"), then apply_neural_filter_preset("name",
layer_id) replays it exactly (verified: ~111k px changed, style visibly
applied). Presets persist in mcp/neural_filter_presets.json (gitignored).
Capture buffer lives in plugin memory — lost on plugin reload/PS crash (one
crash observed right after a manual filter run; programmatic replays did not
crash). filter_id/values/raw_filter_stack forms kept as LEGACY for pre-2024
builds. "Super Zoom" outputs to a new document, known unreliable
programmatically; no wrapper.

Bug fixed: setActiveDocument assigned a plain info dict to app.activeDocument
("Expecting type Document" error — can never have worked upstream). Now
iterates app.documents and throws on unknown id. Verified live.

## Phase 3 — DONE (2026-07-05, all tools live-verified visually on PS 2026)

Layer styles (`commands/layer_styles.js`, shared setLayerEffect helper):
add_bevel_emboss_layer_style, add_inner_glow_layer_style,
add_outer_glow_layer_style, add_satin_layer_style (chromeFX),
add_color_overlay_layer_style (solidFill). All also registered in
BATCH_OPERATIONS. Animation timeline skipped (3/10 in roadmap matrix).

Vector (`commands/shapes.js`, new): create_shape_layer (RECTANGLE with
corner radius, ELLIPSE, LINE; fill + optional stroke; returns new layerId),
create_path_from_points (named paths, bezier forward/backward handles,
open/closed). LINE is a thin rectangle rotated into place — PS v22+
rejects the 'line' contentLayer shape class with error -25920.

Animation (`commands/animation.js`, new; verified end-to-end with a 3-frame
bouncing-ball test incl. pixel-diff between frames): create_frame_animation,
add_animation_frame, select_animation_frame, set_animation_frame_delay,
create_animation_frames_from_layers (requires timeline to exist first).
Verified descriptors on PS 2026: timeline = `makeFrameAnimation` (NOT `make
animationClass`), new frame = `duplicate animationFrameClass` (NOT `make`),
delay/select as expected. NO working descriptor for reading animation state
(get on animationClass / timeline / document frameCount all -25920) — there
is deliberately no get_animation_info tool; callers must track frame count.

ROADMAP COMPLETE. All three phases implemented; 99 tools registered.

## HARD-WON DEBUGGING LESSONS (cost a full day + several PS crashes)

1. **Photoshop's scripting error dialog blocks batchPlay forever.** When a
   batchPlay command errors with default dialog options, PS shows a modal
   dialog titled with the plugin name ("Photoshop MCP Agent: The command
   X is not currently available") and batchPlay does not return until a
   human clicks OK. From the server side this looks like a hang/timeout,
   and PS appears crashed. The dialog may sit behind other windows.
   ALWAYS set `_options: {dialogOptions: "silent"}` on batchPlay
   descriptors ("dontDisplay" did NOT suppress these).
2. **With "silent", failures do not throw.** They come back as
   `{_obj: "error", result: <code>, message}` entries in the batchPlay
   results array. Check results and throw explicitly (see
   throwOnBatchPlayError in shapes.js) or failures pass silently — a
   failed `make` once caused the handler to rename the previously active
   layer instead (data corruption, not just a missed error).
3. **A dialog titled "Photoshop MCP Agent" is OUR plugin** (manifest name
   matches the old uninstalled ccx). Do not chase stale-plugin theories
   first; check for the blocking-dialog scenario above.
4. **After Photoshop restarts, dev plugins are gone until re-loaded in UXP
   Developer Tools**, but a generic connection error can also mean the
   old wedged process is still alive — check `tasklist` for Photoshop.exe
   and its PID before assuming a fresh instance.
5. **In-plugin state (e.g. neural filter capture buffer) dies with PS or
   plugin reload.** Persist captured data server-side immediately (the
   background watcher pattern in scratchpad/nf_capture_watcher.py).

## Testing

- Live smoke test: `get_documents` should return open docs. Then run a new
  tool and pull `get_document_image` to verify visually.
- Handshake test without Photoshop: pipe MCP initialize + tools/list JSON-RPC
  into `uv run --directory mcp mcp run ps-mcp.py` (keep stdin open).
- Direct tool enumeration: import ps-mcp.py via importlib and
  `asyncio.run(m.mcp.list_tools())`.
