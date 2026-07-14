# MIT License
#
# Copyright (c) 2025 Mike Chambers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import io
import json
import os
import tempfile
import time
import sys

from mcp.server.fastmcp import FastMCP, Image
from PIL import Image as PILImage

from core import init, sendCommand, createCommand
import socket_client

# Create an MCP server
mcp_name = "Adobe InDesign MCP Server"
mcp = FastMCP(mcp_name, log_level="ERROR")
print(f"{mcp_name} running on stdio", file=sys.stderr)

APPLICATION = "indesign"
PROXY_URL = 'http://localhost:3001'
PROXY_TIMEOUT = 20

socket_client.configure(
    app=APPLICATION,
    url=PROXY_URL,
    timeout=PROXY_TIMEOUT
)

init(APPLICATION, socket_client)


# ---------------------------------------------------------------------------
# Document lifecycle
# ---------------------------------------------------------------------------

@mcp.tool()
def create_document(
   width: int,
   height: int,
   pages: int = 1,
   pages_facing: bool = False,
   intent: str = "WEB_INTENT",
   columns: dict = {"count": 1, "gutter": 12},
   margins: dict = {"top": 36, "bottom": 36, "left": 36, "right": 36}
):
   """
   Creates a new InDesign document with specified dimensions and layout settings.

   Args:
       width (int): Document width (pixels for WEB/MOBILE intent, points for PRINT)
       height (int): Document height
       pages (int, optional): Number of pages in the document. Defaults to 1.
       pages_facing (bool, optional): Whether to create facing pages (spread layout).
           Defaults to False.
       intent (str, optional): Document intent — determines default units and
           color handling. One of "WEB_INTENT" (pixels, RGB), "PRINT_INTENT"
           (points, CMYK), "MOBILE_INTENT" (pixels, RGB). Defaults to "WEB_INTENT".
       columns (dict, optional): Column layout configuration with keys:
           - count (int): Number of columns per page
           - gutter (int): Space between columns
           Defaults to {"count": 1, "gutter": 12}.
       margins (dict, optional): Page margin settings with keys:
           - top, bottom, left, right (int)
           Defaults to {"top": 36, "bottom": 36, "left": 36, "right": 36}.

   Returns:
       dict: The new document's name, intent, unit, and page count.
   """
   command = createCommand("createDocument", {
       "intent": intent,
       "pageWidth": width,
       "pageHeight": height,
       "margins": margins,
       "columns": columns,
       "pagesPerDocument": pages,
       "facingPages": pages_facing
   })

   return sendCommand(command)


@mcp.tool()
def open_document(file_path: str):
    """
    Opens an existing InDesign document (.indd) from the specified path.

    Args:
        file_path (str): Absolute path to the .indd file.

    Returns:
        dict: The opened document's name and page count.
    """
    command = createCommand("openDocument", {"filePath": file_path})
    return sendCommand(command)


@mcp.tool()
def save_document():
    """
    Saves the active document to its existing location. Fails with an
    explanatory error if the document has never been saved — use
    save_document_as with a file path in that case.
    """
    command = createCommand("saveDocument", {})
    return sendCommand(command)


@mcp.tool()
def save_document_as(file_path: str):
    """
    Saves the active document to a new path.

    Args:
        file_path (str): Absolute output path, should end in .indd
    """
    command = createCommand("saveDocumentAs", {"filePath": file_path})
    return sendCommand(command)


@mcp.tool()
def close_document(save: bool = False):
    """
    Closes the active document.

    Args:
        save (bool, optional): If True, saves before closing (document must
            have been saved before, or this will fail). Defaults to False
            (close without saving).
    """
    command = createCommand("closeDocument", {"save": save})
    return sendCommand(command)


# ---------------------------------------------------------------------------
# Deep read & visual feedback
# ---------------------------------------------------------------------------

@mcp.tool()
def get_document_info():
    """
    Returns a deep description of the active InDesign document: every page with
    its applied master and all page items (type, id, name, bounds, layer), text
    frames with contents preview / story id / overset state / threading, plus
    document paragraph/character/object styles, swatches, layers, and master
    spreads.

    Call this FIRST before manipulating an existing document — item ids and
    story ids returned here are the handles every other tool uses.

    Note: all bounds are geometricBounds in POINTS, as {top, left, bottom,
    right} objects (InDesign's native order is [y1, x1, y2, x2]). Pages are
    1-based everywhere in this API.
    """
    command = createCommand("getDocumentInfo", {})
    return sendCommand(command)


@mcp.tool()
def get_page_image(page_number: int, resolution: int = 72):
    """
    Exports a PNG preview of the specified page and returns it as an image you
    can SEE. Use this after layout changes to visually verify the result — the
    layout you think you made vs. the one you actually made.

    Args:
        page_number (int): 1-based page number.
        resolution (int, optional): Export resolution in DPI. Defaults to 72.
            Use 144 for finer inspection of type details.

    Returns:
        The command result and a viewable image of the page.
    """
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, f"id_page_{page_number}_{int(time.time())}.png")

    command = createCommand("getPageImage", {
        "pageNumber": page_number,
        "resolution": resolution,
        "filePath": file_path
    })

    result = sendCommand(command)

    if not result.get("status") == "SUCCESS":
        return result

    file_path = result["response"]["filePath"]

    with open(file_path, 'rb') as f:
        png_image = PILImage.open(f)

        # Convert to RGB if necessary (removes alpha channel)
        if png_image.mode in ("RGBA", "LA", "P"):
            rgb_image = PILImage.new("RGB", png_image.size, (255, 255, 255))
            rgb_image.paste(png_image, mask=png_image.split()[-1] if png_image.mode == "RGBA" else None)
            png_image = rgb_image

        jpeg_buffer = io.BytesIO()
        png_image.save(jpeg_buffer, format="JPEG", quality=85, optimize=True)
        jpeg_bytes = jpeg_buffer.getvalue()

    image = Image(data=jpeg_bytes, format="jpeg")

    del result["response"]

    try:
        os.remove(file_path)
    except FileNotFoundError:
        pass

    return [result, image]


@mcp.tool()
def export_pdf(file_path: str, preset_name: str = None, page_range: str = None):
    """
    Exports the active document to PDF.

    Args:
        file_path (str): Absolute output path ending in .pdf
        preset_name (str, optional): Name of a PDF export preset (e.g.
            "[High Quality Print]", "[Smallest File Size]"). If omitted, the
            current PDF export preferences are used.
        page_range (str, optional): Page range string like "1-3" or "2, 4-6".
            Defaults to all pages.

    IMPORTANT: On large documents PDF export can exceed the 20 second proxy
    timeout. A timeout response does NOT mean the export failed — check
    whether the output file exists before retrying.
    """
    command = createCommand("exportPdf", {
        "filePath": file_path,
        "presetName": preset_name,
        "pageRange": page_range
    })
    return sendCommand(command)


@mcp.tool()
def get_active_document_settings():
    """
    Lightweight health check: returns the active document's page size, page
    count, facing-pages setting, and margin preferences (or null if no
    document is open). Cheap to call — use it to verify the plugin connection
    before a work session.
    """
    command = createCommand("getActiveDocumentSettings", {})
    return sendCommand(command)


# ---------------------------------------------------------------------------
# Pages, layers & guides
# ---------------------------------------------------------------------------

@mcp.tool()
def add_pages(count: int = 1, after_page_number: int = None):
    """
    Adds pages to the active document.

    Args:
        count (int, optional): Number of pages to add. Defaults to 1.
        after_page_number (int, optional): 1-based page number to insert
            after. Defaults to the end of the document.
    """
    command = createCommand("addPages", {
        "count": count,
        "afterPageNumber": after_page_number
    })
    return sendCommand(command)


@mcp.tool()
def remove_page(page_number: int):
    """
    Removes the specified page (1-based) from the active document. All items
    on the page are deleted with it.
    """
    command = createCommand("removePage", {"pageNumber": page_number})
    return sendCommand(command)


@mcp.tool()
def duplicate_page(page_number: int, after_page_number: int = None):
    """
    Duplicates the specified page (1-based) with everything on it.

    Args:
        page_number (int): 1-based page to duplicate.
        after_page_number (int, optional): 1-based page to place the copy
            after. Defaults to right after the original.
    """
    command = createCommand("duplicatePage", {
        "pageNumber": page_number,
        "afterPageNumber": after_page_number
    })
    return sendCommand(command)


@mcp.tool()
def set_page_numbering(page_number: int, start_at: int = 1,
                       style: str = "ARABIC", prefix: str = None):
    """
    Starts a new numbering section at the specified page.

    Args:
        page_number (int): 1-based page where the section starts.
        start_at (int, optional): First page number of the section. Defaults to 1.
        style (str, optional): Numbering style — ARABIC, LOWER_ROMAN,
            UPPER_ROMAN, LOWER_LETTERS, UPPER_LETTERS. Defaults to ARABIC.
        prefix (str, optional): Section prefix (e.g. "A-").
    """
    command = createCommand("setPageNumbering", {
        "pageNumber": page_number,
        "startAt": start_at,
        "style": style,
        "prefix": prefix
    })
    return sendCommand(command)


