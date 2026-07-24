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

from mcp.server.fastmcp import FastMCP, Image
from PIL import Image as PILImage

from core import init, sendCommand, createCommand
import socket_client
import sys
import os
import io
import json

# Create an MCP server
mcp_name = "Adobe After Effects MCP Server"
mcp = FastMCP(mcp_name, log_level="ERROR")
print(f"{mcp_name} running on stdio", file=sys.stderr)

APPLICATION = "aftereffects"
PROXY_URL = 'http://localhost:3001'
PROXY_TIMEOUT = 20

socket_client.configure(
    app=APPLICATION, 
    url=PROXY_URL,
    timeout=PROXY_TIMEOUT
)

init(APPLICATION, socket_client)

@mcp.tool()
def execute_extend_script(script_string: str):
    """
    Executes arbitrary ExtendScript code in AfterEffects and returns the result.

    The script should use 'return' to send data back. The result will be automatically
    JSON stringified. If the script throws an error, it will be caught and returned
    as an error object.

    Args:
        script_string (str): The ExtendScript code to execute. Must use 'return' to 
                           send results back.

    Returns:
        any: The result returned from the ExtendScript, or an error object containing:
            - error (str): Error message
            - line (str): Line number where error occurred

    Example:
        script = '''
            var doc = app.activeDocument;
            return {
                name: doc.name,
                path: doc.fullName.fsName,
                layers: doc.layers.length
            };
        '''
        result = execute_extend_script(script)
    """
    command = createCommand("executeExtendScript", {
        "scriptString": script_string
    })
    return sendCommand(command)

@mcp.resource("config://get_instructions")
def get_instructions() -> str:
    """Read this first! Returns information and instructions on how to use AfterEffects and this API"""

    return f"""
    You are an Adobe After Effects expert driving AE through this server's
    typed tools. Read this before calling anything.

    THE TOOL MODEL

    1. Read first, then mutate. get_project_info is the health check -
       call it at session start; if it fails, fix the environment before
       anything else. get_composition_details is THE keystone read: the
       full layer tree with types, switches, timing, parenting, transforms,
       and applied effects. Call it before and after layer mutations.
    2. Addressing: project items (comps, footage, folders) are addressed
       by their permanent numeric id. LAYERS are addressed by
       (comp_id, layer_index) where layer_index is 1-BASED and SHIFTS
       whenever layers are added, removed, or reordered - new layers land
       at index 1 (top of stack). After any structural change, re-read
       get_composition_details before making further layer_index-based
       calls; stale indices silently hit the wrong layer.
    3. Times are in SECONDS everywhere (comp durations, layer
       start/in/out, markers, frame renders).
    4. Properties and effects are identified by matchName (e.g.
       "ADBE Transform Group", "ADBE Position") - stable across AE
       versions and locales, unlike display names.
    5. One tool call = one undo step, named "MCP: ..." in the Edit menu.
       Partial-update tools (set_layer_properties, set_layer_transform,
       set_layer_times, set_composition_settings) only touch the
       arguments you pass; everything omitted is left as-is.
    6. set_layer_transform refuses properties that already have keyframes
       (they come back in skipped[] with an explanation) - animated
       properties belong to the keyframe tools.
    7. get_frame_image renders a frame and returns it as an image - use
       it as the visual feedback loop to verify your work.
    8. execute_extend_script is the escape hatch for anything without a
       typed tool. Prefer typed tools: they guard against modal dialogs
       and return structured errors. Scripts must use 'return' and never
       trigger UI dialogs (a modal hangs the whole bridge).
    """



# AfterEffectsd Blend Modes (for future use)
BLEND_MODES = [
    "ADD",
    "ALPHA_ADD",
    "CLASSIC_COLOR_BURN",
    "CLASSIC_COLOR_DODGE",
    "CLASSIC_DIFFERENCE",
    "COLOR",
    "COLOR_BURN",
    "COLOR_DODGE",
    "DANCING_DISSOLVE",
    "DARKEN",
    "DARKER_COLOR",
    "DIFFERENCE",
    "DISSOLVE",
    "EXCLUSION",
    "HARD_LIGHT",
    "HARD_MIX",
    "HUE",
    "LIGHTEN",
    "LIGHTER_COLOR",
    "LINEAR_BURN",
    "LINEAR_DODGE",
    "LINEAR_LIGHT",
    "LUMINESCENT_PREMUL",
    "LUMINOSITY",
    "MULTIPLY",
    "NORMAL",
    "OVERLAY",
    "PIN_LIGHT",
    "SATURATION",
    "SCREEN",
    "SILHOUETE_ALPHA",
    "SILHOUETTE_LUMA",
    "SOFT_LIGHT",
    "STENCIL_ALPHA",
    "STENCIL_LUMA",
    "SUBTRACT",
    "VIVID_LIGHT"
]

# ---------------------------------------------------------------------
# Priority 1: Project & Import Foundation
# ---------------------------------------------------------------------

from typing import Optional


@mcp.tool()
def create_project(force: bool = False):
    """
    Creates a new, empty After Effects project.

    WARNING: this replaces the currently open project. If the current
    project has unsaved changes this call fails unless force=True is
    passed (in which case changes are silently discarded). Save first
    if in doubt.

    Args:
        force (bool): If True, discard unsaved changes in the current
            project. Default False (safer).
    """
    command = createCommand("createProject", {
        "force": force
    })
    return sendCommand(command)


@mcp.tool()
def open_project(path: str, force: bool = False):
    """
    Opens an existing After Effects project file (.aep).

    If the currently open project has unsaved changes this call fails
    unless force=True is passed (in which case changes are silently
    discarded).

    Args:
        path (str): Absolute filesystem path to the .aep file.
        force (bool): If True, discard unsaved changes in the current
            project. Default False (safer).
    """
    command = createCommand("openProject", {
        "path": path,
        "force": force
    })
    return sendCommand(command)


