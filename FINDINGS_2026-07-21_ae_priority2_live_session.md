# Findings — After Effects MCP Priority 2 live session (2026-07-21)

Host: RYUJIN. AE Beta 26.5 (CEP 13, extension junction live-edit).
Proxy: `adb-proxy-socket-win-x64.exe` on port 3001. Panel reload picks up
commands.js changes; no AE restart needed.

## Live verification: 42/42 checks passed

Driver: `scripts/live_test_ae_p2.py` (one-shot socket client, same pattern
as the Priority 1 driver). All 7 Priority 2 handlers verified end-to-end:

- `createComposition`: 1280x720 / 5 s / 30 fps created, opened in viewer
  (`activeItem.id` matches), single undo step, id stable across undo/redo.
- `getCompositionDetails`: empty comp returns full settings block +
  `layers: []`. After populating (red solid + text layer parented to the
  solid + transforms + Gaussian Blur, added via executeExtendScript in
  place of the by-hand step): layer types (AV/Text), parenting
  (`parentIndex` = solid index), switches (shy/solo/enabled/locked/3D),
  transforms (position/rotation/opacity/anchorPoint/scale), sourceId, and
  the applied effect (`ADBE Gaussian Blur 2`, enabled) all read correctly.
- `getFrameImage`: PNG at t=0 and t=2.5, dimensions match comp (1280x720),
  temp file cleaned up; t=999 clamps to `duration - frameDuration`
  (4.9667 s). Python side (`ae-mcp.py get_frame_image`) returns a real MCP
  `Image` (JPEG-converted, pr-mcp pattern), strips the response payload,
  and deletes the temp PNG.
- `setCompositionSettings`: bgColor-only partial update leaves
  name/size/duration/frameRate untouched; multi-field update
  (name/width/height/duration/frameRate) applies all; single undo step.
- `setWorkArea`: start/duration round-trip, single undo step.
- `addCompositionMarker`: point marker (duration 0) + ranged marker
  (duration 2 s) verified via markerProperty readback; each is one undo.
- `openComposition`: switches viewer/activeItem back from a second comp.
- Error paths: all six comp-taking tools return
  `"Composition not found: id 99999"` cleanly.
- Camera/Light comp: getCompositionDetails does not throw.

## AE 26.x divergences from the draft (both fixed/annotated)

1. **`comp.saveFrameToPng` is ASYNCHRONOUS.** The call returns before the
   PNG hits disk (~1 s later on a 720p comp); the draft's immediate
   `f.exists` check always failed even though every frame rendered fine.
   Fix in `getFrameImage`: poll `f.exists && f.length > 0` with
   `$.sleep(100)` up to 15 s. First-run failures (t=0, mid, clamp) all
   passed after the fix.
2. **Camera layers report Opacity/Scale values on 26.x** (100 /
   [100,100,100]) instead of the draft-expected null — the properties
   exist on CameraLayer's transform group here. The null-safe `propValue`
   helper is kept for older builds; required behavior (no throw) holds.
   `sourceId` is correctly null for Camera/Light.

## Response-unwrap note (get_frame_image, Python side)

The AE panel wraps every handler result in a createPacket envelope, so
unlike pr-mcp's `result["response"]["filePath"]`, the AE unwrap is
`json.loads(result["response"]["content"][0]["text"])` → `payload["path"]`.
Non-SUCCESS status, unparseable payloads, and `success != true` all fall
through to returning the raw result (error envelope) unchanged.

## Environment / process notes

- Panel reload can be driven headlessly:
  `AfterFX (Beta).exe -s "app.executeCommand(app.findMenuCommandId('AfterEffects MCP Agent'))"`
  toggles the panel closed/open in the running instance (run twice).
  The Connect click still needs UI automation unless
  "Connect automatically on launch" is checked in the panel.
- Headless tool count after merge: 18 (11 Priority 1 + 7 Priority 2).
