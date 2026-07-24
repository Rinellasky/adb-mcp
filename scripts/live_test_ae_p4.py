"""One-shot live test of the 7 AE MCP Priority 4 (Keyframe Engine) handlers.

Sends command packets through the adb proxy (port 3001) to the
"aftereffects" channel, exactly like mcp/ae-mcp.py does via
core.sendCommand -> socket_client.send_message_blocking.

DESTRUCTIVE: starts with createProject force=true, wiping the open project.
Only run against a scratch AE instance.

Run:  ../mcp/.venv/Scripts/python.exe live_test_ae_p4.py
"""

import sys, os, json, hashlib, traceback

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "..", "mcp"))
import socket_client
from socket_client import AppError

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
SCA = ["ADBE Transform Group", "ADBE Scale"]

def main():
    payload(send("createProject", {"force": True}))

    p = payload(send("createComposition", {
        "name": "MCP_P4_Comp", "width": 1280, "height": 720,
        "pixelAspect": 1.0, "durationSeconds": 5.0, "frameRate": 30.0}))
    comp_id = p.get("id")
    record("createComposition", p.get("success") is True and comp_id is not None, json.dumps(p))
    if comp_id is None:
        return

    p = payload(send("addSolidLayer", {"compId": comp_id, "name": "P4 Solid",
                                       "color": [1.0, 0.3, 0.1], "width": 200,
                                       "height": 200, "durationSeconds": None}))
    record("addSolidLayer", p.get("success") is True and p.get("index") == 1, json.dumps(p))
    LYR = 1

    def kf(action, options, timeout=30):
        opts = {"compId": comp_id, "layerIndex": LYR}
        opts.update(options)
        return payload(send(action, opts, timeout))

    # ---- 1. add_keyframe on position ---------------------------------
    p = kf("addKeyframe", {"propertyPath": POS, "timeSeconds": 0.0, "value": [100, 100]})
    record("addKeyframe pos t=0", p.get("success") is True and p.get("keyIndex") == 1
           and approx(p.get("time"), 0.0), json.dumps(p))
    p = kf("addKeyframe", {"propertyPath": POS, "timeSeconds": 2.0, "value": [1000, 540]})
    record("addKeyframe pos t=2", p.get("success") is True and p.get("keyIndex") == 2
           and approx(p.get("time"), 2.0) and p.get("numKeys") == 2, json.dumps(p))

    h0 = frame_hash(comp_id, 0.0)
    h1 = frame_hash(comp_id, 1.0)
    h2 = frame_hash(comp_id, 2.0)
    record("frame motion t=0/1/2 all differ",
           h0 is not None and len({h0, h1, h2}) == 3,
           "h0=%s h1=%s h2=%s" % (h0, h1, h2))

    # undo: ONE step removes the t=2 key
    es("app.executeCommand(16); return true;")
    n = es("var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
           "return c.layer(1).property('ADBE Transform Group').property('ADBE Position').numKeys;" % comp_id)
    record("addKeyframe single undo step", n == 1, "numKeys after 1 undo = %r" % n)
    es("app.executeCommand(2035); return true;")  # Redo (AE 26)
    n = es("var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
           "return c.layer(1).property('ADBE Transform Group').property('ADBE Position').numKeys;" % comp_id)
    record("addKeyframe redo restores", n == 2, "numKeys after redo = %r" % n)

    # ---- 2. add_keyframes batch: 5 opacity keys, ONE undo step -------
    p = kf("addKeyframes", {"propertyPath": OPA,
                            "times": [0.0, 0.5, 1.0, 1.5, 2.0],
                            "values": [0, 25, 50, 75, 100]})
    record("addKeyframes batch 5 opacity", p.get("success") is True
           and p.get("keysSet") == 5 and p.get("numKeys") == 5, json.dumps(p))
    es("app.executeCommand(16); return true;")
    n = es("var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
           "return c.layer(1).property('ADBE Transform Group').property('ADBE Opacity').numKeys;" % comp_id)
    record("batch = ONE undo step (5 keys gone)", n == 0, "numKeys after 1 undo = %r" % n)
    es("app.executeCommand(2035); return true;")
    n = es("var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
           "return c.layer(1).property('ADBE Transform Group').property('ADBE Opacity').numKeys;" % comp_id)
    record("batch redo restores all 5", n == 5, "numKeys after redo = %r" % n)

    # mismatched lengths error
    p = kf("addKeyframes", {"propertyPath": OPA, "times": [0.0, 1.0], "values": [10]})
    record("addKeyframes length-mismatch error", "error" in p and "equal length" in p["error"], json.dumps(p))

    # ---- 3. get_keyframes round-trip ---------------------------------
    p = kf("getKeyframes", {"propertyPath": OPA})
    keys = p.get("keys", [])
    ok = (p.get("success") is True and p.get("numKeys") == 5 and len(keys) == 5
          and all(approx(keys[i]["time"], [0.0, 0.5, 1.0, 1.5, 2.0][i]) for i in range(5))
          and all(approx(keys[i]["value"], [0, 25, 50, 75, 100][i]) for i in range(5))
          and all(k["inInterpolation"] == "LINEAR" and k["outInterpolation"] == "LINEAR" for k in keys))
    record("getKeyframes opacity round-trip", ok, json.dumps(p)[:400])

    p = kf("getKeyframes", {"propertyPath": POS})
    keys = p.get("keys", [])
    ok = (p.get("success") is True and p.get("numKeys") == 2
          and approx(keys[0]["value"][0], 100) and approx(keys[0]["value"][1], 100)
          and approx(keys[1]["value"][0], 1000) and approx(keys[1]["value"][1], 540))
    record("getKeyframes position spatial values", ok, json.dumps(p)[:400])

    # ---- 4. get_property_value ---------------------------------------
    p = kf("getPropertyValue", {"propertyPath": POS, "timeSeconds": 1.0})
    v = p.get("value")
    record("getPropertyValue t=1 interpolated", p.get("success") is True
           and isinstance(v, list) and approx(v[0], 550, 1.0) and approx(v[1], 320, 1.0), json.dumps(p))

    # omitted time = current value
    p = kf("getPropertyValue", {"propertyPath": OPA})
    record("getPropertyValue current (no time)", p.get("success") is True
           and p.get("time") is None and isinstance(p.get("value"), (int, float)), json.dumps(p))

    # pre_expression True vs False after wiggle
    es("var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
       "c.layer(1).property('ADBE Transform Group').property('ADBE Position').expression='wiggle(2,30)';"
       "return true;" % comp_id)
    p_post = kf("getPropertyValue", {"propertyPath": POS, "timeSeconds": 1.0, "preExpression": False})
    p_pre = kf("getPropertyValue", {"propertyPath": POS, "timeSeconds": 1.0, "preExpression": True})
    vpost, vpre = p_post.get("value"), p_pre.get("value")
    differ = (isinstance(vpost, list) and isinstance(vpre, list)
              and (abs(vpost[0] - vpre[0]) > 0.001 or abs(vpost[1] - vpre[1]) > 0.001))
    record("preExpression True vs False differ", p_post.get("success") is True
           and p_pre.get("success") is True and differ
           and p_pre.get("hasExpression") is True,
           "post=%r pre=%r" % (vpost, vpre))
    es("var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
       "c.layer(1).property('ADBE Transform Group').property('ADBE Position').expression='';"
       "return true;" % comp_id)

    # ---- 5. set_keyframe_interpolation -------------------------------
    p = kf("setKeyframeInterpolation", {"propertyPath": POS, "inType": "HOLD"})
    record("setKeyframeInterpolation HOLD all", p.get("success") is True and p.get("applied") == 2, json.dumps(p))
    # frame just before t=2 must equal t=0 frame (held) — clear the
    # animated opacity keys first so only position affects the render
    kf("removeKeyframes", {"propertyPath": OPA})
    es("var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
       "c.layer(1).property('ADBE Transform Group').property('ADBE Opacity').setValue(100);"
       "return true;" % comp_id)
    h0b = frame_hash(comp_id, 0.0)
    h19 = frame_hash(comp_id, 1.9)
    record("HOLD: frame at 1.9 == frame at 0", h0b is not None and h0b == h19,
           "h0=%s h1.9=%s" % (h0b, h19))
    p = kf("getKeyframes", {"propertyPath": POS})
    record("HOLD readback", all(k["outInterpolation"] == "HOLD" for k in p.get("keys", [])),
           json.dumps([k["outInterpolation"] for k in p.get("keys", [])]))

    p = kf("setKeyframeInterpolation", {"propertyPath": POS, "inType": "LINEAR"})
    record("LINEAR restore", p.get("success") is True, json.dumps(p))
    h19b = frame_hash(comp_id, 1.9)
    record("LINEAR: frame at 1.9 moves again", h19b is not None and h19b != h0b, "")

    # re-add the opacity keys (cleared above for the HOLD render check)
    p = kf("addKeyframes", {"propertyPath": OPA,
                            "times": [0.0, 0.5, 1.0, 1.5, 2.0],
                            "values": [0, 25, 50, 75, 100]})
    record("re-add opacity keys", p.get("success") is True and p.get("numKeys") == 5, json.dumps(p))

    # per-index subset (key 2 only -> BEZIER)
    p = kf("setKeyframeInterpolation", {"propertyPath": OPA, "inType": "BEZIER", "keyIndices": [2]})
    record("interp per-index subset", p.get("success") is True and p.get("applied") == 1, json.dumps(p))
    p = kf("getKeyframes", {"propertyPath": OPA})
    interps = [k["inInterpolation"] for k in p.get("keys", [])]
    record("subset readback (only key 2 BEZIER)",
           interps == ["LINEAR", "BEZIER", "LINEAR", "LINEAR", "LINEAR"], json.dumps(interps))

    # bad type string
    p = kf("setKeyframeInterpolation", {"propertyPath": OPA, "inType": "SPLINE"})
    record("bad interp type errors cleanly", "error" in p and "SPLINE" in p["error"], json.dumps(p))

    # ---- 6. set_keyframe_ease ----------------------------------------
    # spatial (position): ease arrays must be length 1
    p = kf("setKeyframeEase", {"propertyPath": POS, "easyEase": True})
    record("easyEase on position (spatial)", p.get("success") is True and p.get("applied") == 2, json.dumps(p))
    p = kf("getKeyframes", {"propertyPath": POS})
    keys = p.get("keys", [])
    ok = (len(keys) == 2 and all(len(k["easeIn"]) == 1 for k in keys)
          and all(approx(k["easeIn"][0]["influence"], 33.3333, 0.01) for k in keys)
          and all(k["inInterpolation"] == "BEZIER" for k in keys))
    record("position ease: 1-elem array, influence 33.33, BEZIER", ok, json.dumps(keys)[:400])

    # non-spatial multi-D (scale). FINDING (AE 26): layer Scale is
    # PropertyValueType.ThreeD even on a 2D layer in a 2D comp — value
    # reads [100, 100, 100] and ease arrays are 3 elements, not 2.
    p = kf("addKeyframes", {"propertyPath": SCA,
                            "times": [0.0, 1.0, 2.0],
                            "values": [[100, 100], [75, 75], [50, 50]]})
    record("addKeyframes scale (2D value arrays accepted)",
           p.get("success") is True and p.get("keysSet") == 3, json.dumps(p))
    p = kf("setKeyframeEase", {"propertyPath": SCA, "easyEase": True})
    record("easyEase on scale (non-spatial)", p.get("success") is True and p.get("applied") == 3, json.dumps(p))
    p = kf("getKeyframes", {"propertyPath": SCA})
    keys = p.get("keys", [])
    ok = (len(keys) == 3 and all(len(k["easeIn"]) == 3 for k in keys)
          and all(approx(e["influence"], 33.3333, 0.01) for k in keys for e in k["easeIn"]))
    record("scale ease: 3-elem array (ThreeD), influence 33.33 all dims", ok, json.dumps(keys)[:400])

    # explicit asymmetric speeds on a MIDDLE key (in-speed on the first
    # key is normalized to 0 by AE since there is no incoming segment)
    p = kf("setKeyframeEase", {"propertyPath": SCA, "inSpeed": 10.0, "inInfluence": 60.0,
                               "outSpeed": -5.0, "outInfluence": 20.0, "keyIndices": [2]})
    record("explicit asymmetric ease (middle key)", p.get("success") is True and p.get("applied") == 1, json.dumps(p))
    p = kf("getKeyframes", {"propertyPath": SCA})
    k2 = p.get("keys", [{}, {}])[1]
    ok = (approx(k2.get("easeIn", [{}])[0].get("speed"), 10.0, 0.01)
          and approx(k2["easeIn"][0].get("influence"), 60.0, 0.01)
          and approx(k2.get("easeOut", [{}])[0].get("speed"), -5.0, 0.01)
          and approx(k2["easeOut"][0].get("influence"), 20.0, 0.01))
    record("asymmetric ease readback (middle key)", ok, json.dumps(k2))

    # first-key incoming speed normalization (document actual behavior)
    p = kf("setKeyframeEase", {"propertyPath": SCA, "inSpeed": 10.0, "inInfluence": 60.0,
                               "outSpeed": -5.0, "outInfluence": 20.0, "keyIndices": [1]})
    p = kf("getKeyframes", {"propertyPath": SCA})
    k1 = p.get("keys", [{}])[0]
    record("FINDING: first-key inSpeed normalized to 0 (influence kept)",
           approx(k1.get("easeIn", [{}])[0].get("speed"), 0.0, 0.01)
           and approx(k1["easeIn"][0].get("influence"), 60.0, 0.01)
           and approx(k1.get("easeOut", [{}])[0].get("speed"), -5.0, 0.01),
           json.dumps(k1))

    # influence out of range
    p = kf("setKeyframeEase", {"propertyPath": SCA, "inInfluence": 0.05})
    record("influence 0.05 range error", "error" in p and "0.1" in p["error"], json.dumps(p))

    # ---- 7. remove_keyframes -----------------------------------------
    p = kf("removeKeyframes", {"propertyPath": OPA, "keyIndices": [1, 3]})
    record("removeKeyframes subset [1,3]", p.get("success") is True
           and p.get("removed") == 2 and p.get("numKeys") == 3, json.dumps(p))
    p = kf("getKeyframes", {"propertyPath": OPA})
    vals = [k["value"] for k in p.get("keys", [])]
    record("subset removal kept right keys", vals == [25, 75, 100], json.dumps(vals))

    # out-of-range index errors with partial-progress count
    p = kf("removeKeyframes", {"propertyPath": OPA, "keyIndices": [2, 99]})
    record("remove out-of-range errors w/ partial count",
           "error" in p and "out of range" in p["error"] and "removed" in p["error"], json.dumps(p))

    # remove all
    p = kf("removeKeyframes", {"propertyPath": OPA})
    record("removeKeyframes all", p.get("success") is True and p.get("numKeys") == 0, json.dumps(p))

    # ---- 8. property-path errors -------------------------------------
    p = kf("getKeyframes", {"propertyPath": ["ADBE Transform Group", "ADBE Bogus"]})
    record("bad segment error names segment+parent",
           "error" in p and "segment 2" in p["error"] and "ADBE Bogus" in p["error"]
           and "ADBE Transform Group" in p["error"], json.dumps(p))

    p = kf("getKeyframes", {"propertyPath": ["ADBE Transform Group"]})
    record("GROUP path error", "error" in p and "GROUP" in p["error"], json.dumps(p))

    # digit-segment addressing: add an effect, address as ["ADBE Effect Parade", "1"]
    es("var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
       "c.layer(1).property('ADBE Effect Parade').addProperty('ADBE Gaussian Blur 2');"
       "return true;" % comp_id)
    p = kf("getKeyframes", {"propertyPath": ["ADBE Effect Parade", "1", "ADBE Gaussian Blur 2-0001"]})
    record("digit-segment resolves first effect", p.get("success") is True
           and p.get("name") == "Blurriness", json.dumps(p))

    # ---- 9. hidden-property write (P3 finding) -----------------------
    p = payload(send("addCameraLayer", {"compId": comp_id, "name": "P4 Cam",
                                        "centerPoint": [640, 360]}))
    cam_ok = p.get("success") is True
    record("addCameraLayer (for hidden-prop test)", cam_ok, json.dumps(p))
    if cam_ok:
        p = payload(send("addKeyframe", {"compId": comp_id, "layerIndex": 1,
                                         "propertyPath": OPA,
                                         "timeSeconds": 0.0, "value": 50}))
        record("camera opacity keyframe -> clean surfaced error",
               "error" in p, json.dumps(p))
        # clean up camera so layer 1 is the solid again
        payload(send("deleteLayer", {"compId": comp_id, "layerIndex": 1}))

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