@mcp.tool()
def save_project():
    """
    Saves the currently open project to its existing file location.
    Fails with a clear error if the project has never been saved
    (no file path yet) - use save_project_as in that case.
    """
    command = createCommand("saveProject", {})
    return sendCommand(command)


@mcp.tool()
def save_project_as(path: str):
    """
    Saves the currently open project to a new file path (Save As).
    Subsequent save_project calls target this new path.

    Args:
        path (str): Absolute filesystem path to save the .aep file to.
    """
    command = createCommand("saveProjectAs", {
        "path": path
    })
    return sendCommand(command)


@mcp.tool()
def get_project_info():
    """
    Returns a full inventory of the currently open project - THE health
    check tool. Call this before trusting any other tool in a session.

    Returns: project name, file path (or null if unsaved), dirty flag
    (unsaved changes), and a flat list of every project item
    (Composition / Footage / Folder) with id, name, type, and
    parentFolderId. These ids are the namespace all other tools
    (import_file, move_items_to_folder, and later composition tools)
    operate on.
    """
    command = createCommand("getProjectInfo", {})
    return sendCommand(command)


@mcp.tool()
def get_compositions():
    """
    Lists all compositions in the project with id, name, width, height,
    duration (seconds), and frameRate.
    """
    command = createCommand("getCompositions", {})
    return sendCommand(command)


@mcp.tool()
def import_file(path: str, folder_id: Optional[int] = None):
    """
    Imports a footage file (video, image, or audio) into the project.

    Args:
        path (str): Absolute filesystem path to the file to import.
        folder_id (int, optional): If provided, the imported item is
            filed into this project folder (id from get_project_info or
            create_project_folder). Omit to import into the project root.
    """
    command = createCommand("importFile", {
        "path": path,
        "folderId": folder_id
    })
    return sendCommand(command)


@mcp.tool()
def import_image_sequence(path: str, folder_id: Optional[int] = None):
    """
    Imports a numbered image sequence (e.g. frame_0001.png ...) as a
    single footage item.

    Args:
        path (str): Absolute path to the FIRST file in the sequence -
            AE detects and imports the rest of the numbered series.
        folder_id (int, optional): Project folder to file the item into.
            Omit to import into the project root.
    """
    command = createCommand("importImageSequence", {
        "path": path,
        "folderId": folder_id
    })
    return sendCommand(command)


@mcp.tool()
def create_project_folder(name: str, parent_folder_id: Optional[int] = None):
    """
    Creates a new folder in the Project panel.

    Args:
        name (str): Folder display name.
        parent_folder_id (int, optional): id of an existing folder to
            nest this one inside. Omit to create at the project root.
    """
    command = createCommand("createProjectFolder", {
        "name": name,
        "parentFolderId": parent_folder_id
    })
    return sendCommand(command)


@mcp.tool()
def move_items_to_folder(item_ids: list[int], folder_id: Optional[int] = None):
    """
    Moves one or more project items (comps, footage, or folders) into a
    folder in a single batch call (one undo step).

    Args:
        item_ids (list[int]): ids of the items to move (from
            get_project_info, import_file, etc.).
        folder_id (int, optional): Destination folder id. Omit to move
            the items to the project ROOT, out of any folder.
    """
    command = createCommand("moveItemsToFolder", {
        "itemIds": item_ids,
        "folderId": folder_id
    })
    return sendCommand(command)


# ---------------------------------------------------------------------
# Priority 2: Compositions & Visual Feedback
# ---------------------------------------------------------------------


@mcp.tool()
def create_composition(name: str, width: int = 1920, height: int = 1080,
                       duration_seconds: float = 10.0, frame_rate: float = 30.0,
                       pixel_aspect: float = 1.0):
    """
    Creates a new composition and opens it in the viewer.

    Args:
        name (str): Composition name.
        width (int): Width in pixels (1-30000).
        height (int): Height in pixels (1-30000).
        duration_seconds (float): Duration in seconds.
        frame_rate (float): Frames per second (e.g. 23.976, 24, 30, 60).
        pixel_aspect (float): Pixel aspect ratio (1.0 = square pixels).
    """
    command = createCommand("createComposition", {
        "name": name,
        "width": width,
        "height": height,
        "durationSeconds": duration_seconds,
        "frameRate": frame_rate,
        "pixelAspect": pixel_aspect
    })
    return sendCommand(command)


@mcp.tool()
def get_composition_details(comp_id: int):
    """
    THE keystone read tool. Returns the full state of a composition:
    settings (size, duration, frameRate, bgColor, work area) and the
    complete layer tree - for each layer: index, name, type
    (AV/Text/Shape/Camera/Light/Null), source item id, switches
    (enabled/solo/shy/locked/3D/audio), timing (startTime/in/out),
    parenting (parentIndex), transform values (anchorPoint, position,
    scale, rotation incl. X/Y for 3D, opacity), and applied effects
    (index, matchName, name, enabled).

    Call this before and after any layer mutation - the AI cannot
    animate what it cannot see.

    Args:
        comp_id (int): Composition id (from get_project_info,
            get_compositions, or create_composition).
    """
    command = createCommand("getCompositionDetails", {
        "compId": comp_id
    })
    return sendCommand(command)


