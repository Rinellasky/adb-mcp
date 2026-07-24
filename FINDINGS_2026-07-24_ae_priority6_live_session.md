# Findings — After Effects MCP Priority 6 live session (2026-07-24)

Host: RYUJIN. AE 2026 retail 26.3x87 (CEP 13, extension junction
live-edit). Proxy: `adb-proxy-socket-win-x64.exe` on port 3001. Panel
auto-connect did not fire after the menu-toggle reload (per P5 pattern) —
the CDP 8088 `connectToServer()` kick connected it first try, both
reloads this session.

## Merge

Priority 6 complete: 46 → 53 tools (Effects Engine & Switches, 7 tools).
Headless enumeration confirms 53. `commands.js` gains valueTypeToString
in AE_HELPERS plus listEffectMatchNames / addEffect / getLayerEffects /
setEffectProperty / removeEffect / setMotionBlur / setFrameBlending
(7 handlers + registrations). `ae-mcp.py` gains the matching 7 tools.

## Live verification: 54/54 checks passed

Driver: `scripts/live_test_ae_p6.py`. Full canonical workflow verified:
search "gaussian" → add_effect "ADBE Gaussian Blur 2" → get_layer_effects
→ set_effect_property → round-trip → getFrameImage pixel-diff. Also:
color/checkbox/dropdown/point value shapes, keyframed-param refusal with
exact propertyPath (and that path working through add_keyframe),
CUSTOM_VALUE listing, invalid-matchName refusal, remove_effect index
shift, motion blur dual-switch rendering, frame blending enum round-trip,
one undo step per mutating call (Redo id 2035 confirmed).

## Empirical findings (AE 26.3x87)

- **Bug found+fixed during verification: nested property GROUPS break
  JSON.parse.** Every effect carries a "Compositing Options" group
  (`ADBE Effect Built In Params`) among its properties. A group has no
  `propertyValueType`/`value`, and ExtendScript's JSON.stringify emits
  **literal `undefined`** (`"value":undefined`) — invalid JSON. The
  panel's executeAECommand JSON.parse then silently falls back to the
  raw string, so the MCP client received a double-encoded string payload
  instead of an object. getLayerEffects now detects
  `propertyType !== PropertyType.PROPERTY` and reports
  `valueType: "GROUP", value: null`. Guard also added: `value ===
  undefined → null`.
- **Session-sticky effect defaults**: `parade.addProperty(matchName)`
  applies the effect with the AE SESSION's last-used parameter values,
  not factory defaults (fresh project + fresh comp + fresh solid gave
  Blurriness=25 after an earlier set of 25 in the same AE session).
  Callers must read get_layer_effects after add_effect rather than
  assuming factory defaults. Test drivers must be baseline-aware.
- **app.effects enumeration cost**: 446 effects installed; unfiltered
  list_effect_match_names round-trips in ~4-7s through the socket
  (payload survives fine). Filtered calls are fast. Not cheap enough to
  call casually — prefer category/search filters.
- **fx.propertyIndex == Effect Parade ordinal** on this build:
  add_effect's returned effectIndex matched get_layer_effects ordering
  for 1st/2nd/3rd adds, and index-shift after remove behaved as expected
  (former #3 became #2).
- **Dropdown params are plain OneD** (e.g. "Blur Dimensions"
  `ADBE Gaussian Blur 2-0002`): 1-based int 2 set + round-tripped
  exactly. Checkbox ("Repeat Edge Pixels") is also OneD: `true` reads
  back as `1`.
- **COLOR params round-trip 4-component**: set `[0, 0.5, 1]` on
  `ADBE Fill-0002` reads back `[0, 0.5, 1, 1]` (alpha appended).
- **Point param** (`ADBE Circle-0001`, TwoD_SPATIAL): `[111, 222]`
  round-trips exactly.
- **CUSTOM_VALUE write error (26.x pattern confirmed)**: setValue on
  `ADBE CurvesCustom-0001` → "After Effects error: Can not get or set a
  value from this property ... This propertyValueType CUSTOM_VALUE has
  not been implemented." — surfaced cleanly; get_layer_effects lists it
  with value=null without breaking.
- **getFrameImage adds NO undo step** (verified: set → getFrameImage →
  one undo reverted the set). Undo/redo one-step-per-call held for
  add_effect, set_effect_property, remove_effect, set_motion_blur.
- **Motion blur render contract confirmed**: layer switch alone leaves
  the render byte-identical; layer + comp master changes pixels.
  Partial-arg contract holds (comp_enabled alone doesn't touch the
  layer switch).
- **Frame blending on a SOLID layer works** (no footage needed):
  all three states round-trip via `frameBlendingType` enum reads
  (OFF→NO_FRAME_BLEND, FRAME_MIX, PIXEL_MOTION).
- Gaussian Blur search hits 2 entries: the current
  `ADBE Gaussian Blur 2` (Blur & Sharpen) and legacy
  `ADBE Gaussian Blur` (category "Obsolete").
