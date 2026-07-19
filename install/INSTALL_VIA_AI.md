# Installing the InDesign MCP — instructions for AI agents

These steps let an AI agent with shell access (Claude Desktop/Cowork/Code,
or any MCP client) install the InDesign MCP *for* the user. Follow them in
order, ask before overwriting anything, and report each step's outcome.

If you are a human: run the one-liner in the README instead — it does all
of this automatically.

## Prerequisites to verify first

1. `uv --version` succeeds (if not: `winget install astral-sh.uv` on Windows,
   `brew install uv` on macOS — then use a fresh shell).
2. Claude Desktop (or another MCP client) is installed.
3. Adobe InDesign 20.2+ is installed.

## Steps (Windows paths; adapt for macOS)

1. **Get the code.** Download and extract
   `https://github.com/Rinellasky/adb-mcp/archive/refs/heads/master.zip`
   to `%LOCALAPPDATA%\adb-mcp` (or clone the repo there).

2. **Get the proxy.** From the latest release at
   `https://github.com/Rinellasky/adb-mcp/releases/latest`, download
   `adb-proxy-socket-win-x64.exe` (macOS: `adb-proxy-socket-macos-arm64`
   or `-x64`) into that folder.

3. **Register the MCP server.** In the user's MCP client config — for
   Claude Desktop `%APPDATA%\Claude\claude_desktop_config.json` — BACK THE
   FILE UP, then add under `mcpServers` (do not touch other entries):

   ```json
   "indesign-mcp": {
     "command": "uv",
     "args": ["run", "--directory",
              "C:\\Users\\<user>\\AppData\\Local\\adb-mcp\\mcp",
              "mcp", "run", "id-mcp.py"]
   }
   ```

   IMPORTANT: `id-mcp.py` has no `__main__` block — it MUST be launched via
   `mcp run` exactly as above; `python id-mcp.py` exits silently.

4. **Install the UXP plugin.** Download `indesign-mcp-plugin.ccx` from the
   latest release and open it — Adobe Creative Cloud installs it into
   InDesign. (Fallback for development: load `uxp/id/manifest.json` via the
   Adobe UXP Developer Tool.)

5. **Start the proxy.** Launch the proxy executable. It listens on
   `localhost:3001` and must stay running. Verify with a TCP check on
   port 3001.

6. **Connect the plugin.** Have the user open InDesign → Plugins →
   *InDesign MCP Agent* panel → click **Connect** (they can enable
   "Connect on Launch"). This step needs a human — the panel is inside
   InDesign.

7. **Restart the MCP client** (Claude Desktop) so it picks up the new
   server, then health-check by calling the `get_active_document_settings`
   tool — it returns document settings (or null with no document open) and
   proves the whole chain works.

## Troubleshooting for agents

- Tool calls time out → the plugin isn't connected (step 6) or the proxy
  isn't running (step 5). A timeout on long exports (PDF/EPUB/package) is
  NOT a failure — check the output file.
- `TypeError ... undefined` on basic calls → a stale plugin build is
  loaded; reinstall the .ccx or reload via UXP Developer Tool.
- Every command errors with "Requires an open InDesign document" → open or
  create a document first (`create_document`).
- The panel's Connect button does nothing → check the UXP Developer Tool
  console for load errors and that no OS dialog is blocking InDesign.

---

## Premiere MCP variant

Same procedure as above with these substitutions:

| InDesign value | Premiere value |
|---|---|
| server file `id-mcp.py` | `pr-mcp.py` |
| config entry `indesign-mcp` | `premiere-mcp` |
| plugin asset `indesign-mcp-plugin.ccx` | `premiere-mcp-plugin.ccx` |
| one-liner `install-indesign.ps1` | `install-premiere.ps1` |
| panel *InDesign MCP Agent* | *Premiere MCP Agent* (in Premiere Pro **Beta**) |
| health check `get_active_document_settings` | `get_project_info` |

Health-check interpretation: a project payload OR the error `Requires an open
Premiere Project` both mean the full chain is healthy. A fast `Could not connect
to premiere` means the proxy is down or the panel is not connected. A ~4-minute
timeout means a wedged call (see below).

### Premiere-specific rules for agents (important)

1. Never issue calls expected to exceed ~25 seconds through the Claude Desktop
   bridge; a call that hits the 4-minute timeout can take down the entire local
   tool runtime until Claude Desktop restarts. Run long work detached and poll.
2. Timeout does not mean failure — verify actual state with `get_project_info`
   before retrying any mutation.
3. Known issue (Premiere Beta 26.5, since ~2026-07-10): timeline-write tools can
   hang — `overwrite_clip_at_time`, `set_source_in_out`,
   `assemble_timeline_from_plan`, multi-item `create_sequence_from_media` — and a
   hung call holds the project lock so later writes hang too. Verified working:
   `get_project_info`, `get_media_info`, `import_media` (1–2 files),
   `create_sequence_from_media` (single item), `export_frame`.
4. Recovery from a wedge: restart Premiere (releases the lock), restart Claude
   Desktop (restores the runtime), reconnect the panel, re-run the health check.

Full analysis: `FINDINGS_2026-07-12_premiere_live_session.md` (repo root).