@mcp.tool()
def get_frame_image(comp_id: int, time_seconds: float = 0.0):
    """
    Renders a single frame of a composition at the given time and
    returns it as an image - the visual feedback loop. Time is clamped
    to the composition's duration.

    Args:
        comp_id (int): Composition id.
        time_seconds (float): Time in seconds of the frame to render.
    """
    command = createCommand("getFrameImage", {
        "compId": comp_id,
        "timeSeconds": time_seconds
    })
    result = sendCommand(command)

    if not result.get("status") == "SUCCESS":
        return result

    # The panel wraps handler output in a content packet:
    # response = {"content": [{"type": "text", "text": "<json>"}]}
    try:
        payload = json.loads(result["response"]["content"][0]["text"])
    except (KeyError, IndexError, TypeError, ValueError):
        return result

    if not isinstance(payload, dict) or payload.get("success") is not True:
        return result

    file_path = payload["path"]

    with open(file_path, 'rb') as f:
        png_image = PILImage.open(f)

        # Convert to RGB if necessary (removes alpha channel)
        if png_image.mode in ("RGBA", "LA", "P"):
            rgb_image = PILImage.new("RGB", png_image.size, (255, 255, 255))
            rgb_image.paste(png_image, mask=png_image.split()[-1] if png_image.mode == "RGBA" else None)
            png_image = rgb_image

        # Save as JPEG to bytes buffer
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
def open_composition(comp_id: int):
    """
    Opens a composition in the viewer, making it the active item.

    Args:
        comp_id (int): Composition id.
    """
    command = createCommand("openComposition", {
        "compId": comp_id
    })
    return sendCommand(command)


@mcp.tool()
def set_composition_settings(comp_id: int,
                             name: Optional[str] = None,
                             width: Optional[int] = None,
                             height: Optional[int] = None,
                             duration_seconds: Optional[float] = None,
                             frame_rate: Optional[float] = None,
                             bg_color: Optional[list[float]] = None):
    """
    Updates composition settings. Only the arguments you provide are
    changed; omitted arguments are left untouched.

    Args:
        comp_id (int): Composition id.
        name (str, optional): New composition name.
        width (int, optional): New width in pixels.
        height (int, optional): New height in pixels.
        duration_seconds (float, optional): New duration in seconds.
        frame_rate (float, optional): New frame rate.
        bg_color (list[float], optional): Background color as [r, g, b]
            with each channel 0.0-1.0.
    """
    options = {"compId": comp_id}
    if name is not None:
        options["name"] = name
    if width is not None:
        options["width"] = width
    if height is not None:
        options["height"] = height
    if duration_seconds is not None:
        options["durationSeconds"] = duration_seconds
    if frame_rate is not None:
        options["frameRate"] = frame_rate
    if bg_color is not None:
        options["bgColor"] = bg_color
    command = createCommand("setCompositionSettings", options)
    return sendCommand(command)


@mcp.tool()
def set_work_area(comp_id: int, start_seconds: float, duration_seconds: float):
    """
    Sets a composition's work area (the preview/render span).

    Args:
        comp_id (int): Composition id.
        start_seconds (float): Work area start time in seconds.
        duration_seconds (float): Work area duration in seconds.
    """
    command = createCommand("setWorkArea", {
        "compId": comp_id,
        "startSeconds": start_seconds,
        "durationSeconds": duration_seconds
    })
    return sendCommand(command)


@mcp.tool()
def add_composition_marker(comp_id: int, time_seconds: float, comment: str,
                           duration_seconds: Optional[float] = None):
    """
    Adds a marker to a composition's timeline.

    Args:
        comp_id (int): Composition id.
        time_seconds (float): Marker time in seconds.
        comment (str): Marker comment text.
        duration_seconds (float, optional): Marker duration in seconds
            for a ranged marker. Omit for a point marker.
    """
    command = createCommand("addCompositionMarker", {
        "compId": comp_id,
        "timeSeconds": time_seconds,
        "comment": comment,
        "durationSeconds": duration_seconds
    })
    return sendCommand(command)

# ---------------------------------------------------------------------
# Priority 3: The Layer System
# ---------------------------------------------------------------------
# Layer addressing: (comp_id, layer_index). AE layer indices are 1-based
# and SHIFT when layers are added/removed/reordered - re-read
# get_composition_details after structural changes before further
# layer_index-based calls.


@mcp.tool()
def add_solid_layer(comp_id: int, name: str,
                    color: list[float] = [1.0, 1.0, 1.0],
                    width: Optional[int] = None, height: Optional[int] = None,
                    duration_seconds: Optional[float] = None):
    """
    Adds a solid color layer to a composition (lands at top, index 1).

    Args:
        comp_id (int): Composition id.
        name (str): Layer/solid name.
        color (list[float]): [r, g, b], each 0.0-1.0. Default white.
        width (int, optional): Solid width. Defaults to comp width.
        height (int, optional): Solid height. Defaults to comp height.
        duration_seconds (float, optional): Defaults to comp duration.
    """
    command = createCommand("addSolidLayer", {
        "compId": comp_id, "name": name, "color": color,
        "width": width, "height": height,
        "durationSeconds": duration_seconds
    })
    return sendCommand(command)


@mcp.tool()
def add_text_layer(comp_id: int, text: str):
    """
    Adds a text layer with the given source text (lands at top, index 1).
    Styling (font, size, color) comes with the Phase 2 text tools.

    Args:
        comp_id (int): Composition id.
        text (str): The text content.
    """
    command = createCommand("addTextLayer", {
        "compId": comp_id, "text": text
    })
    return sendCommand(command)


@mcp.tool()
def add_null_layer(comp_id: int, name: Optional[str] = None,
                   duration_seconds: Optional[float] = None):
    """
    Adds a null object layer - the standard rigging anchor to parent
    other layers to (see set_layer_parent).

    Args:
        comp_id (int): Composition id.
        name (str, optional): Rename the null (default "Null N").
        duration_seconds (float, optional): Defaults to comp duration.
    """
    command = createCommand("addNullLayer", {
        "compId": comp_id, "name": name,
        "durationSeconds": duration_seconds
    })
    return sendCommand(command)


@mcp.tool()
def add_adjustment_layer(comp_id: int, name: str):
    """
    Adds a comp-sized adjustment layer - effects applied to it affect
    all layers below it.

    Args:
        comp_id (int): Composition id.
        name (str): Layer name.
    """
    command = createCommand("addAdjustmentLayer", {
        "compId": comp_id, "name": name
    })
    return sendCommand(command)


