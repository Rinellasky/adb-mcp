# Findings — After Effects MCP Priority 5 live session (2026-07-24)

Host: RYUJIN. AE 2026 retail 26.3x87 (CEP 13, extension junction
live-edit). Proxy: `adb-proxy-socket-win-x64.exe` on port 3001. Panel did
NOT auto-connect after the menu-toggle reload this session — socket was
null; the CDP 8088 `connectToServer()` kick (P3 findings / memory note)
connected it on the first try.

## Merge

Phase 2 complete: 41 → 46 tools (Expressions Engine, 5 tools). Headless
enumeration confirms 46. `commands.js` gains setExpression /
getExpression / removeExpression (3 handlers + registrations, all riding
resolvePrologue — no new AE_HELPERS). `ae-mcp.py` gains the 5 tools:
set_expression, get_expression, remove_expression,
list_expression_presets, apply_expression_preset — the 6-preset library
(wiggle, loop_out, inertia_bounce, time_rotation, oscillate,
value_follower) compiles to expression strings server-side and rides
setExpression, so new presets need zero JSX changes.

P3 cleanup landed: the literal-`undefined` emission on omitted optional
params is fixed with the standard normalize pattern in addNullLayer /
addShapeLayer / duplicateLayer (name) and addCameraLayer / addLightLayer
(centerPoint). Socket-level no-key calls verified for all five.

## Live verification: 44/44 checks passed

Driver: `scripts/live_test_ae_p5.py` (imports ae-mcp.py itself so the
Python-side preset tools are exercised for real).

- `set_expression` "wiggle(2, 30)" on keyframed position:
  enabled=true; `get_property_value` preExpression True vs False differ
  (post [605.1, 402.7] vs pre [600.0, 400.0]); frame renders at two
  times differ. ONE undo step removes it; redo restores.
- **Validation-with-revert (both rejection paths verified)**: on AE
  26.3 BOTH failure modes take the disable path, not the
  assignment-throw path — assignment succeeds, then
  `expressionEnabled` flips false with `expressionError` set. The
  handler reverts to the previous expression and returns AE's message:
  - syntax error `"wiggle(2,"` → "Expression Disabled ... SyntaxError:
    Unexpected token '}'" (AE's own caret markup included)
  - eval-time error `thisComp.layer("nope").transform.position` →
    "Expression disabled ... layer named 'nope' is missing or does not
    exist"
  After each rejection, `get_expression` shows the GOOD expression
  ("wiggle(2, 30)") intact and still enabled. The property is never
  left broken.
- `get_expression`: full state round-trip (source, canSetExpression,
  hasExpression, enabled, expressionError). Marker property
  (["ADBE Marker"]) → canSetExpression=false with a clean successful
  read.
- `remove_expression`: removed=true and both keyframes survive; second
  call → removed=false ("Property had no expression") with no undoable
  side effect; the removal itself is ONE undo step.
- Presets (each validated by AE like any set_expression):
  - wiggle: defaults compile to "wiggle(2, 30)", custom
    {frequency:5, amplitude:80} → "wiggle(5, 80)".
  - loop_out cycle on the 2-key position (keys t=0.5/1.5): value at
    t=2.0 equals the t=1.0 value and differs from the last key — the
    cycle really wraps. Bad mode → server-side error, no panel
    roundtrip.
  - time_rotation rate=90 on Rotate Z → valueAtTime(2) == 180 exactly.
    Preset apply = ONE undo step.
  - oscillate on opacity 50 (defaults amp 20 / freq 1): peak 70 at
    t=0.25, trough 30 at t=0.75 — exact.
  - inertia_bounce on the keyframed position: post-key deviation 7.93
    at t=1.6 decaying to ~0 by t=2.5 — oscillates and settles onto the
    key value.
  - value_follower (the riskiest assumption): **matchName chaining
    accessors DO work in 26.3 expressions** —
    `thisComp.layer(2)("ADBE Transform Group")("ADBE Position")
    .valueAtTime(time - 0.5)` applied cleanly and
    follower.valueAtTime(1.5) == leader.valueAtTime(1.0) exactly. No
    display-name fallback needed.
  - Error paths are pure server-side (no panel roundtrip): unknown
    preset (lists available), unknown param (lists valid), missing
    required param (value_follower without leader_layer_index).

## Empirical findings (AE 26.3x87)

- **Expression rejection is uniformly the disable path in 26.3**: bad
  expressions (syntax AND eval-time) assign without throwing, then AE
  disables them with `expressionError` populated. The assignment-throw
  branch in setExpression never fired live — keep it anyway for other
  builds; the disable branch carries the full AE error text including
  its caret markup (contains non-ASCII '▶' U+25B6 — cp1252 consoles
  choke printing it; the driver encodes ASCII-safe).
- `expressionError` on a clean property reads "" (empty string), never
  null — the disable check keys off enabled flag + non-empty error.
- Marker (`ADBE Marker`) resolves fine through resolvePropertyPath and
  reports canSetExpression=false — no special-casing needed.
- loopOut('cycle') sampling note for tests: t = lastKey + cycleLength
  lands on the seam (== last key value); assert mid-cycle instead
  (t=2.0 → t=1.0 with keys 0.5/1.5).
- Rotation matchName on a 2D layer is `ADBE Rotate Z` (display name
  "Rotation") — consistent with the Scale-is-ThreeD finding from P4.
- Undo ids unchanged (Undo 16, Redo 2035); set/remove/preset-apply are
  each exactly one undo step.
