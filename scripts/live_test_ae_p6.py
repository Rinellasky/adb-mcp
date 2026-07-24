"""One-shot live test of AE MCP Priority 6 (Effects Engine & Switches, 7 tools).

Sends command packets through the adb proxy (port 3001) to the
"aftereffects" channel — all 7 P6 tools are panel-side.

DESTRUCTIVE: starts with createProject force=true, wiping the open project.
Only run against a scratch AE instance.

Run:  ../mcp/.venv/Scripts/python.exe live_test_ae_p6.py
"""

import sys, os, json, time, hashlib, traceback

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MCP_DIR = os.path.join(SCRIPT_DIR, "..", "mcp")
sys.path.insert(0, MCP_DIR)

import socket_client
socket_client.configure(app="aftereffects", url="http://localhost:3001", timeout=30)

RESULTS = []
FINDINGS = []

def record(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(("PASS  " if ok else "FAIL  ") + name + ("" if not detail else "  -- " + str(detail)[:300]))

def finding(text):
    FINDINGS.append(text)
    print("  [FINDING] " + text)

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

def fx_inventory(comp_id, layer_index):
    return payload(send("getLayerEffects", {"compId": comp_id, "layerIndex": layer_index}))

def find_param(effect, **crit):
    """Find a param dict on an effect by matchName / name / valueType."""
    for p in effect.get("params", []):
        if all(p.get(k) == v for k, v in crit.items()):
            return p
    return None

def find_effect(inv, effect_index):
    for e in inv.get("effects", []):
        if e.get("effectIndex") == effect_index:
            return e
    return None

GB = "ADBE Gaussian Blur 2"

def main():
    payload(send("createProject", {"force": True}))
    v = es("return app.version;")
    finding("AE build: %s" % v)

    p = payload(send("createComposition", {
        "name": "MCP_P6_Comp", "width": 1280, "height": 720,
        "pixelAspect": 1.0, "durationSeconds": 8.0, "frameRate": 30.0}))
    comp_id = p.get("id")
    record("createComposition", p.get("success") is True and comp_id is not None, json.dumps(p))
    if comp_id is None:
        return

    p = payload(send("addSolidLayer", {"compId": comp_id, "name": "P6 Solid",
                                       "color": [0.9, 0.3, 0.1], "width": 400,
                                       "height": 400, "durationSeconds": None}))
    record("addSolidLayer", p.get("success") is True and p.get("index") == 1, json.dumps(p))
    LYR = 1

    # ---- 1. list_effect_match_names ----------------------------------
    t0 = time.time()
    p = payload(send("listEffectMatchNames", {}, timeout=60))
    dt = time.time() - t0
    total = p.get("totalInstalled")
    record("list unfiltered: success + totalInstalled ~400",
           p.get("success") is True and isinstance(total, int) and total >= 300
           and p.get("matched") == total and len(p.get("effects", [])) == total,
           "totalInstalled=%r matched=%r elapsed=%.2fs" % (total, p.get("matched"), dt))
    finding("app.effects enumeration (unfiltered, %r effects): %.2fs round-trip" % (total, dt))

    all_effects = p.get("effects", [])
    gb_entry = next((e for e in all_effects if e["matchName"] == GB), None)
    record("unfiltered list contains ADBE Gaussian Blur 2", gb_entry is not None,
           json.dumps(gb_entry))

    cat = gb_entry["category"] if gb_entry else "Blur & Sharpen"
    expected_cat_count = sum(1 for e in all_effects if e["category"] == cat)
    p = payload(send("listEffectMatchNames", {"category": cat}))
    record("category filter exact-match ('%s')" % cat,
           p.get("success") is True and p.get("matched") == expected_cat_count
           and all(e["category"] == cat for e in p.get("effects", [])),
           "matched=%r expected=%r" % (p.get("matched"), expected_cat_count))

    p = payload(send("listEffectMatchNames", {"search": "BLUR"}))
    hits = p.get("effects", [])
    ok = (p.get("success") is True and p.get("matched") > 0
          and all(("blur" in e["displayName"].lower()) or ("blur" in e["matchName"].lower())
                  for e in hits))
    mn_only = [e for e in hits if "blur" not in e["displayName"].lower()]
    record("search 'BLUR' case-insensitive, both name fields", ok,
           "matched=%r matchName-only hits=%r" % (p.get("matched"),
                                                  [e["displayName"] for e in mn_only[:3]]))

    p = payload(send("listEffectMatchNames", {"search": "zzqxnope"}))
    record("search 0 matches", p.get("success") is True and p.get("matched") == 0
           and p.get("effects") == [], json.dumps(p))

    # ---- 2. canonical workflow ---------------------------------------
    p = payload(send("listEffectMatchNames", {"search": "gaussian"}))
    record("search 'gaussian' finds the matchName",
           any(e["matchName"] == GB for e in p.get("effects", [])), json.dumps(p)[:300])

    h0 = frame_hash(comp_id, 1.0)

    p = payload(send("addEffect", {"compId": comp_id, "layerIndex": LYR, "matchName": GB}))
    record("add_effect Gaussian Blur", p.get("success") is True
           and p.get("effectIndex") == 1 and p.get("matchName") == GB
           and p.get("numEffects") == 1, json.dumps(p))

    inv = fx_inventory(comp_id, LYR)
    fx1 = find_effect(inv, 1)
    blur_p = find_param(fx1, matchName=GB + "-0001") if fx1 else None
    record("get_layer_effects: blurriness param listed (OneD, no keys)",
           inv.get("success") is True and inv.get("numEffects") == 1
           and blur_p is not None and blur_p["valueType"] == "OneD"
           and blur_p["numKeys"] == 0,
           json.dumps(blur_p))
    if fx1:
        finding("Gaussian Blur param inventory: %s" %
                json.dumps([(q["matchName"], q["name"], q["valueType"]) for q in fx1["params"]]))
    # AE 26.3 quirk: addProperty applies the effect with the SESSION's
    # last-used parameter values, not factory defaults. Baseline-aware.
    v0 = blur_p["value"] if blur_p else 0
    if v0 != 0:
        finding("session-sticky effect defaults: fresh addProperty gave Blurriness=%r (not 0)" % v0)
    target = 25 if v0 != 25 else 40

    p = payload(send("setEffectProperty", {"compId": comp_id, "layerIndex": LYR,
                                           "effectIndex": 1,
                                           "paramMatchName": GB + "-0001", "value": target}))
    record("set_effect_property blurriness %s" % target, p.get("success") is True
           and p.get("value") == target, json.dumps(p))

    inv = fx_inventory(comp_id, LYR)
    blur_p = find_param(find_effect(inv, 1) or {}, matchName=GB + "-0001")
    record("round-trip: blurriness reads %s" % target,
           blur_p is not None and blur_p["value"] == target, json.dumps(blur_p))

    h1 = frame_hash(comp_id, 1.0)
    record("pixel-diff: blur changed the frame", h0 is not None and h1 is not None and h0 != h1,
           "h0=%s h1=%s" % (h0, h1))

    # undo/redo: one step per mutating call
    es("app.executeCommand(16); return true;")
    blur_p = find_param(find_effect(fx_inventory(comp_id, LYR), 1) or {}, matchName=GB + "-0001")
    record("set_effect_property single undo step (back to baseline)",
           blur_p is not None and blur_p["value"] == v0, json.dumps(blur_p))
    es("app.executeCommand(2035); return true;")
    blur_p = find_param(find_effect(fx_inventory(comp_id, LYR), 1) or {}, matchName=GB + "-0001")
    record("redo (2035) restores %s" % target,
           blur_p is not None and blur_p["value"] == target, json.dumps(blur_p))

    # add_effect single undo step
    es("app.executeCommand(16); return true;")  # undoes the redone set -> 0
    es("app.executeCommand(16); return true;")  # undoes addEffect
    inv = fx_inventory(comp_id, LYR)
    record("add_effect single undo step (effect gone after 2 undos)",
           inv.get("numEffects") == 0, json.dumps(inv)[:200])
    es("app.executeCommand(2035); return true;")  # redo addEffect
    es("app.executeCommand(2035); return true;")  # redo set 25
    inv = fx_inventory(comp_id, LYR)
    blur_p = find_param(find_effect(inv, 1) or {}, matchName=GB + "-0001")
    record("redo x2 restores effect + value", inv.get("numEffects") == 1
           and blur_p is not None and blur_p["value"] == target, json.dumps(blur_p))

    # ---- 3. param value shapes ---------------------------------------
    p = payload(send("addEffect", {"compId": comp_id, "layerIndex": LYR,
                                   "matchName": "ADBE Fill"}))
    fill_idx = p.get("effectIndex")
    record("add_effect ADBE Fill (effectIndex == ordinal 2)",
           p.get("success") is True and fill_idx == 2, json.dumps(p))

    p = payload(send("setEffectProperty", {"compId": comp_id, "layerIndex": LYR,
                                           "effectIndex": fill_idx,
                                           "paramMatchName": "ADBE Fill-0002",
                                           "value": [0.0, 0.5, 1.0]}))
    ok = p.get("success") is True and isinstance(p.get("value"), list)
    v = p.get("value") or [None, None, None]
    record("color param [r,g,b] set + round-trip", ok
           and approx(v[0], 0.0) and approx(v[1], 0.5) and approx(v[2], 1.0),
           json.dumps(p))
    inv = fx_inventory(comp_id, LYR)
    fill_color = find_param(find_effect(inv, fill_idx) or {}, matchName="ADBE Fill-0002")
    record("color param listed as COLOR", fill_color is not None
           and fill_color["valueType"] == "COLOR", json.dumps(fill_color))

    # checkbox + dropdown discovered by display name on the blur
    fx1 = find_effect(inv, 1)
    chk = next((q for q in (fx1 or {}).get("params", [])
                if q["name"].lower().startswith("repeat edge")), None)
    if chk is not None:
        p = payload(send("setEffectProperty", {"compId": comp_id, "layerIndex": LYR,
                                               "effectIndex": 1,
                                               "paramMatchName": chk["matchName"],
                                               "value": True}))
        record("checkbox param bool set + round-trip", p.get("success") is True
               and p.get("value") in (1, True), json.dumps(p))
    else:
        record("checkbox param bool set + round-trip", False,
               "no 'Repeat Edge*' param on Gaussian Blur: " + json.dumps(
                   [q["name"] for q in (fx1 or {}).get("params", [])]))

    drop = next((q for q in (fx1 or {}).get("params", [])
                 if "dimensions" in q["name"].lower()), None)
    if drop is not None:
        p = payload(send("setEffectProperty", {"compId": comp_id, "layerIndex": LYR,
                                               "effectIndex": 1,
                                               "paramMatchName": drop["matchName"],
                                               "value": 2}))
        record("dropdown param 1-based int set + round-trip (Blur Dimensions=2)",
               p.get("success") is True and p.get("value") == 2, json.dumps(p))
        finding("dropdown '%s' (%s) valueType=%s, int 2 round-tripped as %r"
                % (drop["name"], drop["matchName"], drop["valueType"], p.get("value")))
        payload(send("setEffectProperty", {"compId": comp_id, "layerIndex": LYR,
                                           "effectIndex": 1,
                                           "paramMatchName": drop["matchName"], "value": 1}))
    else:
        record("dropdown param 1-based int set + round-trip", False,
               "no '*Dimensions*' param on Gaussian Blur")

    # point param: ADBE Circle center (TwoD_SPATIAL) if installed
    p = payload(send("listEffectMatchNames", {"search": "ADBE Circle"}))
    if any(e["matchName"] == "ADBE Circle" for e in p.get("effects", [])):
        p = payload(send("addEffect", {"compId": comp_id, "layerIndex": LYR,
                                       "matchName": "ADBE Circle"}))
        circ_idx = p.get("effectIndex")
        inv = fx_inventory(comp_id, LYR)
        pt = next((q for q in (find_effect(inv, circ_idx) or {}).get("params", [])
                   if q["valueType"] in ("TwoD_SPATIAL", "TwoD")), None)
        if pt is not None:
            p = payload(send("setEffectProperty", {"compId": comp_id, "layerIndex": LYR,
                                                   "effectIndex": circ_idx,
                                                   "paramMatchName": pt["matchName"],
                                                   "value": [111, 222]}))
            v = p.get("value") or [None, None]
            record("point param [x,y] set + round-trip", p.get("success") is True
                   and approx(v[0], 111) and approx(v[1], 222), json.dumps(p))
        else:
            record("point param [x,y] set + round-trip", False, "no TwoD param on ADBE Circle")
        payload(send("removeEffect", {"compId": comp_id, "layerIndex": LYR,
                                      "effectIndex": circ_idx}))
    else:
        finding("ADBE Circle not installed - point param check skipped")

    # ---- 4. keyframed-param refusal ----------------------------------
    kf_path = ["ADBE Effect Parade", GB, GB + "-0001"]
    p = payload(send("addKeyframe", {"compId": comp_id, "layerIndex": LYR,
                                     "propertyPath": kf_path,
                                     "timeSeconds": 0.0, "value": 0}))
    record("P4 add_keyframe on effect param via propertyPath works",
           p.get("success") is True, json.dumps(p))
    p = payload(send("setEffectProperty", {"compId": comp_id, "layerIndex": LYR,
                                           "effectIndex": 1,
                                           "paramMatchName": GB + "-0001", "value": 10}))
    err = p.get("error", "")
    record("keyframed param refused w/ exact propertyPath in message",
           "error" in p and "keyframes" in err
           and '"ADBE Effect Parade"' in err and '"%s"' % GB in err
           and '"%s-0001"' % GB in err, json.dumps(p))
    payload(send("removeKeyframes", {"compId": comp_id, "layerIndex": LYR,
                                     "propertyPath": kf_path}))
    inv = fx_inventory(comp_id, LYR)
    blur_p = find_param(find_effect(inv, 1) or {}, matchName=GB + "-0001")
    record("keyframes cleared for later stages", blur_p is not None
           and blur_p["numKeys"] == 0, json.dumps(blur_p))

    # ---- 5. CUSTOM_VALUE + unwritable --------------------------------
    p = payload(send("addEffect", {"compId": comp_id, "layerIndex": LYR,
                                   "matchName": "ADBE CurvesCustom"}))
    curves_idx = p.get("effectIndex")
    record("add_effect Curves (ADBE CurvesCustom)", p.get("success") is True,
           json.dumps(p))
    inv = fx_inventory(comp_id, LYR)
    record("get_layer_effects survives Curves", inv.get("success") is True,
           json.dumps(inv)[:200])
    cfx = find_effect(inv, curves_idx)
    custom = next((q for q in (cfx or {}).get("params", [])
                   if q["valueType"] in ("CUSTOM_VALUE", "NO_VALUE")), None)
    record("Curves custom param listed with value=null",
           custom is not None and custom["value"] is None, json.dumps(custom))
    if custom is not None:
        p = payload(send("setEffectProperty", {"compId": comp_id, "layerIndex": LYR,
                                               "effectIndex": curves_idx,
                                               "paramMatchName": custom["matchName"],
                                               "value": 5}))
        record("write to unwritable param -> clean AE error", "error" in p,
               json.dumps(p))
        finding("unwritable-param error text: %s" % p.get("error", "")[:200])
    payload(send("removeEffect", {"compId": comp_id, "layerIndex": LYR,
                                  "effectIndex": curves_idx}))

    # ---- 6. add_effect extras ----------------------------------------
    p = payload(send("addEffect", {"compId": comp_id, "layerIndex": LYR,
                                   "matchName": "ADBE Tint", "effectName": "My Tint"}))
    tint_idx = p.get("effectIndex")
    record("add_effect custom effect_name", p.get("success") is True
           and p.get("name") == "My Tint", json.dumps(p))

    p = payload(send("addEffect", {"compId": comp_id, "layerIndex": LYR,
                                   "matchName": "ADBE Not A Real Effect"}))
    record("invalid matchName -> canAddProperty refusal citing list tool",
           "error" in p and "list_effect_match_names" in p.get("error", ""),
           json.dumps(p))

    # ---- 7. remove_effect index shift --------------------------------
    # Current parade: 1=Gaussian, 2=Fill, 3=My Tint
    inv = fx_inventory(comp_id, LYR)
    names_before = [(e["effectIndex"], e["matchName"]) for e in inv.get("effects", [])]
    record("parade is [Gaussian, Fill, Tint]",
           [m for _, m in names_before] == [GB, "ADBE Fill", "ADBE Tint"],
           json.dumps(names_before))
    p = payload(send("removeEffect", {"compId": comp_id, "layerIndex": LYR,
                                      "effectIndex": 2}))
    record("remove_effect #2 (Fill)", p.get("success") is True
           and p.get("numEffects") == 2, json.dumps(p))
    inv = fx_inventory(comp_id, LYR)
    names_after = [(e["effectIndex"], e["matchName"]) for e in inv.get("effects", [])]
    record("index shift: former #3 (Tint) is now #2",
           names_after == [(1, GB), (2, "ADBE Tint")], json.dumps(names_after))
    # undo restores the removed effect
    es("app.executeCommand(16); return true;")
    inv = fx_inventory(comp_id, LYR)
    record("remove_effect single undo step (Fill back at #2)",
           [(e["effectIndex"], e["matchName"]) for e in inv.get("effects", [])]
           == [(1, GB), (2, "ADBE Fill"), (3, "ADBE Tint")], json.dumps(inv)[:200])
    es("app.executeCommand(2035); return true;")  # redo the removal

    p = payload(send("removeEffect", {"compId": comp_id, "layerIndex": LYR,
                                      "effectIndex": 99}))
    record("remove_effect out-of-range error", "error" in p
           and "out of range" in p.get("error", ""), json.dumps(p))
    p = payload(send("setEffectProperty", {"compId": comp_id, "layerIndex": LYR,
                                           "effectIndex": 0,
                                           "paramMatchName": "x", "value": 1}))
    record("set_effect_property index 0 out-of-range error", "error" in p
           and "out of range" in p.get("error", ""), json.dumps(p))

    # ---- 8. set_motion_blur ------------------------------------------
    p = payload(send("addSolidLayer", {"compId": comp_id, "name": "P6 Mover",
                                       "color": [0.2, 0.9, 0.4], "width": 150,
                                       "height": 150, "durationSeconds": None}))
    MOV = 1  # added on top
    record("mover solid added", p.get("success") is True and p.get("index") == 1,
           json.dumps(p))
    p = payload(send("addKeyframes", {"compId": comp_id, "layerIndex": MOV,
                                      "propertyPath": ["ADBE Transform Group", "ADBE Position"],
                                      "times": [0.0, 2.0],
                                      "values": [[100, 360], [1180, 360]]}))
    record("mover position keyframes", p.get("success") is True, json.dumps(p))

    hm0 = frame_hash(comp_id, 1.0)

    p = payload(send("setMotionBlur", {"compId": comp_id, "layerIndex": MOV,
                                       "layerEnabled": True}))
    record("set_motion_blur layer switch on", p.get("success") is True
           and p.get("layerMotionBlur") is True and p.get("compMotionBlur") is False,
           json.dumps(p))
    hm1 = frame_hash(comp_id, 1.0)
    record("layer switch alone: render unchanged (comp master off)",
           hm0 is not None and hm1 == hm0, "hm0=%s hm1=%s" % (hm0, hm1))

    p = payload(send("setMotionBlur", {"compId": comp_id, "compEnabled": True}))
    record("set_motion_blur comp master on (partial args)", p.get("success") is True
           and p.get("compMotionBlur") is True and p.get("layerMotionBlur") is None,
           json.dumps(p))
    r = es("var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
           "return c.layer(%d).motionBlur === true;" % (comp_id, MOV))
    record("partial-arg contract: comp_enabled alone left layer switch on",
           r is True, json.dumps(r))
    hm2 = frame_hash(comp_id, 1.0)
    record("pixel-diff: motion blur renders with both switches on",
           hm2 is not None and hm2 != hm0, "hm0=%s hm2=%s" % (hm0, hm2))

    # undo = one step (comp master back off)
    es("app.executeCommand(16); return true;")
    r = es("var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
           "return c.motionBlur === true;" % comp_id)
    record("set_motion_blur single undo step (comp master off again)",
           r is False, json.dumps(r))
    es("app.executeCommand(2035); return true;")

    p = payload(send("setMotionBlur", {"compId": comp_id, "layerEnabled": True}))
    record("layer_enabled without layer_index -> clean error", "error" in p
           and "layerIndex is required" in p.get("error", ""), json.dumps(p))

    # ---- 9. set_frame_blending ---------------------------------------
    BL = MOV  # solid layer; frameBlendingType is an AVLayer property
    for bt, enum_name in [("FRAME_MIX", "FRAME_MIX"),
                          ("PIXEL_MOTION", "PIXEL_MOTION"),
                          ("OFF", "NO_FRAME_BLEND")]:
        p = payload(send("setFrameBlending", {"compId": comp_id, "layerIndex": BL,
                                              "blendType": bt}))
        ok1 = p.get("success") is True and p.get("layerFrameBlending") == bt
        r = es("var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
               "return c.layer(%d).frameBlendingType === FrameBlendingType.%s;"
               % (comp_id, BL, enum_name))
        record("frame blending %s round-trips (enum %s)" % (bt, enum_name),
               ok1 and r is True,
               json.dumps(p) + " / es=" + json.dumps(r))

    p = payload(send("setFrameBlending", {"compId": comp_id, "compEnabled": True}))
    record("frame blending comp master on", p.get("success") is True
           and p.get("compFrameBlending") is True and p.get("layerFrameBlending") is None,
           json.dumps(p))
    p = payload(send("setFrameBlending", {"compId": comp_id, "compEnabled": False}))
    record("frame blending comp master off", p.get("success") is True
           and p.get("compFrameBlending") is False, json.dumps(p))

    p = payload(send("setFrameBlending", {"compId": comp_id, "layerIndex": BL,
                                          "blendType": "BOGUS"}))
    record("bad blend_type string -> clean error", "error" in p
           and "FRAME_MIX" in p.get("error", ""), json.dumps(p))
    p = payload(send("setFrameBlending", {"compId": comp_id, "blendType": "FRAME_MIX"}))
    record("blend_type without layer_index -> clean error", "error" in p
           and "layerIndex is required" in p.get("error", ""), json.dumps(p))

    # ---- summary ------------------------------------------------------
    npass = sum(1 for _, ok, _ in RESULTS if ok)
    print("\n%d/%d checks passed" % (npass, len(RESULTS)))
    if npass != len(RESULTS):
        print("FAILURES:")
        for name, ok, detail in RESULTS:
            if not ok:
                print("  - %s: %s" % (name, detail[:300]))
    if FINDINGS:
        print("\nFINDINGS:")
        for f in FINDINGS:
            print("  * " + f)

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