@mcp.tool()
def add_shape_layer(comp_id: int, name: Optional[str] = None):
    """
    Adds an empty shape layer. Shape contents (rectangles, ellipses,
    paths, fills, strokes) come with the Phase 2 shape tools.

    Args:
        comp_id (int): Composition id.
        name (str, optional): Layer name.
    """
    command = createCommand("addShapeLayer", {
        "compId": comp_id, "name": name
    })
    return sendCommand(command)


@mcp.tool()
def add_footage_layer(comp_id: int, item_id: int,
                      duration_seconds: Optional[float] = None):
    """
    Adds a project item (imported footage, image, audio, or another
    composition) as a layer in a composition.

    Args:
        comp_id (int): Target composition id.
        item_id (int): Project item id (from get_project_info /
            import_file / get_compositions). Adding a comp creates a
            nested comp layer.
        duration_seconds (float, optional): For still images, the layer
            duration. Omit for footage default.
    """
    command = createCommand("addFootageLayer", {
        "compId": comp_id, "itemId": item_id,
        "durationSeconds": duration_seconds
    })
    return sendCommand(command)


@mcp.tool()
def add_camera_layer(comp_id: int, name: str,
                     center_point: Optional[list[float]] = None):
    """
    Adds a camera layer. Cameras only affect 3D layers. Camera settings
    (zoom, depth of field) come in Phase 3.

    Args:
        comp_id (int): Composition id.
        name (str): Camera name.
        center_point (list[float], optional): [x, y] point of interest
            in comp space. Defaults to comp center.
    """
    command = createCommand("addCameraLayer", {
        "compId": comp_id, "name": name, "centerPoint": center_point
    })
    return sendCommand(command)


@mcp.tool()
def add_light_layer(comp_id: int, name: str,
                    center_point: Optional[list[float]] = None):
    """
    Adds a light layer. Lights only affect 3D layers. Light settings
    (type, color, intensity) come in Phase 3.

    Args:
        comp_id (int): Composition id.
        name (str): Light name.
        center_point (list[float], optional): [x, y] in comp space.
            Defaults to comp center.
    """
    command = createCommand("addLightLayer", {
        "compId": comp_id, "name": name, "centerPoint": center_point
    })
    return sendCommand(command)


@mcp.tool()
def set_layer_properties(comp_id: int, layer_index: int,
                         name: Optional[str] = None,
                         enabled: Optional[bool] = None,
                         solo: Optional[bool] = None,
                         locked: Optional[bool] = None,
                         shy: Optional[bool] = None):
    """
    Updates layer switches in one call. Only provided arguments are
    changed; omitted arguments are left untouched.

    AE constraint (26.x): solo cannot coexist with a disabled layer.
    solo=True is refused with a clean error unless the layer is enabled
    (or enabled=True is passed in the same call).

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
        name (str, optional): Rename the layer.
        enabled (bool, optional): Video on/off (eyeball).
        solo (bool, optional): Solo switch.
        locked (bool, optional): Lock switch.
        shy (bool, optional): Shy switch.
    """
    options = {"compId": comp_id, "layerIndex": layer_index}
    if name is not None:
        options["name"] = name
    if enabled is not None:
        options["enabled"] = enabled
    if solo is not None:
        options["solo"] = solo
    if locked is not None:
        options["locked"] = locked
    if shy is not None:
        options["shy"] = shy
    command = createCommand("setLayerProperties", options)
    return sendCommand(command)


@mcp.tool()
def delete_layer(comp_id: int, layer_index: int):
    """
    Deletes a layer. Locked layers are refused - unlock first with
    set_layer_properties. Remaining layer indices shift after deletion;
    re-read get_composition_details.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
    """
    command = createCommand("deleteLayer", {
        "compId": comp_id, "layerIndex": layer_index
    })
    return sendCommand(command)


@mcp.tool()
def duplicate_layer(comp_id: int, layer_index: int,
                    name: Optional[str] = None):
    """
    Duplicates a layer (copy lands directly above the original).

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based index of the layer to duplicate.
        name (str, optional): Name for the duplicate.
    """
    command = createCommand("duplicateLayer", {
        "compId": comp_id, "layerIndex": layer_index, "name": name
    })
    return sendCommand(command)


@mcp.tool()
def reorder_layer(comp_id: int, layer_index: int, position: str,
                  target_index: Optional[int] = None):
    """
    Moves a layer in the stacking order. All layer indices shift after
    reordering; re-read get_composition_details.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based index of the layer to move.
        position (str): "before" or "after" (relative to target_index),
            or "top" / "bottom" (target_index ignored).
        target_index (int, optional): Required for "before"/"after".
    """
    command = createCommand("reorderLayer", {
        "compId": comp_id, "layerIndex": layer_index,
        "position": position, "targetIndex": target_index
    })
    return sendCommand(command)


@mcp.tool()
def set_layer_times(comp_id: int, layer_index: int,
                    start_time: Optional[float] = None,
                    in_point: Optional[float] = None,
                    out_point: Optional[float] = None):
    """
    Sets layer timing in seconds. Only provided arguments are changed.
    startTime shifts the whole layer; in/out trim it.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
        start_time (float, optional): Layer start time in comp seconds.
        in_point (float, optional): Trim-in time in comp seconds.
        out_point (float, optional): Trim-out time in comp seconds.
    """
    command = createCommand("setLayerTimes", {
        "compId": comp_id, "layerIndex": layer_index,
        "startTime": start_time, "inPoint": in_point,
        "outPoint": out_point
    })
    return sendCommand(command)


