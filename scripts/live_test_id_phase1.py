"""
Live verification driver for InDesign MCP Phase 1 (32 tools).

Run stage-by-stage from the repo root:
    uv run --directory mcp python ../scripts/live_test_id_phase1.py --stage smoke
Stages: smoke, build, text2, image, export

Requires: proxy on :3001, InDesign running, adb-mcp-main uxp/id plugin
loaded via UXP Developer Tools and connected.
"""

import argparse
import json
import os
import sys
import tempfile
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MCP_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "mcp"))
sys.path.insert(0, MCP_DIR)

import socket_client  # noqa: E402

socket_client.configure(app="indesign", url="http://localhost:3001", timeout=20)

RESULTS = []
STATE_FILE = os.path.join(tempfile.gettempdir(), "id_live_test_state.json")


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def send(action, options, label=None):
    label = label or action
    cmd = {"application": "indesign", "action": action, "options": options}
    try:
        r = socket_client.send_message_blocking(cmd)
        ok = r.get("status") == "SUCCESS"
        detail = r.get("response") if ok else r.get("message")
        RESULTS.append((label, ok, detail))
        return detail if ok else None
    except Exception as e:
        RESULTS.append((label, False, f"EXC: {e}"))
        return None


def report():
    print("\n" + "=" * 60)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"RESULTS: {passed}/{len(RESULTS)} passed")
    for label, ok, detail in RESULTS:
        mark = "PASS" if ok else "FAIL"
        d = json.dumps(detail, default=str)
        if len(d) > 400:
            d = d[:400] + "..."
        print(f"  [{mark}] {label}: {d}")


# ---------------------------------------------------------------- stages

def stage_smoke(state):
    send("getActiveDocumentSettings", {}, "health-check")
    doc = send("createDocument", {
        "intent": "PRINT_INTENT",
        "pageWidth": 612, "pageHeight": 792,
        "margins": {"top": 36, "bottom": 36, "left": 36, "right": 36},
        "columns": {"count": 1, "gutter": 12},
        "pagesPerDocument": 2,
        "facingPages": False,
    }, "createDocument(PRINT, letter, 2pp)")
    info = send("getDocumentInfo", {}, "getDocumentInfo")
    if info:
        state["docName"] = info["name"]
        print(f"Doc: {info['name']}, pages={info['pageCount']}, "
              f"styles={len(info['paragraphStyles'])}, swatches={len(info['swatches'])}")


def stage_build(state):
    send("createSwatch", {"name": "Brand Red", "colorSpace": "CMYK",
                          "colorValue": [0, 95, 90, 0]}, "createSwatch CMYK")
    send("createSwatch", {"name": "Accent Blue", "colorSpace": "RGB",
                          "colorValue": [40, 90, 220]}, "createSwatch RGB")
    send("createLayer", {"name": "Artwork", "color": "TEAL"}, "createLayer")
    send("setLayerProperties", {"layerName": "Artwork", "locked": False,
                                "visible": True}, "setLayerProperties")

    # headline frame
    head = send("createTextFrame", {
        "pageNumber": 1,
        "bounds": {"top": 40, "left": 40, "bottom": 100, "right": 570},
        "contents": "Phase 1 Live Test",
    }, "createTextFrame headline")
    if head:
        state["headFrameId"] = head["frameId"]
        state["headStoryId"] = head["storyId"]

    # deliberately small frame -> overset expected
    body = send("createTextFrame", {
        "pageNumber": 1,
        "bounds": {"top": 120, "left": 40, "bottom": 200, "right": 300},
        "contents": ("This body text is deliberately long so it cannot fit in a "
                     "small frame. " * 12),
    }, "createTextFrame body (expect overset)")
    if body:
        state["bodyFrameId"] = body["frameId"]
        state["bodyStoryId"] = body["storyId"]
        print(f"body overflows (expect True): {body['overflows']}")

    if state.get("headStoryId"):
        send("styleTextRange", {
            "storyId": state["headStoryId"], "rangeType": "story",
            "pointSize": 36, "alignment": "CENTER", "fontStyle": "Bold",
        }, "styleTextRange headline")
        send("setTextColor", {"storyId": state["headStoryId"],
                              "swatchName": "Brand Red"}, "setTextColor")

    rect = send("createShape", {
        "pageNumber": 1, "shapeType": "RECTANGLE",
        "bounds": {"top": 620, "left": 40, "bottom": 700, "right": 200},
        "fillSwatch": "Brand Red", "cornerOption": "ROUNDED", "cornerRadius": 8,
    }, "createShape rect")
    oval = send("createShape", {
        "pageNumber": 1, "shapeType": "OVAL",
        "bounds": {"top": 620, "left": 220, "bottom": 700, "right": 300},
        "fillSwatch": "Accent Blue",
    }, "createShape oval")
    if rect:
        state["rectId"] = rect["itemId"]
        send("setItemAppearance", {"itemId": rect["itemId"],
                                   "strokeSwatch": "Accent Blue",
                                   "strokeWeight": 2, "opacity": 80},
             "setItemAppearance")
        send("transformItem", {"itemId": rect["itemId"],
                               "moveBy": {"x": 10, "y": -10},
                               "rotation": 15}, "transformItem")
        dup = send("duplicateItem", {"itemId": rect["itemId"],
                                     "offset": {"x": 180, "y": 0}},
                   "duplicateItem")
        if dup and oval:
            grp = send("groupItems",
                       {"itemIds": [dup["id"], oval["itemId"]]}, "groupItems")
            if grp:
                send("groupItems", {"ungroupItemId": grp["id"]}, "ungroupItems")

    send("addGuide", {"pageNumber": 1, "orientation": "HORIZONTAL",
                      "location": 396}, "addGuide")
    send("addPages", {"count": 2}, "addPages(+2)")
    send("duplicatePage", {"pageNumber": 1}, "duplicatePage(1)")
    send("removePage", {"pageNumber": 5}, "removePage(5)")
    send("setPageNumbering", {"pageNumber": 3, "startAt": 10,
                              "style": "LOWER_ROMAN"}, "setPageNumbering")