@mcp.tool()
def create_layer(name: str, color: str = None):
    """
    Creates a new layer in the active document (on top of the stack).

    Args:
        name (str): Layer name (must not already exist).
        color (str, optional): Layer UI color, e.g. BLUE, RED, GREEN, YELLOW,
            MAGENTA, CYAN, ORANGE, VIOLET, GOLD, PINK, PURPLE, CHARCOAL.
    """
    command = createCommand("createLayer", {"name": name, "color": color})
    return sendCommand(command)


@mcp.tool()
def set_layer_properties(layer_name: str, new_name: str = None,
                         locked: bool = None, visible: bool = None,
                         color: str = None):
    """
    Updates properties of an existing layer: rename, lock/unlock, show/hide,
    UI color. Only the parameters you pass are changed.

    Args:
        layer_name (str): Current name of the layer.
        new_name (str, optional): New name for the layer.
        locked (bool, optional): Lock (True) or unlock (False).
        visible (bool, optional): Show (True) or hide (False).
        color (str, optional): Layer UI color (see create_layer).
    """
    command = createCommand("setLayerProperties", {
        "layerName": layer_name,
        "newName": new_name,
        "locked": locked,
        "visible": visible,
        "color": color
    })
    return sendCommand(command)


@mcp.tool()
def delete_layer(layer_name: str):
    """
    Deletes the named layer AND everything on it. Cannot delete the last
    remaining layer.
    """
    command = createCommand("deleteLayer", {"layerName": layer_name})
    return sendCommand(command)


@mcp.tool()
def add_guide(page_number: int, orientation: str, location: float):
    """
    Adds a ruler guide to a page.

    Args:
        page_number (int): 1-based page number.
        orientation (str): "HORIZONTAL" or "VERTICAL".
        location (float): Position in POINTS from the page's top-left ruler
            origin (y for horizontal guides, x for vertical guides).
    """
    command = createCommand("addGuide", {
        "pageNumber": page_number,
        "orientation": orientation,
        "location": location
    })
    return sendCommand(command)


# ---------------------------------------------------------------------------
# Text frames & basic styling
# ---------------------------------------------------------------------------

@mcp.tool()
def create_text_frame(page_number: int, bounds: dict, contents: str = "",
                      layer_name: str = None, name: str = None):
    """
    Creates a text frame on a page.

    Args:
        page_number (int): 1-based page number.
        bounds (dict): Frame bounds in POINTS: {"top": t, "left": l,
            "bottom": b, "right": r}. (InDesign's native geometricBounds
            order is [top, left, bottom, right] — y-first, not x-first.)
        contents (str, optional): Initial text contents.
        layer_name (str, optional): Layer to place the frame on.
        name (str, optional): Item name — named frames are the targets
            populate_template fills.

    Returns:
        dict: frameId, storyId, and overflows. If overflows is True the text
        does not fit — grow the frame, thread another frame, or shrink the type.
    """
    command = createCommand("createTextFrame", {
        "pageNumber": page_number,
        "bounds": bounds,
        "contents": contents,
        "layerName": layer_name,
        "name": name
    })
    return sendCommand(command)


@mcp.tool()
def set_text_contents(contents: str, story_id: int = None, frame_id: int = None):
    """
    Replaces ALL text of a story. Pass either story_id or frame_id (the
    frame's parent story is used — note a story can span multiple threaded
    frames, so this replaces text in all of them).

    Returns per-frame overset state so overflow can be fixed.
    """
    command = createCommand("setTextContents", {
        "storyId": story_id,
        "frameId": frame_id,
        "contents": contents
    })
    return sendCommand(command)


@mcp.tool()
def insert_text(story_id: int, text: str, position: str = "end"):
    """
    Inserts text into a story WITHOUT clobbering existing text or styling.

    Args:
        story_id (int): Story id (from get_document_info or create_text_frame).
        text (str): Text to insert. Use \\r for paragraph breaks and \\n for
            forced line breaks (InDesign convention).
        position (str, optional): "start", "end", or a 0-based character
            index as a string. Defaults to "end".

    Returns per-frame overset state.
    """
    command = createCommand("insertText", {
        "storyId": story_id,
        "text": text,
        "position": position
    })
    return sendCommand(command)


@mcp.tool()
def get_story_contents(story_id: int):
    """
    Returns the full text of a story (spanning ALL of its threaded frames),
    plus character/paragraph counts, overset state, and the ids of the frames
    the story flows through.
    """
    command = createCommand("getStoryContents", {"storyId": story_id})
    return sendCommand(command)


@mcp.tool()
def thread_text_frames(from_frame_id: int, to_frame_id: int):
    """
    Threads (links) two text frames so text flows from the first into the
    second. The target frame must be empty. Use this to fix overset text or
    to build multi-column / multi-page text flows.

    Returns the merged story's per-frame overset state.
    """
    command = createCommand("threadTextFrames", {
        "fromFrameId": from_frame_id,
        "toFrameId": to_frame_id
    })
    return sendCommand(command)


@mcp.tool()
def set_text_frame_options(frame_id: int, column_count: int = None,
                           column_gutter: float = None, inset_spacing=None,
                           vertical_justification: str = None,
                           auto_size: str = None):
    """
    Sets text frame options. Only passed parameters are changed. All
    measurements in POINTS.

    Args:
        frame_id (int): Text frame id.
        column_count (int, optional): Number of columns inside the frame.
        column_gutter (float, optional): Gutter between columns.
        inset_spacing (optional): Either a single number (uniform inset) or
            {"top": t, "left": l, "bottom": b, "right": r}.
        vertical_justification (str, optional): TOP, CENTER, BOTTOM, JUSTIFY.
        auto_size (str, optional): OFF, HEIGHT_ONLY, WIDTH_ONLY,
            HEIGHT_AND_WIDTH, HEIGHT_AND_WIDTH_PROPORTIONALLY.

    Returns frame overset state.
    """
    command = createCommand("setTextFrameOptions", {
        "frameId": frame_id,
        "columnCount": column_count,
        "columnGutter": column_gutter,
        "insetSpacing": inset_spacing,
        "verticalJustification": vertical_justification,
        "autoSize": auto_size
    })
    return sendCommand(command)


@mcp.tool()
def style_text_range(story_id: int, range_type: str = "story",
                     start: int = None, end: int = None,
                     font_family: str = None, font_style: str = None,
                     point_size: float = None, leading: float = None,
                     alignment: str = None, space_before: float = None,
                     space_after: float = None, first_line_indent: float = None,
                     tracking: float = None):
    """
    Applies character/paragraph formatting directly to a text range. (For
    reusable formatting, prefer paragraph/character styles — coming in
    Phase 2.) All measurements in POINTS. Only passed parameters are changed.

    Args:
        story_id (int): Story id.
        range_type (str, optional): "story" (whole story, default),
            "paragraphs", or "characters".
        start (int, optional): 0-based first paragraph/character index
            (required for paragraphs/characters ranges).
        end (int, optional): 0-based last index, INCLUSIVE. Defaults to the
            last paragraph/character.
        font_family (str, optional): e.g. "Minion Pro", "Arial".
        font_style (str, optional): e.g. "Regular", "Bold", "Italic".
        point_size (float, optional): Type size in points.
        leading (float, optional): Leading in points.
        alignment (str, optional): LEFT, CENTER, RIGHT, JUSTIFY (last line
            left), FULLY_JUSTIFY.
        space_before (float, optional): Paragraph space before, points.
        space_after (float, optional): Paragraph space after, points.
        first_line_indent (float, optional): First line indent, points.
        tracking (float, optional): Tracking in 1/1000 em.

    Returns per-frame overset state (styling changes can cause overflow).
    """
    command = createCommand("styleTextRange", {
        "storyId": story_id,
        "rangeType": range_type,
        "start": start,
        "end": end,
        "fontFamily": font_family,
        "fontStyle": font_style,
        "pointSize": point_size,
        "leading": leading,
        "alignment": alignment,
        "spaceBefore": space_before,
        "spaceAfter": space_after,
        "firstLineIndent": first_line_indent,
        "tracking": tracking
    })
    return sendCommand(command)


@mcp.tool()
def set_text_color(story_id: int, swatch_name: str, range_type: str = "story",
                   start: int = None, end: int = None):
    """
    Applies a document swatch as the text fill color of a range.

    Args:
        story_id (int): Story id.
        swatch_name (str): Name of an existing swatch (see get_document_info;
            create new ones with create_swatch).
        range_type (str, optional): "story" (default), "paragraphs", "characters".
        start (int, optional): 0-based first index for ranged types.
        end (int, optional): 0-based last index, INCLUSIVE.
    """
    command = createCommand("setTextColor", {
        "storyId": story_id,
        "swatchName": swatch_name,
        "rangeType": range_type,
        "start": start,
        "end": end
    })
    return sendCommand(command)


# ---------------------------------------------------------------------------
# Shapes, swatches, images & transforms
# ---------------------------------------------------------------------------

