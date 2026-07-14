"""
Live verification driver for InDesign MCP Phase 3 (99 tools total).

Run stage-by-stage from the mcp directory:
    uv run python ../scripts/live_test_id_phase3.py --stage longdoc
Stages: longdoc, templates, exportpf, orchestrate, visual

Requires: proxy on :3001, InDesign running, adb-mcp-main uxp/id plugin
RELOADED after the Phase 3 code landed, and connected.
"""

import argparse
import json
import os
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MCP_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "mcp"))
sys.path.insert(0, MCP_DIR)

import socket_client  # noqa: E402

socket_client.configure(app="indesign", url="http://localhost:3001", timeout=20)

RESULTS = []
STATE_FILE = os.path.join(tempfile.gettempdir(), "id_live_test3_state.json")
OUT_DIR = os.path.join(tempfile.gettempdir(), "id_phase3")
os.makedirs(OUT_DIR, exist_ok=True)


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
        if len(d) > 300:
            d = d[:300] + "..."
        print(f"  [{mark}] {label}: {d}")


# ---------------------------------------------------------------- stages

def stage_longdoc(state):
    send("createDocument", {
        "intent": "PRINT_INTENT", "pageWidth": 612, "pageHeight": 792,
        "margins": {"top": 48, "bottom": 48, "left": 48, "right": 48},
        "columns": {"count": 1, "gutter": 12},
        "pagesPerDocument": 4, "facingPages": False,
    }, "createDocument(4pp)")

    send("createParagraphStyle", {
        "name": "H1", "fontFamily": "Arial", "fontStyle": "Bold",
        "pointSize": 24, "leading": 28, "spaceAfter": 10,
    }, "style H1")
    send("createParagraphStyle", {
        "name": "BodyText", "fontFamily": "Arial", "fontStyle": "Regular",
        "pointSize": 11, "leading": 15, "spaceAfter": 6,
    }, "style BodyText")

    # headings + body on pages 2-4 (page 1 reserved for the TOC)
    story_ids = []
    for page, head in [(2, "Getting Started"), (3, "Device Reference"),
                       (4, "Publishing")]:
        f = send("createTextFrame", {
            "pageNumber": page,
            "bounds": {"top": 60, "left": 48, "bottom": 700, "right": 564},
            "contents": (f"{head}\rBody copy for the {head.lower()} chapter. "
                         "This paragraph exists so the index and "
                         "cross-references have real text to anchor to."),
        }, f"chapter frame p{page}")
        if f:
            story_ids.append(f["storyId"])
            send("applyParagraphStyle", {"styleName": "H1",
                                         "storyId": f["storyId"],
                                         "startParagraph": 0,
                                         "endParagraph": 0},
                 f"H1 on p{page}")
            send("applyParagraphStyle", {"styleName": "BodyText",
                                         "storyId": f["storyId"],
                                         "startParagraph": 1,
                                         "endParagraph": 1},
                 f"BodyText on p{page}")
    state["chapterStories"] = story_ids

    toc = send("createToc", {
        "title": "Contents",
        "entries": [{"styleName": "H1", "level": 1}],
        "pageNumber": 1, "placePoint": {"x": 48, "y": 60},
    }, "createToc")

    send("addSection", {"pageNumber": 2, "startAt": 1, "style": "ARABIC",
                        "prefix": "A-", "includePrefix": False,
                        "marker": "Guide"}, "addSection")

    if story_ids:
        send("createHyperlink", {"url": "https://dev.epicgames.com/documentation/uefn",
                                 "storyId": story_ids[0],
                                 "startCharacter": 0, "endCharacter": 14,
                                 "name": "UEFN docs"}, "createHyperlink url")
        send("createHyperlink", {"toPageNumber": 4,
                                 "storyId": story_ids[1],
                                 "startCharacter": 0, "endCharacter": 5},
             "createHyperlink page")
        send("createBookmark", {"pageNumber": 2, "name": "Getting Started"},
             "createBookmark")
        send("createCrossReference", {
            "sourceStoryId": story_ids[0],
            "destinationStoryId": story_ids[2],
            "destinationParagraph": 0,
            "format": "Page Number",
        }, "createCrossReference")
        send("addIndexEntry", {"term": "HUD", "storyId": story_ids[1],
                               "characterIndex": 5}, "addIndexEntry HUD")
        send("addIndexEntry", {"term": "Devices", "subTerm": "vault alert",
                               "storyId": story_ids[1], "characterIndex": 10},
             "addIndexEntry sub")
        send("generateIndex", {"pageNumber": 4,
                               "placePoint": {"x": 48, "y": 500}},
             "generateIndex")

    # books are feature-detected — record the outcome either way
    send("createBook", {"filePath": os.path.join(OUT_DIR, "test_book.indb")},
         "createBook (feature-detect)")


