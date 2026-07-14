"""
Demo: trendy Fortnite-inspired "season drop" promo page built end-to-end
with the InDesign MCP toolchain — Phase 1 (shapes/text), Phase 2 (styles),
Phase 3 (align/distribute + action-sequence style replay via direct ops).

Run from the mcp directory: uv run python ../scripts/demo_fortnite_drop.py
"""

import json
import os
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MCP_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "mcp"))
sys.path.insert(0, MCP_DIR)

import socket_client  # noqa: E402

socket_client.configure(app="indesign", url="http://localhost:3001", timeout=20)

FAIL = []


def send(action, options, label=None):
    label = label or action
    try:
        r = socket_client.send_message_blocking(
            {"application": "indesign", "action": action, "options": options})
        if r.get("status") == "SUCCESS":
            print("PASS", label)
            return r.get("response")
        FAIL.append(label)
        print("FAIL", label, str(r.get("message"))[:150])
        return None
    except Exception as e:
        FAIL.append(label)
        print("FAIL", label, str(e)[:150])
        return None


W, H = 1280, 720

send("createDocument", {
    "intent": "WEB_INTENT", "pageWidth": W, "pageHeight": H,
    "margins": {"top": 0, "bottom": 0, "left": 0, "right": 0},
    "columns": {"count": 1, "gutter": 12},
    "pagesPerDocument": 1, "facingPages": False,
}, "doc 1280x720")

# ---- palette: fortnite-y neon on deep violet night
for name, val in [
    ("Abyss",     [24, 10, 51]),     # deep violet-navy bg
    ("Storm",     [58, 34, 105]),    # panel violet
    ("NeonCyan",  [0, 234, 255]),
    ("NeonMagenta", [255, 44, 214]),
    ("VoltYellow", [255, 231, 26]),
    ("RareBlue",  [46, 137, 255]),
    ("EpicPurple", [177, 91, 255]),
    ("LegendOrange", [255, 150, 40]),
    ("White",     [250, 250, 255]),
]:
    send("createSwatch", {"name": name, "colorSpace": "RGB", "colorValue": val},
         f"swatch {name}")

# ---- styles
send("createParagraphStyle", {"name": "DropTitle", "fontFamily": "Arial",
                              "fontStyle": "Black", "pointSize": 72,
                              "leading": 70, "alignment": "LEFT",
                              "fillSwatch": "White",
                              "properties": {"capitalization": 1396855150}},
     "style DropTitle (try Black)")
# Arial Black fallback if "Black" face missing
send("createParagraphStyle", {"name": "DropTitle", "fontFamily": "Arial",
                              "fontStyle": "Bold", "pointSize": 72,
                              "leading": 70, "alignment": "LEFT",
                              "fillSwatch": "White"}, "style DropTitle")
send("createParagraphStyle", {"name": "Kicker", "fontFamily": "Arial",
                              "fontStyle": "Bold", "pointSize": 18,
                              "leading": 22, "alignment": "LEFT",
                              "fillSwatch": "VoltYellow",
                              "properties": {"tracking": 220}}, "style Kicker")
send("createParagraphStyle", {"name": "CardName", "fontFamily": "Arial",
                              "fontStyle": "Bold", "pointSize": 20,
                              "leading": 24, "alignment": "CENTER",
                              "fillSwatch": "White"}, "style CardName")
send("createParagraphStyle", {"name": "CardTag", "fontFamily": "Arial",
                              "fontStyle": "Bold", "pointSize": 12,
                              "leading": 14, "alignment": "CENTER",
                              "fillSwatch": "White",
                              "properties": {"tracking": 160}}, "style CardTag")

# ---- background + diagonal energy slashes
send("createShape", {"pageNumber": 1, "shapeType": "RECTANGLE",
                     "bounds": {"top": 0, "left": 0, "bottom": H, "right": W},
                     "fillSwatch": "Abyss"}, "bg")

for i, (sw, x, w, rot, op) in enumerate([
    ("NeonMagenta", 690, 260, 18, 30),
    ("NeonCyan", 860, 320, 18, 26),
    ("EpicPurple", 1040, 380, 18, 22),
]):
    send("createShape", {"pageNumber": 1, "shapeType": "RECTANGLE",
                         "bounds": {"top": -140, "left": x,
                                    "bottom": H + 140, "right": x + w},
                         "fillSwatch": sw, "opacity": op}, f"slash {i}")
    # rotate into diagonals