@mcp.tool()
def create_shape(page_number: int, shape_type: str, bounds: dict,
                 fill_swatch: str = None, stroke_swatch: str = None,
                 stroke_weight: float = None, corner_option: str = None,
                 corner_radius: float = None, opacity: float = None,
                 sides: int = None, layer_name: str = None,
                 name: str = None):
    """
    Creates a shape on a page.

    Args:
        page_number (int): 1-based page number.
        shape_type (str): RECTANGLE, OVAL, POLYGON, or LINE.
        bounds (dict): {"top": t, "left": l, "bottom": b, "right": r} in
            POINTS. For LINE this is the bounding box of the line.
        fill_swatch (str, optional): Swatch name for the fill.
        stroke_swatch (str, optional): Swatch name for the stroke.
        stroke_weight (float, optional): Stroke weight in points.
        corner_option (str, optional): NONE, ROUNDED, INVERSE_ROUNDED, INSET,
            BEVEL, FANCY (applied to all four corners).
        corner_radius (float, optional): Corner radius in points.
        opacity (float, optional): 0-100.
        sides (int, optional): Number of sides for POLYGON. Defaults to 6.
        layer_name (str, optional): Layer to place the shape on.

    Returns:
        dict: itemId, type, and resulting bounds.
    """
    command = createCommand("createShape", {
        "pageNumber": page_number,
        "shapeType": shape_type,
        "bounds": bounds,
        "fillSwatch": fill_swatch,
        "strokeSwatch": stroke_swatch,
        "strokeWeight": stroke_weight,
        "cornerOption": corner_option,
        "cornerRadius": corner_radius,
        "opacity": opacity,
        "sides": sides,
        "layerName": layer_name,
        "name": name
    })
    return sendCommand(command)


@mcp.tool()
def set_item_appearance(item_id: int, fill_swatch: str = None,
                        stroke_swatch: str = None, stroke_weight: float = None,
                        corner_option: str = None, corner_radius: float = None,
                        opacity: float = None):
    """
    Changes the appearance of ANY existing page item by id (shapes, text
    frames, image frames). Only passed parameters are changed. Swatch names
    must exist in the document (use create_swatch / get_document_info).
    Corner options: NONE, ROUNDED, INVERSE_ROUNDED, INSET, BEVEL, FANCY.
    Opacity: 0-100.
    """
    command = createCommand("setItemAppearance", {
        "itemId": item_id,
        "fillSwatch": fill_swatch,
        "strokeSwatch": stroke_swatch,
        "strokeWeight": stroke_weight,
        "cornerOption": corner_option,
        "cornerRadius": corner_radius,
        "opacity": opacity
    })
    return sendCommand(command)


@mcp.tool()
def create_swatch(name: str, color_space: str, color_value: list):
    """
    Creates (or updates, if the name exists) a process color swatch.

    Args:
        name (str): Swatch name, e.g. "Brand Red".
        color_space (str): "CMYK" or "RGB".
        color_value (list): CMYK: [c, m, y, k] each 0-100.
            RGB: [r, g, b] each 0-255.
    """
    command = createCommand("createSwatch", {
        "name": name,
        "colorSpace": color_space,
        "colorValue": color_value
    })
    return sendCommand(command)


@mcp.tool()
def place_image(file_path: str, page_number: int = None, bounds: dict = None,
                frame_id: int = None, fit_option: str = "FILL_PROPORTIONALLY"):
    """
    Places an image file into a frame. Either give page_number + bounds (a
    new frame is created) or frame_id (image is placed into the existing
    frame).

    Args:
        file_path (str): Absolute path to the image (png/jpg/tif/psd/ai/pdf...).
        page_number (int, optional): 1-based page for a new frame.
        bounds (dict, optional): {"top", "left", "bottom", "right"} in POINTS
            for the new frame.
        frame_id (int, optional): Existing frame to place into instead.
        fit_option (str, optional): PROPORTIONALLY, FILL_PROPORTIONALLY
            (default), CONTENT_TO_FRAME, FRAME_TO_CONTENT, CENTER_CONTENT.
    """
    command = createCommand("placeImage", {
        "filePath": file_path,
        "pageNumber": page_number,
        "bounds": bounds,
        "frameId": frame_id,
        "fitOption": fit_option
    })
    return sendCommand(command)


@mcp.tool()
def transform_item(item_id: int, move_by: dict = None, move_to: dict = None,
                   width: float = None, height: float = None,
                   rotation: float = None):
    """
    Moves / resizes / rotates any page item by id. All values in POINTS
    (rotation in degrees, counterclockwise). Only passed parameters are applied.

    Args:
        item_id (int): Page item id.
        move_by (dict, optional): Relative move {"x": dx, "y": dy}.
        move_to (dict, optional): Absolute position of the top-left corner
            {"x": x, "y": y}.
        width (float, optional): New width (top-left corner stays fixed).
        height (float, optional): New height.
        rotation (float, optional): Absolute rotation angle in degrees.

    Returns the item's resulting description including new bounds.
    """
    command = createCommand("transformItem", {
        "itemId": item_id,
        "moveBy": move_by,
        "moveTo": move_to,
        "width": width,
        "height": height,
        "rotation": rotation
    })
    return sendCommand(command)


@mcp.tool()
def duplicate_item(item_id: int, to_page_number: int = None, offset: dict = None):
    """
    Duplicates a page item.

    Args:
        item_id (int): Page item id.
        to_page_number (int, optional): 1-based page to duplicate to. If
            omitted, duplicates in place with an offset.
        offset (dict, optional): {"x": dx, "y": dy} in points for in-place
            duplication. Defaults to {"x": 12, "y": 12}.

    Returns the new item's description (including its new id).
    """
    command = createCommand("duplicateItem", {
        "itemId": item_id,
        "toPageNumber": to_page_number,
        "offset": offset
    })
    return sendCommand(command)


@mcp.tool()
def group_items(item_ids: list = None, ungroup_item_id: int = None):
    """
    Groups page items (pass item_ids, at least 2, all on the same page), or
    ungroups an existing group (pass ungroup_item_id).

    Returns the group's description (or the freed item ids when ungrouping).
    """
    command = createCommand("groupItems", {
        "itemIds": item_ids,
        "ungroupItemId": ungroup_item_id
    })
    return sendCommand(command)


# ---------------------------------------------------------------------------
# Styles engine (Phase 2)
# ---------------------------------------------------------------------------

@mcp.tool()
def create_paragraph_style(name: str, font_family: str = None,
                           font_style: str = None, point_size: float = None,
                           leading: float = None, alignment: str = None,
                           space_before: float = None, space_after: float = None,
                           first_line_indent: float = None,
                           hyphenation: bool = None, fill_swatch: str = None,
                           based_on: str = None, next_style: str = None,
                           properties: dict = None):
    """
    Creates (or updates, if the name exists) a paragraph style. Styles are how
    a document stays consistent — one style edit restyles everything using it.
    All measurements in POINTS. Only passed parameters are set.

    Args:
        name (str): Style name (upsert semantics).
        font_family (str, optional): e.g. "Arial", "Minion Pro".
        font_style (str, optional): e.g. "Regular", "Bold", "Italic".
        point_size (float, optional): Type size.
        leading (float, optional): Leading in points.
        alignment (str, optional): LEFT, CENTER, RIGHT, JUSTIFY, FULLY_JUSTIFY.
        space_before / space_after (float, optional): Paragraph spacing.
        first_line_indent (float, optional): First line indent.
        hyphenation (bool, optional): Enable/disable hyphenation.
        fill_swatch (str, optional): Text color swatch name.
        based_on (str, optional): Parent style name.
        next_style (str, optional): Next-style name.
        properties (dict, optional): ADVANCED — extra InDesign DOM style
            properties set verbatim (values ending in Color resolve swatch
            names), e.g. {"underline": true, "strikeThru": false}.

    WARNING: always pass font_family together with font_style — a style
    definition referencing a face that isn't installed is accepted silently
    and later triggers a blocking "Missing Fonts" dialog.
    """
    command = createCommand("createParagraphStyle", {
        "name": name, "fontFamily": font_family, "fontStyle": font_style,
        "pointSize": point_size, "leading": leading, "alignment": alignment,
        "spaceBefore": space_before, "spaceAfter": space_after,
        "firstLineIndent": first_line_indent, "hyphenation": hyphenation,
        "fillSwatch": fill_swatch, "basedOn": based_on,
        "nextStyle": next_style, "properties": properties
    })
    return sendCommand(command)


@mcp.tool()
def create_character_style(name: str, font_family: str = None,
                           font_style: str = None, point_size: float = None,
                           tracking: float = None, fill_swatch: str = None,
                           based_on: str = None, properties: dict = None):
    """
    Creates (or updates) a character style — for inline formatting like
    emphasis, code, prices. Only passed parameters are set (character styles
    leave unset attributes transparent).

    Args mirror create_paragraph_style where applicable; tracking is in
    1/1000 em. properties is the same advanced DOM passthrough.

    WARNING: always pass font_family together with font_style. A style
    definition with a face the machine doesn't have (e.g. font_style="Bold
    Italic" alone) is accepted SILENTLY and later triggers a blocking
    "Missing Fonts" dialog in InDesign.
    """
    command = createCommand("createCharacterStyle", {
        "name": name, "fontFamily": font_family, "fontStyle": font_style,
        "pointSize": point_size, "tracking": tracking,
        "fillSwatch": fill_swatch, "basedOn": based_on,
        "properties": properties
    })
    return sendCommand(command)