def stage_templates(state):
    # build a small template with NAMED frames, save as .indd, reopen as copy
    send("createDocument", {
        "intent": "WEB_INTENT", "pageWidth": 800, "pageHeight": 500,
        "margins": {"top": 24, "bottom": 24, "left": 24, "right": 24},
        "columns": {"count": 1, "gutter": 12},
        "pagesPerDocument": 1, "facingPages": False,
    }, "template doc")
    send("createTextFrame", {"pageNumber": 1,
                             "bounds": {"top": 40, "left": 40, "bottom": 120,
                                        "right": 760},
                             "contents": "TITLE PLACEHOLDER",
                             "name": "title"}, "named frame title")
    send("createTextFrame", {"pageNumber": 1,
                             "bounds": {"top": 140, "left": 40, "bottom": 300,
                                        "right": 480},
                             "contents": "BODY PLACEHOLDER",
                             "name": "body"}, "named frame body")
    r = send("createShape", {"pageNumber": 1, "shapeType": "RECTANGLE",
                             "bounds": {"top": 140, "left": 500, "bottom": 300,
                                        "right": 760},
                             "name": "photo"}, "named frame photo")
    tpl_path = os.path.join(OUT_DIR, "badge_template.indd")
    send("saveDocumentAs", {"filePath": tpl_path}, "save template")
    state["templatePath"] = tpl_path

    # snippet round trip while the template is open
    if r:
        snip = os.path.join(OUT_DIR, "photo_box.idms")
        send("saveSnippet", {"itemId": r["itemId"], "filePath": snip},
             "saveSnippet")
        send("placeSnippet", {"filePath": snip, "pageNumber": 1,
                              "position": {"x": 520, "y": 320}},
             "placeSnippet")

    send("closeDocument", {"save": True}, "close template")

    send("openAsTemplate", {"filePath": tpl_path}, "openAsTemplate")

    # test image for the photo frame
    img = os.path.join(OUT_DIR, "avatar.png")
    try:
        from PIL import Image as PILImage
        im = PILImage.new("RGB", (300, 200), (150, 70, 255))
        im.save(img)
    except ImportError:
        img = None

    content = {"title": "RIN ELLA — CREATOR BADGE",
               "body": "Verse Island / BrainDead Guild\rAccess level: ALL ZONES",
               "missing_frame": "should be reported NOT_FOUND"}
    if img:
        content["photo"] = {"imagePath": img}
    pt = send("populateTemplate", {"contentMap": content}, "populateTemplate")
    if pt:
        print("populate results:", json.dumps(pt["results"]))

    # data merge (feature-detected)
    csv = os.path.join(OUT_DIR, "names.csv")
    with open(csv, "w", encoding="utf-8") as f:
        f.write("Name,Role\rAlpha,Builder\rBravo,Scripter\r")
    send("setDataMergeSource", {"filePath": csv},
         "setDataMergeSource (feature-detect)")