@mcp.tool()
def set_layer_transform(comp_id: int, layer_index: int,
                        anchor_point: Optional[list[float]] = None,
                        position: Optional[list[float]] = None,
                        scale: Optional[list[float]] = None,
                        rotation: Optional[float] = None,
                        rotation_x: Optional[float] = None,
                        rotation_y: Optional[float] = None,
                        opacity: Optional[float] = None):
    """
    Sets static transform values. Only provided arguments are changed.
    Properties that already have keyframes are skipped with an
    explanation (use the Phase 2 keyframe tools for animated
    properties). Response includes applied/skipped lists plus the
    resulting transform state.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
        anchor_point (list[float], optional): [x, y] or [x, y, z].
        position (list[float], optional): [x, y] or [x, y, z].
        scale (list[float], optional): [x, y] or [x, y, z] percent
            (100 = original size).
        rotation (float, optional): Z rotation in degrees.
        rotation_x (float, optional): X rotation (3D layers only).
        rotation_y (float, optional): Y rotation (3D layers only).
        opacity (float, optional): 0-100.
    """
    options = {"compId": comp_id, "layerIndex": layer_index}
    if anchor_point is not None:
        options["anchorPoint"] = anchor_point
    if position is not None:
        options["position"] = position
    if scale is not None:
        options["scale"] = scale
    if rotation is not None:
        options["rotation"] = rotation
    if rotation_x is not None:
        options["rotationX"] = rotation_x
    if rotation_y is not None:
        options["rotationY"] = rotation_y
    if opacity is not None:
        options["opacity"] = opacity
    command = createCommand("setLayerTransform", options)
    return sendCommand(command)


@mcp.tool()
def set_layer_parent(comp_id: int, layer_index: int,
                     parent_index: Optional[int] = None):
    """
    Parents a layer to another layer (the rigging primitive - parent to
    nulls from add_null_layer). Omit parent_index to unparent.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based index of the child layer.
        parent_index (int, optional): 1-based index of the parent layer.
            Omit (or None) to remove the parent.
    """
    command = createCommand("setLayerParent", {
        "compId": comp_id, "layerIndex": layer_index,
        "parentIndex": parent_index
    })
    return sendCommand(command)


@mcp.tool()
def precompose_layers(comp_id: int, layer_indices: list[int], name: str,
                      move_all_attributes: bool = True):
    """
    Precomposes layers into a new nested composition. Returns the new
    comp id and the index of the precomp layer left in the original
    comp. Layer indices shift afterward; re-read
    get_composition_details.

    Args:
        comp_id (int): Composition id.
        layer_indices (list[int]): 1-based indices of layers to
            precompose.
        name (str): Name for the new nested composition.
        move_all_attributes (bool): Move all attributes into the new
            comp. Must be True when precomposing multiple layers
            (AE API constraint). Default True.
    """
    command = createCommand("precomposeLayers", {
        "compId": comp_id, "layerIndices": layer_indices,
        "name": name, "moveAllAttributes": move_all_attributes
    })
    return sendCommand(command)


# ---------------------------------------------------------------------------
# Priority 4: Keyframe Engine
# Property addressing: property_path is a list of matchName strings walked
# from the layer, e.g. ["ADBE Transform Group", "ADBE Position"] or
# ["ADBE Effect Parade", "ADBE Gaussian Blur 2", "ADBE Gaussian Blur 2-0001"].
# A segment that is all digits (e.g. "2") is treated as a 1-based numeric
# property index - useful for duplicate effects. Discover matchNames via
# get_composition_details (effects) and standard transform matchNames.


@mcp.tool()
def add_keyframe(comp_id: int, layer_index: int, property_path: list[str],
                 time_seconds: float, value):
    """
    Adds (or overwrites) a keyframe on any keyframeable property at the
    given time. Returns the resulting key index.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
        property_path (list[str]): matchName path from the layer, e.g.
            ["ADBE Transform Group", "ADBE Position"]. All-digit segments
            are 1-based numeric indices (for duplicate effects).
        time_seconds (float): Keyframe time in seconds.
        value: The value - scalar (opacity/rotation), [x, y] or
            [x, y, z] (position/scale/anchor), [r, g, b] (color), etc.
            Must match the property's dimensionality.
    """
    command = createCommand("addKeyframe", {
        "compId": comp_id, "layerIndex": layer_index,
        "propertyPath": property_path,
        "timeSeconds": time_seconds, "value": value
    })
    return sendCommand(command)


@mcp.tool()
def add_keyframes(comp_id: int, layer_index: int, property_path: list[str],
                  times: list[float], values: list):
    """
    Batch-adds keyframes in ONE call and ONE undo step - always prefer
    this over repeated add_keyframe calls. times and values must be
    equal-length; values[i] lands at times[i].

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
        property_path (list[str]): matchName path from the layer, e.g.
            ["ADBE Transform Group", "ADBE Position"]. All-digit segments
            are 1-based numeric indices (for duplicate effects).
        times (list[float]): Keyframe times in seconds.
        values (list): One value per time, each matching the property's
            dimensionality.
    """
    command = createCommand("addKeyframes", {
        "compId": comp_id, "layerIndex": layer_index,
        "propertyPath": property_path,
        "times": times, "values": values
    })
    return sendCommand(command)


@mcp.tool()
def remove_keyframes(comp_id: int, layer_index: int,
                     property_path: list[str],
                     key_indices: Optional[list[int]] = None):
    """
    Removes keyframes from a property. Omit key_indices to remove ALL
    keyframes. One undo step.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
        property_path (list[str]): matchName path from the layer.
        key_indices (list[int], optional): 1-based key indices to remove
            (from get_keyframes). Omit to clear every keyframe.
    """
    command = createCommand("removeKeyframes", {
        "compId": comp_id, "layerIndex": layer_index,
        "propertyPath": property_path,
        "keyIndices": key_indices
    })
    return sendCommand(command)