@mcp.tool()
def create_object_style(name: str, fill_swatch: str = None,
                        stroke_swatch: str = None, stroke_weight: float = None,
                        based_on: str = None, properties: dict = None):
    """
    Creates (or updates) an object style — reusable frame appearance (fill,
    stroke, and any DOM property via the properties passthrough).
    """
    command = createCommand("createObjectStyle", {
        "name": name, "fillSwatch": fill_swatch,
        "strokeSwatch": stroke_swatch, "strokeWeight": stroke_weight,
        "basedOn": based_on, "properties": properties
    })
    return sendCommand(command)


@mcp.tool()
def apply_paragraph_style(style_name: str, story_id: int = None,
                          frame_id: int = None, start_paragraph: int = None,
                          end_paragraph: int = None,
                          clear_overrides: bool = False):
    """
    Applies a paragraph style to a whole story (default) or a paragraph range.
    Pass story_id or frame_id (frame's parent story is used).

    Args:
        style_name (str): Existing paragraph style.
        start_paragraph / end_paragraph (int, optional): 0-based inclusive
            paragraph range; omit for the whole story.
        clear_overrides (bool, optional): Also clear local formatting overrides.

    Returns per-frame overset state.
    """
    command = createCommand("applyParagraphStyle", {
        "styleName": style_name, "storyId": story_id, "frameId": frame_id,
        "startParagraph": start_paragraph, "endParagraph": end_paragraph,
        "clearOverrides": clear_overrides
    })
    return sendCommand(command)


@mcp.tool()
def apply_character_style(style_name: str, story_id: int,
                          start_character: int = None,
                          end_character: int = None):
    """
    Applies a character style to a character range of a story (0-based,
    end-inclusive), or the whole story if no range given.
    """
    command = createCommand("applyCharacterStyle", {
        "styleName": style_name, "storyId": story_id,
        "startCharacter": start_character, "endCharacter": end_character
    })
    return sendCommand(command)


@mcp.tool()
def apply_object_style(style_name: str, item_id: int,
                       clear_overrides: bool = False):
    """
    Applies an object style to any page item by id.
    """
    command = createCommand("applyObjectStyle", {
        "styleName": style_name, "itemId": item_id,
        "clearOverrides": clear_overrides
    })
    return sendCommand(command)


@mcp.tool()
def list_styles():
    """
    Lists ALL styles in the document (paragraph, character, object, table,
    cell — including styles inside groups) with their key properties.
    The read half of the styles round-trip: create → list → edit → verify.
    """
    command = createCommand("listStyles", {})
    return sendCommand(command)


@mcp.tool()
def create_style_group(style_type: str, name: str, style_names: list = None):
    """
    Creates a style group (folder) and optionally moves existing styles into it.

    Args:
        style_type (str): paragraph, character, object, table, or cell.
        name (str): Group name (reused if it exists).
        style_names (list, optional): Names of styles to move into the group.
    """
    command = createCommand("createStyleGroup", {
        "styleType": style_type, "name": name, "styleNames": style_names
    })
    return sendCommand(command)


@mcp.tool()
def edit_style_property(style_type: str, style_name: str, property: str,
                        value):
    """
    Targeted single-property edit on any style ("make Body 0.5pt looser").

    Args:
        style_type (str): paragraph, character, object, table, or cell.
        style_name (str): Style to edit.
        property (str): InDesign DOM property name (e.g. "leading",
            "pointSize", "spaceAfter", "fillColor" — Color properties accept
            swatch names; "basedOn"/"nextStyle" accept style names;
            "justification" accepts LEFT/CENTER/RIGHT/JUSTIFY/FULLY_JUSTIFY).
        value: The new value.
    """
    command = createCommand("editStyleProperty", {
        "styleType": style_type, "styleName": style_name,
        "property": property, "value": value
    })
    return sendCommand(command)


@mcp.tool()
def delete_style(style_type: str, style_name: str,
                 replacement_style_name: str = None):
    """
    Deletes a style. If replacement_style_name is given, text/items using the
    deleted style are reassigned to it (otherwise formatting is preserved as
    local overrides).
    """
    command = createCommand("deleteStyle", {
        "styleType": style_type, "styleName": style_name,
        "replacementStyleName": replacement_style_name
    })
    return sendCommand(command)


# ---------------------------------------------------------------------------
# Find/Change & GREP (Phase 2)
# ---------------------------------------------------------------------------

@mcp.tool()
def find_text(find_what: str, case_sensitive: bool = False,
              whole_word: bool = False, story_id: int = None):
    """
    Literal text search across the document (or one story). Returns up to 200
    matches with story ids, character indices, and surrounding context.
    """
    command = createCommand("findText", {
        "findWhat": find_what, "caseSensitive": case_sensitive,
        "wholeWord": whole_word, "storyId": story_id
    })
    return sendCommand(command)


@mcp.tool()
def change_text(find_what: str, change_to: str, case_sensitive: bool = False,
                whole_word: bool = False, story_id: int = None):
    """
    Literal text find & replace across the document (or one story).
    Returns the number of changes made.
    """
    command = createCommand("changeText", {
        "findWhat": find_what, "changeTo": change_to,
        "caseSensitive": case_sensitive, "wholeWord": whole_word,
        "storyId": story_id
    })
    return sendCommand(command)


@mcp.tool()
def find_grep(find_what: str, story_id: int = None, context_chars: int = 40):
    """
    GREP (regex) search across the document (or one story). InDesign GREP
    syntax: \\d digits, \\s whitespace, \\r paragraph end, etc. Returns up to
    200 matches with story ids, character indices, and context.

    Tip: run this (or find_change_report) BEFORE change_grep to preview what
    a bulk change will touch.
    """
    command = createCommand("findGrep", {
        "findWhat": find_what, "storyId": story_id,
        "contextChars": context_chars
    })
    return sendCommand(command)


@mcp.tool()
def change_grep(find_what: str, change_to: str = None, story_id: int = None,
                applied_character_style: str = None,
                applied_paragraph_style: str = None):
    """
    GREP (regex) replace across the document (or one story) — the flagship
    bulk-editing tool. Supports $1-style backreferences in change_to (e.g.
    find "(\\d+)-(\\d+)" change "$1–$2" fixes hyphens to en-dashes). Can also
    (or instead) apply a character/paragraph style to every match.

    Returns the number of changes made.
    """
    command = createCommand("changeGrep", {
        "findWhat": find_what, "changeTo": change_to, "storyId": story_id,
        "appliedCharacterStyle": applied_character_style,
        "appliedParagraphStyle": applied_paragraph_style
    })
    return sendCommand(command)


@mcp.tool()
def grep_apply_style(find_what: str, character_style: str = None,
                     paragraph_style: str = None, story_id: int = None):
    """
    Applies a character or paragraph style to every GREP match WITHOUT
    changing the text ("italicize every Latin binomial"). Convenience wrapper
    over change_grep.
    """
    command = createCommand("grepApplyStyle", {
        "findWhat": find_what, "characterStyle": character_style,
        "paragraphStyle": paragraph_style, "storyId": story_id
    })
    return sendCommand(command)


@mcp.tool()
def find_change_report(patterns: list, story_id: int = None):
    """
    Dry run: GREP match counts per pattern, changing nothing. Use before a
    bulk change_grep to sanity-check pattern reach.

    Args:
        patterns (list): List of GREP pattern strings.
    """
    command = createCommand("findChangeReport", {
        "patterns": patterns, "storyId": story_id
    })
    return sendCommand(command)


# ---------------------------------------------------------------------------
# Master pages & tables (Phase 2)
# ---------------------------------------------------------------------------

@mcp.tool()
def create_master_spread(name_prefix: str = None, base_name: str = None,
                         based_on_master: str = None,
                         placeholders: list = None):
    """
    Creates a master (parent) spread, optionally with placeholder items.

    Args:
        name_prefix (str, optional): e.g. "B" (master becomes "B-<base_name>").
        base_name (str, optional): e.g. "Section" → "B-Section".
        based_on_master (str, optional): Existing master to base this one on.
        placeholders (list, optional): Items to create on the master. Each:
            {"pageIndex": 0, "type": "TEXT"|"PAGE_NUMBER"|"RECTANGLE",
             "bounds": {"top","left","bottom","right"} (POINTS),
             "contents": "..." (TEXT only), "fillSwatch": "..." (RECTANGLE)}.
            PAGE_NUMBER inserts an auto page-number marker frame.

    Returns the master's name and created placeholder item ids.
    """
    command = createCommand("createMasterSpread", {
        "namePrefix": name_prefix, "baseName": base_name,
        "basedOnMaster": based_on_master, "placeholders": placeholders
    })
    return sendCommand(command)


