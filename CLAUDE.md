# CLAUDE.md — adb-mcp (Photoshop + Premiere MCP Plugins) Project Context

This is a fork/working copy of adb-mcp (Mike Chambers) extended per the
technical roadmaps in `C:\AppDev\ClaudeMCP\`. BOTH roadmaps are COMPLETE and
live-verified: Photoshop (99 tools, `Technical_Roadmap.md`) and Premiere
(110 tools, `Technical_Roadmap_Premiere.md`).

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

## PREMIERE PRO — Phase 1 implemented (2026-07-08, per Technical_Roadmap_Premiere.md)

Took `mcp/pr-mcp.py` from 26 → 55 tools (29 new). LIVE-VERIFIED 2026-07-08
against Premiere 25.x (test project F:\premier\test.prproj, driver script
`scripts/live_test_pr_phase1.py` — stages: smoke/build/effects/timeline/
audio/retest; ffmpeg-generated test media in F:\premier\media).

### Empirical findings from live verification (Premiere 25.x)

- **Crop effect matchName is `AE.ADBE AECrop`** — there is no "AE.ADBE Crop".
- **`createSetInPointAction` shifts the clip's TIMELINE START by the in-point
  delta and leaves the end unchanged.** Combining it with setEnd collapses a
  clip to zero length. splitClip's right piece = setInPoint(+offset) then
  createMoveAction(-offset), in one transaction.
- **Volume "Level" param stores `10^((dB_UI - 15)/20)`** — UI 0.0 dB reads
  0.17782794. amplitudeToDb/dbToAmplitude in audio.js encode this.
- **Audio intrinsics:** mono clip chain = ["Internal Volume Mono"]; stereo =
  ["Internal Volume Stereo", "Internal Channel Volume Stereo"]. The UI
  Panner is NOT in the component chain. Panning works by applying the
  "Balance" audio filter → component "Internal Audio Balance", param
  "Balance" normalized 0..1 (0.5 = center); set_clip_pan does this
  automatically and maps ±100 → 0..1.
- **Keyframe `.value` comes back wrapped as `{value: X}`** — unwrapped in
  utils.js sanitizeParamValue.
- **Track channel format follows the FIRST clip used to create the sequence**
  (mono clipA → mono A1; stereo clips on that track get mono components).
- **Unavailable in this version (feature-detected, clean errors):**
  TransitionFactory.createAudioTransition, audio track lock setter.
- 111 video effect matchNames / 55 audio effect displayNames enumerated live.
- Verified live: get_sequence_details, get_track_count, insert/overwrite/
  clone/move/split/remove clips, select/get_selected_clips, generic effects
  add/read/set-param/remove, set_clip_transform (Position PointF via {x,y} +
  Scale), set_clip_crop, set_clip_volume round-trip, set_clip_pan round-trip,
  fade_audio_in/out (keyframes + timeVarying confirmed). NOT yet live-tested:
  create_subsequence (needs in/out set), insert_mogrt (needs a .mogrt file),
  copy_clip_effects, add_video_transition-adjacent flows, tint white-map fix.

- **Premiere UXP is a DIFFERENT API from Photoshop:** `require("premierepro")`
  modern DOM only — no batchPlay. Everything async/await. Every mutation goes
  through `project.lockedAccess(() => project.executeTransaction(...))` — use
  `execute(getActions, project)` from `uxp/pr/commands/utils.js`.
- New UXP modules (each exports `commandHandlers`, merged in `commands/index.js`):
  - `commands/sequence_editor.js` (P1): getSequenceDetails (keystone read:
    tracks/clips/times/effects), getTrackCount, insertClipAtTime,
    overwriteClipAtTime, cloneClip, moveClip, splitClip, removeClips,
    selectClips, getSelectedClips, createSubsequence, insertMogrt.
  - `commands/effects.js` (P2): listVideoEffects/listAudioEffects (discovery),
    addVideoEffect (generic by matchName), addAudioEffect (by displayName),
    getClipEffects, setEffectParameter, removeEffect, setClipTransform
    (intrinsic "AE.ADBE Motion"), setClipCrop ("AE.ADBE Crop", auto-applied),
    copyClipEffects.
  - `commands/audio.js` (P3): setClipVolume (dB→amplitude 10^(dB/20) — VERIFY
    against UI; rawValue escape hatch provided), setClipPan, fadeAudioIn/Out
    (volume keyframes: setTimeVarying + keyframes, keyframe.position in
    sequence time), addAudioTransition (feature-detected — TransitionFactory
    only documents video), setAudioTrackLocked (feature-detected — no
    documented setter in 25.x), getAudioClipInfo.
- Descoped: set_clip_audio_gain (no UXP API surface for clip gain in 25.x).
- Bugs fixed in existing code: `appendVideoFilter` called nonexistent
  `getTrackTrack` (all 4 legacy effect tools were broken); `addMarkerToSequence`
  hardcoded marker type "WebLink" (now honors markerType); tick docstring said
  "per day" (it's 254,016,000,000 ticks per SECOND); add_tint_effect white-map/
  amount properties re-enabled (packed 64-bit ARGB via rgb_to_premiere_color —
  VERIFY live). 4 legacy effect tools marked DEPRECATED (use add_video_effect).
- `split_clip` is a composite (no native razor): overwrite-clone at split
  offset truncates the original, then the clone is trimmed into the right
  piece (setEnd + setInPoint). KNOWN LIMITATION: intermediate step can damage
  a downstream clip that starts within (split-start) seconds after the clip's
  end — documented in the tool docstring.
- API signatures verified against developer.adobe.com/premiere-pro/uxp
  (SequenceEditor, Sequence, Video/AudioClipTrackItem, TrackItemSelection,
  VideoComponentChain, ComponentParam, Markers, TransitionFactory,
  Audio/VideoFilterFactory). Version floor 25.6 for SequenceEditor.
- `config://get_instructions` in pr-mcp.py rewritten (read-first workflow,
  ticks vs seconds, insert vs overwrite, generic effects engine, audio).