@mcp.tool()
def get_keyframes(comp_id: int, layer_index: int, property_path: list[str]):
    """
    Reads all keyframes on a property: per key - 1-based keyIndex, time,
    value, in/out interpolation (LINEAR/BEZIER/HOLD), and temporal ease
    (speed/influence per dimension). Also reports whether an expression
    is present.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
        property_path (list[str]): matchName path from the layer.
    """
    command = createCommand("getKeyframes", {
        "compId": comp_id, "layerIndex": layer_index,
        "propertyPath": property_path
    })
    return sendCommand(command)


@mcp.tool()
def get_property_value(comp_id: int, layer_index: int,
                       property_path: list[str],
                       time_seconds: Optional[float] = None,
                       pre_expression: bool = False):
    """
    Reads a property's value - current value if time_seconds is omitted,
    or the evaluated value at any time (including between keyframes and
    with expressions applied).

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
        property_path (list[str]): matchName path from the layer.
        time_seconds (float, optional): Evaluate at this time. Omit for
            the current value.
        pre_expression (bool): If True, return the pre-expression
            (keyframed) value instead of the post-expression result.
            Default False.
    """
    command = createCommand("getPropertyValue", {
        "compId": comp_id, "layerIndex": layer_index,
        "propertyPath": property_path,
        "timeSeconds": time_seconds,
        "preExpression": pre_expression
    })
    return sendCommand(command)


@mcp.tool()
def set_keyframe_interpolation(comp_id: int, layer_index: int,
                               property_path: list[str], in_type: str,
                               out_type: Optional[str] = None,
                               key_indices: Optional[list[int]] = None):
    """
    Sets keyframe interpolation type. Omit key_indices to apply to ALL
    keys; omit out_type to use in_type for both sides.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
        property_path (list[str]): matchName path from the layer.
        in_type (str): "LINEAR", "BEZIER", or "HOLD".
        out_type (str, optional): Same options; defaults to in_type.
        key_indices (list[int], optional): 1-based key indices. Omit for
            all keys.
    """
    command = createCommand("setKeyframeInterpolation", {
        "compId": comp_id, "layerIndex": layer_index,
        "propertyPath": property_path,
        "inType": in_type, "outType": out_type,
        "keyIndices": key_indices
    })
    return sendCommand(command)


@mcp.tool()
def set_keyframe_ease(comp_id: int, layer_index: int,
                      property_path: list[str],
                      easy_ease: bool = False,
                      in_speed: float = 0.0, in_influence: float = 33.3333,
                      out_speed: float = 0.0, out_influence: float = 33.3333,
                      key_indices: Optional[list[int]] = None):
    """
    Sets temporal ease on keyframes (forces BEZIER interpolation, like
    F9). easy_ease=True is the classic Easy Ease shorthand (speed 0,
    influence 33.33 both sides) and overrides the explicit values.
    Omit key_indices to apply to ALL keys.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
        property_path (list[str]): matchName path from the layer.
        easy_ease (bool): Apply standard Easy Ease. Default False.
        in_speed (float): Incoming speed (0 = full stop at the key).
        in_influence (float): Incoming influence 0.1-100.
        out_speed (float): Outgoing speed.
        out_influence (float): Outgoing influence 0.1-100.
        key_indices (list[int], optional): 1-based key indices. Omit for
            all keys.
    """
    command = createCommand("setKeyframeEase", {
        "compId": comp_id, "layerIndex": layer_index,
        "propertyPath": property_path,
        "easyEase": easy_ease,
        "inSpeed": in_speed, "inInfluence": in_influence,
        "outSpeed": out_speed, "outInfluence": out_influence,
        "keyIndices": key_indices
    })
    return sendCommand(command)


# -------------------------------------------------------------------
# Priority 5: Expressions Engine
# ---------------------------------------------------------------------
# Expression preset library
# ---------------------------------------------------------------------
# Each preset: description, params (name -> {description, default}),
# and a build(params) -> expression string.

def _preset_wiggle(p):
    return "wiggle({freq}, {amp})".format(freq=p["frequency"], amp=p["amplitude"])


def _preset_loop_out(p):
    mode = p["mode"]
    if mode not in ("cycle", "pingpong", "continue", "offset"):
        raise ValueError("loop_out mode must be cycle, pingpong, continue, or offset")
    return "loopOut('{mode}')".format(mode=mode)


def _preset_inertia_bounce(p):
    return (
        "n = 0;\n"
        "if (numKeys > 0) {{\n"
        "    n = nearestKey(time).index;\n"
        "    if (key(n).time > time) {{ n--; }}\n"
        "}}\n"
        "if (n == 0) {{ t = 0; }} else {{ t = time - key(n).time; }}\n"
        "if (n > 0 && t < 4) {{\n"
        "    v = velocityAtTime(key(n).time - thisComp.frameDuration / 10);\n"
        "    amp = {amp};\n"
        "    freq = {freq};\n"
        "    decay = {decay};\n"
        "    value + v * amp * Math.sin(freq * t * 2 * Math.PI) / Math.exp(decay * t);\n"
        "}} else {{\n"
        "    value;\n"
        "}}"
    ).format(amp=p["amplitude"], freq=p["frequency"], decay=p["decay"])


def _preset_time_rotation(p):
    return "time * {rate}".format(rate=p["rate"])


def _preset_oscillate(p):
    return "value + {amp} * Math.sin({freq} * time * 2 * Math.PI)".format(
        amp=p["amplitude"], freq=p["frequency"])


def _preset_value_follower(p):
    # Follows the SAME property (the one this preset is applied to) on a
    # leader layer, with a time delay. Expressions support matchName
    # lookups via property("matchName") chaining.
    delay = p["delay_seconds"]
    leader = p["leader_layer_index"]
    return None, delay, leader  # assembled in apply_expression_preset (needs property_path)