@mcp.tool()
def apply_master(master_name: str = None, start_page: int = 1,
                 end_page: int = None):
    """
    Applies a master spread to a page range (1-based, inclusive). Accepts the
    full name ("B-Section") or base name ("Section"). Pass master_name=None
    to apply [None] (remove the master).
    """
    command = createCommand("applyMaster", {
        "masterName": master_name, "startPage": start_page,
        "endPage": end_page
    })
    return sendCommand(command)


@mcp.tool()
def override_master_item(item_id: int, page_number: int):
    """
    Overrides a master item onto a document page so it can be edited locally.
    item_id is the id of the item ON THE MASTER (returned by
    create_master_spread; note master items do NOT appear in
    get_document_info page items). Returns the new local item's id.
    """
    command = createCommand("overrideMasterItem", {
        "itemId": item_id, "pageNumber": page_number
    })
    return sendCommand(command)


@mcp.tool()
def create_table(data: list, story_id: int = None, frame_id: int = None,
                 page_number: int = None, bounds: dict = None,
                 header_rows: int = 0, column_widths: list = None):
    """
    Creates a table from a 2D data array. Give ONE anchor: story_id (table
    appended at story end), frame_id, or page_number+bounds (a new text frame
    is created for the table).

    Args:
        data (list): 2D array of cell values, e.g. [["Name","Qty"],["Ink",2]].
            The first header_rows rows become table header rows.
        header_rows (int, optional): Number of header rows. Defaults to 0.
        column_widths (list, optional): Column widths in POINTS (null entries
            skip a column).
        bounds (dict, optional): {"top","left","bottom","right"} in POINTS for
            the new frame when using page_number.

    Returns storyId + tableIndex (the handle other table tools use), row and
    column counts, and overset state.
    """
    command = createCommand("createTable", {
        "data": data, "storyId": story_id, "frameId": frame_id,
        "pageNumber": page_number, "bounds": bounds,
        "headerRows": header_rows, "columnWidths": column_widths
    })
    return sendCommand(command)


@mcp.tool()
def set_cell_contents(story_id: int, cells: list, table_index: int = 0):
    """
    Writes/updates table cells by 0-based row/column.

    Args:
        story_id (int): Story containing the table.
        cells (list): [{"row": 0, "column": 1, "contents": "..."}, ...]
        table_index (int, optional): Which table in the story. Defaults to 0.
    """
    command = createCommand("setCellContents", {
        "storyId": story_id, "tableIndex": table_index, "cells": cells
    })
    return sendCommand(command)


@mcp.tool()
def add_table_rows_columns(story_id: int, table_index: int = 0,
                           add_rows: int = 0, add_columns: int = 0,
                           position: str = "END"):
    """
    Adds rows and/or columns to a table at BEGINNING or END.
    """
    command = createCommand("addTableRowsColumns", {
        "storyId": story_id, "tableIndex": table_index,
        "addRows": add_rows, "addColumns": add_columns, "position": position
    })
    return sendCommand(command)


@mcp.tool()
def merge_cells(story_id: int, start_row: int, start_column: int,
                end_row: int, end_column: int, table_index: int = 0):
    """
    Merges a rectangular cell range (0-based, inclusive) into one cell.
    """
    command = createCommand("mergeCells", {
        "storyId": story_id, "tableIndex": table_index,
        "startRow": start_row, "startColumn": start_column,
        "endRow": end_row, "endColumn": end_column
    })
    return sendCommand(command)


@mcp.tool()
def create_table_style(name: str, properties: dict = None):
    """
    Creates (or updates) a table style. properties is an InDesign DOM
    passthrough (keys ending in Color resolve swatch names), e.g.
    {"bodyRegionCellStyle": ..., "startRowStrokeWeight": 0.5}.
    """
    command = createCommand("createTableStyle", {
        "name": name, "properties": properties
    })
    return sendCommand(command)


@mcp.tool()
def create_cell_style(name: str, fill_swatch: str = None,
                      fill_tint: float = None, properties: dict = None):
    """
    Creates (or updates) a cell style (fill swatch + tint, plus a DOM
    properties passthrough for insets/strokes, e.g. {"topInset": 4,
    "bottomInset": 4}).
    """
    command = createCommand("createCellStyle", {
        "name": name, "fillSwatch": fill_swatch, "fillTint": fill_tint,
        "properties": properties
    })
    return sendCommand(command)


@mcp.tool()
def apply_table_style(story_id: int, table_index: int = 0,
                      table_style_name: str = None,
                      cell_style_name: str = None, region: str = "ALL",
                      alternating_fills: dict = None):
    """
    Applies styles to an existing table: a table style, a cell style (region:
    ALL or HEADER), and/or direct alternating row fills
    ({"swatch": "...", "tint": 20, "frequency": 2} = every 2nd body row).
    """
    command = createCommand("applyTableStyle", {
        "storyId": story_id, "tableIndex": table_index,
        "tableStyleName": table_style_name, "cellStyleName": cell_style_name,
        "region": region, "alternatingFills": alternating_fills
    })
    return sendCommand(command)


# ---------------------------------------------------------------------------
# Advanced typography (Phase 2)
# ---------------------------------------------------------------------------

@mcp.tool()
def set_baseline_grid(start: float = None, increment: float = None,
                      shown: bool = None, view_threshold: float = None):
    """
    Sets the document baseline grid (all values in POINTS): start offset from
    the page top, increment between baselines, and grid visibility. Use
    set_align_to_baseline to snap paragraphs/styles to the grid.
    """
    command = createCommand("setBaselineGrid", {
        "start": start, "increment": increment, "shown": shown,
        "viewThreshold": view_threshold
    })
    return sendCommand(command)


@mcp.tool()
def set_align_to_baseline(align: bool = True, style_name: str = None,
                          story_id: int = None, start_paragraph: int = None,
                          end_paragraph: int = None):
    """
    Turns align-to-baseline-grid on/off for a paragraph style (style_name) OR
    a story / paragraph range (story_id + optional 0-based inclusive range).
    """
    command = createCommand("setAlignToBaseline", {
        "align": align, "styleName": style_name, "storyId": story_id,
        "startParagraph": start_paragraph, "endParagraph": end_paragraph
    })
    return sendCommand(command)


@mcp.tool()
def set_text_wrap(item_id: int, mode: str = "BOUNDING_BOX", offsets=None):
    """
    Sets text wrap on any page item.

    Args:
        item_id (int): Page item id.
        mode (str, optional): NONE, BOUNDING_BOX (default), CONTOUR,
            JUMP_OBJECT, NEXT_COLUMN.
        offsets (optional): Wrap offset in POINTS — a single number (uniform)
            or {"top","left","bottom","right"}.
    """
    command = createCommand("setTextWrap", {
        "itemId": item_id, "mode": mode, "offsets": offsets
    })
    return sendCommand(command)


@mcp.tool()
def create_anchored_object(story_id: int, character_index: int = None,
                           type: str = "TEXT_FRAME", width: float = 100,
                           height: float = 100, contents: str = None,
                           position: str = "INLINE", y_offset: float = None):
    """
    Creates an object anchored into text so it travels with its reference.

    Args:
        story_id (int): Story to anchor into.
        character_index (int, optional): Insertion point index (0-based);
            defaults to the story end.
        type (str, optional): TEXT_FRAME (default) or RECTANGLE.
        width / height (float, optional): Object size in POINTS.
        contents (str, optional): Text contents (TEXT_FRAME only).
        position (str, optional): INLINE (default), ABOVE_LINE, or ANCHORED
            (custom/floating).
        y_offset (float, optional): Vertical offset for INLINE position.
    """
    command = createCommand("createAnchoredObject", {
        "storyId": story_id, "characterIndex": character_index,
        "type": type, "width": width, "height": height,
        "contents": contents, "position": position, "yOffset": y_offset
    })
    return sendCommand(command)


@mcp.tool()
def insert_special_character(story_id: int, character: str,
                             position: str = "end"):
    """
    Inserts an InDesign special character into a story.

    Args:
        story_id (int): Target story.
        character (str): SpecialCharacters enum name, e.g. AUTO_PAGE_NUMBER,
            NEXT_PAGE_NUMBER, SECTION_MARKER, BULLET_CHARACTER, EM_DASH,
            EN_DASH, EM_SPACE, EN_SPACE, COLUMN_BREAK, FRAME_BREAK,
            PAGE_BREAK. (An invalid name returns the full valid list.)
        position (str, optional): "start", "end" (default), or a 0-based
            insertion point index as a string.
    """
    command = createCommand("insertSpecialCharacter", {
        "storyId": story_id, "character": character, "position": position
    })
    return sendCommand(command)


@mcp.tool()
def set_bullets_numbering(list_type: str = "BULLETS", style_name: str = None,
                          story_id: int = None, start_paragraph: int = None,
                          end_paragraph: int = None,
                          numbering_expression: str = None,
                          restart_numbering: bool = None,
                          left_indent: float = None,
                          first_line_indent: float = None):
    """
    Sets bulleted/numbered list formatting on a paragraph style (style_name)
    OR a story / paragraph range.

    Args:
        list_type (str): BULLETS, NUMBERS, or NONE.
        numbering_expression (str, optional): For NUMBERS, e.g. "^#.^t".
        restart_numbering (bool, optional): Restart numbering at this range.
        left_indent / first_line_indent (float, optional): POINTS; a hanging
            indent is typically left_indent=18, first_line_indent=-18.
    """
    command = createCommand("setBulletsNumbering", {
        "listType": list_type, "styleName": style_name, "storyId": story_id,
        "startParagraph": start_paragraph, "endParagraph": end_paragraph,
        "numberingExpression": numbering_expression,
        "restartNumbering": restart_numbering, "leftIndent": left_indent,
        "firstLineIndent": first_line_indent
    })
    return sendCommand(command)