- Headless enumeration works the same as ps:
  `uv run python -c "...spec_from_file_location('prmcp','pr-mcp.py')..."` → 55.

## PREMIERE PRO — Phase 2 implemented (2026-07-08, per Technical_Roadmap_Premiere.md)

Took `mcp/pr-mcp.py` from 55 → 86 tools (31 new). LIVE-VERIFIED 2026-07-08
(driver stages keyframes/lumetri/markers/transcripts in
`scripts/live_test_pr_phase1.py`).

- New UXP modules: `commands/keyframes.js` (P4: addKeyframes batch engine —
  stopwatch txn + all keyframes in ONE txn + interpolation pass; get/remove/
  clear; fadeVideoIn/Out on Opacity; kenBurns Scale+Position w/ BEZIER;
  animate_clip_property is Python-side name mapping onto addKeyframes),
  `commands/color.js` (P5: setLumetriParams ensures single Lumetri instance,
  per-param try/catch, reports availableParams on miss; getLumetriSettings),
  `commands/markers_metadata.js` (P6: sequence marker CRUD by index,
  addMarkersBatch, clip markers, Metadata get/set, batchRenameProjectItems,
  getMediaInfo, setClipLabelColor by Constants.ProjectItemColorLabel name),
  `commands/transcripts.js` (P7: Transcript.exportToJSON/importFromJSON,
  getCaptions; find_in_transcript + create_markers_from_transcript +
  export_transcript are Python-side over the JSON with a schema-tolerant
  word extractor).
- Descoped: set_lumetri_curves (needs hand-captured curve encoding first).

### Empirical findings (Premiere 25.x, live)

- **Lumetri param display names REPEAT across sections** and section headers
  appear as bool params. Verified: Basic Saturation = occurrence 1 (idx 16),
  Creative Saturation = occurrence 2 (idx 43), vignette Amount is unique
  (idx 110), "Input LUT" appears twice. setLumetriParams supports
  {occurrence: n | -1} and {paramIndex} for disambiguation; Python wrappers
  already pass the right occurrences. Basic names verified: Exposure,
  Contrast, Highlights, Shadows, Whites, Blacks, Temperature, Tint,
  Saturation, Vibrance, Intensity, Faded Film, Sharpen, Feather.
- **`Markers.getMarkers()` returns a Promise — must be awaited** (docs imply
  sync; unawaited use cost a live bug in addClipMarker).
- **`keyframe.getTemporalInterpolationMode()` returns a Promise** despite
  docs saying number. Observed values: LINEAR=0, BEZIER=5.
- **Transcript APIs ARE present in retail 25.x** (not beta-only here):
  exportToJSON succeeds on an untranscribed sequence and yields 0 words.
