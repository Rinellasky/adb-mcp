"""One-shot live test of the 16 AE MCP Priority 3 (Layer System) handlers.

Sends command packets through the adb proxy (port 3001) to the
"aftereffects" channel, exactly like mcp/ae-mcp.py does via
core.sendCommand -> socket_client.send_message_blocking.

DESTRUCTIVE: starts with createProject force=true, wiping the open project.
Only run against a scratch AE instance.

Run:  ../mcp/.venv/Scripts/python.exe live_test_ae_p3.py
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

def details(comp_id):
    return payload(send("getCompositionDetails", {"compId": comp_id}))

def layer_by_name(comp_id, name):
    d = details(comp_id)
    for l in d.get("layers", []):
        if l["name"] == name:
            return l
    return None

def undo_redo_single_step(label, check_script):
    """Verify a mutation reverts with exactly ONE undo and returns with one redo."""
    applied = es("return (" + check_script + ");")
    if applied is not True:
        record(label + " [pre-undo state]", False, "mutation not visible: %r" % (applied,))
        return
    es("app.executeCommand(16); return true;")    # Edit > Undo
    after_undo = es("return (" + check_script + ");")
    es("app.executeCommand(2035); return true;")  # Edit > Redo (AE 26: 2035)
    after_redo = es("return (" + check_script + ");")
    ok = (after_undo is False) and (after_redo is True)
    record(label + " [single undo step]", ok,
           "" if ok else "after_undo=%r after_redo=%r" % (after_undo, after_redo))

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

def main():
    payload(send("createProject", {"force": True}))

    # test still for footage import
    still_path = os.path.join(SCRIPT_DIR, "ae_p3_test_still.png")
    from PIL import Image as PILImage
    PILImage.new("RGB", (100, 80), (0, 200, 60)).save(still_path)
    imp = payload(send("importFile", {"path": still_path}))
    item_id = imp.get("id")
    record("importFile(test still)", isinstance(item_id, int), json.dumps(imp))

    p = payload(send("createComposition", {
        "name": "MCP_P3_Comp", "width": 1280, "height": 720,
        "pixelAspect": 1.0, "durationSeconds": 5.0, "frameRate": 30.0}))
    comp_id = p.get("id")
    record("createComposition", p.get("success") is True and comp_id is not None, json.dumps(p))
    if comp_id is None:
        return

    # ---- 1. add_* tools -----------------------------------------------
    p = payload(send("addSolidLayer", {"compId": comp_id, "name": "P3 Solid",
                                       "color": [1.0, 0.2, 0.2], "width": 320,
                                       "height": 240, "durationSeconds": None}))
    record("addSolidLayer(custom color+size)", p.get("success") is True and p.get("index") == 1
           and isinstance(p.get("sourceId"), int), json.dumps(p))
    solid_src = es("""
        var comp=null; for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)comp=app.project.item(i);}
        var s = comp.layer(1).source;
        return {w: s.width, h: s.height, c: s.mainSource.color};
    """ % comp_id)
    record("solid custom size/color verified",
           isinstance(solid_src, dict) and solid_src.get("w") == 320 and solid_src.get("h") == 240
           and approx(solid_src["c"][0], 1.0, 0.01) and approx(solid_src["c"][1], 0.2, 0.01),
           json.dumps(solid_src))

    p = payload(send("addTextLayer", {"compId": comp_id, "text": "P3 Text"}))
    record("addTextLayer", p.get("success") is True and p.get("index") == 1, json.dumps(p))

    p = payload(send("addNullLayer", {"compId": comp_id, "name": "P3 Null"}))
    record("addNullLayer(renamed)", p.get("success") is True and p.get("index") == 1
           and p.get("name") == "P3 Null", json.dumps(p))

    p = payload(send("addAdjustmentLayer", {"compId": comp_id, "name": "P3 Adjust"}))
    record("addAdjustmentLayer", p.get("success") is True and p.get("index") == 1, json.dumps(p))
    adj_flag = es("""
        var comp=null; for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)comp=app.project.item(i);}
        return comp.layer(1).adjustmentLayer === true;
    """ % comp_id)
    record("adjustment flag set", adj_flag is True, repr(adj_flag))

    p = payload(send("addShapeLayer", {"compId": comp_id, "name": "P3 Shape"}))
    record("addShapeLayer", p.get("success") is True and p.get("index") == 1
           and p.get("name") == "P3 Shape", json.dumps(p))

    p = payload(send("addFootageLayer", {"compId": comp_id, "itemId": item_id,
                                         "durationSeconds": 3.0}))
    record("addFootageLayer(still)", p.get("success") is True and p.get("index") == 1
           and p.get("sourceId") == item_id, json.dumps(p))

    p2 = payload(send("createComposition", {"name": "MCP_P3_Nested_Src", "width": 320,
                                            "height": 240, "pixelAspect": 1.0,
                                            "durationSeconds": 2.0, "frameRate": 30.0}))
    nested_src_id = p2.get("id")
    p = payload(send("addFootageLayer", {"compId": comp_id, "itemId": nested_src_id}))
    record("addFootageLayer(comp -> nested comp layer)", p.get("success") is True
           and p.get("index") == 1 and p.get("sourceId") == nested_src_id, json.dumps(p))

    p = payload(send("addCameraLayer", {"compId": comp_id, "name": "P3 Cam",
                                        "centerPoint": None}))
    record("addCameraLayer", p.get("success") is True and p.get("index") == 1, json.dumps(p))

    p = payload(send("addLightLayer", {"compId": comp_id, "name": "P3 Light",
                                       "centerPoint": [400, 300]}))
    record("addLightLayer", p.get("success") is True and p.get("index") == 1
           and isinstance(p.get("lightType"), str), json.dumps(p))
    undo_redo_single_step("addLightLayer", (
        "(function(){var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
        "for(var j=1;j<=c.numLayers;j++){if(c.layer(j).name==='P3 Light')return true;}return false;})()" % comp_id))

    # type reporting from the keystone read
    d = details(comp_id)
    types = {l["name"]: l["type"] for l in d.get("layers", [])}
    expect = {"P3 Solid": "AV", "P3 Text": "Text", "P3 Null": "Null", "P3 Adjust": "AV",
              "P3 Shape": "Shape", "P3 Cam": "Camera", "P3 Light": "Light"}
    bad = {k: (types.get(k), v) for k, v in expect.items() if types.get(k) != v}
    record("getCompositionDetails layer types", not bad and d.get("numLayers") == 9,
           json.dumps(types) if not bad else json.dumps(bad))

    # ---- 2. setLayerProperties ---------------------------------------
    solid = layer_by_name(comp_id, "P3 Solid")
    p = payload(send("setLayerProperties", {"compId": comp_id, "layerIndex": solid["index"],
                                            "name": "P3 Solid R"}))
    ok = (p.get("success") is True and p.get("name") == "P3 Solid R"
          and p.get("enabled") is True and p.get("solo") is False
          and p.get("locked") is False and p.get("shy") is False)
    record("setLayerProperties(rename only, switches untouched)", ok, json.dumps(p))

    p = payload(send("setLayerProperties", {"compId": comp_id, "layerIndex": solid["index"],
                                            "solo": True, "shy": True}))
    ok = (p.get("success") is True and p.get("name") == "P3 Solid R"
          and p.get("solo") is True and p.get("shy") is True and p.get("enabled") is True
          and p.get("locked") is False)
    record("setLayerProperties(multi-switch, name untouched)", ok, json.dumps(p))
    undo_redo_single_step("setLayerProperties", (
        "(function(){var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
        "var l=c.layer(%d);return l.solo===true&&l.shy===true;})()"
        % (comp_id, solid["index"])))
    # AE 26.x constraint: solo=true + enabled=false is impossible - refused
    p = payload(send("setLayerProperties", {"compId": comp_id, "layerIndex": solid["index"],
                                            "solo": True, "enabled": False}))
    record("setLayerProperties(solo+disable) -> constraint refusal",
           isinstance(p.get("error"), str) and "solo=true requires an enabled layer" in p["error"],
           json.dumps(p))
    payload(send("setLayerProperties", {"compId": comp_id, "layerIndex": solid["index"],
                                        "solo": False, "shy": False, "enabled": True}))

    # ---- 3. rig: parent to null, move null, pixel-diff ---------------
    null_l = layer_by_name(comp_id, "P3 Null")
    solid = layer_by_name(comp_id, "P3 Solid R")
    text = layer_by_name(comp_id, "P3 Text")
    p = payload(send("setLayerParent", {"compId": comp_id, "layerIndex": solid["index"],
                                        "parentIndex": null_l["index"]}))
    record("setLayerParent(solid -> null)", p.get("success") is True
           and p.get("parentIndex") == null_l["index"], json.dumps(p))
    p = payload(send("setLayerParent", {"compId": comp_id, "layerIndex": text["index"],
                                        "parentIndex": null_l["index"]}))
    record("setLayerParent(text -> null)", p.get("success") is True
           and p.get("parentIndex") == null_l["index"], json.dumps(p))

    h_before = frame_hash(comp_id)
    p = payload(send("setLayerTransform", {"compId": comp_id, "layerIndex": null_l["index"],
                                           "position": [900, 550]}))
    record("setLayerTransform(move null)", p.get("success") is True
           and "position" in p.get("applied", []), json.dumps(p))
    h_after = frame_hash(comp_id)
    record("children moved with null (frame changed)",
           h_before is not None and h_after is not None and h_before != h_after,
           "before=%s after=%s" % (h_before, h_after))

    p = payload(send("setLayerParent", {"compId": comp_id, "layerIndex": solid["index"]}))
    record("setLayerParent(unparent solid)", p.get("success") is True
           and p.get("parentIndex") is None, json.dumps(p))
    undo_redo_single_step("setLayerParent unparent", (
        "(function(){var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
        "return c.layer(%d).parent===null;})()" % (comp_id, solid["index"])))
    d_check = layer_by_name(comp_id, "P3 Text")
    record("text still parented after solid unparent",
           d_check["parentIndex"] == null_l["index"], json.dumps(d_check["parentIndex"]))

    # ---- 4. setLayerTransform ----------------------------------------
    # partial update: scale only; position must be untouched
    before_pos = layer_by_name(comp_id, "P3 Solid R")["position"]
    p = payload(send("setLayerTransform", {"compId": comp_id, "layerIndex": solid["index"],
                                           "scale": [50, 50]}))
    after = layer_by_name(comp_id, "P3 Solid R")
    record("setLayerTransform(partial: scale only)",
           p.get("success") is True and p.get("applied") == ["scale"]
           and after["scale"][:2] == [50, 50] and after["position"] == before_pos,
           json.dumps({"applied": p.get("applied"), "scale": after["scale"], "pos": (before_pos, after["position"])}))
    undo_redo_single_step("setLayerTransform", (
        "(function(){var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
        "var s=c.layer(%d).property('ADBE Transform Group').property('ADBE Scale').value;"
        "return Math.abs(s[0]-50)<0.01;})()" % (comp_id, solid["index"])))

    # keyframe refusal: keyframe text position, then try position + opacity
    text = layer_by_name(comp_id, "P3 Text")
    es("""
        var c=null; for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}
        var prop = c.layer(%d).property("ADBE Transform Group").property("ADBE Position");
        prop.setValueAtTime(0, [100, 100]); prop.setValueAtTime(1, [200, 200]);
        return prop.numKeys;
    """ % (comp_id, text["index"]))
    p = payload(send("setLayerTransform", {"compId": comp_id, "layerIndex": text["index"],
                                           "position": [10, 10], "opacity": 42}))
    skipped = p.get("skipped", [])
    ok = (p.get("success") is True and p.get("applied") == ["opacity"]
          and len(skipped) == 1 and skipped[0].startswith("position")
          and "keyframe" in skipped[0])
    record("setLayerTransform(keyframed position skipped, opacity applied)", ok, json.dumps(p))
    kf_intact = es("""
        var c=null; for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}
        var t=c.layer(%d).property("ADBE Transform Group");
        return {keys: t.property("ADBE Position").numKeys, op: t.property("ADBE Opacity").value};
    """ % (comp_id, text["index"]))
    record("keyframes intact + opacity=42", isinstance(kf_intact, dict)
           and kf_intact.get("keys") == 2 and approx(kf_intact.get("op"), 42, 0.01),
           json.dumps(kf_intact))

    # all-requested-props skipped -> hard error
    p = payload(send("setLayerTransform", {"compId": comp_id, "layerIndex": text["index"],
                                           "position": [10, 10]}))
    record("setLayerTransform(only keyframed prop) -> error",
           isinstance(p.get("error"), str) and "keyframe" in p["error"], json.dumps(p))

    # 3D path
    es("""
        var c=null; for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}
        c.layer(%d).threeDLayer = true; return true;
    """ % (comp_id, solid["index"]))
    p = payload(send("setLayerTransform", {"compId": comp_id, "layerIndex": solid["index"],
                                           "rotationX": 10, "rotationY": 20}))
    rot = es("""
        var c=null; for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}
        var t=c.layer(%d).property("ADBE Transform Group");
        return {x: t.property("ADBE Rotate X").value, y: t.property("ADBE Rotate Y").value};
    """ % (comp_id, solid["index"]))
    record("setLayerTransform(3D rotationX/Y)", p.get("success") is True
           and sorted(p.get("applied", [])) == ["rotationX", "rotationY"]
           and isinstance(rot, dict) and approx(rot.get("x"), 10, 0.01) and approx(rot.get("y"), 20, 0.01),
           json.dumps({"resp": p.get("applied"), "read": rot}))

    # opacity on a Camera layer (AE 26.x quirk: property exists)
    cam = layer_by_name(comp_id, "P3 Cam")
    p = payload(send("setLayerTransform", {"compId": comp_id, "layerIndex": cam["index"],
                                           "opacity": 70}))
    record("setLayerTransform(opacity on Camera) [26.x quirk probe]",
           p.get("success") is True or isinstance(p.get("error"), str), json.dumps(p))

    # ---- 5. setLayerTimes --------------------------------------------
    solid = layer_by_name(comp_id, "P3 Solid R")
    p = payload(send("setLayerTimes", {"compId": comp_id, "layerIndex": solid["index"],
                                       "startTime": 1.0}))
    record("setLayerTimes(startTime shift)", p.get("success") is True
           and approx(p.get("startTime"), 1.0), json.dumps(p))
    p = payload(send("setLayerTimes", {"compId": comp_id, "layerIndex": solid["index"],
                                       "inPoint": 1.5, "outPoint": 2.5}))
    record("setLayerTimes(in/out trim)", p.get("success") is True
           and approx(p.get("inPoint"), 1.5) and approx(p.get("outPoint"), 2.5)
           and approx(p.get("startTime"), 1.0), json.dumps(p))
    l = layer_by_name(comp_id, "P3 Solid R")
    record("layer times verified via details", approx(l["startTime"], 1.0)
           and approx(l["inPoint"], 1.5) and approx(l["outPoint"], 2.5),
           json.dumps({k: l[k] for k in ("startTime", "inPoint", "outPoint")}))
    undo_redo_single_step("setLayerTimes", (
        "(function(){var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
        "var l=c.layer(%d);return Math.abs(l.inPoint-1.5)<0.05;})()" % (comp_id, solid["index"])))

    # ---- 6. duplicate / reorder / delete -----------------------------
    solid = layer_by_name(comp_id, "P3 Solid R")
    p = payload(send("duplicateLayer", {"compId": comp_id, "layerIndex": solid["index"],
                                        "name": "P3 Dup"}))
    ok = (p.get("success") is True and p.get("name") == "P3 Dup"
          and p.get("index") == solid["index"] and p.get("sourceLayerIndex") == solid["index"] + 1)
    record("duplicateLayer(lands above original)", ok, json.dumps(p))
    undo_redo_single_step("duplicateLayer", (
        "(function(){var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
        "for(var j=1;j<=c.numLayers;j++){if(c.layer(j).name==='P3 Dup')return true;}return false;})()" % comp_id))

    n = details(comp_id)["numLayers"]
    dup = layer_by_name(comp_id, "P3 Dup")
    p = payload(send("reorderLayer", {"compId": comp_id, "layerIndex": dup["index"], "position": "top"}))
    record("reorderLayer(top)", p.get("success") is True and p.get("index") == 1, json.dumps(p))
    p = payload(send("reorderLayer", {"compId": comp_id, "layerIndex": 1, "position": "bottom"}))
    record("reorderLayer(bottom)", p.get("success") is True and p.get("index") == n, json.dumps(p))
    p = payload(send("reorderLayer", {"compId": comp_id, "layerIndex": n, "position": "before",
                                      "targetIndex": 3}))
    record("reorderLayer(before target 3)", p.get("success") is True and p.get("index") == 3, json.dumps(p))
    p = payload(send("reorderLayer", {"compId": comp_id, "layerIndex": 3, "position": "after",
                                      "targetIndex": 1}))
    record("reorderLayer(after target 1)", p.get("success") is True and p.get("index") == 2, json.dumps(p))
    undo_redo_single_step("reorderLayer", (
        "(function(){var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
        "return c.layer(2).name==='P3 Dup';})()" % comp_id))

    dup = layer_by_name(comp_id, "P3 Dup")
    payload(send("setLayerProperties", {"compId": comp_id, "layerIndex": dup["index"], "locked": True}))
    p = payload(send("deleteLayer", {"compId": comp_id, "layerIndex": dup["index"]}))
    record("deleteLayer(locked) -> refusal", isinstance(p.get("error"), str)
           and "locked" in p["error"], json.dumps(p))
    payload(send("setLayerProperties", {"compId": comp_id, "layerIndex": dup["index"], "locked": False}))
    p = payload(send("deleteLayer", {"compId": comp_id, "layerIndex": dup["index"]}))
    record("deleteLayer(after unlock)", p.get("success") is True
           and p.get("deletedName") == "P3 Dup" and p.get("numLayers") == n - 1, json.dumps(p))
    undo_redo_single_step("deleteLayer", (
        "(function(){var c=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===%d)c=app.project.item(i);}"
        "for(var j=1;j<=c.numLayers;j++){if(c.layer(j).name==='P3 Dup')return false;}return true;})()" % comp_id))
    # redo left it deleted; nothing to clean up

    # ---- 7. precomposeLayers -----------------------------------------
    d = details(comp_id)
    shape = next(l for l in d["layers"] if l["name"] == "P3 Shape")
    adjust = next(l for l in d["layers"] if l["name"] == "P3 Adjust")
    n_before = d["numLayers"]
    p = payload(send("precomposeLayers", {"compId": comp_id,
                                          "layerIndices": [shape["index"], adjust["index"]],
                                          "name": "P3 Pre Multi", "moveAllAttributes": True}))
    new_id = p.get("newCompId")
    ok = (p.get("success") is True and isinstance(new_id, int)
          and isinstance(p.get("precompLayerIndex"), int) and p.get("numLayersInNewComp") == 2)
    record("precomposeLayers(two layers)", ok, json.dumps(p))
    if ok:
        nd = details(new_id)
        names = sorted(l["name"] for l in nd.get("layers", []))
        record("precomp contents verified", names == ["P3 Adjust", "P3 Shape"], json.dumps(names))
        pl = details(comp_id)
        record("original comp layer count after precompose",
               pl["numLayers"] == n_before - 1, "numLayers=%r want=%r" % (pl["numLayers"], n_before - 1))
        pre_layer = pl["layers"][p["precompLayerIndex"] - 1]
        record("precomp layer index correct", pre_layer["sourceId"] == new_id
               and pre_layer["name"] == "P3 Pre Multi",
               json.dumps({"index": p["precompLayerIndex"], "name": pre_layer["name"]}))

    # single-layer precompose, both move_all_attributes values
    for maa in (True, False):
        d = details(comp_id)
        foot = next((l for l in d["layers"] if l["sourceId"] == item_id), None)
        if foot is None:
            record("precompose single (moveAll=%s) [locate footage layer]" % maa, False, "footage layer gone")
            continue
        p = payload(send("precomposeLayers", {"compId": comp_id, "layerIndices": [foot["index"]],
                                              "name": "P3 Pre Single %s" % maa,
                                              "moveAllAttributes": maa}))
        ok = p.get("success") is True and p.get("numLayersInNewComp") == 1
        record("precomposeLayers(single, moveAll=%s)" % maa, ok, json.dumps(p))
        if ok and maa is False:
            undo_redo_single_step("precomposeLayers", (
                "(function(){for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).name==='P3 Pre Single False')return true;}return false;})()"))
        if ok:
            # after each round the footage-holding layer's source is the new
            # precomp; look it up by that id next round
            item_id = p["newCompId"]

    # ---- 8. error paths ----------------------------------------------
    numl = details(comp_id)["numLayers"]
    err_cases = [
        ("addSolidLayer", {"compId": 99999, "name": "x", "color": [1, 1, 1],
                           "width": None, "height": None, "durationSeconds": None},
         "Composition not found"),
        ("setLayerProperties", {"compId": comp_id, "layerIndex": 0, "name": "x"}, "Layer not found"),
        ("setLayerProperties", {"compId": comp_id, "layerIndex": numl + 1, "name": "x"}, "Layer not found"),
        ("addFootageLayer", {"compId": comp_id, "itemId": 424242, "durationSeconds": None},
         "not found"),
        ("reorderLayer", {"compId": comp_id, "layerIndex": 1, "position": "before",
                          "targetIndex": None}, "targetIndex is required"),
        ("setLayerParent", {"compId": comp_id, "layerIndex": 1, "parentIndex": 1},
         "cannot be parented to itself"),
        ("precomposeLayers", {"compId": comp_id, "layerIndices": [], "name": "x",
                              "moveAllAttributes": True}, "at least one layer"),
        ("deleteLayer", {"compId": comp_id, "layerIndex": 0}, "Layer not found"),
        ("duplicateLayer", {"compId": comp_id, "layerIndex": numl + 1, "name": None}, "Layer not found"),
        ("setLayerTransform", {"compId": comp_id, "layerIndex": 0, "opacity": 50}, "Layer not found"),
        ("setLayerTimes", {"compId": comp_id, "layerIndex": 0, "startTime": 0,
                           "inPoint": None, "outPoint": None}, "Layer not found"),
    ]
    for action, opts, needle in err_cases:
        p = payload(send(action, opts))
        record("%s -> clean error (%s)" % (action, needle),
               isinstance(p.get("error"), str) and needle in p["error"], json.dumps(p))

    # multi-layer precompose with moveAll=false -> API-constraint error
    d = details(comp_id)
    if d["numLayers"] >= 2:
        p = payload(send("precomposeLayers", {"compId": comp_id, "layerIndices": [1, 2],
                                              "name": "x", "moveAllAttributes": False}))
        record("precomposeLayers(multi, moveAll=false) -> constraint error",
               isinstance(p.get("error"), str) and "moveAllAttributes" in p["error"], json.dumps(p))

    try:
        os.remove(still_path)
    except OSError:
        pass

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