@mcp.tool()
def set_drop_cap(lines: int = 3, characters: int = 1,
                 character_style: str = None, style_name: str = None,
                 story_id: int = None, start_paragraph: int = None,
                 end_paragraph: int = None):
    """
    Sets a drop cap on a paragraph style (style_name) OR a story / paragraph
    range: number of lines tall, number of characters, optional character
    style applied to the dropped characters.
    """
    command = createCommand("setDropCap", {
        "lines": lines, "characters": characters,
        "characterStyle": character_style, "styleName": style_name,
        "storyId": story_id, "startParagraph": start_paragraph,
        "endParagraph": end_paragraph
    })
    return sendCommand(command)


@mcp.tool()
def set_hyphenation_justification(style_name: str = None, story_id: int = None,
                                  start_paragraph: int = None,
                                  end_paragraph: int = None,
                                  hyphenation: bool = None,
                                  hyphenate_words_longer_than: int = None,
                                  hyphenation_zone: float = None,
                                  hyphen_ladder_limit: int = None,
                                  hyphenate_capitalized_words: bool = None,
                                  minimum_word_spacing: float = None,
                                  desired_word_spacing: float = None,
                                  maximum_word_spacing: float = None,
                                  minimum_letter_spacing: float = None,
                                  desired_letter_spacing: float = None,
                                  maximum_letter_spacing: float = None,
                                  single_word_justification: str = None):
    """
    Fine typesetting controls on a paragraph style (style_name) OR a story /
    paragraph range: hyphenation rules (min word length, zone in points,
    ladder limit, capitalized words) and justification spacing (word/letter
    spacing percentages, e.g. 80/100/133; single_word_justification: LEFT,
    CENTER, RIGHT, JUSTIFY).
    """
    command = createCommand("setHyphenationJustification", {
        "styleName": style_name, "storyId": story_id,
        "startParagraph": start_paragraph, "endParagraph": end_paragraph,
        "hyphenation": hyphenation,
        "hyphenateWordsLongerThan": hyphenate_words_longer_than,
        "hyphenationZone": hyphenation_zone,
        "hyphenLadderLimit": hyphen_ladder_limit,
        "hyphenateCapitalizedWords": hyphenate_capitalized_words,
        "minimumWordSpacing": minimum_word_spacing,
        "desiredWordSpacing": desired_word_spacing,
        "maximumWordSpacing": maximum_word_spacing,
        "minimumLetterSpacing": minimum_letter_spacing,
        "desiredLetterSpacing": desired_letter_spacing,
        "maximumLetterSpacing": maximum_letter_spacing,
        "singleWordJustification": single_word_justification
    })
    return sendCommand(command)


# ---------------------------------------------------------------------------
# Long-document tools (Phase 3)
# ---------------------------------------------------------------------------

@mcp.tool()
def create_toc(entries: list, title: str = "Contents", page_number: int = 1,
               place_point: dict = None, replace_existing: bool = True):
    """
    Builds (or rebuilds) a table of contents from paragraph styles and places
    the TOC story on a page.

    Args:
        entries (list): Which styles to gather, at which levels:
            [{"styleName": "Headline", "level": 1},
             {"styleName": "Subhead", "level": 2}]
        title (str, optional): TOC title text. Defaults to "Contents".
        page_number (int, optional): 1-based page to place the TOC on.
        place_point (dict, optional): {"x": x, "y": y} in POINTS for the TOC
            frame's top-left. Defaults to {"x": 48, "y": 48}.
        replace_existing (bool, optional): Update an existing TOC in place.

    Returns the TOC story id, frames, and overset state.
    """
    command = createCommand("createToc", {
        "entries": entries, "title": title, "pageNumber": page_number,
        "placePoint": place_point, "replaceExisting": replace_existing
    })
    return sendCommand(command)


@mcp.tool()
def add_section(page_number: int, start_at: int = None, style: str = None,
                prefix: str = None, include_prefix: bool = None,
                marker: str = None, continue_numbering: bool = False):
    """
    Starts a numbering section at a page — the full version of
    set_page_numbering: adds section prefix (e.g. "A-"), whether the prefix
    shows in page numbers, and the section marker text (shown wherever a
    SECTION_MARKER special character is inserted).

    Style: ARABIC, LOWER_ROMAN, UPPER_ROMAN, LOWER_LETTERS, UPPER_LETTERS.
    NOTE: section numbering changes page NAMES ("1" may become "x" or "A-1");
    1-based positional page numbers in this API stay stable.
    """
    command = createCommand("addSection", {
        "pageNumber": page_number, "startAt": start_at, "style": style,
        "prefix": prefix, "includePrefix": include_prefix, "marker": marker,
        "continueNumbering": continue_numbering
    })
    return sendCommand(command)


@mcp.tool()
def create_hyperlink(url: str = None, to_page_number: int = None,
                     story_id: int = None, start_character: int = None,
                     end_character: int = None, item_id: int = None,
                     name: str = None):
    """
    Creates a hyperlink for interactive PDF/EPUB. Destination: url OR
    to_page_number. Source: a text range (story_id + start/end_character,
    0-based inclusive) OR a page item (item_id).
    """
    command = createCommand("createHyperlink", {
        "url": url, "toPageNumber": to_page_number, "storyId": story_id,
        "startCharacter": start_character, "endCharacter": end_character,
        "itemId": item_id, "name": name
    })
    return sendCommand(command)


@mcp.tool()
def create_bookmark(page_number: int, name: str = None,
                    parent_bookmark: str = None):
    """
    Creates a PDF bookmark pointing at a page. parent_bookmark (a bookmark
    name) nests this one under it.
    """
    command = createCommand("createBookmark", {
        "pageNumber": page_number, "name": name,
        "parentBookmark": parent_bookmark
    })
    return sendCommand(command)


@mcp.tool()
def create_cross_reference(source_story_id: int, destination_story_id: int,
                           destination_paragraph: int = 0,
                           source_character_index: int = None,
                           format: str = "Page Number", name: str = None):
    """
    Inserts a live cross-reference ("see page X") that updates automatically.

    Args:
        source_story_id (int): Story where the reference text is inserted.
        source_character_index (int, optional): Insertion point (0-based);
            defaults to the story start.
        destination_story_id (int): Story containing the target paragraph.
        destination_paragraph (int, optional): 0-based paragraph index.
        format (str, optional): Cross-reference format name, e.g.
            "Page Number", "Paragraph Text & Page Number". An invalid name
            returns the available list.
    """
    command = createCommand("createCrossReference", {
        "sourceStoryId": source_story_id,
        "sourceCharacterIndex": source_character_index,
        "destinationStoryId": destination_story_id,
        "destinationParagraph": destination_paragraph,
        "format": format, "name": name
    })
    return sendCommand(command)


@mcp.tool()
def add_index_entry(term: str, story_id: int, character_index: int = None,
                    sub_term: str = None):
    """
    Adds an index topic (and optional sub-topic) with a page reference at a
    text location. Topics are reused if they already exist.
    """
    command = createCommand("addIndexEntry", {
        "term": term, "storyId": story_id,
        "characterIndex": character_index, "subTerm": sub_term
    })
    return sendCommand(command)


@mcp.tool()
def generate_index(page_number: int = None, place_point: dict = None):
    """
    Generates (places) the index story from all entries added with
    add_index_entry. Defaults to the last page at {"x": 48, "y": 48}.
    """
    command = createCommand("generateIndex", {
        "pageNumber": page_number, "placePoint": place_point
    })
    return sendCommand(command)


@mcp.tool()
def create_book(file_path: str):
    """
    Creates a new .indb book file for multi-document publications.
    (Feature-detected: returns a clean error if the Books API is not exposed
    in this InDesign UXP build.)
    """
    command = createCommand("createBook", {"filePath": file_path})
    return sendCommand(command)


@mcp.tool()
def manage_book(action: str, book_name: str = None, document_path: str = None,
                style_source_index: int = None, output_path: str = None):
    """
    Operates on an open book. Actions: ADD_DOCUMENT (document_path),
    SYNCHRONIZE (styles across the book; optional style_source_index),
    EXPORT_PDF (output_path — may exceed the proxy timeout; timeout is not
    failure), SAVE, LIST.
    """
    command = createCommand("manageBook", {
        "action": action, "bookName": book_name,
        "documentPath": document_path, "styleSourceIndex": style_source_index,
        "outputPath": output_path
    })
    return sendCommand(command)


# ---------------------------------------------------------------------------
# Data merge & templates (Phase 3)
# ---------------------------------------------------------------------------