for i, item in enumerate([]):
    pass

# rotate the slashes: fetch ids via getDocumentInfo is heavy — rotate at
# creation isn't supported, so track ids ourselves
info = send("getDocumentInfo", {}, "read back items")
slash_ids = []
if info:
    for it in info["pages"][0]["items"]:
        b = it["bounds"]
        if b["bottom"] - b["top"] > H + 200:  # the tall slashes
            slash_ids.append(it["id"])
for sid in slash_ids:
    send("transformItem", {"itemId": sid, "rotation": 18}, f"rotate slash {sid}")

# ---- kicker + title + subline
send("createTextFrame", {"pageNumber": 1,
                         "bounds": {"top": 78, "left": 72, "bottom": 108,
                                    "right": 700},
                         "contents": "VERSE ISLAND  //  SEASON 9  //  NEW DROP"},
     "kicker frame")
send("createTextFrame", {"pageNumber": 1,
                         "bounds": {"top": 112, "left": 68, "bottom": 268,
                                    "right": 900},
                         "contents": "EMBER\rWATCH"}, "title frame")
send("createTextFrame", {"pageNumber": 1,
                         "bounds": {"top": 272, "left": 72, "bottom": 310,
                                    "right": 800},
                         "contents": "Limited-time HUD skins land Friday. Squad up."},
     "subline frame")

info = send("getDocumentInfo", {}, "read back text")
frames = {}
if info:
    for it in info["pages"][0]["items"]:
        if it["type"] == "TextFrame" and it.get("contentsPreview"):
            frames[it["contentsPreview"][:12]] = it
kicker = frames.get("VERSE ISLAND")
title = frames.get("EMBER\rWATCH") or frames.get("EMBER")
sub = frames.get("Limited-time")
if kicker:
    send("applyParagraphStyle", {"styleName": "Kicker",
                                 "storyId": kicker["storyId"]}, "style kicker")
if title:
    send("applyParagraphStyle", {"styleName": "DropTitle",
                                 "storyId": title["storyId"]}, "style title")
    send("setTextColor", {"storyId": title["storyId"],
                          "swatchName": "NeonCyan", "rangeType": "paragraphs",
                          "start": 1, "end": 1}, "title line2 cyan")
if sub:
    send("applyParagraphStyle", {"styleName": "CardTag",
                                 "storyId": sub["storyId"]}, "style subline")
    send("styleTextRange", {"storyId": sub["storyId"], "alignment": "LEFT",
                            "pointSize": 14}, "subline tweaks")

# ---- volt underline bar
send("createShape", {"pageNumber": 1, "shapeType": "RECTANGLE",
                     "bounds": {"top": 322, "left": 72, "bottom": 330,
                                "right": 470},
                     "fillSwatch": "VoltYellow"}, "volt bar")