def stage_text2(state):
    # empty frame on page 2 to catch the overset body text
    cont = send("createTextFrame", {
        "pageNumber": 2,
        "bounds": {"top": 40, "left": 40, "bottom": 400, "right": 570},
        "contents": "",
    }, "createTextFrame continuation")
    if cont and state.get("bodyFrameId"):
        thread = send("threadTextFrames", {
            "fromFrameId": state["bodyFrameId"],
            "toFrameId": cont["frameId"],
        }, "threadTextFrames")
        if thread:
            print(f"after threading, story overflows (expect False): "
                  f"{thread['overflows']}")

    if state.get("bodyStoryId"):
        send("insertText", {"storyId": state["bodyStoryId"],
                            "text": "\rAppended paragraph via insertText.",
                            "position": "end"}, "insertText")
        send("getStoryContents", {"storyId": state["bodyStoryId"]},
             "getStoryContents")
        send("styleTextRange", {
            "storyId": state["bodyStoryId"], "rangeType": "paragraphs",
            "start": 0, "end": 0, "pointSize": 14, "spaceAfter": 6,
        }, "styleTextRange paragraph 0")

    if state.get("bodyFrameId"):
        send("setTextFrameOptions", {"frameId": state["bodyFrameId"],
                                     "columnCount": 2, "columnGutter": 12,
                                     "insetSpacing": 4,
                                     "verticalJustification": "TOP"},
             "setTextFrameOptions")


def stage_image(state):
    # generate a test image
    img_path = os.path.join(tempfile.gettempdir(), "id_test_image.png")
    try:
        from PIL import Image as PILImage
        im = PILImage.new("RGB", (400, 300))
        px = im.load()
        for y in range(300):
            for x in range(400):
                px[x, y] = (int(255 * x / 400), int(255 * y / 300), 128)
        im.save(img_path)
    except ImportError:
        img_path = None

    if img_path:
        send("placeImage", {
            "filePath": img_path, "pageNumber": 1,
            "bounds": {"top": 420, "left": 40, "bottom": 580, "right": 280},
            "fitOption": "FILL_PROPORTIONALLY",
        }, "placeImage")

    png_out = os.path.join(tempfile.gettempdir(),
                           f"id_page1_{int(time.time())}.png")
    r = send("getPageImage", {"pageNumber": 1, "resolution": 72,
                              "filePath": png_out}, "getPageImage")
    if r and os.path.exists(r["filePath"]):
        print(f"PAGE_IMAGE: {r['filePath']} "
              f"({os.path.getsize(r['filePath'])} bytes)")
        state["pageImage"] = r["filePath"]


def stage_export(state):
    pdf_path = os.path.join(tempfile.gettempdir(), "id_live_test.pdf")
    send("exportPdf", {"filePath": pdf_path, "presetName": None,
                       "pageRange": "1-2"}, "exportPdf")
    if os.path.exists(pdf_path):
        print(f"PDF: {pdf_path} ({os.path.getsize(pdf_path)} bytes)")

    indd_path = os.path.join(tempfile.gettempdir(), "id_live_test.indd")
    send("saveDocumentAs", {"filePath": indd_path}, "saveDocumentAs")
    send("saveDocument", {}, "saveDocument")


STAGES = {
    "smoke": stage_smoke,
    "build": stage_build,
    "text2": stage_text2,
    "image": stage_image,
    "export": stage_export,
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=STAGES.keys())
    args = ap.parse_args()

    state = load_state()
    STAGES[args.stage](state)
    save_state(state)
    report()