- Keyframe engine verified end-to-end: 3-kf batch on Motion Scale, readback,
  remove-at-time, clear (+stopwatch off), Opacity fades (0→100/100→0 at
  exact times), kenBurns (Position PointF serializes back as [x,y] array),
  marker CRUD incl. move/color/type, media info (fps/PAR/path/label),
  label color MANGO→index 7 round-trip, batch rename + undo, 9.5KB project
  metadata read.
- Known gap: getMediaInfo does not return media duration (getMedia() fails
  silently on these clips) — durationSeconds absent from response.

## PREMIERE PRO — Phase 3 implemented (2026-07-09) — ROADMAP COMPLETE

Took `mcp/pr-mcp.py` from 86 → 110 tools (24 new). LIVE-VERIFIED 2026-07-09
(driver stages pipeline/orchestration). All three Premiere phases done.

- New UXP module `commands/pipeline.js` (P8-P10): getSequenceList,
  createEmptySequence (createSequenceWithPresetPath fallback),
  duplicateSequence (createCloneAction + getSequences diff + best-effort
  rename via projectItem), nestClips (feature-detect — NO nest API in 25.x),
  openInSourceMonitor, setSourceInOut (ClipProjectItem
  createSetInOutPointsAction / createClearInOutPointsAction),
  getInstalledMogrtPath, getMogrtParameters / setMogrtParameter
  (getMGTComponent feature-detected, falls back to component chain),
  exportWithEncoder (ExportType IMMEDIATELY/QUEUE_TO_AME/QUEUE_TO_APP),
  getExportFileExtension, batchExportSequences (startBatchEncode 26.3+
  feature-detected), exportProjectInterchange (AAF/FCPXML/OTIO — NOT exposed
  by UXP in 25.x; probes candidates, clean error).
- Python-side (P11): PR_BATCH_OPERATIONS registry (17 clip ops) +
  create/play/list/delete_action_sequence (ported from ps-mcp.py; persist in
  mcp/pr_action_sequences.json), assemble_timeline_from_plan (one JSON EDL →
  clips/transitions/effects/lumetri/audio/markers with per-step error
  collection), auto_cut_at_markers (right-to-left, re-reads timeline per cut),
  list_mogrt_library + list_export_presets (server-side fs scans; 4979 .epr
  found), export_audio_only, create_title (insert_mogrt + set Source Text).
- **split_clip rewritten with a SAFE PATH**: when a downstream clip sits in
  the danger window, it clones to another track with free space, trims there,
  trims the original, clones the piece back, and removes the temp copy. Both
  paths live-verified via auto_cut_at_markers on adjacent clips (response
  includes path: "fast" | "temp-track").

### Empirical findings (Premiere 25.x, live)

- **Clone placement frame-snaps to the sequence timebase** (requested 15.0s
  landed at 15.015 on 23.976). Locating a fresh clone needs frame-level
  tolerance (FRAME_EPS 0.06s) and trims must be computed from the clone's
  ACTUAL start, not the requested time. This bug left an intermediate state
  (truncated original + untrimmed clone) before the fix.
- **createEmptySequence default preset was 23.976 fps 1920x1080** — requested
  clip times snap to that grid (10.0 → 10.01). The sequence timebase follows
  the preset, NOT the first clip added (unlike createSequenceFromMedia).
- Three-point editing verified: setSourceInOut(2,4) + overwrite → [0, 2.002)
  with inPoint ≈1.96 (frame-snapped).
- duplicate_sequence + rename verified; open_in_source_monitor verified.
- get_export_file_extension verified ("aif" from AIFF preset).
- Full JSON-plan assembly verified: 2 clips + cross dissolve + B&W + Lumetri
  + volume/fade + 2 markers in one call; then auto_cut_at_markers made 2/2
  cuts (one fast, one temp-track), then warm_look action sequence replayed
  on 2 clips. Transition with no media handles trims clip edges slightly
  (clipA end 9.968) and leaves a 1-frame gap at the join — expected.

## INDESIGN — Phase 1 implemented (2026-07-10, per Technical_Roadmap_InDesign.md)

Took `mcp/id-mcp.py` from 1 → 32 tools (31 new). LIVE-VERIFIED 2026-07-10
against InDesign 2026 (driver `scripts/live_test_id_phase1.py`, stages:
smoke/build/text2/image/export; final page visually verified via
get_page_image — headline color, 2-column threaded text, placed image,
rotated/rounded shapes all confirmed on the exported PNG).

