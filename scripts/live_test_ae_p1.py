"""One-shot live test of the 9 AE MCP Priority 1 handlers.

Sends command packets through the adb proxy (port 3001) to the
"aftereffects" channel, exactly like mcp/ae-mcp.py does via
core.sendCommand -> socket_client.send_message_blocking.

DESTRUCTIVE: ends with createProject force=true, wiping the open project.
Only run against a scratch AE instance.

Run:  ..\mcp\.venv\Scripts\python.exe live_test_ae_p1.py <assets_dir>
assets_dir must contain test_footage.png and seq\frame_0001.png..frame_0005.png
(any small PNGs work).
"""

import sys, os, json, traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mcp"))
import socket_client
from socket_client import AppError

socket_client.configure(app="aftereffects", url="http://localhost:3001", timeout=30)

ASSETS = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
FOOTAGE = os.path.join(ASSETS, "test_footage.png")
SEQ_FIRST = os.path.join(ASSETS, "seq", "frame_0001.png")
AEP_PATH = os.path.join(ASSETS, "mcp_p1_test.aep")

RESULTS = []

def record(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(("PASS  " if ok else "FAIL  ") + name + ("" if not detail else "  -- " + detail))

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
    """Verify a mutation reverts with exactly ONE undo and returns with one redo.

    check_script must be ExtendScript returning true/false for
    'mutation currently applied'.
    """
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

def main():
    # start from a clean empty project so checks aren't polluted by probes
    payload(send("createProject", {"force": True}))

    # ---- 1. getProjectInfo: health check ------------------------------
    resp = send("getProjectInfo")
    info = payload(resp)
    ok = info.get("success") is True and "items" in info and "dirty" in info
    record("getProjectInfo", ok, json.dumps({k: info.get(k) for k in ("name", "path", "dirty", "numItems")}))
    if not ok:
        print("Health check failed, aborting.")
        return

    # ---- 2. createProjectFolder --------------------------------------
    p = payload(send("createProjectFolder", {"name": "MCP_Test_Folder"}))
    ok = p.get("type") == "Folder" and isinstance(p.get("id"), int)
    record("createProjectFolder(root)", ok, json.dumps(p))
    undo_redo_single_step("createProjectFolder",
        "(function(){for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).name==='MCP_Test_Folder')return true;}return false;})()")
    # refresh id after undo/redo in case it changed
    info = payload(send("getProjectInfo"))
    folder_id = next((it["id"] for it in info["items"] if it["name"] == "MCP_Test_Folder"), None)
    record("folder id stable after redo", folder_id is not None, "id=%r" % folder_id)
    if folder_id is None:
        print("No folder id - aborting to avoid cascading vacuous results.")
        return

    # nested folder + invalid parent error path
    p = payload(send("createProjectFolder", {"name": "MCP_Nested", "parentFolderId": folder_id}))
    record("createProjectFolder(nested)", p.get("parentFolderId") == folder_id, json.dumps(p))
    p = payload(send("createProjectFolder", {"name": "MCP_Bad", "parentFolderId": 999999}))
    record("createProjectFolder(bad parent -> error)", "error" in p, json.dumps(p))

    # ---- 3. importFile ------------------------------------------------
    p = payload(send("importFile", {"path": FOOTAGE, "folderId": folder_id}))
    ok = p.get("type") == "Footage" and p.get("parentFolderId") == folder_id
    record("importFile(into folder)", ok, json.dumps(p))
    undo_redo_single_step("importFile",
        "(function(){for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).name==='test_footage.png')return true;}return false;})()")
    p = payload(send("importFile", {"path": FOOTAGE + ".nope"}))
    record("importFile(missing file -> error)", "error" in p, json.dumps(p))

    # ---- 4. importImageSequence (folder_id omitted -> root) -----------
    p = payload(send("importImageSequence", {"path": SEQ_FIRST}))
    seq_id = p.get("id")
    ok = p.get("type") == "Footage" and p.get("parentFolderId") is None
    record("importImageSequence(root)", ok, json.dumps(p))
    # confirm it really imported as a sequence (duration > single frame)
    d = es("var it=(function(){for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===" + str(seq_id) + ")return app.project.item(i);}return null;})(); return {frames: it.duration * it.frameRate};")
    frames = round(d.get("frames", 0)) if isinstance(d, dict) else 0
    record("importImageSequence is 5-frame sequence", frames == 5, "frames=%r" % frames)

    # ---- 5. moveItemsToFolder ----------------------------------------
    p = payload(send("moveItemsToFolder", {"itemIds": [seq_id], "folderId": folder_id}))
    record("moveItemsToFolder(into folder)", p.get("moved") == [seq_id] and p.get("failed") == [], json.dumps(p))
    loc = es("var it=(function(){for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===" + str(seq_id) + ")return app.project.item(i);}return null;})(); return it.parentFolder.id;")
    record("moveItemsToFolder landed in folder", loc == folder_id, "parent=%r want=%r" % (loc, folder_id))
    undo_redo_single_step("moveItemsToFolder",
        "(function(){for(var i=1;i<=app.project.numItems;i++){var it=app.project.item(i);if(it.id===" + str(seq_id) + ")return it.parentFolder.id===" + str(folder_id) + ";}return false;})()")

    # folder_id omitted -> move back to root
    p = payload(send("moveItemsToFolder", {"itemIds": [seq_id]}))
    record("moveItemsToFolder(omitted -> root)", p.get("moved") == [seq_id], json.dumps(p))
    at_root = es("var it=(function(){for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i).id===" + str(seq_id) + ")return app.project.item(i);}return null;})(); return it.parentFolder === app.project.rootFolder;")
    record("moveItemsToFolder item at root", at_root is True, "at_root=%r" % at_root)
    # unknown id lands in failed[]
    p = payload(send("moveItemsToFolder", {"itemIds": [999999], "folderId": folder_id}))
    record("moveItemsToFolder(unknown id -> failed[])", p.get("failed") == [999999], json.dumps(p))

    # ---- 6. saveProjectAs --------------------------------------------
    if os.path.exists(AEP_PATH):
        os.remove(AEP_PATH)
    p = payload(send("saveProjectAs", {"path": AEP_PATH}))
    record("saveProjectAs", p.get("success") is True and os.path.exists(AEP_PATH), json.dumps(p))
    info = payload(send("getProjectInfo"))
    record("saveProjectAs -> project not dirty", info.get("dirty") is False, "dirty=%r" % info.get("dirty"))

    # ---- 7. saveProject ----------------------------------------------
    es("app.project.items.addFolder('MCP_Dirty_Marker'); return true;")  # make dirty
    p = payload(send("saveProject"))
    record("saveProject", p.get("success") is True, json.dumps(p))
    info = payload(send("getProjectInfo"))
    record("saveProject -> clean", info.get("dirty") is False, "dirty=%r" % info.get("dirty"))

    # ---- 8. openProject (incl. dirty guard) --------------------------
    es("app.project.items.addFolder('MCP_Dirty_2'); return true;")  # dirty again
    p = payload(send("openProject", {"path": AEP_PATH}))
    record("openProject(dirty, no force -> error)", "error" in p, json.dumps(p))
    p = payload(send("openProject", {"path": AEP_PATH, "force": True}))
    record("openProject(force)", p.get("success") is True, json.dumps(p))
    p = payload(send("openProject", {"path": AEP_PATH + ".nope"}))
    record("openProject(missing file -> error)", "error" in p, json.dumps(p))

    # ---- 9. createProject dirty guard --------------------------------
    es("app.project.items.addFolder('MCP_Dirty_3'); return true;")  # dirty
    p = payload(send("createProject"))
    record("createProject(dirty, no force -> error)", "error" in p, json.dumps(p))
    p = payload(send("createProject", {"force": True}))
    record("createProject(force)", p.get("success") is True, json.dumps(p))
    info = payload(send("getProjectInfo"))
    record("createProject -> empty untitled", info.get("numItems") == 0 and info.get("path") is None,
           json.dumps({k: info.get(k) for k in ("name", "path", "numItems")}))
    # clean project: createProject without force must also succeed
    p = payload(send("createProject"))
    record("createProject(clean, no force)", p.get("success") is True, json.dumps(p))

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