def stage_exportpf(state):
    # work in whatever document is active (the populated template)
    send("listExportPresets", {}, "listExportPresets")

    pdf = os.path.join(OUT_DIR, "advanced.pdf")
    send("exportPdfAdvanced", {"filePath": pdf,
                               "presetName": "[High Quality Print]",
                               "pageRange": "1"}, "exportPdfAdvanced")
    print("pdf exists:", os.path.exists(pdf))

    ipdf = os.path.join(OUT_DIR, "interactive.pdf")
    send("exportPdfAdvanced", {"filePath": ipdf, "interactive": True},
         "exportPdfAdvanced interactive")

    idml = os.path.join(OUT_DIR, "doc.idml")
    send("exportIdml", {"filePath": idml}, "exportIdml")
    print("idml exists:", os.path.exists(idml))

    send("exportPagesAsImages", {"outputFolder": OUT_DIR, "baseName": "img",
                                 "format": "JPEG", "resolution": 96,
                                 "quality": "HIGH"}, "exportPagesAsImages")

    send("runPreflight", {}, "runPreflight [Basic]")
    send("definePreflightProfile", {
        "name": "MCP Checks",
        "rules": [{"id": "ADBE_MissingFonts"}, {"id": "ADBE_OversetText"}],
    }, "definePreflightProfile")
    send("runPreflight", {"profileName": "MCP Checks"}, "runPreflight custom")

    send("saveDocumentAs", {"filePath": os.path.join(OUT_DIR, "populated.indd")},
         "save for package")
    send("packageDocument", {"outputFolder": os.path.join(OUT_DIR, "package")},
         "packageDocument")

    epub = os.path.join(OUT_DIR, "doc.epub")
    send("exportEpub", {"filePath": epub}, "exportEpub (may timeout)")


def stage_orchestrate(state):
    send("getDocuments", {}, "getDocuments")

    # shapes to orchestrate on
    ids = []
    for i in range(4):
        r = send("createShape", {
            "pageNumber": 1, "shapeType": "RECTANGLE",
            "bounds": {"top": 330 + i * 7, "left": 40 + i * 95,
                       "bottom": 380 + i * 7, "right": 110 + i * 95},
        }, f"rect {i}")
        if r:
            ids.append(r["itemId"])
    state["rects"] = ids

    if len(ids) == 4:
        send("alignItems", {"itemIds": ids, "mode": "TOP",
                            "reference": "FIRST"}, "alignItems TOP")
        send("distributeItems", {"itemIds": ids, "axis": "HORIZONTAL",
                                 "spacing": 18}, "distributeItems fixed gap")

    send("createSwatch", {"name": "Slate", "colorSpace": "RGB",
                          "colorValue": [42, 38, 74]}, "swatch Slate")

    # action-sequence steps replayed back-to-back per target (the python-side
    # sequence tools themselves are tested separately via module import)
    for item_id in (state.get("rects") or [])[:2]:
        send("setItemAppearance", {"itemId": item_id, "fillSwatch": "Slate",
                                   "cornerOption": "ROUNDED",
                                   "cornerRadius": 6}, f"seq step1 on {item_id}")
        send("transformItem", {"itemId": item_id, "rotation": 8},
             f"seq step2 on {item_id}")

    send("createCharacterStyle", {"name": "Callout", "fontFamily": "Arial",
                                  "fontStyle": "Bold"}, "style Callout")
    send("batchApplyStyle", {"grepFindWhat": r"ALL ZONES",
                             "characterStyleName": "Callout",
                             "allOpenDocuments": True}, "batchApplyStyle")


def stage_visual(state):
    png = os.path.join(OUT_DIR, "phase3_active_p1.png")
    r = send("getPageImage", {"pageNumber": 1, "resolution": 96,
                              "filePath": png}, "getPageImage active p1")
    if r:
        print("PAGE_IMAGE_OK", r["filePath"])

    docs = send("getDocuments", {}, "getDocuments final")
    if docs:
        print("open docs:", [d["name"] for d in docs["documents"]])


STAGES = {
    "longdoc": stage_longdoc,
    "templates": stage_templates,
    "exportpf": stage_exportpf,
    "orchestrate": stage_orchestrate,
    "visual": stage_visual,
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=STAGES.keys())
    args = ap.parse_args()

    state = load_state()
    STAGES[args.stage](state)
    save_state(state)
    report()