- New UXP modules in `uxp/id/commands/` (each exports `commandHandlers`,
  merged in `index.js` router): `utils.js` (points normalization, 1-based
  pages, bounds {top,left,bottom,right} ↔ [y1,x1,y2,x2], itemByID/story
  lookup, overset serializers), `core.js` (create/open/save/saveAs/close,
  getDocumentInfo keystone read, getPageImage, exportPdf,
  getActiveDocumentSettings, debugEnums introspection), `pages.js` (add/
  remove/duplicate page, sections/numbering, layers CRUD, guides),
  `text.js` (frames, contents, insertText, stories, threading, frame
  options, styleTextRange, setTextColor — every text mutation returns
  per-frame overset state), `shapes.js` (createShape RECT/OVAL/POLYGON/LINE,
  setItemAppearance, createSwatch upsert, placeImage+fit, transformItem,
  duplicateItem, group/ungroup).
- Cleanup bugs fixed: `requiresActiveProject` ReferenceError (blocked every
  command except createDocument); `getActiveDocumentSettings` now registered
  as a real tool AND made never-throwing (main.js appends it to EVERY
  response — with no doc open it used to poison successful commands);
  `WEB_INTENT` un-hardcoded (intent param: WEB/PRINT/MOBILE, unit follows);
  createDocument returns doc info (was undefined); Python sent `pagesFacing`
  but the handler read `facingPages` (facing pages silently never applied);
  manifest panel label said "Premiere MCP Agent".

### Empirical findings (InDesign 2026, live)

- **UXP Developer Tools loads plugins by absolute manifest path** stored in
  `%APPDATA%\Adobe\Adobe UXP Developer Tool\plugins_workspace.json`. The
  InDesign entry pointed at the OTHER project
  (`C:\AppDev\ClaudeMCP\adobe-mcp\uxp-plugins\indesign`) — symptom: reload
  "works" but our code never loads, and that plugin dies at load with
  "Could not find panel vanilla in manifest", leaving a dead Connect button.
  Check the manifest path FIRST when the panel won't connect.
- **`PNGOptionsExportRange` is NOT exported by `require("indesign")`** in
  ID 2026. Recover the enum class from the current preference value:
  `app.pngExportPreferences.pngExportRange.constructor.EXPORT_RANGE`
  (enum values are instances of their enum class). getPageImage does this.
- **Enum statics are non-enumerable**: `Object.keys(Justification)` returns
  `[]`. Use `Object.getOwnPropertyNames`. The `debugEnums` UXP command
  (not an MCP tool) introspects module exports by name filter.
- **`doc.fullName` is a Promise under UXP** resolving to a file entry —
  use `(await doc.fullName).nativePath`.
- **`range.fontStyle = "Bold"` throws if the applied font lacks that
  style** ("The requested font style is not available"). The reliable form
  is one assignment: `range.appliedFont = "Family\tStyle"`. styleTextRange
  wraps the style-only path with an actionable error.
- Overset round-trip verified: small frame overflows=true → thread to an
  empty frame → story overflows=false with per-frame states. threadTextFrames
  refuses non-empty targets (threading would discard their text).
- Section numbering renames pages: after LOWER_ROMAN startAt=10 on page 3,
  `page.name` is "x" — positional tools use `pages.item(index)` so 1-based
  pageNumber params stay stable, but names returned to the AI change.
- PDF export (2pp, ~20KB) well under the 20s proxy timeout; large docs will
  exceed it — docstrings already warn timeout ≠ failure.
- NOT yet exercised: openDocument/closeDocument round-trip, MOBILE_INTENT,
  POLYGON/LINE shapes, place into existing frameId, moveTo (absolute),
  layer color enum coverage, export presets by name.

`claude_desktop_config.json`: `indesign-mcp` entry added (2026-07-11),
mirroring photoshop-mcp: `uv run --directory
C:\AppDev\ClaudeMCP\adb-mcp-main\mcp mcp run id-mcp.py`. The pre-existing
`adobe-indesign` entry belongs to the OTHER project (adobe-mcp) — leave it.

## INDESIGN — Phase 2 implemented (2026-07-11, per Technical_Roadmap_InDesign.md)

