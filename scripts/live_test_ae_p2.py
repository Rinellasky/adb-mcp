"""One-shot live test of the 7 AE MCP Priority 2 handlers.

Sends command packets through the adb proxy (port 3001) to the
"aftereffects" channel, exactly like mcp/ae-mcp.py does via
core.sendCommand -> socket_client.send_message_blocking.

DESTRUCTIVE: starts with createProject force=true, wiping the open project.
Only run against a scratch AE instance.

Run:  ..\mcp\.venv\Scripts\python.exe live_test_ae_p2.py
"""

import sys, os, json, traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mcp"))
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
    """Unwrap createPacket envelope -> the handler's JSON result object."""
    txt = resp["response"]["content"][0]["text"]
    return json.loads(txt)

def es(script, timeout=30):
    """Run raw ExtendScript via the executeExtendScript handler."""
    return payload(send("executeExtendScript", {"scriptString": script}, timeout))

def undo_redo_single_step(label, check_script):
    """Verify a mutation reverts with exactly ONE undo and returns with one redo."""
    applied = es("return (" + check_script + ");")
    if applied is not True:
        record(label + " [pre-undo state]", False, "mutation not visible: %r" % (applied,))
        return
    es("app.executeCommand(16); return true;")  # Edit > Undo
    after_undo = es("return (" + check_script + ");")
    es("app.executeCommand(2035); return true;")  # Edit > Redo (AE 26: 2035, not 17)
    after_redo = es("return (" + check_script + ");")
    ok = (after_undo is False) and (after_redo is True)
    record(label + " [single undo step]", ok,
           "" if ok else "after_undo=%r after_redo=%r" % (after_undo, after_redo))

def approx(a, b, eps=0.002):
    return a is not None and b is not None and abs(a - b) <= eps

