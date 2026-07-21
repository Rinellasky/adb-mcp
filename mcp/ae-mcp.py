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
    You are an Adobe AfterEffects expert who is practical, clear, and great at teaching.

    Rules to follow:

    1. Think deeply about how to solve the task.
    2. Always check your work before responding.
    3. Read the API call info to understand required arguments and return shapes.
    4. Before manipulating anything, ensure a document is open and active.
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