Took `mcp/id-mcp.py` from 32 → 66 tools (34 new). LIVE-VERIFIED 2026-07-11
(driver `scripts/live_test_id_phase2.py`, stages: styles/grep/tables/typo/
visual — 50/50 checks; pages 1+3 visually confirmed: drop cap w/ character
style, bullets, em-dash, inline anchored rect, object-styled card, master
running header + auto page number, table w/ header cell style, alternating
fills, merged cell).

- New UXP modules: `commands/styles.js` (P5: create/apply paragraph,
  character, object styles — all upsert; listStyles incl. group members;
  createStyleGroup + move; editStyleProperty w/ swatch+style+justification
  resolution; deleteStyle w/ replacement; generic `properties` DOM
  passthrough on all create tools), `commands/findchange.js` (P6: findText/
  changeText, findGrep/changeGrep w/ $1 backrefs + style application,
  grepApplyStyle, findChangeReport dry-run; prefs reset to
  NothingEnum.NOTHING before AND after every op in try/finally),
  `commands/masters_tables.js` (P7: createMasterSpread w/ placeholder
  frames + AUTO_PAGE_NUMBER markers, applyMaster by range,
  overrideMasterItem, createTable from 2D array, setCellContents,
  addTableRowsColumns, mergeCells, table/cell styles, applyTableStyle w/
  direct alternating fills), `commands/typography.js` (P8: baseline grid +
  setAlignToBaseline, setTextWrap, createAnchoredObject, 
  insertSpecialCharacter, setBulletsNumbering, setDropCap,
  setHyphenationJustification — all typo tools target a paragraph style OR
  a story/paragraph range via shared resolveTarget).

### Empirical findings (InDesign 2026, live)

- **`alignToBaseline` works as a direct property** on text ranges and
  paragraph styles (was flagged uncertain pre-verification; no GridAlignment
  fallback needed).
- **Unset character-style numeric props read back as `{}`** (empty object),
  e.g. pointSize/tracking on a style that doesn't define them — expected,
  not a bug.
- **Root styles throw "Invalid request on a root style"** on some property
  reads ([No Paragraph Style]) — listStyles catches per-style and reports a
  readError field instead of failing the call.
- **Styles moved into groups disappear from `doc.paragraphStyles`** but stay
  addressable via `doc.allParagraphStyles` — findStyle checks both, so
  edit/apply/delete keep working after a group move (verified).
- **Master items are NOT in `doc.pageItems`** — overrideMasterItem searches
  `page.appliedMaster.pages...allPageItems` by id.
- **`table.rows` includes header rows first**; filling row-major from the 2D
  array with headerRowCount set works directly. mergeCells via
  `cellA.merge(cellB)`. Alternating fills = direct cell fillColor+fillTint
  writes (no style needed).
- **`insertionPoint.contents = SpecialCharacters.X` works** (EM_DASH,
  AUTO_PAGE_NUMBER verified). Invalid names get the full valid list from
  `Object.getOwnPropertyNames(SpecialCharacters)`.
- **Style DEFINITIONS accept missing fonts silently.** createCharacterStyle
  with fontStyle "Bold Italic" and no family succeeded but recorded a
  missing-font reference (default face had no Bold Italic) — surfaced later
  as a blocking "Missing Fonts" dialog on recompose. Ranges throw
  immediately; style definitions don't. Always pass fontFamily WITH
  fontStyle when creating styles.
- `nextStyle` defaults to the style itself when unset.
- GREP scoped to a story via `story.findGrep()/changeGrep()` works the same
  as doc-level (all grep tools take optional storyId).
- NOT yet exercised: object style enableFill/enableStroke flags on older
  builds, table styles with real formatting properties (created bare),
  ANCHORED (floating) anchored-object position, NUMBERS list type,
  find/change wholeWord=true path.

## INDESIGN — Phase 3 implemented (2026-07-13) — ROADMAP COMPLETE

Took `mcp/id-mcp.py` from 66 → 99 tools (33 new). LIVE-VERIFIED 2026-07-13
(driver `scripts/live_test_id_phase3.py`, stages: longdoc/templates/exportpf/
orchestrate — 55+ checks passed; demo `scripts/demo_fortnite_drop.py` built a
full promo page end-to-end incl. Phase 3 geometry tools, visually verified).

