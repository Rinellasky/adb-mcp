# Findings — After Effects MCP Priority 4 live session (2026-07-24)

Host: RYUJIN. AE 2026 retail 26.3x87 (CEP 13, extension junction
live-edit). Proxy: `adb-proxy-socket-win-x64.exe` on port 3001. Panel was
open in the restored workspace and auto-connected on launch — no CDP
kick needed this time (8088 route still documented in the P3 findings).

## Merge

Phase 2 begins: 34 → 41 tools (Keyframe Engine, 7 tools). Headless
enumeration confirms 41. `commands.js` gains resolvePropertyPath /
easeCountFor / buildEaseArray / interpTypeFromString / interpTypeToString
in AE_HELPERS, panel-side `resolvePrologue(o)` next to the handlers, 7
handlers + 7 registrations. `ae-mcp.py` gains the 7 matching tools.

## Live verification: 43/43 checks passed

Driver: `scripts/live_test_ae_p4.py`. All 7 handlers verified end-to-end
on a fresh comp + solid:

- `addKeyframe`: position keys at t=0 [100,100] and t=2 [1000,540];
  keyIndex/time/numKeys correct; getFrameImage pixel-diff at t=0/1/2
  shows motion (3 distinct hashes). One undo step per call; Redo (id
  2035) restores.
- `addKeyframes` (batch): 5 opacity keys in ONE call → ONE undo step
  removes all 5, one redo restores all 5 (the critical batching
  contract). `setValuesAtTimes` works on spatial props (position) in
  26.3 — no divergence. Length-mismatch errors cleanly.
- `getKeyframes`: times/values/interpolation round-trip exactly;
  temporal ease (speed/influence per dimension) included; spatial
  values serialize through JSON as arrays without issue.
- `getPropertyValue`: t=1 between-keys interpolation ≈ [550, 320];
  omitted time returns current value with `time: null`;
  `preExpression` True vs False differ once `wiggle(2,30)` is applied
  (post [555.1, 322.7] vs pre [550.0, 320.0]).
- `setKeyframeInterpolation`: HOLD on all keys → frame at t=1.9
  pixel-identical to t=0; LINEAR restore resumes motion; per-index
  subset ([2] → only key 2 BEZIER); "SPLINE" errors cleanly.
- `setKeyframeEase`: easy_ease on position (spatial → 1-elem ease
  array) and scale; influence 33.3333 read back exactly; forces BEZIER
  (F9 behavior). Explicit asymmetric speeds round-trip on a middle key.
  Influence 0.05 → clean range error before any mutation.
- `removeKeyframes`: subset [1,3] of 5 (descending-safe) keeps
  [25,75,100]; out-of-range index errors with partial-progress count
  ("removed 0 before failing" — validation precedes each removal, and
  [2,99] sorts descending so 99 fails first); omit indices = clear all.
- Property-path errors: bad segment → "failed at segment 2 ('ADBE
  Bogus') under 'ADBE Transform Group'"; group-only path → "resolved to
  a property GROUP" error; digit segment ["ADBE Effect Parade", "1",
  "ADBE Gaussian Blur 2-0001"] resolves the first effect's Blurriness.
- Hidden-property write (P3 finding confirmed for keyframes): keyframe
  on Camera opacity → clean surfaced AE error "Can not 'set value at
  time' with this property, because the property or a parent property
  is hidden." No dialog, no wedge.

## Empirical findings (AE 26.3)

- **Layer Scale is PropertyValueType.ThreeD even on a 2D layer in a 2D
  comp** — value reads `[100, 100, 100]` and temporal-ease arrays are
  3 elements, not 2. easeCountFor's dimensionality fan-out handles it;
  2-element value arrays are still ACCEPTED on write (AE fills z=100).
  Don't assert 2-element eases for "2D" scale.
- **First-key incoming ease speed is normalized to 0 by AE** (no
  incoming segment exists); influence is kept. Same applies
  symmetrically to the last key's outgoing side. setTemporalEaseAtKey
  succeeds — the readback just differs. Assert asymmetric speeds on
  middle keys only.
- **Spatial position keys report default ease influence 16.666666667**
  (not 33.33) in the LINEAR state — AE's auto-Bezier spatial default.
  After easy-ease it reads exactly 33.3333.
- **`setValuesAtTimes` on spatial properties works in 26.3** (was a
  flagged 26.x watch item) — batch position keys land correctly.
- **Position values on a 2D layer serialize as `[x, y, 0]`** (3-elem)
  through keyValue/valueAtTime; write side accepts 2-elem.
- `addCameraLayer` (P3 handler) requires `centerPoint` when driven raw
  over the socket: `JSON.stringify(undefined)` emits the literal
  `undefined` into the ES3 script, which fails `=== null` and reaches
  `addCamera(name, undefined)` → "parameter 2 ... undefined". The
  Python tool always sends the key (None → null → comp-center default),
  so MCP callers are unaffected. Fix candidate for a cleanup pass:
  `JSON.stringify(o.centerPoint ?? null)`.
- Undo command ids stable: Undo 16, Redo 2035 (AE 26).
