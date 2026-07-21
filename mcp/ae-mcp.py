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

from mcp.server.fastmcp import FastMCP
from core import init, sendCommand, createCommand
import socket_client
import sys

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