- New UXP modules: `commands/longdoc.js` (P9: createToc via a managed
  "MCP TOC Style" + tocStyleEntries, addSection, hyperlinks/bookmarks,
  createCrossReference via paragraphDestinations + crossReferenceSources,
  index topics/pageReferences/generate, createBook/manageBook),
  `commands/merge_templates.js` (P10: data merge select/place/merge,
  openAsTemplate OPEN_COPY, populateTemplate by NAMED frames w/ per-frame
  status + availableFrameNames, snippets via INDESIGN_SNIPPET), 
  `commands/export_preflight.js` (P11: exportPdfAdvanced print+interactive+
  security, exportIdml, exportEpub, exportPagesAsImages, packageForPrint,
  preflight profiles/processes, listExportPresets),
  `commands/geometry_docs.js` (P12: alignItems/distributeItems as computed
  geometry — no selection needed, getDocuments/setActiveDocument (iterate,
  never assign plain objects), batchApplyStyle across all open docs).
- Python-side: ID_BATCH_OPERATIONS registry (15 story/frame/item ops) +
  create/play/list/delete_action_sequence ported from ps-mcp.py (persist in
  mcp/id_action_sequences.json, gitignored). create_text_frame/create_shape
  gained `name` params (populate_template targets).

### Empirical findings (InDesign 2026, live)

- **EPUB export wedges EVERYTHING via the OS "Pick an app" dialog.** The
  default "view after export" tried to open the .epub, Windows showed an
  app picker, and InDesign's scripting engine blocked — every subsequent
  command timed out. Panel reconnects and even a PROXY RESTART don't help
  while the dialog is up; dismissing the dialog instantly recovers.
  exportEpub now sets `viewDocumentAfterExport = false` first (both epub
  pref objects; verify on next plugin reload). The .epub itself HAD been
  created fine (timeout ≠ failure, again).
- **Books, Data Merge, Preflight, packageForPrint are ALL exposed in UXP**
  (each was flagged "may not be exposed" pre-verification): createBook made
  a real .indb (book panel appeared), selectDataSource accepted a string
  path and dataMergeFields read back, preflight processes ran ([Basic] and
  a custom profile w/ ADBE_MissingFonts + ADBE_OversetText), packaging
  produced a full package folder.
- **A text range can host only ONE hyperlink/xref source** — creating a
  cross-reference over characters already inside a hyperlink source fails
  with "object already in use by another hyperlink". Use a free range.
- **createTOC needs an active page**: set `layoutWindows.item(0).activePage`
  before `doc.createTOC(style, true, undefined, [x, y])`.
- **jpegExportRange's enum could NOT be resolved** via the value-constructor
  trick (worked for PNG) — exportPagesAsImages JPEG errored; PNG path fine.
  setExportRange now reports the constructor's own property names in the
  error for self-diagnosis (verify JPEG on next reload).
- populateTemplate round-trip verified: named frames filled (text + image w/
  fit), unknown keys reported NOT_FOUND with availableFrameNames returned.
- Windows-MCP PowerShell transport caps ~60-90s regardless of timeout param —
  long driver stages must run detached (`Start-Process cmd /c ... > log`)
  with the log polled afterwards.

ROADMAP COMPLETE: all three InDesign phases done — 99 tools (ps=99, pr=110,
id=99). NOT yet exercised: merge_records execution (source+fields verified),
book ADD_DOCUMENT/SYNCHRONIZE/EXPORT_PDF actions, EPUB fixed-layout,
export_pages_as_images JPEG (pending enum), interactive-PDF page ranges.

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



<!-- APPEND THIS SECTION to the existing CLAUDE.md at C:\AppDev\ClaudeMCP\adb-mcp-main\CLAUDE.md -->
<!-- The existing file covers the Photoshop plugin; this adds the Premiere Pro context. -->

---

# Premiere Pro MCP Plugin (pr-mcp)

## Current Work

Implementing the Premiere technical roadmap: `docs/Technical_Roadmap_Premiere.md` (26 → ~108 tools, 3 phases). Phase 1 = SequenceEditor operations, generic effects engine, audio essentials. Start with `get_sequence_details` — every other tool consumes its output.

## Architecture

