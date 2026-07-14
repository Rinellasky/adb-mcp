"""
Demo: build a UEFN UI design-spec document end-to-end with the InDesign MCP
toolchain (Phases 1+2). 1280x720 landscape, 3 pages:
  1 - cover: title, palette chips, type styles
  2 - HUD mockup: minimap, storm timer, shield/health, hotbar, alert banner
  3 - element spec table on a master-driven page

Run from the mcp directory: uv run python ../scripts/demo_uefn_ui.py
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

FAILURES = []


def send(action, options, label=None):
    label = label or action
    cmd = {"application": "indesign", "action": action, "options": options}
    try:
        r = socket_client.send_message_blocking(cmd)
        if r.get("status") == "SUCCESS":
            print("PASS", label)
            return r.get("response")
        FAILURES.append((label, r.get("message")))
        print("FAIL", label, str(r.get("message"))[:200])
        return None
    except Exception as e:
        FAILURES.append((label, str(e)))
        print("FAIL", label, str(e)[:200])
        return None


W, H = 1280, 720

# ---------------------------------------------------------------- document

send("createDocument", {
    "intent": "WEB_INTENT", "pageWidth": W, "pageHeight": H,
    "margins": {"top": 40, "bottom": 40, "left": 48, "right": 48},
    "columns": {"count": 1, "gutter": 12},
    "pagesPerDocument": 3, "facingPages": False,
}, "createDocument 1280x720x3")

# ---------------------------------------------------------------- swatches

for name, space, val in [
    ("Night",    "RGB", [16, 12, 38]),
    ("Slate",    "RGB", [42, 38, 74]),
    ("Electric", "RGB", [0, 200, 255]),
    ("Violet",   "RGB", [150, 70, 255]),
    ("Gold",     "RGB", [255, 200, 40]),
    ("Shield",   "RGB", [70, 140, 255]),
    ("Health",   "RGB", [90, 225, 125]),
    ("Snow",     "RGB", [245, 247, 255]),
]:
    send("createSwatch", {"name": name, "colorSpace": space,
                          "colorValue": val}, f"swatch {name}")

# ---------------------------------------------------------------- styles

send("createParagraphStyle", {
    "name": "UEFN Title", "fontFamily": "Arial", "fontStyle": "Bold",
    "pointSize": 56, "leading": 58, "alignment": "LEFT",
    "fillSwatch": "Snow",
}, "style UEFN Title")
send("createParagraphStyle", {
    "name": "Section Head", "fontFamily": "Arial", "fontStyle": "Bold",
    "pointSize": 20, "leading": 24, "alignment": "LEFT",
    "fillSwatch": "Electric", "spaceAfter": 8,
}, "style Section Head")
send("createParagraphStyle", {
    "name": "Spec Body", "fontFamily": "Arial", "fontStyle": "Regular",
    "pointSize": 12, "leading": 17, "alignment": "LEFT",
    "fillSwatch": "Snow", "spaceAfter": 6,
}, "style Spec Body")
send("createParagraphStyle", {
    "name": "HUD Label", "fontFamily": "Arial", "fontStyle": "Bold",
    "pointSize": 10, "leading": 12, "alignment": "LEFT",
    "fillSwatch": "Electric",
}, "style HUD Label")
send("createParagraphStyle", {
    "name": "Chip Label", "fontFamily": "Arial", "fontStyle": "Bold",
    "pointSize": 11, "leading": 13, "alignment": "CENTER",
    "fillSwatch": "Snow",
}, "style Chip Label")
send("createStyleGroup", {"styleType": "paragraph", "name": "UEFN",
                          "styleNames": ["UEFN Title", "Section Head",
                                         "Spec Body", "HUD Label",
                                         "Chip Label"]}, "group styles")


def dark_bg(page, label):
    send("createShape", {
        "pageNumber": page, "shapeType": "RECTANGLE",
        "bounds": {"top": 0, "left": 0, "bottom": H, "right": W},
        "fillSwatch": "Night",
    }, label)


def text(page, bounds, contents, style, label, color=None):
    f = send("createTextFrame", {"pageNumber": page, "bounds": bounds,
                                 "contents": contents}, label)
    if f:
        send("applyParagraphStyle", {"styleName": style,
                                     "storyId": f["storyId"]},
             f"{label}:style")
        if f.get("overflows"):
            print("  !! overset:", label)
    return f


# ---------------------------------------------------------------- page 1

dark_bg(1, "p1 bg")
send("createShape", {  # gold accent bar
    "pageNumber": 1, "shapeType": "RECTANGLE",
    "bounds": {"top": 84, "left": 48, "bottom": 92, "right": 360},
    "fillSwatch": "Gold",
}, "p1 accent bar")
text(1, {"top": 100, "left": 48, "bottom": 230, "right": 900},
     "UEFN UI DESIGN SPEC", "UEFN Title", "p1 title")
text(1, {"top": 205, "left": 48, "bottom": 260, "right": 900},
     "Verse Island — HUD + device UI reference. Built by the InDesign MCP toolchain.",
     "Spec Body", "p1 subtitle")

# palette chips
text(1, {"top": 300, "left": 48, "bottom": 335, "right": 500},
     "PALETTE", "Section Head", "p1 palette head")
chips = ["Night", "Slate", "Electric", "Violet", "Gold", "Shield", "Health", "Snow"]
x = 48
for name in chips:
    send("createShape", {
        "pageNumber": 1, "shapeType": "RECTANGLE",
        "bounds": {"top": 350, "left": x, "bottom": 460, "right": x + 118},
        "fillSwatch": name, "strokeSwatch": "Snow", "strokeWeight": 1,
        "cornerOption": "ROUNDED", "cornerRadius": 10,
    }, f"chip {name}")
    text(1, {"top": 468, "left": x, "bottom": 492, "right": x + 118},
         name, "Chip Label", f"chip label {name}")
    x += 148

# type specimen
text(1, {"top": 540, "left": 48, "bottom": 575, "right": 500},
     "TYPE STYLES", "Section Head", "p1 type head")
text(1, {"top": 580, "left": 48, "bottom": 680, "right": 1100},
     "UEFN Title 56/58 Bold\rSection Head 20/24 Bold — Electric\r"
     "Spec Body 12/17 Regular — Snow\rHUD Label 10/12 Bold — Electric",
     "Spec Body", "p1 specimen")

# ---------------------------------------------------------------- page 2

dark_bg(2, "p2 bg")
text(2, {"top": 20, "left": 48, "bottom": 50, "right": 700},
     "HUD LAYOUT — 1920x1080 SAFE FRAME @ 2/3", "Section Head", "p2 head")

# minimap (top-right)
send("createShape", {
    "pageNumber": 2, "shapeType": "OVAL",
    "bounds": {"top": 70, "left": 1080, "bottom": 220, "right": 1230},
    "fillSwatch": "Slate", "strokeSwatch": "Electric", "strokeWeight": 2,
}, "minimap")
text(2, {"top": 226, "left": 1080, "bottom": 250, "right": 1230},
     "MINIMAP  anchor TR", "HUD Label", "minimap label")

# storm timer under minimap
send("createShape", {
    "pageNumber": 2, "shapeType": "RECTANGLE",
    "bounds": {"top": 258, "left": 1104, "bottom": 286, "right": 1206},
    "fillSwatch": "Slate", "strokeSwatch": "Violet", "strokeWeight": 1.5,
    "cornerOption": "ROUNDED", "cornerRadius": 14,
}, "storm timer")
text(2, {"top": 292, "left": 1080, "bottom": 316, "right": 1240},
     "STORM TIMER  anchor TR", "HUD Label", "storm label")

# alert banner (top-center) — the vault_alert_device nod
send("createShape", {
    "pageNumber": 2, "shapeType": "RECTANGLE",
    "bounds": {"top": 64, "left": 420, "bottom": 112, "right": 860},
    "fillSwatch": "Slate", "strokeSwatch": "Gold", "strokeWeight": 2,
    "cornerOption": "ROUNDED", "cornerRadius": 8,
}, "alert banner")
ab = text(2, {"top": 76, "left": 440, "bottom": 104, "right": 840},
          "VAULT ALERT — DOORS OPEN IN 30s", "Chip Label", "alert text")
text(2, {"top": 118, "left": 420, "bottom": 142, "right": 860},
     "HUD MESSAGE DEVICE  anchor TC  (vault_alert_device.verse)",
     "HUD Label", "alert label")

# crosshair (center)
cx, cy = W / 2, H / 2
send("createShape", {"pageNumber": 2, "shapeType": "RECTANGLE",
                     "bounds": {"top": cy - 14, "left": cx - 1.5,
                                "bottom": cy + 14, "right": cx + 1.5},
                     "fillSwatch": "Snow"}, "crosshair v")
send("createShape", {"pageNumber": 2, "shapeType": "RECTANGLE",
                     "bounds": {"top": cy - 1.5, "left": cx - 14,
                                "bottom": cy + 1.5, "right": cx + 14},
                     "fillSwatch": "Snow"}, "crosshair h")

# shield + health (bottom-left)
send("createShape", {"pageNumber": 2, "shapeType": "RECTANGLE",
                     "bounds": {"top": 610, "left": 48, "bottom": 628,
                                "right": 380},
                     "fillSwatch": "Shield", "cornerOption": "ROUNDED",
                     "cornerRadius": 9}, "shield bar")
send("createShape", {"pageNumber": 2, "shapeType": "RECTANGLE",
                     "bounds": {"top": 636, "left": 48, "bottom": 654,
                                "right": 380},
                     "fillSwatch": "Health", "cornerOption": "ROUNDED",
                     "cornerRadius": 9}, "health bar")
text(2, {"top": 660, "left": 48, "bottom": 684, "right": 500},
     "SHIELD / HEALTH  anchor BL", "HUD Label", "bars label")

# hotbar (bottom-right): 5 slots
x = 900
for i in range(5):
    send("createShape", {
        "pageNumber": 2, "shapeType": "RECTANGLE",
        "bounds": {"top": 596, "left": x, "bottom": 660, "right": x + 64},
        "fillSwatch": "Slate", "strokeSwatch": "Snow", "strokeWeight": 1,
        "cornerOption": "ROUNDED", "cornerRadius": 6,
    }, f"hotbar slot {i+1}")
    x += 72
text(2, {"top": 666, "left": 900, "bottom": 690, "right": 1260},
     "HOTBAR x5  anchor BR", "HUD Label", "hotbar label")

# ---------------------------------------------------------------- page 3

m = send("createMasterSpread", {
    "namePrefix": "U", "baseName": "Spec",
    "placeholders": [
        {"pageIndex": 0, "type": "TEXT", "contents": "UEFN UI SPEC — VERSE ISLAND",
         "bounds": {"top": 16, "left": 48, "bottom": 36, "right": 600}},
        {"pageIndex": 0, "type": "PAGE_NUMBER",
         "bounds": {"top": 16, "left": 1200, "bottom": 36, "right": 1232}},
    ],
}, "master U-Spec")
if m:
    send("applyMaster", {"masterName": "U-Spec", "startPage": 3,
                         "endPage": 3}, "apply master p3")

text(3, {"top": 60, "left": 48, "bottom": 95, "right": 700},
     "ELEMENT SPEC", "Section Head", "p3 head")

t = send("createTable", {
    "pageNumber": 3,
    "bounds": {"top": 110, "left": 48, "bottom": 560, "right": 1232},
    "data": [
        ["Element", "Anchor", "Size (px)", "Color", "Source"],
        ["Minimap", "Top Right", "300 x 300", "Slate / Electric stroke", "engine HUD"],
        ["Storm Timer", "Top Right", "204 x 56", "Slate / Violet stroke", "engine HUD"],
        ["Alert Banner", "Top Center", "880 x 96", "Slate / Gold stroke", "vault_alert_device.verse"],
        ["Shield Bar", "Bottom Left", "664 x 36", "Shield", "engine HUD"],
        ["Health Bar", "Bottom Left", "664 x 36", "Health", "engine HUD"],
        ["Hotbar Slots", "Bottom Right", "5 x (128 x 128)", "Slate / Snow stroke", "engine HUD"],
        ["Crosshair", "Center", "28 x 28", "Snow", "engine HUD"],
    ],
    "headerRows": 1,
    "columnWidths": [200, 160, 200, 300, 324],
}, "spec table")
if t:
    send("createCellStyle", {"name": "UEFN Header", "fillSwatch": "Night",
                             "properties": {"topInset": 6, "bottomInset": 6,
                                            "leftInset": 8}},
         "cell style UEFN Header")
    send("applyTableStyle", {
        "storyId": t["storyId"], "tableIndex": t["tableIndex"],
        "cellStyleName": "UEFN Header", "region": "HEADER",
        "alternatingFills": {"swatch": "Slate", "tint": 18, "frequency": 2},
    }, "table styling")

# ---------------------------------------------------------------- output

indd = r"C:\AppDev\ClaudeMCP\adb-mcp-main\test-outputs\uefn_ui_spec.indd"
send("saveDocumentAs", {"filePath": indd}, "save uefn_ui_spec.indd")

for p in (1, 2, 3):
    png = os.path.join(tempfile.gettempdir(), f"uefn_page{p}.png")
    r = send("getPageImage", {"pageNumber": p, "resolution": 96,
                              "filePath": png}, f"export page {p}")

print("\nFAILURES:", len(FAILURES))
for label, msg in FAILURES:
    print("  -", label, ":", str(msg)[:200])