EXPRESSION_PRESETS = {
    "wiggle": {
        "description": "Organic random motion. The workhorse of motion design.",
        "params": {
            "frequency": {"description": "Wiggles per second", "default": 2},
            "amplitude": {"description": "Wiggle amount in property units (px for position, % for scale...)", "default": 30},
        },
        "build": _preset_wiggle,
        "note": "Works on any dimensionality.",
    },
    "loop_out": {
        "description": "Loops the property's existing keyframes forever past the last key.",
        "params": {
            "mode": {"description": "cycle | pingpong | continue | offset", "default": "cycle"},
        },
        "build": _preset_loop_out,
        "note": "Requires at least 2 keyframes to have a visible effect.",
    },
    "inertia_bounce": {
        "description": "Elastic overshoot/settle after the last keyframe - the classic bounce.",
        "params": {
            "amplitude": {"description": "Overshoot strength", "default": 0.05},
            "frequency": {"description": "Oscillations per second", "default": 4.0},
            "decay": {"description": "How fast the bounce settles (higher = faster)", "default": 8.0},
        },
        "build": _preset_inertia_bounce,
        "note": "Apply to a property that has keyframes; bounce begins at each key.",
    },
    "time_rotation": {
        "description": "Constant rate of change - classic use: endless rotation.",
        "params": {
            "rate": {"description": "Units per second (degrees/sec on rotation)", "default": 90},
        },
        "build": _preset_time_rotation,
        "note": "Best on 1D properties (rotation, opacity...).",
    },
    "oscillate": {
        "description": "Smooth sine-wave oscillation around the current value.",
        "params": {
            "amplitude": {"description": "Swing in property units", "default": 20},
            "frequency": {"description": "Cycles per second", "default": 1.0},
        },
        "build": _preset_oscillate,
        "note": "1D properties only (the scalar sine cannot add to array values).",
    },
    "value_follower": {
        "description": "Follows the same property on another (leader) layer with a time delay - instant follow-through/staggered animation.",
        "params": {
            "leader_layer_index": {"description": "1-based index of the layer to follow", "default": None},
            "delay_seconds": {"description": "Lag behind the leader in seconds", "default": 0.5},
        },
        "build": _preset_value_follower,
        "note": "Applies to the same property_path on the leader layer.",
    },
}


@mcp.tool()
def set_expression(comp_id: int, layer_index: int, property_path: list[str],
                   expression: str):
    """
    Sets an expression on a layer property - procedural animation in one
    call, no keyframes needed. AE validates the expression; on rejection
    the previous expression is restored and AE's error message returned.

    Common patterns: "wiggle(2, 30)" (organic motion), "loopOut('cycle')"
    (loop keyframes forever), "time * 90" (constant rotation deg/sec).
    See apply_expression_preset for a parameterized library.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
        property_path (list[str]): matchName path from the layer, e.g.
            ["ADBE Transform Group", "ADBE Position"].
        expression (str): The expression source code.
    """
    command = createCommand("setExpression", {
        "compId": comp_id, "layerIndex": layer_index,
        "propertyPath": property_path, "expression": expression
    })
    return sendCommand(command)


@mcp.tool()
def get_expression(comp_id: int, layer_index: int, property_path: list[str]):
    """
    Reads a property's expression state: source, enabled flag, AE's
    expression error (if any), and whether the property can hold an
    expression at all.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
        property_path (list[str]): matchName path from the layer.
    """
    command = createCommand("getExpression", {
        "compId": comp_id, "layerIndex": layer_index,
        "propertyPath": property_path
    })
    return sendCommand(command)


@mcp.tool()
def remove_expression(comp_id: int, layer_index: int,
                      property_path: list[str]):
    """
    Removes the expression from a property (keyframed/static value
    remains). Succeeds with removed=false if there was none.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
        property_path (list[str]): matchName path from the layer.
    """
    command = createCommand("removeExpression", {
        "compId": comp_id, "layerIndex": layer_index,
        "propertyPath": property_path
    })
    return sendCommand(command)


@mcp.tool()
def list_expression_presets():
    """
    Lists the expression preset library: name, description, parameters
    (with defaults), and usage notes for each. Use with
    apply_expression_preset.
    """
    catalog = {}
    for name, spec in EXPRESSION_PRESETS.items():
        catalog[name] = {
            "description": spec["description"],
            "params": {
                pname: {"description": pspec["description"], "default": pspec["default"]}
                for pname, pspec in spec["params"].items()
            },
            "note": spec.get("note", ""),
        }
    return catalog


@mcp.tool()
def apply_expression_preset(comp_id: int, layer_index: int,
                            property_path: list[str], preset: str,
                            params: Optional[dict] = None):
    """
    Applies a preset from the expression library to a property. The
    preset compiles to an expression string server-side and is validated
    by AE like any set_expression call.

    Presets: wiggle, loop_out, inertia_bounce, time_rotation, oscillate,
    value_follower. See list_expression_presets for parameters.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
        property_path (list[str]): matchName path from the layer.
        preset (str): Preset name.
        params (dict, optional): Preset parameters; unspecified ones use
            defaults (e.g. {"frequency": 3, "amplitude": 50}).
    """
    spec = EXPRESSION_PRESETS.get(preset)
    if spec is None:
        return {
            "error": "Unknown preset '{p}'. Available: {names}".format(
                p=preset, names=", ".join(sorted(EXPRESSION_PRESETS.keys())))
        }

    merged = {}
    supplied = params or {}
    unknown = [k for k in supplied.keys() if k not in spec["params"]]
    if unknown:
        return {
            "error": "Unknown param(s) for preset '{p}': {u}. Valid: {v}".format(
                p=preset, u=", ".join(unknown), v=", ".join(spec["params"].keys()))
        }
    for pname, pspec in spec["params"].items():
        merged[pname] = supplied.get(pname, pspec["default"])
        if merged[pname] is None:
            return {"error": "Preset '{p}' requires param '{n}'.".format(p=preset, n=pname)}

    if preset == "value_follower":
        # Assembled here because it needs the property_path itself:
        # follow the same property on the leader layer via matchName
        # chaining, lagged by delay_seconds.
        accessors = "".join('("{seg}")'.format(seg=seg) for seg in property_path)
        expression = "thisComp.layer({idx}){acc}.valueAtTime(time - {delay})".format(
            idx=int(merged["leader_layer_index"]), acc=accessors,
            delay=float(merged["delay_seconds"]))
    else:
        try:
            expression = spec["build"](merged)
        except ValueError as e:
            return {"error": str(e)}

    command = createCommand("setExpression", {
        "compId": comp_id, "layerIndex": layer_index,
        "propertyPath": property_path, "expression": expression
    })
    return sendCommand(command)



