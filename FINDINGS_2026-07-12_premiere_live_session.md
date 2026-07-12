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