@mcp.tool()
def set_data_merge_source(file_path: str):
    """
    Attaches a CSV/TXT data source to the active document for data merge.
    Returns the field names found. (Feature-detected — clean error if data
    merge is not exposed in this UXP build.)
    """
    command = createCommand("setDataMergeSource", {"filePath": file_path})
    return sendCommand(command)


@mcp.tool()
def place_merge_field(field_name: str, story_id: int,
                      character_index: int = None):
    """
    Inserts a data merge field placeholder into a story (at character_index,
    default story end). Requires set_data_merge_source first.
    """
    command = createCommand("placeMergeField", {
        "fieldName": field_name, "storyId": story_id,
        "characterIndex": character_index
    })
    return sendCommand(command)


@mcp.tool()
def merge_records(record_number: int = None):
    """
    Executes the data merge into a NEW document (all records, or one record
    if record_number given). The merged document becomes active — AI-driven
    certificates, badges, catalogs from a spreadsheet.
    """
    command = createCommand("mergeRecords", {"recordNumber": record_number})
    return sendCommand(command)


@mcp.tool()
def open_as_template(file_path: str):
    """
    Opens an .indd/.indt file as an untitled copy, leaving the original
    untouched — the start of every fill-a-template workflow.
    """
    command = createCommand("openAsTemplate", {"filePath": file_path})
    return sendCommand(command)


@mcp.tool()
def populate_template(content_map: dict, fit_option: str = "FILL_PROPORTIONALLY"):
    """
    The one-shot template filler: fills NAMED frames in the active document.

    Args:
        content_map (dict): Keys are frame names (set in the Layers panel or
            via set_layer_properties/item names); values are text strings or
            {"imagePath": "C:/path/img.png"} for image frames.
        fit_option (str, optional): Image fitting — PROPORTIONALLY,
            FILL_PROPORTIONALLY (default), CONTENT_TO_FRAME, CENTER_CONTENT.

    Returns per-frame status (TEXT_SET + overset flag, IMAGE_PLACED,
    NOT_FOUND) plus all available frame names so misses can be corrected.
    """
    command = createCommand("populateTemplate", {
        "contentMap": content_map, "fitOption": fit_option
    })
    return sendCommand(command)


@mcp.tool()
def save_snippet(item_id: int, file_path: str):
    """
    Exports a page item (or group) as a reusable .idms snippet file.
    """
    command = createCommand("saveSnippet", {
        "itemId": item_id, "filePath": file_path
    })
    return sendCommand(command)


@mcp.tool()
def place_snippet(file_path: str, page_number: int = 1, position: dict = None):
    """
    Places a .idms snippet onto a page, optionally moving it so its top-left
    lands at position {"x": x, "y": y} (POINTS). Returns the new item ids.
    """
    command = createCommand("placeSnippet", {
        "filePath": file_path, "pageNumber": page_number, "position": position
    })
    return sendCommand(command)


# ---------------------------------------------------------------------------
# Export & preflight (Phase 3)
# ---------------------------------------------------------------------------

@mcp.tool()
def export_pdf_advanced(file_path: str, preset_name: str = None,
                        page_range: str = None, interactive: bool = False,
                        security: dict = None, properties: dict = None):
    """
    Full-control PDF export.

    Args:
        file_path (str): Output .pdf path.
        preset_name (str, optional): PDF preset (see list_export_presets).
        page_range (str, optional): e.g. "1-3" or "2, 4-6". Default all.
        interactive (bool, optional): Export interactive PDF (hyperlinks,
            bookmarks live) instead of print PDF.
        security (dict, optional): {"openPassword": "...",
            "permissionsPassword": "..."}.
        properties (dict, optional): ADVANCED — extra pdfExportPreferences DOM
            properties set verbatim (unknown ones are reported as skipped,
            not fatal).

    IMPORTANT: big documents exceed the 20s proxy timeout — a timeout does
    NOT mean failure; check the output file before retrying.
    """
    command = createCommand("exportPdfAdvanced", {
        "filePath": file_path, "presetName": preset_name,
        "pageRange": page_range, "interactive": interactive,
        "security": security, "properties": properties
    })
    return sendCommand(command)


@mcp.tool()
def export_idml(file_path: str):
    """
    Exports the active document as IDML — the interchange/downgrade format
    older InDesign versions can open.
    """
    command = createCommand("exportIdml", {"filePath": file_path})
    return sendCommand(command)


@mcp.tool()
def export_epub(file_path: str, fixed_layout: bool = False):
    """
    Exports the active document as an EPUB e-book (reflowable by default,
    fixed-layout with fixed_layout=True). Routinely exceeds the proxy
    timeout — timeout is not failure; check the output file.
    """
    command = createCommand("exportEpub", {
        "filePath": file_path, "fixedLayout": fixed_layout
    })
    return sendCommand(command)


@mcp.tool()
def export_pages_as_images(output_folder: str, base_name: str = "page",
                           format: str = "PNG", resolution: int = 150,
                           start_page: int = None, end_page: int = None,
                           quality: str = None):
    """
    Batch-exports a page range as numbered PNG or JPEG files
    (<base_name>_001.png ...). quality (JPEG only): LOW, MEDIUM, HIGH,
    MAXIMUM. Long ranges can exceed the proxy timeout.
    """
    command = createCommand("exportPagesAsImages", {
        "outputFolder": output_folder, "baseName": base_name,
        "format": format, "resolution": resolution,
        "startPage": start_page, "endPage": end_page, "quality": quality
    })
    return sendCommand(command)


@mcp.tool()
def package_document(output_folder: str, include_idml: bool = False,
                     include_pdf: bool = False, pdf_preset_name: str = None):
    """
    Packages the document for print handoff: collects fonts, linked graphics,
    profiles, and a report into output_folder (optionally with IDML and PDF).
    The document must be saved first. Packaging exceeds the proxy timeout on
    real documents — timeout is not failure.
    """
    command = createCommand("packageDocument", {
        "outputFolder": output_folder, "includeIdml": include_idml,
        "includePdf": include_pdf, "pdfPresetName": pdf_preset_name
    })
    return sendCommand(command)


@mcp.tool()
def define_preflight_profile(name: str, description: str = "",
                             rules: list = None):
    """
    Defines (replaces if existing) a preflight profile.

    Args:
        rules (list): [{"id": "ADBE_MissingFonts"},
                       {"id": "ADBE_ImageResolution",
                        "data": {"min_resolution": 250}}, ...]
            Common rule ids: ADBE_MissingFonts, ADBE_OversetText,
            ADBE_ImageResolution, ADBE_MissingModifiedGraphics, ADBE_Bleed.
            Failed rules are reported, not fatal.
    """
    command = createCommand("definePreflightProfile", {
        "name": name, "description": description, "rules": rules
    })
    return sendCommand(command)


@mcp.tool()
def run_preflight(profile_name: str = None):
    """
    Runs preflight on the active document (with profile_name, or the default
    [Basic] profile) and returns the aggregated error report — use it to find
    and fix overset text, missing fonts/links, low-res images.
    """
    command = createCommand("runPreflight", {"profileName": profile_name})
    return sendCommand(command)


@mcp.tool()
def list_export_presets():
    """
    Lists available PDF export presets (print and interactive) so exports can
    reference them by exact name.
    """
    command = createCommand("listExportPresets", {})
    return sendCommand(command)


# ---------------------------------------------------------------------------
# Geometry & multi-document (Phase 3)
# ---------------------------------------------------------------------------

@mcp.tool()
def align_items(item_ids: list, mode: str, reference: str = "FIRST"):
    """
    Aligns page items. mode: LEFT, RIGHT, TOP, BOTTOM, CENTER_HORIZONTAL,
    CENTER_VERTICAL. reference: FIRST (align to the first item, default) or
    PAGE (align to the first item's page bounds). Returns resulting bounds.
    """
    command = createCommand("alignItems", {
        "itemIds": item_ids, "mode": mode, "reference": reference
    })
    return sendCommand(command)


@mcp.tool()
def distribute_items(item_ids: list, axis: str = "HORIZONTAL",
                     spacing: float = None):
    """
    Distributes items along an axis. With spacing (POINTS): fixed gaps
    stacking from the first item. Without: equal gaps between the first and
    last items' current positions (needs >= 3 items).
    """
    command = createCommand("distributeItems", {
        "itemIds": item_ids, "axis": axis, "spacing": spacing
    })
    return sendCommand(command)


@mcp.tool()
def get_documents():
    """
    Lists all open InDesign documents (name, saved/modified state, page
    count, which is active).
    """
    command = createCommand("getDocuments", {})
    return sendCommand(command)


@mcp.tool()
def set_active_document(name: str):
    """
    Makes the named open document active — all other tools operate on the
    active document. Use get_documents to see what's open.
    """
    command = createCommand("setActiveDocument", {"name": name})
    return sendCommand(command)