AI ↔ `mcp/pr-mcp.py` (Python, FastMCP) ↔ Node proxy (`adb-proxy-socket`, ws://localhost:3001) ↔ UXP plugin (`uxp/pr/`) ↔ Premiere Pro Beta (25.3+).

- MCP side: `@mcp.tool()` functions calling `createCommand("commandName", {...})` → `sendCommand(command)`
- UXP side: handlers in `uxp/pr/commands/`, registered in the `commandHandlers` router in `index.js`
- Runtime: `uv run --directory C:\AppDev\ClaudeMCP\adb-mcp-main\mcp mcp run pr-mcp.py` (no `__main__` block — `python pr-mcp.py` does NOT work; piping EOF kills `mcp run` before it processes messages, use a subprocess driver that keeps stdin open)

## Before Implementing Anything

1. Premiere (Beta) running, project open
2. Proxy server running (`adb-proxy-socket`)
3. Plugin loaded via UXP Developer Tool (**must reload after every Premiere restart**), Connect clicked in the panel
4. **Health check: call `get_project_info` successfully.** If it fails or times out, fix the environment before writing code. If basic calls fail with undefined-object errors, a stale plugin build is loaded — reload in UXP Developer Tool.

## API Rules (non-negotiable)

- **Modern UXP DOM only:** `const ppro = require("premierepro")`. No ExtendScript, no ActionDescriptor/batchPlay patterns — they don't exist in Premiere UXP.
- **Await everything.** Nearly all Premiere UXP APIs return Promises; missing awaits produce silently wrong results.
- **Every mutation** goes inside `project.lockedAccess(() => { project.executeTransaction((compoundAction) => {...}, "MCP: <Action Name>") })`. Transaction names appear in the Undo stack — always prefix `"MCP: "`. One tool call = one transaction (batch keyframes etc. into a single transaction).
- **Time = ticks:** 254,016,000,000 ticks per **second** (the old docstring saying "per day" is wrong — fix on sight). Expose seconds in MCP tool signatures; convert with `ppro.TickTime.createWithSeconds()` on the UXP side.
- **Effects by matchName** (`"AE.ADBE Gaussian Blur 2"`, `"PR.ADBE Gamma Correction"`, `"AE.ADBE Lumetri"`). Enumerate at runtime via `ppro.VideoFilterFactory.getMatchNames()` / `AudioFilterFactory`. Never address effects by display name.
- **Track indices are 0-based** and video/audio are separate index spaces — document this in every tool docstring.
- **No native razor:** split = clone (`createCloneTrackItemAction`) + trim both parts. No native move: clone + remove.

## Known Gotchas

- **Proxy timeout ≠ failure:** `PROXY_TIMEOUT = 20`s; exports and renders routinely exceed it. The operation is still running — don't retry blindly (that's how duplicate operations happen).
- **Socket.IO replay bug (fixed for ps, verify for pr):** `socket_client.py` needs `reconnection=False` + a `command_sent` guard, or reconnects replay commands (symptom last time: duplicate adjustment layers).
- **Headless tool enumeration** (verify tool count without Claude Desktop), from the `mcp` directory:
  `uv run python -c "import importlib.util as u, asyncio; spec=u.spec_from_file_location('prmcp','pr-mcp.py'); m=u.module_from_spec(spec); spec.loader.exec_module(m); ts=asyncio.run(m.mcp.list_tools()); print(len(ts))"`
- `claude_desktop_config.json` must point at `...\adb-mcp-main\mcp` (not the repo root).
- Update the `config://get_instructions` resource in `pr-mcp.py` whenever tool semantics change — it's what the AI reads at session start.

## Reference Material

- `@adobe/premierepro` npm package = authoritative TypeScript API surface (`npm install -D @adobe/premierepro`; use `@beta` channel for preview APIs)
- Adobe's `premiere-api` sample panel = working code for every subsystem (clone https://github.com/AdobeDocs/uxp-premiere-pro-samples adjacent to this repo); its `src/` modules cover sequenceEditor, effects, keyframes, markers, metadata, encoder, transcripts
- `@adobe/eslint-plugin-premierepro` catches missing awaits and transaction misuse
- Transcript JSON spec: `sample-panels/premiere-api/html/assets/transcript_format_spec.json` in the samples repo

## Conventions

- New tools follow the roadmap's naming (`insert_clip_at_time`, `add_video_effect`, ...)
- Legacy hardcoded effect tools (`add_black_and_white_effect` etc.) become thin wrappers over `add_video_effect` — do not delete them
- Live-verify each tool against a real open project before marking it complete; verify Undo groups as one step per call
- Track roadmap progress by checking off tools in `docs/Technical_Roadmap_Premiere.md`
