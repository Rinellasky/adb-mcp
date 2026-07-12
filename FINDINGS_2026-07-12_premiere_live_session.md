# Session Findings - 2026-07-12 - Premiere MCP live validation (showcase edit session)

## CRITICAL: long-running synchronous calls take down the entire Claude Desktop local-tool bridge
Three reproductions in one session:
1. import_media (pre-restart plugin build) - hung, never returned
2. create_sequence_from_media with 2 items - hung (single-item calls work fine)
3. assemble_timeline_from_plan with 7 clips - exceeded 4-min bridge timeout

Cascade effect: after each wedged call, ALL local MCP servers (including unrelated
Windows-MCP and Filesystem) time out until Claude Desktop is fully restarted.
The cascade is a Claude Desktop bridge-level issue, not adb-mcp - but the practical
plugin-side requirement is absolute: every handler must return well under 4 minutes.

NOTE: assemble_timeline_from_plan may have been legitimately still executing when the
timeout hit (7x 4K clip placements). Timeout != failure. Sequence state unconfirmed
at time of writing - check BLUE_BASE_60 in blue_base_showcase-2.prproj.

## Architectural fix required (priority)
Async execution pattern for any op that loops over items:
  submit -> returns jobId immediately -> poll_job(jobId) tool for status/result
(same shape as vidIQ job_poll). Interim mitigation: chunk multi-item plans into
single-item calls (one clip / one transition / one marker per call).

## BUG: exported frame path reported with doubled extension
- Plugin writes the file with the correct single extension (verified on disk: f0010.jpg)
- But the RESPONSE path string doubles it (f0010.jpg.jpg)
- get_sequence_frame_image server builds its read-back path from the reported string,
  so it reads frame_<seqid>_<sec>.png.png -> [Errno 2] every time
- Fix: correct the response path string in the uxp/pr exportFrame handler (or strip
  the duplicate ext server-side in pr-mcp.py)
- Workaround (validated): pre-seed %TEMP%\frame_<seqid>_<sec>.png.png with a
  downscaled PNG before calling; server returns it inline. Bonus: pre-seeding small
  images keeps context cost low (~100KB vs 2.4MB native 4K frames).

## Verified-good single operations (fast, reliable, repeated all session)
open_project, get_project_info, get_media_info, import_media (1-2 files),
create_sequence_from_media (single item), export_frame

## Wedge list (hang, no return, cascades to bridge)
- create_sequence_from_media (2+ items)
- assemble_timeline_from_plan (7 clips) - possibly execution-time, not a hang
- photoshop-mcp open_photoshop_file (known dialog-wedge family, PS side)

## Environment notes
- Premiere Beta auto-recovered project as blue_base_showcase-2.prproj after restart;
  all imports and sequences survived. senderId churn is normal across reconnects.
- ticksPerSecond confirmed 254016000000 in live sequence payloads.

## UPDATE (same day, later): ROOT CAUSE CONFIRMED - Premiere Beta 26.5 breaking changes
- Premiere Beta auto-updated to 26.5.0.59 (verified via exe VersionInfo). Plugin was verified Jul 4-9 on the prior build.
- Adobe posted "Premiere 26.3 API Updates" on the CC Developer Forums on 2026-07-10 announcing BREAKING CHANGES:
  1. Action creation must now happen inside project.lockedAccess() (enforcement tightened).
  2. Sync/async signatures are churning per release (e.g. Sequence.setSelection is now synchronous).
  https://forums.creativeclouddeveloper.com/t/premiere-26-3-api-updates/12009
- Our failure mode: utils.js ticksFromSeconds() returns app.TickTime.createWithSeconds(seconds) UNAWAITED.
  Handlers pass the resulting Promise into create*Action() natives (createOverwriteItemAction,
  createSetInOutPointsAction), some even calling ticksFromSeconds INSIDE the executeTransaction callback
  where await is impossible. On 26.5 this hangs the native bridge (no throw, no reply) and the wedged
  transaction keeps holding the project lock, blocking ALL subsequent lockedAccess writes.
- Same-family suspect: `const editor = app.SequenceEditor.getEditor(sequence)` unawaited (Adobe samples await it).
- Fix pattern (per Adobe samples): hoist `await app.TickTime.createWithSeconds(...)` and `await getEditor(...)`
  BEFORE the lockedAccess block; create only Action objects inside the lock.
- Adopt @adobe/eslint-plugin-premierepro to catch these statically:
  https://github.com/adobe/eslint-plugin-premierepro
- Full audit of every execute()-using handler needed in Claude Code; this session live-patches only the
  minimal handler set (overwriteClipAtTime, setSourceInOut, getEditor call sites) to finish the showcase edit.

## FINAL (session close): patch attempt + fallback delivery
- Live-patched sequence_editor.js / pipeline.js (awaited TickTime + getEditor, hoisted out of locks),
  reloaded plugin via UDT on 26.5 -> setSourceInOut STILL hangs. The unawaited-Promise theory is
  insufficient; 26.5 breakage is deeper (createSetInOutPointsAction / lock path itself). Needs UDT
  console debugging in Claude Code. Patched files left in worktree UNCOMMITTED (originals preserved
  as *.bak265) - review before keeping.
- Showcase video delivered via detached-ffmpeg fallback implementing the exact planned edit
  (7 segments, xfade fade/zoomin/fadeblack transitions, eq grade, -6/-12dB audio, acrossfades):
  F:\premier\mcp_showcase\BLUE_BASE_60.mp4 (55.66s, 4K30, NVENC). Build script:
  F:\premier\mcp_showcase\assets\build_video.ps1. Frame-verified.
- Detached-execution + poll pattern (Start-Process hidden + marker file) worked flawlessly and is
  the model for the async MCP architecture: NEVER let a tool call wait on long work.
- Bridge cascade root observation refined: ANY local tool call exceeding the 4-min bridge timeout
  (incl. a heavy Windows-MCP Snapshot) can kill the entire Claude Desktop local-tool runtime.
