# Release v1.1.0 install-path test plan (for a clean VM)

Purpose: validate the three install paths for the InDesign MCP release
exactly as a new user would experience them. Nothing on the VM may be
pre-configured beyond the stated prerequisites — the whole point is a
cold-start test.

Report results per test as PASS / FAIL with exact error text, a screenshot
at each failure, and the versions listed under "Record".

---

## VM prerequisites (set up BEFORE testing starts)

- Windows 10/11 **x64** VM, 8 GB+ RAM, ~25 GB free disk, internet access
- **Adobe Creative Cloud desktop app** installed and **signed in** with a
  license that includes InDesign; install **InDesign 2026 (20.2+)** through
  it. Launch InDesign once and dismiss first-run dialogs.
- **Claude Desktop** installed and **signed in** (account with MCP support).
  Launch once to confirm it works.
- `winget` available (Windows 11 default; on Win10 install App Installer).
- Do **NOT** pre-install: uv, Python, Node, git. The installer must cope.
- Snapshot the VM here ("CLEAN") so each test can start from the same state.

## Record (once per VM)

Windows version/build, PowerShell version (`$PSVersionTable.PSVersion`),
InDesign version (Help > About), Creative Cloud version, Claude Desktop
version, whether the account is Pro/Max/Team.

---

## TEST 1 — the one-liner (headline path) [restore CLEAN first]

In a NORMAL PowerShell window (not admin):

```powershell
irm https://raw.githubusercontent.com/Rinellasky/adb-mcp/master/install/install-indesign.ps1 | iex
```

Verify each of these, in order:

1. If uv was missing, it installs via winget without an unrecoverable error.
   (A required fresh shell after uv install is a KNOWN caveat — if the
   script says to re-run in a new terminal, that's acceptable behavior;
   note it.)
2. `%LOCALAPPDATA%\adb-mcp` exists and contains `mcp\id-mcp.py`,
   `adb-proxy-socket-win-x64.exe`, `indesign-mcp-plugin.ccx`.
3. `%APPDATA%\Claude\claude_desktop_config.json` now contains an
   `indesign-mcp` entry, AND a backup file
   `claude_desktop_config.json.bak-indesign-mcp` exists. If the config had
   other servers, confirm they are untouched.
4. The `.ccx` opened and Creative Cloud installed the plugin (CC may show a
   confirmation; InDesign > Plugins menu should list *InDesign MCP Agent*
   after an InDesign restart).
5. Final instructions printed (proxy + Connect steps).

Then complete the chain manually:

6. Run `%LOCALAPPDATA%\adb-mcp\adb-proxy-socket-win-x64.exe`. Watch for
   SmartScreen ("Windows protected your PC") — if it appears, record it,
   choose More info > Run anyway. Confirm it logs it is listening on 3001.
7. InDesign: Plugins > InDesign MCP Agent > **Connect** (button flips to
   Disconnect).
8. Restart Claude Desktop. Confirm `indesign-mcp` appears in the tools/
   connectors list.
9. In a Claude chat, run the smoke sequence:
   - `get_active_document_settings` → returns (null is fine with no doc)
   - `create_document` (612 x 792, PRINT_INTENT, 1 page)
   - `create_text_frame` page 1, bounds {top:100,left:100,bottom:200,
     right:400}, contents "VM install test"
   - `get_page_image` page 1 → Claude should SEE the text on the page
   - `export_pdf` to `%USERPROFILE%\Desktop\vm_test.pdf` → file exists

PASS = all 9. Items 1-5 are the installer's responsibility; 6-9 the
runtime chain.

---

## TEST 2 — .dxt double-click path [restore CLEAN first]

1. Download from https://github.com/Rinellasky/adb-mcp/releases/latest :
   `indesign-mcp.dxt`, `indesign-mcp-plugin.ccx`,
   `adb-proxy-socket-win-x64.exe`.
2. Install uv first (`winget install astral-sh.uv`, then open a NEW
   terminal) — the .dxt path assumes uv exists; we need to confirm how the
   failure looks WITHOUT uv too, so first try step 3 with NO uv and record
   Claude Desktop's error, then install uv and redo.
3. Double-click `indesign-mcp.dxt` (or Claude Desktop > Settings >
   Extensions > install from file). Approve. Restart Claude Desktop.
4. Double-click the `.ccx` → Creative Cloud installs the plugin.
5. Run the proxy, Connect the panel, and run the same smoke sequence as
   Test 1 step 9.

PASS = extension installs, tools appear, smoke sequence completes. Also
record the no-uv error message verbatim (we may need to document it).

---

## TEST 3 — AI-agent install path [restore CLEAN first]

1. Install uv + Claude Desktop as per prerequisites (agent may do this).
2. In a Claude Desktop chat (or Cowork with shell access), prompt exactly:

   > Follow https://github.com/Rinellasky/adb-mcp/blob/master/install/INSTALL_VIA_AI.md
   > and install the InDesign MCP for me.

3. Let the agent work; only intervene where the doc says a human is needed
   (clicking Connect in InDesign; restarting Claude Desktop).
4. Judge: did the agent complete steps 1-5 of the doc without inventing
   wrong steps? Did the health check pass? Record where it deviated or got
   confused — every confusion is a doc bug to report.

---

## Failure-report format (per failure)

```
TEST n / step m
Command or action:
Expected:
Actual (verbatim error / screenshot):
Workaround found (if any):
```

## Known caveats (do not report as bugs, but DO note occurrences)

- uv PATH not live in the same shell after winget install → fresh terminal
- SmartScreen prompt on the proxy exe (unsigned binary)
- InDesign must be RESTARTED after .ccx install for the panel to appear
- Long exports (PDF/EPUB/package) may exceed the 20s proxy timeout —
  timeout is not failure; check the output file
- EPUB export: fixed in code to suppress "view after export", but if an OS
  "Pick an app" dialog ever appears, EVERYTHING blocks until dismissed
