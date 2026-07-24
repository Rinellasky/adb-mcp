"""One-shot live test of AE MCP Priority 5 (Expressions Engine, 5 tools)
plus the P3 optional-param (literal-undefined) regression fixes.

Sends command packets through the adb proxy (port 3001) to the
"aftereffects" channel. The preset tools (apply_expression_preset,
list_expression_presets) are Python-side, so ae-mcp.py itself is imported
and its tool functions called directly (they ride the same socket).

DESTRUCTIVE: starts with createProject force=true, wiping the open project.
Only run against a scratch AE instance.

Run:  ../mcp/.venv/Scripts/python.exe live_test_ae_p5.py
"""

import sys, os, json, hashlib, traceback, importlib.util

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MCP_DIR = os.path.join(SCRIPT_DIR, "..", "mcp")
sys.path.insert(0, MCP_DIR)

# Import ae-mcp.py as a module (configures socket_client on import).
spec = importlib.util.spec_from_file_location("aemcp", os.path.join(MCP_DIR, "ae-mcp.py"))
aemcp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aemcp)

import socket_client
socket_client.configure(app="aftereffects", url="http://localhost:3001", timeout=30)

RESULTS = []

def record(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(("PASS  " if ok else "FAIL  ") + name + ("" if not detail else "  -- " + str(detail)[:300]))

def send(action, options=None, timeout=30):
    cmd = {"application": "aftereffects", "action": action, "options": options or {}}
    return socket_client.send_message_blocking(cmd, timeout=timeout)

def payload(resp):
    txt = resp["response"]["content"][0]["text"]
    return json.loads(txt)

def tool(resp):
    """Unwrap a direct ae-mcp tool-function return (same packet shape),
    or pass through a plain dict (server-side preset errors)."""
    if isinstance(resp, dict) and "response" not in resp:
        return resp
    return payload(resp)

def es(script, timeout=30):
    return payload(send("executeExtendScript", {"scriptString": script}, timeout))

def approx(a, b, eps=0.05):
    return a is not None and b is not None and abs(a - b) <= eps

def frame_hash(comp_id, t=0.0):
    p = payload(send("getFrameImage", {"compId": comp_id, "timeSeconds": t}, timeout=60))
    if p.get("success") is not True:
        return None
    with open(p["path"], "rb") as f:
        h = hashlib.md5(f.read()).hexdigest()
    os.remove(p["path"])
    return h

POS = ["ADBE Transform Group", "ADBE Position"]
OPA = ["ADBE Transform Group", "ADBE Opacity"]
ROT = ["ADBE Transform Group", "ADBE Rotate Z"]

def main():
    payload(send("createProject", {"force": True}))

    p = payload(send("createComposition", {
        "name": "MCP_P5_Comp", "width": 1280, "height": 720,
        "pixelAspect": 1.0, "durationSeconds": 8.0, "frameRate": 30.0}))
    comp_id = p.get("id")
    record("createComposition", p.get("success") is True and comp_id is not None, json.dumps(p))
    if comp_id is None:
        return

    # ---- P3 regression: no-key optional params at the socket level ----
    # (pre-fix these emitted literal `undefined` into ES3)
    p = payload(send("addNullLayer", {"compId": comp_id}))
    record("P3 fix: addNullLayer no name key", p.get("success") is True, json.dumps(p))
    if p.get("success"):
        payload(send("deleteLayer", {"compId": comp_id, "layerIndex": 1}))
    p = payload(send("addShapeLayer", {"compId": comp_id}))
    record("P3 fix: addShapeLayer no name key", p.get("success") is True, json.dumps(p))
    if p.get("success"):
        payload(send("deleteLayer", {"compId": comp_id, "layerIndex": 1}))
    p = payload(send("addCameraLayer", {"compId": comp_id, "name": "P5 Cam"}))
    record("P3 fix: addCameraLayer no centerPoint key", p.get("success") is True, json.dumps(p))
    if p.get("success"):
        payload(send("deleteLayer", {"compId": comp_id, "layerIndex": 1}))
    p = payload(send("addLightLayer", {"compId": comp_id, "name": "P5 Light"}))
    record("P3 fix: addLightLayer no centerPoint key", p.get("success") is True, json.dumps(p))
    if p.get("success"):
        payload(send("deleteLayer", {"compId": comp_id, "layerIndex": 1}))

    # solid 1: the keyframed workhorse
    p = payload(send("addSolidLayer", {"compId": comp_id, "name": "P5 Solid",
                                       "color": [1.0, 0.3, 0.1], "width": 200,
                                       "height": 200, "durationSeconds": None}))
    record("addSolidLayer", p.get("success") is True and p.get("index") == 1, json.dumps(p))
    LYR = 1

    p = payload(send("duplicateLayer", {"compId": comp_id, "layerIndex": 1}))
    record("P3 fix: duplicateLayer no name key", p.get("success") is True, json.dumps(p))
    if p.get("success"):
        payload(send("deleteLayer", {"compId": comp_id, "layerIndex": p.get("index", 1)}))

    # 2 position keyframes on the solid
    p = payload(send("addKeyframes", {"compId": comp_id, "layerIndex": LYR,
                                      "propertyPath": POS,
                                      "times": [0.5, 1.5],
                                      "values": [[300, 300], [900, 500]]}))
    record("setup: 2 position keyframes", p.get("success") is True and p.get("numKeys") == 2, json.dumps(p))

    def getval(path, t, pre=False, layer=LYR):
        return payload(send("getPropertyValue", {"compId": comp_id, "layerIndex": layer,
                                                 "propertyPath": path, "timeSeconds": t,
                                                 "preExpression": pre}))

    # ---- 1. set_expression wiggle on position ------------------------
    p = tool(aemcp.set_expression(comp_id, LYR, POS, "wiggle(2, 30)"))
    record("set_expression wiggle(2,30)", p.get("success") is True
           and p.get("expressionEnabled") is True, json.dumps(p))

    v_post = getval(POS, 1.0, pre=False).get("value")
    v_pre = getval(POS, 1.0, pre=True).get("value")
    differ = (isinstance(v_post, list) and isinstance(v_pre, list)
              and (abs(v_post[0] - v_pre[0]) > 0.001 or abs(v_post[1] - v_pre[1]) > 0.001))
    record("wiggle: pre vs post expression values differ", differ,
           "post=%r pre=%r" % (v_post, v_pre))

    # renders at two times differ (motion from keys + wiggle)
    ha = frame_hash(comp_id, 0.2)
    hb = frame_hash(comp_id, 0.9)
    record("wiggle: frame renders at two times differ", ha is not None and ha != hb,
           "ha=%s hb=%s" % (ha, hb))

    # undo: ONE step removes the expression
    es("app.executeCommand(16); return true;")
    p = tool(aemcp.get_expression(comp_id, LYR, POS))
    record("set_expression single undo step", p.get("success") is True
           and p.get("hasExpression") is False, json.dumps(p))
    es("app.executeCommand(2035); return true;")  # Redo (AE 26)
    p = tool(aemcp.get_expression(comp_id, LYR, POS))
    record("set_expression redo restores", p.get("hasExpression") is True
           and p.get("expressionEnabled") is True, json.dumps(p))

    # ---- 2. validation-with-revert -----------------------------------
    # good expression is in place ("wiggle(2, 30)" after redo)
    p = tool(aemcp.set_expression(comp_id, LYR, POS, "wiggle(2,"))
    record("syntax-error expression rejected w/ AE message",
           "error" in p and len(p["error"]) > 20, json.dumps(p))
    syntax_path = p.get("error", "")

    g = tool(aemcp.get_expression(comp_id, LYR, POS))
    record("good expression intact after rejected set",
           g.get("expression") == "wiggle(2, 30)" and g.get("expressionEnabled") is True
           and (g.get("expressionError") in ("", None)), json.dumps(g))

    # eval-time error: references a missing layer. Document which
    # rejection path it takes (assignment-throw vs disable+expressionError).
    p = tool(aemcp.set_expression(comp_id, LYR, POS,
                                  'thisComp.layer("nope").transform.position'))
    eval_rejected = "error" in p
    record("missing-layer expression handling (documenting path)",
           True,  # informational — either rejection or acceptance is documented
           "rejected=%r resp=%s" % (eval_rejected, json.dumps(p)[:200]))
    g = tool(aemcp.get_expression(comp_id, LYR, POS))
    if eval_rejected:
        record("good expression intact after eval-error set",
               g.get("expression") == "wiggle(2, 30)" and g.get("expressionEnabled") is True,
               json.dumps(g))
    else:
        record("eval-error expression state (documenting)", True, json.dumps(g))
        # restore the good expression for the next stages
        tool(aemcp.set_expression(comp_id, LYR, POS, "wiggle(2, 30)"))
    print("  [FINDING] syntax-error path: %s"
          % syntax_path[:200].encode("ascii", "backslashreplace").decode("ascii"))

    # ---- 3. get_expression full round-trip + marker property ---------
    g = tool(aemcp.get_expression(comp_id, LYR, POS))
    record("get_expression round-trip", g.get("success") is True
           and g.get("expression") == "wiggle(2, 30)"
           and g.get("canSetExpression") is True
           and g.get("hasExpression") is True
           and g.get("expressionEnabled") is True
           and g.get("matchName") == "ADBE Position", json.dumps(g))

    g = tool(aemcp.get_expression(comp_id, LYR, ["ADBE Marker"]))
    record("marker property: canSetExpression false, clean read",
           g.get("success") is True and g.get("canSetExpression") is False,
           json.dumps(g))

    # ---- 4. remove_expression ----------------------------------------
    p = tool(aemcp.remove_expression(comp_id, LYR, POS))
    record("remove_expression removed=true", p.get("success") is True
           and p.get("removed") is True, json.dumps(p))
    p2 = payload(send("getKeyframes", {"compId": comp_id, "layerIndex": LYR,
                                       "propertyPath": POS}))
    record("keyframes survive removal", p2.get("numKeys") == 2, json.dumps(p2)[:200])
    p = tool(aemcp.remove_expression(comp_id, LYR, POS))
    record("remove_expression second call removed=false",
           p.get("success") is True and p.get("removed") is False, json.dumps(p))
    # undo of remove: expression back (undo the removed=true step;
    # the removed=false call made no undoable change)
    es("app.executeCommand(16); return true;")
    g = tool(aemcp.get_expression(comp_id, LYR, POS))
    record("remove_expression single undo step (expression back)",
           g.get("hasExpression") is True, json.dumps(g))
    tool(aemcp.remove_expression(comp_id, LYR, POS))  # clear again for presets

    # ---- 5. presets ---------------------------------------------------
    cat = aemcp.list_expression_presets()
    record("list_expression_presets catalog", isinstance(cat, dict)
           and set(cat.keys()) == {"wiggle", "loop_out", "inertia_bounce",
                                   "time_rotation", "oscillate", "value_follower"}
           and all("params" in v and "description" in v for v in cat.values()),
           json.dumps(sorted(cat.keys())))

    # wiggle: defaults then custom
    p = tool(aemcp.apply_expression_preset(comp_id, LYR, POS, "wiggle"))
    record("preset wiggle defaults", p.get("success") is True, json.dumps(p))
    g = tool(aemcp.get_expression(comp_id, LYR, POS))
    record("preset wiggle defaults expr text", g.get("expression") == "wiggle(2, 30)", json.dumps(g)[:200])
    p = tool(aemcp.apply_expression_preset(comp_id, LYR, POS, "wiggle",
                                           {"frequency": 5, "amplitude": 80}))
    record("preset wiggle custom params", p.get("success") is True, json.dumps(p))
    g = tool(aemcp.get_expression(comp_id, LYR, POS))
    record("preset wiggle custom expr text", g.get("expression") == "wiggle(5, 80)", json.dumps(g)[:200])
    tool(aemcp.remove_expression(comp_id, LYR, POS))

    # loop_out cycle on the 2-key position: value past last key cycles.
    # keys at t=0.5 (300,300) and t=1.5 (900,500); cycle length 1.0s so
    # valueAtTime(2.5) == valueAtTime(1.5)... actually cycle restarts:
    # t=lastKey+dt maps to firstKey+dt -> valueAtTime(2.5) == value at 1.5?
    # loopOut('cycle'): after last key, time wraps to first key. At
    # t = 1.5 + 1.0 = 2.5 the wrapped time is 0.5+1.0=1.5 (full cycle) —
    # sample mid-cycle instead: t=2.0 wraps to t=1.0.
    p = tool(aemcp.apply_expression_preset(comp_id, LYR, POS, "loop_out"))
    record("preset loop_out cycle applied", p.get("success") is True, json.dumps(p))
    v_wrapped = getval(POS, 2.0).get("value")
    v_src = getval(POS, 1.0).get("value")
    v_last = getval(POS, 1.5, pre=True).get("value")
    ok = (isinstance(v_wrapped, list) and isinstance(v_src, list)
          and approx(v_wrapped[0], v_src[0], 1.0) and approx(v_wrapped[1], v_src[1], 1.0)
          and not (approx(v_wrapped[0], v_last[0], 1.0) and approx(v_wrapped[1], v_last[1], 1.0)))
    record("loop_out: t=2.0 cycles back to t=1.0 value", ok,
           "wrapped=%r src=%r last=%r" % (v_wrapped, v_src, v_last))
    # bad mode: pure server-side error, no panel roundtrip
    p = tool(aemcp.apply_expression_preset(comp_id, LYR, POS, "loop_out", {"mode": "bogus"}))
    record("loop_out bad mode server-side error", "error" in p and "cycle" in p["error"], json.dumps(p))
    tool(aemcp.remove_expression(comp_id, LYR, POS))

    # time_rotation rate=90 on rotation -> valueAtTime(2) == 180
    p = tool(aemcp.apply_expression_preset(comp_id, LYR, ROT, "time_rotation", {"rate": 90}))
    record("preset time_rotation applied", p.get("success") is True, json.dumps(p))
    v = getval(ROT, 2.0).get("value")
    record("time_rotation valueAtTime(2) == 180", approx(v, 180.0, 0.1), "v=%r" % v)
    # preset apply = ONE undo step
    es("app.executeCommand(16); return true;")
    g = tool(aemcp.get_expression(comp_id, LYR, ROT))
    record("preset apply single undo step", g.get("hasExpression") is False, json.dumps(g)[:200])

    # oscillate on opacity (1D): value 50, amplitude 20, freq 1.0 ->
    # peak 70 at t=0.25, trough 30 at t=0.75
    es("var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
       "c.layer(1).property('ADBE Transform Group').property('ADBE Opacity').setValue(50);"
       "return true;" % comp_id)
    p = tool(aemcp.apply_expression_preset(comp_id, LYR, OPA, "oscillate"))
    record("preset oscillate applied", p.get("success") is True, json.dumps(p))
    v_peak = getval(OPA, 0.25).get("value")
    v_trough = getval(OPA, 0.75).get("value")
    record("oscillate extremes ~ value +/- amplitude",
           approx(v_peak, 70.0, 0.5) and approx(v_trough, 30.0, 0.5),
           "peak=%r trough=%r" % (v_peak, v_trough))
    tool(aemcp.remove_expression(comp_id, LYR, OPA))

    # inertia_bounce on the keyframed position: post-key samples
    # oscillate around and settle toward the last key value
    p = tool(aemcp.apply_expression_preset(comp_id, LYR, POS, "inertia_bounce"))
    record("preset inertia_bounce applied", p.get("success") is True, json.dumps(p))
    key_v = getval(POS, 1.5, pre=True).get("value")
    samples = [getval(POS, t).get("value") for t in (1.6, 1.75, 1.9, 2.5, 3.5)]
    devs = [max(abs(s[0] - key_v[0]), abs(s[1] - key_v[1])) if isinstance(s, list) else None
            for s in samples]
    ok = (all(d is not None for d in devs)
          and max(devs[:3]) > 1.0            # visible bounce right after the key
          and devs[-1] < max(devs[:3])       # settling
          and devs[-1] < 5.0)                # near the key value by t=3.5
    record("inertia_bounce oscillates then settles", ok, "devs=%r" % devs)
    tool(aemcp.remove_expression(comp_id, LYR, POS))

    # value_follower: leader (the keyframed solid) + follower layer.
    # Add follower solid ABOVE -> leader becomes index 2.
    p = payload(send("addSolidLayer", {"compId": comp_id, "name": "P5 Follower",
                                       "color": [0.2, 0.6, 1.0], "width": 120,
                                       "height": 120, "durationSeconds": None}))
    record("follower solid added", p.get("success") is True and p.get("index") == 1, json.dumps(p))
    FOL, LEAD = 1, 2
    p = tool(aemcp.apply_expression_preset(comp_id, FOL, POS, "value_follower",
                                           {"leader_layer_index": LEAD, "delay_seconds": 0.5}))
    vf_ok = p.get("success") is True
    record("preset value_follower applied (matchName chaining)", vf_ok, json.dumps(p))
    if vf_ok:
        f_v = getval(POS, 1.5, layer=FOL).get("value")
        l_v = getval(POS, 1.0, layer=LEAD).get("value")
        ok = (isinstance(f_v, list) and isinstance(l_v, list)
              and approx(f_v[0], l_v[0], 1.0) and approx(f_v[1], l_v[1], 1.0))
        record("value_follower: follower(t) == leader(t-0.5)", ok,
               "follower@1.5=%r leader@1.0=%r" % (f_v, l_v))
    else:
        print("  [FINDING] matchName chaining accessor FAILED in expressions: %s"
              % json.dumps(p)[:300])

    # preset error paths (server-side, no panel roundtrip)
    p = tool(aemcp.apply_expression_preset(comp_id, LYR, POS, "no_such_preset"))
    record("unknown preset server-side error", "error" in p and "Unknown preset" in p["error"], json.dumps(p))
    p = tool(aemcp.apply_expression_preset(comp_id, LYR, POS, "wiggle", {"bogus": 1}))
    record("unknown param server-side error", "error" in p and "Unknown param" in p["error"], json.dumps(p))
    p = tool(aemcp.apply_expression_preset(comp_id, LYR, POS, "value_follower",
                                           {"delay_seconds": 0.5}))
    record("missing required param server-side error",
           "error" in p and "requires param" in p["error"], json.dumps(p))

    # ---- summary ------------------------------------------------------
    npass = sum(1 for _, ok, _ in RESULTS if ok)
    print("\n%d/%d checks passed" % (npass, len(RESULTS)))
    if npass != len(RESULTS):
        print("FAILURES:")
        for name, ok, detail in RESULTS:
            if not ok:
                print("  - %s: %s" % (name, detail[:300]))

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