@mcp.tool()
def batch_apply_style(grep_find_what: str, character_style_name: str = None,
                      paragraph_style_name: str = None,
                      all_open_documents: bool = False):
    """
    Applies a character/paragraph style to every GREP match across the active
    document or ALL open documents in one call — the cross-document version
    of grep_apply_style. Returns per-document change counts.
    """
    command = createCommand("batchApplyStyle", {
        "grepFindWhat": grep_find_what,
        "characterStyleName": character_style_name,
        "paragraphStyleName": paragraph_style_name,
        "allOpenDocuments": all_open_documents
    })
    return sendCommand(command)


# ---------------------------------------------------------------------------
# Action sequences (Phase 3 — ported from ps-mcp.py)
# ---------------------------------------------------------------------------

# operation name -> (UXP action, key that receives the target id)
ID_BATCH_OPERATIONS = {
    "apply_paragraph_style": ("applyParagraphStyle", "storyId"),
    "apply_character_style": ("applyCharacterStyle", "storyId"),
    "style_text_range": ("styleTextRange", "storyId"),
    "set_text_color": ("setTextColor", "storyId"),
    "set_drop_cap": ("setDropCap", "storyId"),
    "set_bullets_numbering": ("setBulletsNumbering", "storyId"),
    "set_hyphenation_justification": ("setHyphenationJustification", "storyId"),
    "change_grep": ("changeGrep", "storyId"),
    "insert_special_character": ("insertSpecialCharacter", "storyId"),
    "set_text_frame_options": ("setTextFrameOptions", "frameId"),
    "apply_object_style": ("applyObjectStyle", "itemId"),
    "set_item_appearance": ("setItemAppearance", "itemId"),
    "transform_item": ("transformItem", "itemId"),
    "duplicate_item": ("duplicateItem", "itemId"),
    "set_text_wrap": ("setTextWrap", "itemId"),
}

ID_SEQUENCES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "id_action_sequences.json")


def _load_sequences() -> dict:
    try:
        with open(ID_SEQUENCES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_sequences(sequences: dict):
    with open(ID_SEQUENCES_FILE, "w", encoding="utf-8") as f:
        json.dump(sequences, f, indent=2)


def _validate_operations(operations: list):
    for i, step in enumerate(operations):
        if not isinstance(step, dict) or "operation" not in step:
            raise ValueError(f"Step {i} must be a dict with an 'operation' key")
        if step["operation"] not in ID_BATCH_OPERATIONS:
            raise ValueError(
                f"Step {i}: unknown operation '{step['operation']}'. "
                f"Valid operations: {', '.join(sorted(ID_BATCH_OPERATIONS))}"
            )


@mcp.tool()
def create_action_sequence(sequence_name: str, operations: list,
                           description: str = ""):
    """
    Saves a named, reusable sequence of operations to replay against one or
    more targets (stories/items) with play_action_sequence. Persists across
    server restarts; same name overwrites. ONE tool call replays the whole
    recipe — much faster than call-per-step.

    Args:
        operations (list): Ordered steps: [{"operation": "<name>",
            "settings": {...}}] using the same camelCase option keys as the
            corresponding single tool (target id excluded — injected on
            replay). Valid operations: apply_paragraph_style,
            apply_character_style, style_text_range, set_text_color,
            set_drop_cap, set_bullets_numbering,
            set_hyphenation_justification, change_grep,
            insert_special_character, set_text_frame_options,
            apply_object_style, set_item_appearance, transform_item,
            duplicate_item, set_text_wrap.
    """
    _validate_operations(operations)
    sequences = _load_sequences()
    sequences[sequence_name] = {
        "description": description,
        "operations": operations,
    }
    _save_sequences(sequences)
    return {"saved": sequence_name, "steps": len(operations)}


@mcp.tool()
def play_action_sequence(sequence_name: str, target_ids: list):
    """
    Replays a saved sequence against each target id in order. The target id
    is injected as storyId/frameId/itemId depending on each operation — so a
    sequence should target ONE kind of object (all-story ops or all-item
    ops). Per-step errors are recorded and processing continues; a lost
    connection aborts and marks the rest SKIPPED.
    """
    sequences = _load_sequences()
    if sequence_name not in sequences:
        raise ValueError(
            f"No sequence named '{sequence_name}'. "
            f"Available: {', '.join(sorted(sequences)) or '(none)'}"
        )
    operations = sequences[sequence_name]["operations"]

    results = []
    aborted = False
    for target_id in target_ids:
        if aborted:
            results.append({"targetId": target_id, "status": "SKIPPED",
                            "error": "Skipped: connection to InDesign lost"})
            continue
        step_results = []
        for step in operations:
            action, key = ID_BATCH_OPERATIONS[step["operation"]]
            options = dict(step.get("settings") or {})
            options[key] = target_id
            try:
                response = sendCommand(createCommand(action, options))
                step_results.append({"operation": step["operation"],
                                     "status": "SUCCESS"})
            except socket_client.AppError as e:
                step_results.append({"operation": step["operation"],
                                     "status": "FAILURE", "error": str(e)})
            except RuntimeError as e:
                step_results.append({"operation": step["operation"],
                                     "status": "FAILURE", "error": str(e)})
                aborted = True
                break
        results.append({"targetId": target_id, "steps": step_results})

    return {"sequence": sequence_name, "results": results}


@mcp.tool()
def list_action_sequences():
    """
    Lists saved action sequences with their descriptions and step counts.
    """
    sequences = _load_sequences()
    return {
        "sequences": [
            {"name": name, "description": seq.get("description", ""),
             "steps": len(seq.get("operations", []))}
            for name, seq in sorted(sequences.items())
        ]
    }


@mcp.tool()
def delete_action_sequence(sequence_name: str):
    """
    Deletes a saved action sequence by name.
    """
    sequences = _load_sequences()
    if sequence_name not in sequences:
        raise ValueError(f"No sequence named '{sequence_name}'")
    del sequences[sequence_name]
    _save_sequences(sequences)
    return {"deleted": sequence_name}


# ---------------------------------------------------------------------------
# Instructions resource
# ---------------------------------------------------------------------------

@mcp.resource("config://get_instructions")
def get_instructions() -> str:
    """Read this first! Returns information and instructions on how to use InDesign and this API"""

    return f"""
    You are an InDesign and page-layout expert who is creative and loves to help other people learn to use InDesign and create.

    Rules to follow:

    1. Think deeply about how to solve the task
    2. Always check your work — visually, with get_page_image
    3. Read the info for the API calls to make sure you understand the requirements and arguments

    Core concepts of this API:

    - UNITS: everything is in POINTS (1 pt = 1/72 inch) unless a tool says otherwise.
    - BOUNDS: all bounds are {{"top", "left", "bottom", "right"}} objects. InDesign's
      native geometricBounds order is [top, left, bottom, right] (y-first!).
    - PAGES are 1-based in every tool.
    - ITEMS: page items are addressed by numeric id. Call get_document_info first to
      discover ids — it is the keystone read tool.
    - STORIES vs FRAMES: text lives in stories; one story can flow through many
      threaded text frames. Text tools address stories by storyId.
    - OVERSET: every text-mutating tool returns an "overflows" state. If a frame
      overflows, the text does not fit — grow the frame (transform_item), thread a
      new frame (thread_text_frames), or reduce the type size. Never leave a layout
      with overset text.
    - WORKFLOW: get_document_info → make changes → get_page_image to verify → iterate.
    - TIMEOUTS: export_pdf on big documents may exceed the proxy timeout; a timeout
      does not mean the export failed. Check the output file before retrying.
    - STYLES (prefer over direct formatting for multi-page work): create styles once,
      apply everywhere; one edit_style_property call restyles the whole document.
      list_styles is the read half of the round-trip.
    - GREP: change_grep is the bulk editor — regex with $1 backreferences across the
      whole document in one call. Preview reach with find_grep or find_change_report
      first. grep_apply_style formats matches without changing text.
    - MASTERS: create_master_spread (placeholders incl. AUTO_PAGE_NUMBER markers) →
      apply_master to page ranges → override_master_item for local edits.
    - TABLES: create_table from a 2D array returns storyId + tableIndex — the handle
      for set_cell_contents / merge_cells / apply_table_style (incl. alternating fills).
    - TYPOGRAPHY details: baseline grid + align-to-grid, text wrap, anchored objects,
      special characters (page-number markers, breaks), bullets/numbering, drop caps,
      hyphenation & justification — all target a style OR a story/paragraph range.
    - LONG DOCUMENTS: create_toc gathers paragraph styles into a placed TOC story;
      add_section for numbering/prefixes; hyperlinks/bookmarks/cross-references for
      interactive PDF; add_index_entry + generate_index for indexing.
    - TEMPLATES: open_as_template + populate_template (named frames from a JSON map,
      text or image paths, per-frame overset report) is the fastest fill workflow;
      data merge (set_data_merge_source → place_merge_field → merge_records) for
      CSV-driven batches; snippets for reusable fragments.
    - EXPORT: export_pdf_advanced (presets/ranges/security/interactive), IDML, EPUB,
      export_pages_as_images, package_document. run_preflight and fix what it reports
      BEFORE final export.
    - BATCH: create_action_sequence + play_action_sequence replay recipes across many
      stories/items in fewer calls; batch_apply_style GREP-restyles all open docs;
      align_items/distribute_items for geometry cleanup.
    """