@mcp.tool()
def list_effect_match_names(category: Optional[str] = None,
                            search: Optional[str] = None):
    """
    Enumerates installed effects ({displayName, matchName, category}).
    ~400 built-ins unfiltered - prefer filtering. matchNames from here
    feed add_effect.

    Args:
        category (str, optional): Exact category filter (e.g.
            "Blur & Sharpen", "Color Correction", "Stylize").
        search (str, optional): Case-insensitive substring match against
            displayName or matchName (e.g. "blur", "glow").
    """
    command = createCommand("listEffectMatchNames", {
        "category": category, "search": search
    })
    return sendCommand(command)


@mcp.tool()
def add_effect(comp_id: int, layer_index: int, match_name: str,
               effect_name: Optional[str] = None):
    """
    Applies an effect to a layer by matchName (from
    list_effect_match_names, e.g. "ADBE Gaussian Blur 2", "ADBE Fill",
    "ADBE Glo2"). Returns the 1-based effect_index used by
    set_effect_property / remove_effect.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
        match_name (str): Effect matchName.
        effect_name (str, optional): Custom display name for this
            instance.
    """
    command = createCommand("addEffect", {
        "compId": comp_id, "layerIndex": layer_index,
        "matchName": match_name, "effectName": effect_name
    })
    return sendCommand(command)


@mcp.tool()
def get_layer_effects(comp_id: int, layer_index: int):
    """
    Reads all effects applied to a layer with every parameter's
    matchName, display name, value type, current value, keyframe count,
    and expression flag - the round-trip that makes "make it blurrier"
    possible. CUSTOM_VALUE/NO_VALUE params (curves, buttons) list with
    value=null.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
    """
    command = createCommand("getLayerEffects", {
        "compId": comp_id, "layerIndex": layer_index
    })
    return sendCommand(command)


@mcp.tool()
def set_effect_property(comp_id: int, layer_index: int, effect_index: int,
                        param_match_name: str, value):
    """
    Sets a parameter on an applied effect. Keyframed parameters are
    refused with a pointer to the keyframe tools (which address effect
    params via propertyPath ["ADBE Effect Parade", "<effect>",
    "<param>"]).

    Value shapes: sliders take numbers; colors take [r, g, b] 0.0-1.0;
    points take [x, y]; checkboxes take true/false (or 1/0); dropdowns
    take the 1-based option index; layer-select params take a 1-based
    layer index.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
        effect_index (int): 1-based effect index (from add_effect /
            get_layer_effects).
        param_match_name (str): Parameter matchName (from
            get_layer_effects).
        value: The new value (see shapes above).
    """
    command = createCommand("setEffectProperty", {
        "compId": comp_id, "layerIndex": layer_index,
        "effectIndex": effect_index,
        "paramMatchName": param_match_name, "value": value
    })
    return sendCommand(command)


@mcp.tool()
def remove_effect(comp_id: int, layer_index: int, effect_index: int):
    """
    Removes an applied effect. Remaining effect indices SHIFT - re-read
    get_layer_effects before further effect_index-based calls.

    Args:
        comp_id (int): Composition id.
        layer_index (int): 1-based layer index.
        effect_index (int): 1-based effect index.
    """
    command = createCommand("removeEffect", {
        "compId": comp_id, "layerIndex": layer_index,
        "effectIndex": effect_index
    })
    return sendCommand(command)


@mcp.tool()
def set_motion_blur(comp_id: int, layer_index: Optional[int] = None,
                    layer_enabled: Optional[bool] = None,
                    comp_enabled: Optional[bool] = None):
    """
    Sets motion blur switches. Motion blur only RENDERS when both the
    layer switch and the comp master are on - this tool can set either
    or both in one call. Only provided args are touched.

    Args:
        comp_id (int): Composition id.
        layer_index (int, optional): 1-based layer index (required with
            layer_enabled).
        layer_enabled (bool, optional): Layer motion blur switch.
        comp_enabled (bool, optional): Comp master motion blur toggle.
    """
    command = createCommand("setMotionBlur", {
        "compId": comp_id, "layerIndex": layer_index,
        "layerEnabled": layer_enabled, "compEnabled": comp_enabled
    })
    return sendCommand(command)


@mcp.tool()
def set_frame_blending(comp_id: int, layer_index: Optional[int] = None,
                       blend_type: Optional[str] = None,
                       comp_enabled: Optional[bool] = None):
    """
    Sets frame blending. The layer setting is a three-state type; the
    comp master must also be on for blending to render. Only provided
    args are touched.

    Args:
        comp_id (int): Composition id.
        layer_index (int, optional): 1-based layer index (required with
            blend_type).
        blend_type (str, optional): "OFF", "FRAME_MIX" (fast
            crossfade), or "PIXEL_MOTION" (optical-flow interpolation).
        comp_enabled (bool, optional): Comp master frame blending
            toggle.
    """
    command = createCommand("setFrameBlending", {
        "compId": comp_id, "layerIndex": layer_index,
        "blendType": blend_type, "compEnabled": comp_enabled
    })
    return sendCommand(command)