# ---- rarity cards (built rough, then aligned + distributed by tools)
cards = [
    ("SPARK TRAIL", "RARE", "RareBlue", 800),
    ("EMBER WATCH", "EPIC", "EpicPurple", 900),
    ("VAULT BREAKER", "LEGENDARY", "LegendOrange", 1000),
]
card_ids = []
for i, (nm, tier, sw, vb) in enumerate(cards):
    left = 90 + i * 385 + (i * 13)  # deliberately sloppy: tools will fix
    top = 392 + i * 9
    body = send("createShape", {
        "pageNumber": 1, "shapeType": "RECTANGLE",
        "bounds": {"top": top, "left": left, "bottom": top + 250,
                   "right": left + 340},
        "fillSwatch": "Storm", "strokeSwatch": sw, "strokeWeight": 3,
        "cornerOption": "ROUNDED", "cornerRadius": 14,
        "name": f"card_{i}",
    }, f"card {tier}")
    if body:
        card_ids.append(body["itemId"])
    # rarity ribbon
    send("createShape", {"pageNumber": 1, "shapeType": "RECTANGLE",
                         "bounds": {"top": top + 250 - 58, "left": left + 14,
                                    "bottom": top + 250 - 34,
                                    "right": left + 340 - 14},
                         "fillSwatch": sw, "opacity": 90,
                         "cornerOption": "ROUNDED", "cornerRadius": 8,
                         "name": f"ribbon_{i}"}, f"ribbon {tier}")
    nf = send("createTextFrame", {"pageNumber": 1,
                                  "bounds": {"top": top + 156,
                                             "left": left + 14,
                                             "bottom": top + 188,
                                             "right": left + 326},
                                  "contents": nm, "name": f"name_{i}"},
              f"name {nm}")
    tf = send("createTextFrame", {"pageNumber": 1,
                                  "bounds": {"top": top + 250 - 55,
                                             "left": left + 14,
                                             "bottom": top + 250 - 36,
                                             "right": left + 326},
                                  "contents": f"{tier}  •  {vb} V-BUCKS",
                                  "name": f"tag_{i}"}, f"tag {tier}")
    if nf:
        send("applyParagraphStyle", {"styleName": "CardName",
                                     "storyId": nf["storyId"]}, f"style name {i}")
    if tf:
        send("applyParagraphStyle", {"styleName": "CardTag",
                                     "storyId": tf["storyId"]}, f"style tag {i}")

# fix the sloppy card bodies with phase 3 geometry
if len(card_ids) == 3:
    send("alignItems", {"itemIds": card_ids, "mode": "TOP",
                        "reference": "FIRST"}, "align cards")
    send("distributeItems", {"itemIds": card_ids, "axis": "HORIZONTAL",
                             "spacing": 40}, "distribute cards")

# NOTE: card decorations were placed per-card with correct offsets relative
# to final positions only for card 0; realign decorations to their cards
info = send("getDocumentInfo", {}, "read back cards")
if info:
    items = {i["name"]: i for i in info["pages"][0]["items"] if i.get("name")}
    for i in range(3):
        card = items.get(f"card_{i}")
        if not card:
            continue
        cb = card["bounds"]
        fixes = [
            (f"ribbon_{i}", {"top": cb["bottom"] - 58, "left": cb["left"] + 14,
                             "bottom": cb["bottom"] - 34,
                             "right": cb["right"] - 14}),
            (f"name_{i}", {"top": cb["top"] + 156, "left": cb["left"] + 14,
                           "bottom": cb["top"] + 188, "right": cb["right"] - 14}),
            (f"tag_{i}", {"top": cb["bottom"] - 55, "left": cb["left"] + 14,
                          "bottom": cb["bottom"] - 36, "right": cb["right"] - 14}),
        ]
        for name, b in fixes:
            it = items.get(name)
            if it:
                send("transformItem", {"itemId": it["id"],
                                       "moveTo": {"x": b["left"], "y": b["top"]}},
                     f"reseat {name}")

# ---- CTA chip bottom-left
send("createShape", {"pageNumber": 1, "shapeType": "RECTANGLE",
                     "bounds": {"top": 664 - 44, "left": 72, "bottom": 664,
                                "right": 330},
                     "fillSwatch": "NeonMagenta", "cornerOption": "ROUNDED",
                     "cornerRadius": 22}, "cta chip")
cta = send("createTextFrame", {"pageNumber": 1,
                               "bounds": {"top": 664 - 36, "left": 72,
                                          "bottom": 664 - 8, "right": 330},
                               "contents": "PLAY 9-4407-1440"}, "cta text")
if cta:
    send("applyParagraphStyle", {"styleName": "CardName",
                                 "storyId": cta["storyId"]}, "style cta")
    send("styleTextRange", {"storyId": cta["storyId"], "pointSize": 16},
         "cta size")

# ---- export
out = os.path.join(tempfile.gettempdir(), "fortnite_drop.png")
send("getPageImage", {"pageNumber": 1, "resolution": 96, "filePath": out},
     "export page image")
send("saveDocumentAs",
     {"filePath": r"C:\AppDev\ClaudeMCP\adb-mcp-main\test-outputs\fortnite_drop.indd"},
     "save indd")

print("\nFAILED:", len(FAIL), FAIL)