def main():
    payload(send("createProject", {"force": True}))

    # ---- 1. createComposition ----------------------------------------
    p = payload(send("createComposition", {
        "name": "MCP_P2_Comp", "width": 1280, "height": 720,
        "pixelAspect": 1.0, "durationSeconds": 5.0, "frameRate": 30.0}))
    comp_id = p.get("id")
    ok = (p.get("success") is True and p.get("width") == 1280 and p.get("height") == 720
          and approx(p.get("duration"), 5.0) and approx(p.get("frameRate"), 30.0))
    record("createComposition", ok, json.dumps(p))
    if comp_id is None:
        print("No comp id - aborting.")
        return
    active = es("return app.project.activeItem !== null ? app.project.activeItem.id : null;")
    record("createComposition opened in viewer", active == comp_id, "activeItem id=%r want=%r" % (active, comp_id))
    undo_redo_single_step("createComposition",
        "(function(){for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).name==='MCP_P2_Comp')return true;}return false;})()")
    # refresh id in case it changed across undo/redo
    comp_id = es("return (function(){for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).name==='MCP_P2_Comp')return app.project.item(i).id;}return null;})();")
    record("comp id stable after redo", comp_id is not None, "id=%r" % comp_id)
    if comp_id is None:
        return

    # ---- 2. getCompositionDetails ------------------------------------
    d = payload(send("getCompositionDetails", {"compId": comp_id}))
    ok = (d.get("success") is True and d.get("id") == comp_id and d.get("width") == 1280
          and d.get("height") == 720 and approx(d.get("duration"), 5.0)
          and approx(d.get("frameRate"), 30.0) and approx(d.get("pixelAspect"), 1.0)
          and isinstance(d.get("bgColor"), list) and len(d["bgColor"]) == 3
          and approx(d.get("workAreaStart"), 0.0) and d.get("numLayers") == 0
          and d.get("layers") == [])
    record("getCompositionDetails(empty comp)", ok, json.dumps({k: d.get(k) for k in ("id","width","height","duration","frameRate","pixelAspect","bgColor","workAreaStart","workAreaDuration","numLayers")}))

    # populate: solid + text layer, parent text->solid, transforms, effect
    r = es("""
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).id === %d) { comp = app.project.item(i); }
        }
        app.beginUndoGroup("Test: populate comp");
        var solid = comp.layers.addSolid([1, 0, 0], "Test Solid", 640, 360, 1.0);
        var text = comp.layers.addText("Hello MCP");
        text.parent = solid;
        solid.property("ADBE Transform Group").property("ADBE Position").setValue([400, 300]);
        solid.property("ADBE Transform Group").property("ADBE Rotate Z").setValue(15);
        solid.property("ADBE Transform Group").property("ADBE Opacity").setValue(80);
        solid.solo = false; solid.shy = true;
        var fx = solid.property("ADBE Effect Parade").addProperty("ADBE Gaussian Blur 2");
        app.endUndoGroup();
        return {solidIndex: solid.index, textIndex: text.index, fxMatch: fx.matchName};
    """ % comp_id)
    record("populate comp (solid+text+parent+blur)", isinstance(r, dict) and "solidIndex" in r, json.dumps(r))

    d = payload(send("getCompositionDetails", {"compId": comp_id}))
    layers = {l["name"]: l for l in d.get("layers", [])}
    solid = layers.get("Test Solid"); text = layers.get("Hello MCP")
    ok = solid is not None and text is not None and d.get("numLayers") == 2
    record("details: both layers present", ok, "names=%r" % list(layers.keys()))
    if solid and text:
        record("details: layer types", solid["type"] == "AV" and text["type"] == "Text",
               "solid=%r text=%r" % (solid["type"], text["type"]))
        record("details: parenting (text -> solid)", text["parentIndex"] == solid["index"],
               "parentIndex=%r solidIndex=%r" % (text["parentIndex"], solid["index"]))
        record("details: transforms", (solid["position"][:2] == [400, 300] and approx(solid["rotation"], 15)
               and approx(solid["opacity"], 80) and isinstance(solid["anchorPoint"], list)
               and isinstance(solid["scale"], list)),
               json.dumps({k: solid[k] for k in ("position","rotation","opacity","anchorPoint","scale")}))
        record("details: switches", solid["shy"] is True and solid["solo"] is False
               and solid["enabled"] is True and solid["locked"] is False,
               json.dumps({k: solid[k] for k in ("enabled","solo","shy","locked","threeD")}))
        record("details: sourceId set on solid", isinstance(solid["sourceId"], int), "sourceId=%r" % solid["sourceId"])
        fx = solid.get("effects", [])
        record("details: applied effect visible", len(fx) == 1 and fx[0]["matchName"] == "ADBE Gaussian Blur 2"
               and fx[0]["enabled"] is True, json.dumps(fx))

    # ---- 3. getFrameImage --------------------------------------------
    try:
        from PIL import Image as PILImage
        HAVE_PIL = True
    except ImportError:
        HAVE_PIL = False

    for t_req, label in ((0.0, "t=0"), (2.5, "t=mid")):
        p = payload(send("getFrameImage", {"compId": comp_id, "timeSeconds": t_req}, timeout=60))
        ok = p.get("success") is True and p.get("path") and os.path.exists(p["path"])
        record("getFrameImage(%s) file exists" % label, ok, json.dumps(p))
        if ok:
            if HAVE_PIL:
                with PILImage.open(p["path"]) as im:
                    record("getFrameImage(%s) dimensions" % label, im.size == (1280, 720), "size=%r" % (im.size,))
            os.remove(p["path"])
            record("getFrameImage(%s) temp cleanup" % label, not os.path.exists(p["path"]))

    # time clamping: t=999 -> duration - frameDuration
    p = payload(send("getFrameImage", {"compId": comp_id, "timeSeconds": 999.0}, timeout=60))
    expect = 5.0 - (1.0 / 30.0)
    ok = p.get("success") is True and approx(p.get("time"), expect, eps=0.01)
    record("getFrameImage(t=999) clamped", ok, "time=%r expect~%r" % (p.get("time"), expect))
    if p.get("path") and os.path.exists(p["path"]):
        os.remove(p["path"])

    # Python-side: real MCP Image object via ae-mcp.py's get_frame_image
    try:
        import importlib.util as u
        spec = u.spec_from_file_location("aemcp", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mcp", "ae-mcp.py"))
        m = u.module_from_spec(spec)
        spec.loader.exec_module(m)
        res = m.get_frame_image(comp_id, 1.0)
        from mcp.server.fastmcp import Image as MCPImage
        ok = (isinstance(res, list) and len(res) == 2 and isinstance(res[1], MCPImage)
              and res[0].get("status") == "SUCCESS" and "response" not in res[0])
        record("get_frame_image (python) returns MCP Image", ok, "type=%r" % type(res))
    except Exception as e:
        record("get_frame_image (python) returns MCP Image", False, "%s: %s" % (type(e).__name__, e))

    # ---- 4. setCompositionSettings -----------------------------------
    before = payload(send("getCompositionDetails", {"compId": comp_id}))
    p = payload(send("setCompositionSettings", {"compId": comp_id, "bgColor": [0.0, 0.5, 1.0]}))
    ok = p.get("success") is True and all(approx(a, b) for a, b in zip(p.get("bgColor", []), [0.0, 0.5, 1.0]))
    record("setCompositionSettings(bgColor only)", ok, json.dumps(p))
    after = payload(send("getCompositionDetails", {"compId": comp_id}))
    unchanged = all(before.get(k) == after.get(k) for k in ("name", "width", "height", "duration", "frameRate", "numLayers"))
    record("setCompositionSettings partial: others unchanged", unchanged,
           json.dumps({k: (before.get(k), after.get(k)) for k in ("name","width","height","duration","frameRate")}))
    undo_redo_single_step("setCompositionSettings",
        "(function(){for(var i=1;i<=app.project.numItems;i++){var it=app.project.item(i);if(it.id===%d)return Math.abs(it.bgColor[2]-1.0)<0.002;}return false;})()" % comp_id)

    p = payload(send("setCompositionSettings", {
        "compId": comp_id, "name": "MCP_P2_Renamed", "width": 1920, "height": 1080,
        "durationSeconds": 8.0, "frameRate": 24.0}))
    ok = (p.get("success") is True and p.get("name") == "MCP_P2_Renamed" and p.get("width") == 1920
          and p.get("height") == 1080 and approx(p.get("duration"), 8.0) and approx(p.get("frameRate"), 24.0))
    record("setCompositionSettings(multi-field)", ok, json.dumps(p))

    # ---- 5. setWorkArea / addCompositionMarker / openComposition -----
    p = payload(send("setWorkArea", {"compId": comp_id, "startSeconds": 1.0, "durationSeconds": 3.0}))
    ok = p.get("success") is True and approx(p.get("workAreaStart"), 1.0, 0.05) and approx(p.get("workAreaDuration"), 3.0, 0.05)
    record("setWorkArea", ok, json.dumps(p))
    undo_redo_single_step("setWorkArea",
        "(function(){for(var i=1;i<=app.project.numItems;i++){var it=app.project.item(i);if(it.id===%d)return Math.abs(it.workAreaStart-1.0)<0.05;}return false;})()" % comp_id)

    p = payload(send("addCompositionMarker", {"compId": comp_id, "timeSeconds": 2.0, "comment": "point marker"}))
    record("addCompositionMarker(point)", p.get("success") is True and p.get("numMarkers") == 1, json.dumps(p))
    p = payload(send("addCompositionMarker", {"compId": comp_id, "timeSeconds": 4.0, "comment": "ranged marker", "durationSeconds": 2.0}))
    record("addCompositionMarker(ranged)", p.get("success") is True and p.get("numMarkers") == 2, json.dumps(p))
    mk = es("""
        var comp=null; for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)comp=app.project.item(i);}
        var mp = comp.markerProperty;
        return {n: mp.numKeys,
                c1: mp.keyValue(1).comment, d1: mp.keyValue(1).duration, t1: mp.keyTime(1),
                c2: mp.keyValue(2).comment, d2: mp.keyValue(2).duration, t2: mp.keyTime(2)};
    """ % comp_id)
    ok = (isinstance(mk, dict) and mk.get("n") == 2 and mk.get("c1") == "point marker" and approx(mk.get("d1"), 0.0)
          and approx(mk.get("t1"), 2.0, 0.05) and mk.get("c2") == "ranged marker" and approx(mk.get("d2"), 2.0, 0.05)
          and approx(mk.get("t2"), 4.0, 0.05))
    record("markers verified (times/comments/durations)", ok, json.dumps(mk))
    undo_redo_single_step("addCompositionMarker",
        "(function(){for(var i=1;i<=app.project.numItems;i++){var it=app.project.item(i);if(it.id===%d)return it.markerProperty.numKeys===2;}return false;})()" % comp_id)

    # openComposition: create a 2nd comp, then re-open the first
    p2 = payload(send("createComposition", {"name": "MCP_P2_Other", "width": 320, "height": 240,
                                            "pixelAspect": 1.0, "durationSeconds": 2.0, "frameRate": 30.0}))
    other_id = p2.get("id")
    active = es("return app.project.activeItem !== null ? app.project.activeItem.id : null;")
    record("second comp active after create", active == other_id, "active=%r" % active)
    p = payload(send("openComposition", {"compId": comp_id}))
    active = es("return app.project.activeItem !== null ? app.project.activeItem.id : null;")
    record("openComposition switches viewer", p.get("success") is True and active == comp_id,
           "active=%r want=%r" % (active, comp_id))

    # ---- 6. Error paths ----------------------------------------------
    for action, opts in (
        ("getCompositionDetails", {"compId": 99999}),
        ("getFrameImage", {"compId": 99999, "timeSeconds": 0}),
        ("openComposition", {"compId": 99999}),
        ("setCompositionSettings", {"compId": 99999, "name": "x"}),
        ("setWorkArea", {"compId": 99999, "startSeconds": 0, "durationSeconds": 1}),
        ("addCompositionMarker", {"compId": 99999, "timeSeconds": 0, "comment": "x"}),
    ):
        p = payload(send(action, opts))
        record("%s(99999) -> clean error" % action,
               isinstance(p.get("error"), str) and "Composition not found" in p["error"], json.dumps(p))

    # Camera/Light comp: opacity/rotation must be null, not a throw
    r = es("""
        var comp = app.project.items.addComp("MCP_P2_3D", 640, 480, 1.0, 2.0, 30.0);
        var cam = comp.layers.addCamera("Test Cam", [320, 240]);
        var light = comp.layers.addLight("Test Light", [320, 240]);
        return {id: comp.id};
    """)
    cam_comp_id = r.get("id") if isinstance(r, dict) else None
    d = payload(send("getCompositionDetails", {"compId": cam_comp_id}))
    ok = d.get("success") is True and d.get("numLayers") == 2
    record("details on Camera/Light comp (no throw)", ok, json.dumps({k: d.get(k) for k in ("success","numLayers","error")}))
    if ok:
        cam = next((l for l in d["layers"] if l["type"] == "Camera"), None)
        light = next((l for l in d["layers"] if l["type"] == "Light"), None)
        record("camera/light types detected", cam is not None and light is not None,
               "types=%r" % [l["type"] for l in d["layers"]])
        if cam:
            # AE 26 divergence from draft expectation: Camera layers DO
            # report Opacity/Scale values (100 / [100,100,100]) instead of
            # null - the null-safe propValue path matters for older builds,
            # but on 26.x the properties exist. Required behavior: no throw.
            record("camera props read without throw", (cam["opacity"] is None or cam["opacity"] == 100)
                   and cam["sourceId"] is None,
                   json.dumps({k: cam[k] for k in ("opacity","scale","rotation","sourceId")}))

    # ---- summary ------------------------------------------------------
    fails = [r for r in RESULTS if not r[1]]
    print("\n==== %d/%d passed ====" % (len(RESULTS) - len(fails), len(RESULTS)))
    for name, _, detail in fails:
        print("FAILED: %s  %s" % (name, detail))
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    try:
        main()
    except AppError as e:
        print("APP ERROR: %s" % e)
        sys.exit(2)
    except Exception:
        traceback.print_exc()
        sys.exit(3)
