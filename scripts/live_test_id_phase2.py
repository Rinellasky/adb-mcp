"""
Live verification driver for InDesign MCP Phase 2 (66 tools total).

Run stage-by-stage from the mcp directory:
    uv run python ../scripts/live_test_id_phase2.py --stage styles
Stages: styles, grep, tables, typo, visual

Requires: proxy on :3001, InDesign running, adb-mcp-main uxp/id plugin
loaded (RELOADED after the Phase 2 code landed) and connected.
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
STATE_FILE = os.path.join(tempfile.gettempdir(), "id_live_test2_state.json")


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
        if len(d) > 350:
            d = d[:350] + "..."
        print(f"  [{mark}] {label}: {d}")


# ---------------------------------------------------------------- stages

def stage_styles(state):
    doc = send("createDocument", {
        "intent": "PRINT_INTENT", "pageWidth": 612, "pageHeight": 792,
        "margins": {"top": 36, "bottom": 36, "left": 36, "right": 36},
        "columns": {"count": 1, "gutter": 12},
        "pagesPerDocument": 3, "facingPages": False,
    }, "createDocument(3pp)")

    send("createSwatch", {"name": "Ink", "colorSpace": "CMYK",
                          "colorValue": [80, 60, 0, 70]}, "swatch Ink")

    send("createParagraphStyle", {
        "name": "Body", "fontFamily": "Arial", "fontStyle": "Regular",
        "pointSize": 11, "leading": 14, "alignment": "LEFT",
        "spaceAfter": 6, "hyphenation": True,
    }, "createParagraphStyle Body")
    send("createParagraphStyle", {
        "name": "Headline", "fontFamily": "Arial", "fontStyle": "Bold",
        "pointSize": 28, "leading": 30, "alignment": "LEFT",
        "spaceAfter": 12, "fillSwatch": "Ink", "nextStyle": "Body",
    }, "createParagraphStyle Headline")
    send("createCharacterStyle", {
        "name": "Emphasis", "fontStyle": "Bold Italic", "fillSwatch": "Ink",
    }, "createCharacterStyle Emphasis")
    send("createObjectStyle", {
        "name": "Card", "fillSwatch": "Ink", "strokeWeight": 0,
    }, "createObjectStyle Card")

    body_text = ("Styled body paragraph one with enough words to wrap and "
                 "hyphenate across lines nicely.\r"
                 "Second paragraph mentions vital data worth emphasizing.\r"
                 "Third paragraph closes the section.")
    f = send("createTextFrame", {
        "pageNumber": 1,
        "bounds": {"top": 40, "left": 40, "bottom": 90, "right": 570},
        "contents": "Styles Engine Live",
    }, "headline frame")
    b = send("createTextFrame", {
        "pageNumber": 1,
        "bounds": {"top": 100, "left": 40, "bottom": 320, "right": 570},
        "contents": body_text,
    }, "body frame")
    if f:
        state["headStoryId"] = f["storyId"]
        send("applyParagraphStyle", {"styleName": "Headline",
                                     "storyId": f["storyId"]},
             "applyParagraphStyle Headline")
    if b:
        state["bodyStoryId"] = b["storyId"]
        state["bodyFrameId"] = b["frameId"]
        send("applyParagraphStyle", {"styleName": "Body",
                                     "storyId": b["storyId"]},
             "applyParagraphStyle Body")
        send("applyCharacterStyle", {"styleName": "Emphasis",
                                     "storyId": b["storyId"],
                                     "startCharacter": 0,
                                     "endCharacter": 5},
             "applyCharacterStyle chars 0-5")

    rect = send("createShape", {
        "pageNumber": 1, "shapeType": "RECTANGLE",
        "bounds": {"top": 340, "left": 40, "bottom": 420, "right": 200},
    }, "shape for object style")
    if rect:
        state["cardId"] = rect["itemId"]
        send("applyObjectStyle", {"styleName": "Card",
                                  "itemId": rect["itemId"]},
             "applyObjectStyle Card")

    ls = send("listStyles", {}, "listStyles")
    if ls:
        print("paragraph styles:", [s["name"] for s in ls["paragraph"]])

    send("editStyleProperty", {"styleType": "paragraph",
                               "styleName": "Body", "property": "leading",
                               "value": 14.5}, "editStyleProperty leading")
    send("createStyleGroup", {"styleType": "paragraph", "name": "Editorial",
                              "styleNames": ["Body", "Headline"]},
         "createStyleGroup + move")
    # style inside a group must still be findable
    send("editStyleProperty", {"styleType": "paragraph",
                               "styleName": "Body", "property": "spaceAfter",
                               "value": 7}, "edit style inside group")
    send("createParagraphStyle", {"name": "Doomed", "pointSize": 9},
         "createParagraphStyle Doomed")
    send("deleteStyle", {"styleType": "paragraph", "styleName": "Doomed",
                         "replacementStyleName": "Body"},
         "deleteStyle w/ replacement")


def stage_grep(state):
    text = ("Report 2020-2024 shows growth.  Double space one.  Double two. "
            "Contact 555-0100 or 555-0199. Homo sapiens and Felis catus are "
            "species names. price: 25 USD and price: 100 USD end.")
    f = send("createTextFrame", {
        "pageNumber": 2,
        "bounds": {"top": 40, "left": 40, "bottom": 300, "right": 570},
        "contents": text,
    }, "grep test frame")
    if not f:
        return
    sid = f["storyId"]
    state["grepStoryId"] = sid

    r = send("findText", {"findWhat": "price:", "storyId": sid}, "findText")
    if r:
        print("findText count (expect 2):", r["count"])
    send("changeText", {"findWhat": "price:", "changeTo": "Price:",
                        "storyId": sid}, "changeText")

    r = send("findGrep", {"findWhat": r"\d{3}-\d{4}", "storyId": sid},
             "findGrep phones")
    if r:
        print("findGrep phone count (expect 2):", r["count"])

    r = send("findChangeReport", {
        "patterns": [r"\d{4}-\d{4}", r"  +", r"\d+ USD"],
        "storyId": sid}, "findChangeReport")
    if r:
        print("report:", r["report"])

    send("changeGrep", {"findWhat": r"(\d{4})-(\d{4})",
                        "changeTo": "$1–$2", "storyId": sid},
         "changeGrep en-dash backrefs")
    send("changeGrep", {"findWhat": r"  +", "changeTo": " ",
                        "storyId": sid}, "changeGrep double spaces")
    send("grepApplyStyle", {
        "findWhat": r"[A-Z][a-z]+ [a-z]+us\b",
        "characterStyle": "Emphasis", "storyId": sid},
        "grepApplyStyle binomials")

    r = send("getStoryContents", {"storyId": sid}, "verify grep results")
    if r:
        print("story after grep:", r["contents"][:160])


def stage_tables(state):
    m = send("createMasterSpread", {
        "namePrefix": "B", "baseName": "Body",
        "placeholders": [
            {"pageIndex": 0, "type": "PAGE_NUMBER",
             "bounds": {"top": 750, "left": 40, "bottom": 770, "right": 120}},
            {"pageIndex": 0, "type": "TEXT", "contents": "RUNNING HEADER",
             "bounds": {"top": 20, "left": 40, "bottom": 36, "right": 300}},
        ],
    }, "createMasterSpread B-Body")
    if m:
        state["masterItems"] = [p["itemId"] for p in m["placeholders"]]
        send("applyMaster", {"masterName": "B-Body", "startPage": 2,
                             "endPage": 3}, "applyMaster 2-3")
        send("overrideMasterItem", {"itemId": m["placeholders"][1]["itemId"],
                                    "pageNumber": 3}, "overrideMasterItem")

    t = send("createTable", {
        "pageNumber": 3,
        "bounds": {"top": 60, "left": 40, "bottom": 360, "right": 570},
        "data": [["Item", "Qty", "Price"],
                 ["Ink cartridge", "2", "25 USD"],
                 ["Paper ream", "10", "60 USD"],
                 ["Stapler", "1", "12 USD"]],
        "headerRows": 1,
        "columnWidths": [260, 100, 170],
    }, "createTable 4x3 + header")
    if not t:
        return
    state["tableStoryId"] = t["storyId"]
    state["tableIndex"] = t["tableIndex"]
    sid, tix = t["storyId"], t["tableIndex"]

    send("setCellContents", {"storyId": sid, "tableIndex": tix,
                             "cells": [{"row": 1, "column": 2,
                                        "contents": "27 USD"}]},
         "setCellContents")
    send("addTableRowsColumns", {"storyId": sid, "tableIndex": tix,
                                 "addRows": 1}, "addTableRowsColumns")
    send("setCellContents", {"storyId": sid, "tableIndex": tix,
                             "cells": [{"row": 4, "column": 0,
                                        "contents": "TOTAL"},
                                       {"row": 4, "column": 2,
                                        "contents": "99 USD"}]},
         "fill new row")
    send("mergeCells", {"storyId": sid, "tableIndex": tix,
                        "startRow": 4, "startColumn": 0,
                        "endRow": 4, "endColumn": 1}, "mergeCells")
    send("createCellStyle", {"name": "HeaderCell", "fillSwatch": "Ink",
                             "properties": {"topInset": 4, "bottomInset": 4}},
         "createCellStyle")
    send("createTableStyle", {"name": "CleanTable"}, "createTableStyle")
    send("applyTableStyle", {
        "storyId": sid, "tableIndex": tix,
        "tableStyleName": "CleanTable", "cellStyleName": "HeaderCell",
        "region": "HEADER",
        "alternatingFills": {"swatch": "Ink", "tint": 12, "frequency": 2},
    }, "applyTableStyle + fills")


def stage_typo(state):
    send("setBaselineGrid", {"start": 36, "increment": 14.5, "shown": True},
         "setBaselineGrid")
    if state.get("bodyStoryId"):
        send("setAlignToBaseline", {"storyId": state["bodyStoryId"],
                                    "align": True}, "setAlignToBaseline")
        send("setDropCap", {"storyId": state["bodyStoryId"],
                            "startParagraph": 0, "endParagraph": 0,
                            "lines": 3, "characters": 1,
                            "characterStyle": "Emphasis"}, "setDropCap")
        send("setHyphenationJustification", {
            "storyId": state["bodyStoryId"], "hyphenation": True,
            "hyphenateWordsLongerThan": 6, "hyphenLadderLimit": 2,
            "singleWordJustification": "LEFT",
        }, "setHyphenationJustification")
        send("insertSpecialCharacter", {"storyId": state["bodyStoryId"],
                                        "character": "EM_DASH",
                                        "position": "end"},
             "insertSpecialCharacter EM_DASH")
        send("setBulletsNumbering", {"storyId": state["bodyStoryId"],
                                     "startParagraph": 1, "endParagraph": 2,
                                     "listType": "BULLETS",
                                     "leftIndent": 18,
                                     "firstLineIndent": -18},
             "setBulletsNumbering")
        anchored = send("createAnchoredObject", {
            "storyId": state["bodyStoryId"], "characterIndex": 40,
            "type": "RECTANGLE", "width": 40, "height": 20,
            "position": "INLINE",
        }, "createAnchoredObject")
    if state.get("cardId"):
        send("setTextWrap", {"itemId": state["cardId"],
                             "mode": "BOUNDING_BOX", "offsets": 8},
             "setTextWrap")


def stage_visual(state):
    for page in (1, 2, 3):
        png = os.path.join(tempfile.gettempdir(), f"id_p2_page{page}.png")
        r = send("getPageImage", {"pageNumber": page, "resolution": 96,
                                  "filePath": png}, f"getPageImage p{page}")
        if r and os.path.exists(r["filePath"]):
            print(f"PAGE_IMAGE_OK {page}: {r['filePath']}")


STAGES = {
    "styles": stage_styles,
    "grep": stage_grep,
    "tables": stage_tables,
    "typo": stage_typo,
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
