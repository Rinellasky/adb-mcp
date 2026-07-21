# Findings — After Effects MCP Priority 1 live session (2026-07-20)

Host: RYUJIN. AE Beta 26.5 (CEP 13 runtime, extension `com.mikechambers.ae.mcp`
loaded via junction at `%APPDATA%\Adobe\CEP\extensions\com.mikechambers.ae`).
Proxy: `adb-proxy-socket-win-x64.exe` on port 3001.

## Live verification: 28/28 checks passed

One-shot socket test client (modeled on `mcp/socket_client.py` /
`mcp/core.py sendCommand`) drove all 9 Priority 1 handlers through the proxy
against the live panel:

- `getProjectInfo` (rich): name/path/dirty/numItems/items inventory.
- `createProjectFolder`: root + nested (parentFolderId honored), bad-parent
  id returns error.
- `importFile`: into folder via folderId; missing file returns error.
- `importImageSequence`: `frame_0001.png` picks up all 5 frames as one
  footage item (verified duration × frameRate = 5); folderId omitted lands
  at root.
- `moveItemsToFolder`: batch move into folder, folderId omitted moves to
  ROOT (verified `parentFolder === rootFolder`), unknown ids land in
  `failed[]` without aborting the batch.
- `saveProjectAs` / `saveProject`: file written, dirty flag clears; save on
  never-saved project correctly errors toward save_project_as.
- `openProject`: dirty-guard errors without `force`, succeeds with
  `force=true`; missing file errors. No modal dialogs at any point.
- `createProject`: same dirty-guard semantics; clean project needs no force.

Undo verification: each mutating handler (createProjectFolder, importFile,
moveItemsToFolder) reverts with exactly ONE Edit > Undo and returns with one
Redo. Undo group names ("MCP: ...") verified by code inspection —
ExtendScript has no API to read undo-stack labels.

**No commands.js bugs found.** All first-run test failures were harness-side.

## AE 26 scripting gotchas (for future test harnesses)

- Edit > Redo menu command id is **2035**, not 17. `app.executeCommand(17)`
  silently does nothing; `app.findMenuCommandId("Redo")` returns 0 because
  the menu label is dynamic ("Redo Create Folder"). Undo is still 16.
- Item ids are stable across undo/redo of their creation.
- Root-level items report `parentFolder.id === 0` (rootFolder id).

## Claude Desktop bridge deaths — root cause investigation

The bridge died 4× in the prior chat session (post-reboot, every ~2nd call).
Suspected cause was the new `aftereffects-mcp` config entry crash-looping.
That hypothesis is **not supported**:

1. `ae-mcp.py` imports clean in 0.93 s — `socket_client.configure()` and
   `core.init()` only set globals; no network, no blocking at import time.
   Nothing to fix.
2. The string "aftereffects" appears in **zero** Claude Desktop logs
   (mcp.log, main.log, main1.log, no `mcp-server-aftereffects*.log`) — the
   entry was never even launched by Desktop.
3. `claude_desktop_config.json` has been **rewritten by Claude Desktop and
   the entire `mcpServers` block is gone** — all ~17 server registrations
   (photoshop-mcp, premiere-mcp, aftereffects-mcp, blender, github, ...),
   plus `localAgentModeTrustedFolders` and other preferences. The `.bak`
   predates the aftereffects entry and is the only surviving copy of the
   registrations.
4. The actual smoking gun found: the old config's `token-meter` MCP sets
   `TOKEN_METER_WS_PORT=3001` — the same port as the adb proxy. Its log
   shows `WebSocket error on :3001: listen EADDRINUSE` followed by
   unexpected transport closes. Two processes fighting over 3001 is the
   plausible bridge destabilizer, not ae-mcp.py.

### Follow-ups — RESOLVED later the same session

- Config fully restored (2026-07-20, Desktop closed during edit): all 17
  `mcpServers` entries from the `.bak` plus a new `aftereffects-mcp` entry
  (`uv run --directory ...\mcp mcp run ae-mcp.py`, same pattern as ps/pr;
  launch command smoke-tested, exit 0).
- token-meter moved to `TOKEN_METER_WS_PORT=3002`. The adb proxy KEEPS
  3001 — that port is hardcoded in the CEP/UXP panels, all five mcp/*.py
  servers, and the dist exe, so token-meter (one env var) was the right
  side to move.
- Wiped preferences restored from `.bak` (trusted folders, chrome
  extension, permission opt-ins, epitaxy permission modes); newer UI state
  kept. Pre-edit copies: `claude_desktop_config.json.pre-restore` and
  `.pre-prefs-restore`.
- STILL OPEN: rotate the plaintext GitHub PAT (`ghp_...`) in the `github`
  server env — it lives in the restored config AND the `.bak`.
