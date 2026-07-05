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
from core import init, sendCommand, createCommand
from fonts import list_all_fonts_postscript
import numpy as np
import base64
import socket_client
import sys
import os
import json

FONT_LIMIT = 1000 #max number of font names to return to AI

#logger.log(f"Python path: {sys.executable}")
#logger.log(f"PYTHONPATH: {os.environ.get('PYTHONPATH')}")
#logger.log(f"Current working directory: {os.getcwd()}")
#logger.log(f"Sys.path: {sys.path}")


mcp_name = "Adobe Photoshop MCP Server"
mcp = FastMCP(mcp_name, log_level="ERROR")
print(f"{mcp_name} running on stdio", file=sys.stderr)

APPLICATION = "photoshop"
PROXY_URL = 'http://localhost:3001'
PROXY_TIMEOUT = 20

socket_client.configure(
    app=APPLICATION, 
    url=PROXY_URL,
    timeout=PROXY_TIMEOUT
)

init(APPLICATION, socket_client)

@mcp.tool()
def set_active_document(document_id:int):
    """
    Sets the document with the specified ID to the active document in Photoshop

    Args:
        document_id (int): ID for the document to set as active.
    """

    command = createCommand("setActiveDocument", {
        "documentId":document_id
    })

    return sendCommand(command)

@mcp.tool()
def get_documents():
    """
    Returns information on the documents currently open in Photoshop
    """

    command = createCommand("getDocuments", {
    })

    return sendCommand(command)


@mcp.tool()
def create_gradient_layer_style(
    layer_id: int,
    angle: int,
    type:str,
    color_stops: list,
    opacity_stops: list):
    """
    Applies gradient to active selection or entire layer if no selection exists.

    Color stops define transition points along the gradient (0-100), with color blending between stops. Opacity stops similarly control transparency transitions.

    Args:
        layer_id (int): ID for layer to apply gradient to.
        angle (int): Gradient angle (-180 to 180).
        type (str): LINEAR or RADIAL gradient.
        color_stops (list): Dictionaries defining color stops:
            - location (int): Position (0-100) along gradient.
            - color (dict): RGB values (0-255 for red/green/blue).
            - midpoint (int): Transition bias (0-100, default 50).
        opacity_stops (list): Dictionaries defining opacity stops:
            - location (int): Position (0-100) along gradient.
            - opacity (int): Level (0=transparent, 100=opaque).
            - midpoint (int): Transition bias (0-100, default 50).
    """

    command = createCommand("createGradientLayerStyle", {
        "layerId":layer_id,
        "angle":angle,
        "colorStops":color_stops,
        "type":type,
        "opacityStops":opacity_stops
    })

    return sendCommand(command)


@mcp.tool()
def duplicate_document(document_name: str):
    """Duplicates the current Photoshop Document into a new file


        Args:
            document_name (str): Name for the new document being created
    """
    
    command = createCommand("duplicateDocument", {
        "name":document_name
    })

    return sendCommand(command)


@mcp.tool()
def create_document(document_name: str, width: int, height:int, resolution:int, fill_color:dict = {"red":0, "green":0, "blue":0}, color_mode:str = "RGB"):
    """Creates a new Photoshop Document

        Layer are created from bottom up based on the order they are created in, so create background elements first and then build on top.

        New document will contain a layer named "Background" that is filled with the specified fill color

        Args:
            document_name (str): Name for the new document being created
            width (int): Width in pixels of the new document
            height (int): Height in pixels of the new document
            resolution (int): Resolution (Pixels per Inch) of the new document
            fill_color (dict): dict defining the background color fill of the new document
            color_mode (str): Color mode for the new document
    """
    
    command = createCommand("createDocument", {
        "name":document_name,
        "width":width,
        "height":height,
        "resolution":resolution,
        "fillColor":fill_color,
        "colorMode":color_mode
    })

    return sendCommand(command)

@mcp.tool()
def export_layers_as_png(layers_info: list[dict[str, str|int]]):
    """Exports multiple layers from the Photoshop document as PNG files.
    
    This function exports each specified layer as a separate PNG image file to its 
    corresponding file path. The entire layer, including transparent space will be saved.
    
    Args:
        layers_info (list[dict[str, str|int]]): A list of dictionaries containing the export information.
            Each dictionary must have the following keys:
                - "layerId" (int): The ID of the layer to export as PNG. 
                   This layer must exist in the current document.
                - "filePath" (str): The absolute file path including filename where the PNG
                   will be saved (e.g., "/path/to/directory/layername.png").
                   The parent directory must already exist or the export will fail.
    """
    
    command = createCommand("exportLayersAsPng", {
        "layersInfo":layers_info
    })

    return sendCommand(command)



@mcp.tool()
def save_document_as(file_path: str, file_type: str = "PSD"):
    """Saves the current Photoshop document to the specified location and format.
    
    Args:
        file_path (str): The absolute path (including filename) where the file will be saved.
            Example: "/Users/username/Documents/my_image.psd"
        file_type (str, optional): The file format to use when saving the document.
            Defaults to "PSD".
            Supported formats:
                - "PSD": Adobe Photoshop Document (preserves layers and editability)
                - "PNG": Portable Network Graphics (lossless compression with transparency)
                - "JPG": Joint Photographic Experts Group (lossy compression)
    
    Returns:
        dict: Response from the Photoshop operation indicating success status, and the path that the file was saved at
    """
    
    command = createCommand("saveDocumentAs", {
        "filePath":file_path,
        "fileType":file_type
    })

    return sendCommand(command)

@mcp.tool()
def save_document():
    """Saves the current Photoshop Document
    """
    
    command = createCommand("saveDocument", {
    })

    return sendCommand(command)

@mcp.tool()
def group_layers(group_name: str, layer_ids: list[int]) -> list:
    """
    Creates a new layer group from the specified layers in Photoshop.

    Note: The layers will be added to the group in the order they are specified in the document, and not the order of their layerIds passed in. The group will be made at the same level as the top most layer in the layer tree.

    Args:
        groupName (str): The name to assign to the newly created layer group.
        layerIds (list[int]): A list of layer ids to include in the new group.

    Raises:
        RuntimeError: If the operation fails or times out.

    """


    command = createCommand("groupLayers", {
        "groupName":group_name,
        "layerIds":layer_ids
    })

    return sendCommand(command)


@mcp.tool()
def get_layer_image(layer_id: int):
    """Returns a jpeg of the specified layer's content as an MCP Image object that can be displayed."""

    command = createCommand("getLayerImage",
        {
            "layerId":layer_id
        }
    )

    response = sendCommand(command)

    if response.get('status') == 'SUCCESS' and 'response' in response:
        image_data = response['response']
        data_url = image_data.get('dataUrl')

        if data_url and data_url.startswith("data:image/jpeg;base64,"):
            # Strip the data URL prefix and decode the base64 JPEG bytes
            base64_data = data_url.split(",", 1)[1]
            jpeg_bytes = base64.b64decode(base64_data)

            return Image(data=jpeg_bytes, format="jpeg")

    return response


@mcp.tool()
def get_document_image():
    """Returns a jpeg of the current visible Photoshop document as an MCP Image object that can be displayed."""
    command = createCommand("getDocumentImage", {})
    response = sendCommand(command)

    if response.get('status') == 'SUCCESS' and 'response' in response:
        image_data = response['response']
        data_url = image_data.get('dataUrl')

        if data_url and data_url.startswith("data:image/jpeg;base64,"):
            # Strip the data URL prefix and decode the base64 JPEG bytes
            base64_data = data_url.split(",", 1)[1]
            jpeg_bytes = base64.b64decode(base64_data)

            return Image(data=jpeg_bytes, format="jpeg")

    return response

@mcp.tool()
def save_document_image_as_png(file_path: str):
    """
    Capture the Photoshop document and save as PNG file
    
    Args:
        file_path: Where to save the PNG file
        
    Returns:
        dict: Status and file info
    """
    command = createCommand("getDocumentImage", {})
    response = sendCommand(command)
    
    if response.get('format') == 'raw' and 'rawDataBase64' in response:
        try:
            # Decode raw data
            raw_bytes = base64.b64decode(response['rawDataBase64'])
            
            # Extract metadata
            width = response['width']
            height = response['height']
            components = response['components']
            
            # Convert to numpy array and reshape
            pixel_array = np.frombuffer(raw_bytes, dtype=np.uint8)
            image_array = pixel_array.reshape((height, width, components))
            
            # Create and save PNG
            mode = 'RGBA' if components == 4 else 'RGB'
            image = Image.fromarray(image_array, mode)
            image.save(file_path, 'PNG')
            
            return {
                'status': 'success',
                'file_path': file_path,
                'width': width,
                'height': height,
                'size_bytes': os.path.getsize(file_path)
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    else:
        return {
            'status': 'error',
            'error': 'No raw image data received'
        }

@mcp.tool()
def get_layers() -> list:
    """Returns a nested list of dicts that contain layer info and the order they are arranged in.

    Args:
        None
        
    Returns:
        list: A nested list of dictionaries containing layer information and hierarchy.
            Each dict has at minimum a 'name' key with the layer name.
            If a layer has sublayers, they will be contained in a 'layers' key which contains another list of layer dicts.
            Example: [{'name': 'Group 1', 'layers': [{'name': 'Layer 1'}, {'name': 'Layer 2'}]}, {'name': 'Background'}]
    """

    command = createCommand("getLayers", {})

    return sendCommand(command)


@mcp.tool()
def place_image(
    layer_id: int,
    image_path: str
):
    """Places the image at the specified path on the existing pixel layer with the specified id.

    The image will be placed on the center of the layer, and will fill the layer without changing its aspect ration (thus there may be bars at the top or bottom) 

    Args:
        layer_id (int): The id of the layer where the image will be placed.
        image_path (str): The file path to the image that will be placed on the layer.
    """
    
    command = createCommand("placeImage", {
        "layerId":layer_id,
        "imagePath":image_path
    })

    return sendCommand(command)

@mcp.tool()
def harmonize_layer(layer_id:int,  new_layer_name:str, rasterize_layer:bool = True):
    """Harmonizes (matches lighting and other settings) the selected layer with the background layers.

    The layer being harmonized should be rasterized and have some transparency.

    Args:
        layer_id (int): ID of the layer to be harmonizes.
        new_layer_name (str): Name for the new layer that will be created with the harmonized content
        rasterize_layer (bool): Whether the new layer should be rasterized.
            If not rasterized, the layer will remain a generative layer which
            allows the user to interact with it. True by default.
    """

    command = createCommand("harmonizeLayer", {
        "layerId":layer_id,
         "newLayerName":new_layer_name,
        "rasterizeLayer":rasterize_layer
    })

    return sendCommand(command)


@mcp.tool()
def rename_layers(
    layer_data: list[dict]
):
    """Renames one or more layers

    Args:
        layer_data (list[dict]): A list of dictionaries containing layer rename information.
            Each dictionary must have the following keys:
                - "layer_id" (int): ID of the layer to be renamed.
                - "new_layer_name" (str): New name for the layer.
    """
    
    command = createCommand("renameLayers", {
        "layerData":layer_data
    })
    
    return sendCommand(command)


@mcp.tool()
def scale_layer(
    layer_id:int,
    width:int,
    height:int,
    anchor_position:str,
    interpolation_method:str = "AUTOMATIC"
):
    """Scales the layer with the specified ID.

    Args:
        layer_id (int): ID of layer to be scaled.
        width (int): Percentage to scale horizontally.
        height (int): Percentage to scale vertically.
        anchor_position (str): The anchor position to rotate around,
        interpolation_method (str): Interpolation method to use when resampling the image
    """
    
    command = createCommand("scaleLayer", {
        "layerId":layer_id,
        "width":width,
        "height":height,
        "anchorPosition":anchor_position,
        "interpolationMethod":interpolation_method
    })

    return sendCommand(command)


@mcp.tool()
def rotate_layer(
    layer_id:int,
    angle:int,
    anchor_position:str,
    interpolation_method:str = "AUTOMATIC"
):
    """Rotates the layer with the specified ID.

    Args:
        layer_id (int): ID of layer to be scaled.
        angle (int): Angle (-359 to 359) to rotate the layer by in degrees
        anchor_position (str): The anchor position to rotate around,
        interpolation_method (str): Interpolation method to use when resampling the image
    """
    
    command = createCommand("rotateLayer", {
        "layerId":layer_id,
        "angle":angle,
        "anchorPosition":anchor_position,
        "interpolationMethod":interpolation_method
    })

    return sendCommand(command)


@mcp.tool()
def flip_layer(
    layer_id:int,
    axis:str
):
    """Flips the layer with the specified ID on the specified axis.

    Args:
        layer_id (int): ID of layer to be scaled.
        axis (str): The axis on which to flip the layer. Valid values are "horizontal", "vertical" or "both"
    """
    
    command = createCommand("flipLayer", {
        "layerId":layer_id,
        "axis":axis
    })

    return sendCommand(command)


@mcp.tool()
def delete_layer(
    layer_id:int
):
    """Deletes the layer with the specified ID

    Args:
        layer_id (int): ID of the layer to be deleted
    """
    
    command = createCommand("deleteLayer", {
        "layerId":layer_id
    })

    return sendCommand(command)



@mcp.tool()
def set_layer_visibility(
    layer_id:int,
    visible:bool
):
    """Sets the visibility of the layer with the specified ID

    Args:
        layer_id (int): ID of the layer to set visibility
        visible (bool): Whether the layer is visible
    """
    
    command = createCommand("setLayerVisibility", {
        "layerId":layer_id,
        "visible":visible
    })

    return sendCommand(command)


@mcp.tool()
def generate_image(
    layer_name:str,
    prompt:str,
    content_type:str = "none"
):
    """Uses Adobe Firefly Generative AI to generate an image on a new layer with the specified layer name.

    If there is an active selection, it will use that region for the generation. Otherwise it will generate
    on the entire layer.

    Args:
        layer_name (str): Name for the layer that will be created and contain the generated image
        prompt (str): Prompt describing the image to be generated
        content_type (str): The type of image to be generated. Options include "photo", "art" or "none" (default)
    """
    
    command = createCommand("generateImage", {
        "layerName":layer_name,
        "prompt":prompt,
        "contentType":content_type
    })

    return sendCommand(command)

@mcp.tool()
def generative_fill(
    layer_name: str,
    prompt: str,
    layer_id: int,
    content_type: str = "none"
):
    """Uses Adobe Firefly Generative AI to perform generative fill within the current selection.

    This function uses generative fill to seamlessly integrate new content into the existing image.
    It requires an active selection, and will fill that region taking into account the surrounding 
    context and layers below. The AI considers the existing content to create a natural, 
    contextually-aware fill.

    Args:
        layer_name (str): Name for the layer that will be created and contain the generated fill
        prompt (str): Prompt describing the content to be generated within the selection
        layer_id (int): ID of the layer to work with (though a new layer is created for the result)
        content_type (str): The type of image to be generated. Options include "photo", "art" or "none" (default)
    
    Returns:
        dict: Response from Photoshop containing the operation status and layer information
    """

    command = createCommand("generativeFill", {
        "layerName":layer_name,
        "prompt":prompt,
        "layerId":layer_id,
        "contentType":content_type,
    })

    return sendCommand(command)


@mcp.tool()
def move_layer(
    layer_id:int,
    position:str
):
    """Moves the layer within the layer stack based on the specified position

    Args:
        layer_id (int): Name for the layer that will be moved
        position (str): How the layer position within the layer stack will be updated. Value values are: TOP (Place above all layers), BOTTOM (Place below all layers), UP (Move up one layer), DOWN (Move down one layer)
    """

    command = createCommand("moveLayer", {
        "layerId":layer_id,
        "position":position
    })

    return sendCommand(command)

@mcp.tool()
def get_document_info():
    """Retrieves information about the currently active document.

    Returns:
        response : An object containing the following document properties:
            - height (int): The height of the document in pixels.
            - width (int): The width of the document in pixels.
            - colorMode (str): The document's color mode as a string.
            - pixelAspectRatio (float): The pixel aspect ratio of the document.
            - resolution (float): The document's resolution (DPI).
            - path (str): The file path of the document, if saved.
            - saved (bool): Whether the document has been saved (True if it has a valid file path).
            - hasUnsavedChanges (bool): Whether the document contains unsaved changes.

    """

    command = createCommand("getDocumentInfo", {})

    return sendCommand(command)

@mcp.tool()
def crop_document():
    """Crops the document to the active selection.

    This function removes all content outside the selection area and resizes the document 
    so that the selection becomes the new canvas size.

    An active selection is required.
    """

    command = createCommand("cropDocument", {})

    return sendCommand(command)

@mcp.tool()
def paste_from_clipboard(layer_id: int, paste_in_place: bool = True):
    """Pastes the current clipboard contents onto the specified layer.

    If `paste_in_place` is True, the content will be positioned exactly where it was cut or copied from.
    If False and an active selection exists, the content will be centered within the selection.
    If no selection is active, the content will be placed at the center of the layer.

    Args:
        layer_id (int): The ID of the layer where the clipboard contents will be pasted.
        paste_in_place (bool): Whether to paste at the original location (True) or adjust based on selection/layer center (False).
    """


    command = createCommand("pasteFromClipboard", {
        "layerId":layer_id,
        "pasteInPlace":paste_in_place
    })

    return sendCommand(command)

@mcp.tool()
def rasterize_layer(layer_id: int):
    """Converts the specified layer into a rasterized (flat) image.

    This process removes any vector, text, or smart object properties, turning the layer 
    into pixel-based content.

    Args:
        layer_id (int): The name of the layer to rasterize.
    """

    command = createCommand("rasterizeLayer", {
        "layerId":layer_id
    })

    return sendCommand(command)

@mcp.tool()
def open_photoshop_file(file_path: str):
    """Opens the specified Photoshop-compatible file within Photoshop.

    This function attempts to open a file in Adobe Photoshop. The file must be in a 
    format compatible with Photoshop, such as PSD, TIFF, JPEG, PNG, etc.

    Args:
        file_path (str): Complete absolute path to the file to be opened, including filename and extension.

    Returns:
        dict: Response from the Photoshop operation indicating success status.
        
    Raises:
        RuntimeError: If the file doesn't exist, is not accessible, or is in an unsupported format.
    """

    command = createCommand("openFile", {
        "filePath":file_path
    })

    return sendCommand(command)

@mcp.tool()
def cut_selection_to_clipboard(layer_id: int):
    """Copies and removes (cuts) the selected pixels from the specified layer to the system clipboard.

    This function requires an active selection.

    Args:
        layer_id (int): The name of the layer that contains the pixels to copy and remove.
    """

    command = createCommand("cutSelectionToClipboard", {
        "layerId":layer_id
    })

    return sendCommand(command)


@mcp.tool()
def copy_merged_selection_to_clipboard():
    """Copies the selected pixels from all visible layers to the system clipboard.

    This function requires an active selection. If no selection is active, the operation will fail.
    The copied content will include pixel data from all visible layers within the selection area,
    effectively capturing what you see on screen.

    Returns:
        dict: Response from the Photoshop operation indicating success status.
        
    Raises:
        RuntimeError: If no active selection exists.
    """

    command = createCommand("copyMergedSelectionToClipboard", {})

    return sendCommand(command)

@mcp.tool()
def copy_selection_to_clipboard(layer_id: int):
    """Copies the selected pixels from the specified layer to the system clipboard.

    This function requires an active selection. If no selection is active, the operation will fail.

    Args:
        layer_id (int): The name of the layer that contains the pixels to copy.
        
    Returns:
        dict: Response from the Photoshop operation indicating success status.
    """

    command = createCommand("copySelectionToClipboard", {
        "layerId":layer_id
    })

    return sendCommand(command)

@mcp.tool()
def select_subject(layer_id: int):
    """Automatically selects the subject in the specified layer.

    This function identifies and selects the subject in the given image layer. 
    It returns an object containing a property named `hasActiveSelection`, 
    which indicates whether any pixels were selected (e.g., if no subject was detected).

    Args:
        layer_int (int): The name of that contains the image to select the subject from.
    """

    
    command = createCommand("selectSubject", {
        "layerId":layer_id
    })

    return sendCommand(command)

@mcp.tool()
def select_sky(layer_id: int):
    """Automatically selects the sky in the specified layer.

    This function identifies and selects the sky in the given image layer. 
    It returns an object containing a property named `hasActiveSelection`, 
    which indicates whether any pixels were selected (e.g., if no sky was detected).

    Args:
        layer_id (int): The name of that contains the image to select the sky from.
    """

    
    command = createCommand("selectSky", {
        "layerId":layer_id
    })

    return sendCommand(command)


@mcp.tool()
def get_layer_bounds(
    layer_id: int
):
    """Returns the pixel bounds for the layer with the specified ID
    
    Args:
        layer_id (int): ID of the layer to get the bounds information from

    Returns:
        dict: A dictionary containing the layer bounds with the following properties:
            - left (int): The x-coordinate of the left edge of the layer
            - top (int): The y-coordinate of the top edge of the layer
            - right (int): The x-coordinate of the right edge of the layer
            - bottom (int): The y-coordinate of the bottom edge of the layer
            
    Raises:
        RuntimeError: If the layer doesn't exist or if the operation fails
    """
    
    command = createCommand("getLayerBounds", {
        "layerId":layer_id
    })

    return sendCommand(command)

@mcp.tool()
def remove_background(
    layer_id:int
):
    """Automatically removes the background of the image in the layer with the specified ID and keeps the main subject
    
    Args:
        layer_id (int): ID of the layer to remove the background from
    """
    
    command = createCommand("removeBackground", {
        "layerId":layer_id
    })

    return sendCommand(command)

@mcp.tool()
def create_pixel_layer(
    layer_name:str,
    fill_neutral:bool,
    opacity:int = 100,
    blend_mode:str = "NORMAL",
):
    """Creates a new pixel layer with the specified ID
    
    Args:
        layer_name (str): Name of the new layer being created
        fill_neutral (bool): Whether to fill the layer with a neutral color when applying Blend Mode.
        opacity (int): Opacity of the newly created layer
        blend_mode (str): Blend mode of the newly created layer
    """
    
    command = createCommand("createPixelLayer", {
        "layerName":layer_name,
        "opacity":opacity,
        "fillNeutral":fill_neutral,
        "blendMode":blend_mode
    })

    return sendCommand(command)

@mcp.tool()
def create_multi_line_text_layer(
    layer_name:str, 
    text:str, 
    font_size:int, 
    postscript_font_name:str, 
    opacity:int = 100,
    blend_mode:str = "NORMAL",
    text_color:dict = {"red":255, "green":255, "blue":255}, 
    position:dict = {"x": 100, "y":100},
    bounds:dict = {"top": 0, "left": 0, "bottom": 250, "right": 300},
    justification:str = "LEFT"
    ):

    """
    Creates a new multi-line text layer with the specified ID within the current Photoshop document.
    
    Args:
        layer_name (str): The name of the layer to be created. Can be used to select in other api calls.
        text (str): The text to include on the layer.
        font_size (int): Font size.
        postscript_font_name (string): Postscript Font Name to display the text in. Valid list available via get_option_info.
        opacity (int): Opacity for the layer specified in percent.
        blend_mode (str): Blend Mode for the layer. Valid list available via get_option_info
        text_color (dict): Color of the text expressed in Red, Green, Blue values between 0 and 255
        position (dict): Position (dict with x, y values) where the text will be placed in the layer. Based on bottom left point of the text.
        bounds (dict): text bounding box
        justification (str): text justification. Valid list available via get_option_info.
    """

    command = createCommand("createMultiLineTextLayer", {
        "layerName":layer_name,
        "contents":text,
        "fontSize": font_size,
        "opacity":opacity,
        "position":position,
        "fontName":postscript_font_name,
        "textColor":text_color,
        "blendMode":blend_mode,
        "bounds":bounds,
        "justification":justification
    })

    return sendCommand(command)


@mcp.tool()
def create_single_line_text_layer(
    layer_name:str, 
    text:str, 
    font_size:int, 
    postscript_font_name:str, 
    opacity:int = 100,
    blend_mode:str = "NORMAL",
    text_color:dict = {"red":255, "green":255, "blue":255}, 
    position:dict = {"x": 100, "y":100}
    ):

    """
    Create a new single line text layer with the specified ID within the current Photoshop document.
    
     Args:
        layer_name (str): The name of the layer to be created. Can be used to select in other api calls.
        text (str): The text to include on the layer.
        font_size (int): Font size.
        postscript_font_name (string): Postscript Font Name to display the text in. Valid list available via get_option_info.
        opacity (int): Opacity for the layer specified in percent.
        blend_mode (str): Blend Mode for the layer. Valid list available via get_option_info
        text_color (dict): Color of the text expressed in Red, Green, Blue values between 0 and 255
        position (dict): Position (dict with x, y values) where the text will be placed in the layer. Based on bottom left point of the text.
    """

    command = createCommand("createSingleLineTextLayer", {
        "layerName":layer_name,
        "contents":text,
        "fontSize": font_size,
        "opacity":opacity,
        "position":position,
        "fontName":postscript_font_name,
        "textColor":text_color,
        "blendMode":blend_mode
    })

    return sendCommand(command)

@mcp.tool()
def edit_text_layer(
    layer_id:int, 
    text:str = None,
    font_size:int = None,
    postscript_font_name:str = None, 
    text_color:dict = None,
    ):

    """
    Edits the text content of an existing text layer in the current Photoshop document.
    
    Args:
        layer_id (int): The ID of the existing text layer to edit.
        text (str): The new text content to replace the current text in the layer. If None, text will not be changed.
        font_size (int): Font size. If None, size will not be changed.
        postscript_font_name (string): Postscript Font Name to display the text in. Valid list available via get_option_info. If None, font will not will not be changed.
        text_color (dict): Color of the text expressed in Red, Green, Blue values between 0 and 255 in format of {"red":255, "green":255, "blue":255}. If None, color will not be changed
    """

    command = createCommand("editTextLayer", {
        "layerId":layer_id,
        "contents":text,
        "fontSize": font_size,
        "fontName":postscript_font_name,
        "textColor":text_color
    })

    return sendCommand(command)



@mcp.tool()
def translate_layer(
    layer_id: int,
    x_offset:int = 0,
    y_offset:int = 0
    ):

    """
        Moves the layer with the specified ID on the X and Y axis by the specified number of pixels.

    Args:
        layer_name (str): The name of the layer that should be moved.
        x_offset (int): Amount to move on the horizontal axis. Negative values move the layer left, positive values right
        y_offset (int): Amount to move on the vertical axis. Negative values move the layer down, positive values up
    """
    
    command = createCommand("translateLayer", {
        "layerId":layer_id,
        "xOffset":x_offset,
        "yOffset":y_offset
    })

    return sendCommand(command)

@mcp.tool()
def remove_layer_mask(
    layer_id: int
    ):

    """Removes the layer mask from the specified layer.

    Args:
        None
    """
    
    command = createCommand("removeLayerMask", {
        "layerId":layer_id
    })

    return sendCommand(command)

@mcp.tool()
def add_layer_mask_from_selection(
    layer_id: int
    ):

    """Creates a layer mask on the specified layer defined by the active selection.
    
    This function takes the current active selection in the document and converts it into a layer mask
    for the specified layer. Selected areas will be visible, while non-selected areas will be hidden.
    An active selection must exist before calling this function.

    Args:
        layer_name (str): The name of the layer to which the mask will be applied
    """
    
    command = createCommand("addLayerMask", {
        "layerId":layer_id
    })

    return sendCommand(command)

@mcp.tool()
def set_layer_properties(
    layer_id: int,
    blend_mode: str = "NORMAL",
    layer_opacity: int = 100,
    fill_opacity: int = 100,
    is_clipping_mask: bool = False
    ):

    """Sets the blend mode and opacity properties on the layer with the specified ID

    Args:
        layer_id (int): The ID of the layer whose properties should be updated
        blend_mode (str): The blend mode for the layer
        layer_opacity (int): The opacity for the layer (0 - 100)
        fill_opacity (int): The fill opacity for the layer (0 - 100). Will ignore anny effects that have been applied to the layer.
        is_clipping_mask (bool): A boolean indicating whether this layer will be clipped to (masked by) the layer below it
    """
    
    command = createCommand("setLayerProperties", {
        "layerId":layer_id,
        "blendMode":blend_mode,
        "layerOpacity":layer_opacity,
        "fillOpacity":fill_opacity,
        "isClippingMask":is_clipping_mask
    })

    return sendCommand(command)

@mcp.tool()
def fill_selection(
    layer_id: int,
    color:dict = {"red":255, "green":0, "blue":0},
    blend_mode:str = "NORMAL",
    opacity:int = 100,
    ):

    """Fills the selection on the pixel layer with the specified ID
    
    Args:
        layer_id (int): The ID of existing pixel layer to add the fill
        color (dict): The color of the fill
        blend_mode (dict): The blend mode for the fill
        opacity (int) : The opacity of the color for the fill
    """
    
    command = createCommand("fillSelection", {
        "layerId":layer_id,
        "color":color,
        "blendMode":blend_mode,
        "opacity":opacity
    })

    return sendCommand(command)



@mcp.tool()
def delete_selection(
    layer_id: int
    ):

    """Removes the pixels within the selection on the pixel layer with the specified ID
    
    Args:
        layer_id (int): The ID of the layer from which the content of the selection should be deleted
    """
    
    command = createCommand("deleteSelection", {
        "layerId":layer_id
    })

    return sendCommand(command)


@mcp.tool()
def invert_selection():
    
    """Inverts the current selection in the Photoshop document"""

    command = createCommand("invertSelection", {})
    return sendCommand(command)


@mcp.tool()
def clear_selection():
    
    """Clears / deselects the current selection"""

    command = createCommand("selectRectangle", {
        "feather":0,
        "antiAlias":True,
        "bounds":{"top": 0, "left": 0, "bottom": 0, "right": 0}
    })

    return sendCommand(command)

@mcp.tool()
def select_rectangle(
    layer_id:int,
    feather:int = 0,
    anti_alias:bool = True,
    bounds:dict = {"top": 0, "left": 0, "bottom": 100, "right": 100}
    ):
    
    """Creates a rectangular selection and selects the specified layer
    
    Args:
        layer_id (int): The layer to do the select rectangle action on.
        feather (int): The amount of feathering in pixels to apply to the selection (0 - 1000)
        anti_alias (bool): Whether anti-aliases is applied to the selection
        bounds (dict): The bounds for the rectangle selection
    """

    command = createCommand("selectRectangle", {
        "layerId":layer_id,
        "feather":feather,
        "antiAlias":anti_alias,
        "bounds":bounds
    })

    return sendCommand(command)

@mcp.tool()
def select_polygon(
    layer_id:int,
    feather:int = 0,
    anti_alias:bool = True,
    points:list[dict[str, int]] = [{"x": 50, "y": 10}, {"x": 100, "y": 90}, {"x": 10, "y": 40}]
    ):
    
    """Creates an n-sided polygon selection and selects the specified layer
    
    Args:
        layer_id (int): The layer to do the selection action on.
        feather (int): The amount of feathering in pixels to apply to the selection (0 - 1000)
        anti_alias (bool): Whether anti-aliases is applied to the selection
        points (list): The points that define the sides of the selection, defined via a list of dicts with x, y values.
    """

    command = createCommand("selectPolygon", {
        "layerId":layer_id,
        "feather":feather,
        "antiAlias":anti_alias,
        "points":points
    })

    return sendCommand(command)

@mcp.tool()
def select_ellipse(
    layer_id:int,
    feather:int = 0,
    anti_alias:bool = True,
    bounds:dict = {"top": 0, "left": 0, "bottom": 100, "right": 100}
    ):
    
    """Creates an elliptical selection and selects the specified layer
    
    Args:
        layer_id (int): The layer to do the selection action on.
        feather (int): The amount of feathering in pixels to apply to the selection (0 - 1000)
        anti_alias (bool): Whether anti-aliases is applied to the selection
        bounds (dict): The bounds that will define the elliptical selection.
    """

    command = createCommand("selectEllipse", {
        "layerId":layer_id,
        "feather":feather,
        "antiAlias":anti_alias,
        "bounds":bounds
    })

    return sendCommand(command)

@mcp.tool()
def align_content(
    layer_id: int,
    alignment_mode:str
    ):
    
    """
    Aligns content on layer with the specified ID to the current selection.

    Args:
        layer_id (int): The ID of the layer in which to align the content
        alignment_mode (str): How the content should be aligned. Available options via alignment_modes
    """

    command = createCommand("alignContent", {
        "layerId":layer_id,
        "alignmentMode":alignment_mode
    })

    return sendCommand(command)

@mcp.tool()
def add_drop_shadow_layer_style(
    layer_id: int,
    blend_mode:str = "MULTIPLY",
    color:dict = {"red":0, "green":0, "blue":0},
    opacity:int = 35,
    angle:int = 160,
    distance:int = 3,
    spread:int = 0,
    size:int = 7
    ):
    """Adds a drop shadow layer style to the layer with the specified ID

    Args:
        layer_id (int): The ID for the layer with the content to add the drop shadow to
        blend_mode (str): The blend mode for the drop shadow
        color (dict): The color for the drop shadow
        opacity (int): The opacity of the drop shadow
        angle (int): The angle (-180 to 180) of the drop shadow relative to the content
        distance (int): The distance in pixels of the drop shadow (0 to 30000)
        spread (int): Defines how gradually the shadow fades out at its edges, with higher values creating a harsher, more defined edge, and lower values a softer, more feathered edge (0 to 100)
        size (int): Control the blur and spread of the shadow effect (0 to 250)
    """

    command = createCommand("addDropShadowLayerStyle", {
        "layerId":layer_id,
        "blendMode":blend_mode,
        "color":color,
        "opacity":opacity,
        "angle":angle,
        "distance":distance,
        "spread":spread,
        "size":size
    })

    return sendCommand(command)

@mcp.tool()
def duplicate_layer(layer_to_duplicate_id:int, duplicate_layer_name:str):
    """
    Duplicates the layer specified by layer_to_duplicate_id ID, creating a new layer above it with the name specified by duplicate_layer_name

    Args:
        layer_to_duplicate_id (id): The id of the layer to be duplicated
        duplicate_layer_name (str): Name for the newly created layer
    """

    command = createCommand("duplicateLayer", {
        "sourceLayerId":layer_to_duplicate_id,
        "duplicateLayerName":duplicate_layer_name,
    })

    return sendCommand(command)

@mcp.tool()
def flatten_all_layers(layer_name:str):
    """
    Flatten all layers in the document into a single layer with specified name

    Args:
        layer_name (str): The name of the merged layer
    """

    command = createCommand("flattenAllLayers", {
        "layerName":layer_name,
    })

    return sendCommand(command)

@mcp.tool()
def add_color_balance_adjustment_layer(
    layer_id: int,
    highlights:list = [0,0,0],
    midtones:list = [0,0,0],
    shadows:list = [0,0,0]):
    """Adds an adjustment layer to the layer with the specified ID to adjust color balance

    Each property highlights, midtones and shadows contains an array of 3 values between
    -100 and 100 that represent the relative position between two colors.

    First value is between cyan and red
    The second value is between magenta and green
    The third value is between yellow and blue    

    Args:
        layer_id (int): The ID of the layer to apply the color balance adjustment layer
        highlights (list): Relative color values for highlights
        midtones (list): Relative color values for midtones
        shadows (list): Relative color values for shadows
    """

    command = createCommand("addColorBalanceAdjustmentLayer", {
        "layerId":layer_id,
        "highlights":highlights,
        "midtones":midtones,
        "shadows":shadows
    })

    return sendCommand(command)

@mcp.tool()
def add_brightness_contrast_adjustment_layer(
    layer_id: int,
    brightness:int = 0,
    contrast:int = 0):
    """Adds an adjustment layer to the layer with the specified ID to adjust brightness and contrast

    Args:
        layer_id (int): The ID of the layer to apply the brightness and contrast adjustment layer
        brightness (int): The brightness value (-150 to 150)
        contrasts (int): The contrast value (-50 to 100)
    """

    command = createCommand("addBrightnessContrastAdjustmentLayer", {
        "layerId":layer_id,
        "brightness":brightness,
        "contrast":contrast
    })

    return sendCommand(command)


@mcp.tool()
def add_stroke_layer_style(
    layer_id: int,
    size: int = 2,
    color: dict = {"red": 0, "green": 0, "blue": 0},
    opacity: int = 100,
    position: str = "CENTER",
    blend_mode: str = "NORMAL"
    ):
    """Adds a stroke layer style to the layer with the specified ID.
    
    Args:
        layer_id (int): The ID of the layer to apply the stroke effect to.
        size (int, optional): The width of the stroke in pixels. Defaults to 2.
        color (dict, optional): The color of the stroke as RGB values. Defaults to black {"red": 0, "green": 0, "blue": 0}.
        opacity (int, optional): The opacity of the stroke as a percentage (0-100). Defaults to 100.
        position (str, optional): The position of the stroke relative to the layer content. 
                                 Options include "CENTER", "INSIDE", or "OUTSIDE". Defaults to "CENTER".
        blend_mode (str, optional): The blend mode for the stroke effect. Defaults to "NORMAL".
    """

    command = createCommand("addStrokeLayerStyle", {
        "layerId":layer_id,
        "size":size,
        "color":color,
        "opacity":opacity,
        "position":position,
        "blendMode":blend_mode
    })

    return sendCommand(command)


@mcp.tool()
def add_vibrance_adjustment_layer(
    layer_id: int,
    vibrance:int = 0,
    saturation:int = 0):
    """Adds an adjustment layer to layer with the specified ID to adjust vibrance and saturation
    
    Args:
        layer_id (int): The ID of the layer to apply the vibrance and saturation adjustment layer
        vibrance (int): Controls the intensity of less-saturated colors while preventing oversaturation of already-saturated colors. Range -100 to 100.
        saturation (int): Controls the intensity of all colors equally. Range -100 to 100.
    """
    #0.1 to 255

    command = createCommand("addAdjustmentLayerVibrance", {
        "layerId":layer_id,
        "saturation":saturation,
        "vibrance":vibrance
    })

    return sendCommand(command)

@mcp.tool()
def add_black_and_white_adjustment_layer(
    layer_id: int,
    colors: dict = {"blue": 20, "cyan": 60, "green": 40, "magenta": 80, "red": 40, "yellow": 60},
    tint: bool = False,
    tint_color: dict = {"red": 225, "green": 211, "blue": 179}
):
    """Adds a Black & White adjustment layer to the specified layer.
    
    Creates an adjustment layer that converts the target layer to black and white. Optionally applies a color tint to the result.
    
    Args:
        layer_id (int): The ID of the layer to apply the black and white adjustment to.
        colors (dict): Controls how each color channel converts to grayscale. Values range from 
                      -200 to 300, with higher values making that color appear lighter in the 
                      conversion. Must include all keys: red, yellow, green, cyan, blue, magenta.
        tint (bool, optional): Whether to apply a color tint to the black and white result.
                              Defaults to False.
        tint_color (dict, optional): The RGB color dict to use for tinting
                                    with "red", "green", and "blue" keys (values 0-255).
    """

    command = createCommand("addAdjustmentLayerBlackAndWhite", {
        "layerId":layer_id,
        "colors":colors,
        "tint":tint,
        "tintColor":tint_color
    })

    return sendCommand(command)

@mcp.tool()
def apply_gaussian_blur(layer_id: int, radius: float = 2.5):
    """Applies a Gaussian Blur to the layer with the specified ID
    
    Args:
        layer_id (int): ID of layer to be blurred
        radius (float): The blur radius in pixels determining the intensity of the blur effect. Default is 2.5.
        Valid values range from 0.1 (subtle blur) to 10000 (extreme blur).

    Returns:
        dict: Response from the Photoshop operation
        
    Raises:
        RuntimeError: If the operation fails or times out
    """



    command = createCommand("applyGaussianBlur", {
        "layerId":layer_id,
        "radius":radius,
    })

    return sendCommand(command)




@mcp.tool()
def apply_motion_blur(layer_id: int, angle: int = 0, distance: float = 30):
    """Applies a Motion Blur to the layer with the specified ID

    Args:
    layer_id (int): ID of layer to be blurred
    angle (int): The angle in degrees (0 to 360) that determines the direction of the motion blur effect. Default is 0.
    distance (float): The distance in pixels that controls the length/strength of the motion blur. Default is 30.
        Higher values create a more pronounced motion effect.

    Returns:
        dict: Response from the Photoshop operation
        
    Raises:
        RuntimeError: If the operation fails or times out
    """


    command = createCommand("applyMotionBlur", {
        "layerId":layer_id,
        "angle":angle,
        "distance":distance
    })

    return sendCommand(command)


@mcp.tool()
def select_color_range(
    layer_id: int,
    color: dict,
    fuzziness: int = 40):
    """Creates a selection of all pixels in the document similar to the specified color.

    Args:
        layer_id (int): The ID of the layer to make active before selecting.
        color (dict): The color to select, with red, green and blue properties (0 to 255).
        fuzziness (int): How similar colors must be to be included (0 to 200).
            Lower values select colors very close to the target color, higher
            values select a broader range of colors.
    """

    command = createCommand("selectColorRange", {
        "layerId": layer_id,
        "color": color,
        "fuzziness": fuzziness
    })

    return sendCommand(command)

@mcp.tool()
def magic_wand_select(
    layer_id: int,
    x: int,
    y: int,
    tolerance: int = 32,
    anti_alias: bool = True,
    contiguous: bool = True,
    sample_all_layers: bool = False):
    """Performs a magic wand selection at the specified point, selecting pixels
    of similar color.

    Args:
        layer_id (int): The ID of the layer to sample from.
        x (int): Horizontal pixel position to sample.
        y (int): Vertical pixel position to sample.
        tolerance (int): How similar pixels must be to be selected (0 to 255).
        anti_alias (bool): Whether to smooth the selection edges.
        contiguous (bool): If True, only selects connected pixels. If False,
            selects all similar pixels in the layer.
        sample_all_layers (bool): If True, samples color from the merged image
            rather than just the specified layer.
    """

    command = createCommand("magicWandSelect", {
        "layerId": layer_id,
        "point": {"x": x, "y": y},
        "tolerance": tolerance,
        "antiAlias": anti_alias,
        "contiguous": contiguous,
        "sampleAllLayers": sample_all_layers
    })

    return sendCommand(command)

@mcp.tool()
def modify_selection(
    mode: str,
    amount: int):
    """Modifies the current active selection. Requires an active selection.

    Args:
        mode (str): The modification to apply. One of "expand", "contract",
            "feather", "smooth" or "border".
        amount (int): The amount in pixels to apply (e.g. feather radius,
            expansion distance, border width).
    """

    command = createCommand("modifySelection", {
        "mode": mode,
        "amount": amount
    })

    return sendCommand(command)

@mcp.tool()
def grow_selection(tolerance: int = 32):
    """Grows the current selection to include adjacent pixels of similar color.
    Requires an active selection.

    Args:
        tolerance (int): How similar adjacent pixels must be to be included (0 to 255).
    """

    command = createCommand("growSelection", {
        "tolerance": tolerance
    })

    return sendCommand(command)

@mcp.tool()
def select_similar(tolerance: int = 32):
    """Expands the current selection to include all pixels of similar color
    anywhere in the image (not just adjacent pixels). Requires an active selection.

    Args:
        tolerance (int): How similar pixels must be to be included (0 to 255).
    """

    command = createCommand("selectSimilar", {
        "tolerance": tolerance
    })

    return sendCommand(command)

@mcp.tool()
def add_curves_adjustment_layer(
    layer_id: int,
    channel_curves: list):
    """Adds a curves adjustment layer above the layer with the specified ID.

    Each entry in channel_curves defines a curve for one channel via control
    points. Each point maps an input tonal value (0 to 255) to an output value
    (0 to 255). Points must be sorted by ascending input value, and should
    normally include the endpoints (0 and 255) plus 1 to 3 mid points.

    Example (classic S-curve for added contrast on the composite channel):
    [
        {
            "channel": "composite",
            "points": [
                {"input": 0, "output": 0},
                {"input": 64, "output": 50},
                {"input": 192, "output": 205},
                {"input": 255, "output": 255}
            ]
        }
    ]

    Args:
        layer_id (int): The ID of the layer to add the adjustment layer above.
        channel_curves (list): List of curve definitions. Each has a "channel"
            ("composite", "red", "green" or "blue") and a "points" list of
            {"input": int, "output": int} dicts.
    """

    command = createCommand("addCurvesAdjustmentLayer", {
        "layerId": layer_id,
        "channelCurves": channel_curves
    })

    return sendCommand(command)

@mcp.tool()
def add_levels_adjustment_layer(
    layer_id: int,
    channel: str = "composite",
    input_black: int = 0,
    input_white: int = 255,
    gamma: float = 1.0,
    output_black: int = 0,
    output_white: int = 255):
    """Adds a levels adjustment layer above the layer with the specified ID.

    Args:
        layer_id (int): The ID of the layer to add the adjustment layer above.
        channel (str): The channel to adjust: "composite", "red", "green" or "blue".
        input_black (int): Input black point (0 to 253). Raising this darkens shadows.
        input_white (int): Input white point (2 to 255). Lowering this brightens highlights.
        gamma (float): Midtone gamma (0.1 to 9.99). Above 1.0 brightens midtones,
            below 1.0 darkens them.
        output_black (int): Output black point (0 to 255).
        output_white (int): Output white point (0 to 255).
    """

    command = createCommand("addLevelsAdjustmentLayer", {
        "layerId": layer_id,
        "channel": channel,
        "inputBlack": input_black,
        "inputWhite": input_white,
        "gamma": gamma,
        "outputBlack": output_black,
        "outputWhite": output_white
    })

    return sendCommand(command)

@mcp.tool()
def add_hue_saturation_adjustment_layer(
    layer_id: int,
    hue: int = 0,
    saturation: int = 0,
    lightness: int = 0,
    colorize: bool = False):
    """Adds a hue/saturation adjustment layer above the layer with the specified ID.

    Args:
        layer_id (int): The ID of the layer to add the adjustment layer above.
        hue (int): Hue shift in degrees (-180 to 180).
        saturation (int): Saturation adjustment (-100 to 100).
        lightness (int): Lightness adjustment (-100 to 100).
        colorize (bool): If True, colorizes the image with the given hue rather
            than shifting existing hues.
    """

    command = createCommand("addHueSaturationAdjustmentLayer", {
        "layerId": layer_id,
        "hue": hue,
        "saturation": saturation,
        "lightness": lightness,
        "colorize": colorize
    })

    return sendCommand(command)

@mcp.tool()
def add_selective_color_adjustment_layer(
    layer_id: int,
    corrections: list,
    method: str = "relative"):
    """Adds a selective color adjustment layer above the layer with the specified ID,
    adjusting the amount of process colors within a specific color range.

    Example (make reds less magenta and slightly darker):
    [
        {"target": "reds", "cyan": 0, "magenta": -20, "yellow": 0, "black": 5}
    ]

    Args:
        layer_id (int): The ID of the layer to add the adjustment layer above.
        corrections (list): List of corrections. Each has a "target" (one of
            "reds", "yellows", "greens", "cyans", "blues", "magentas", "whites",
            "neutrals", "blacks") and "cyan", "magenta", "yellow", "black"
            values from -100 to 100.
        method (str): "relative" adjusts proportionally to existing values,
            "absolute" adjusts by absolute amounts.
    """

    command = createCommand("addSelectiveColorAdjustmentLayer", {
        "layerId": layer_id,
        "corrections": corrections,
        "method": method
    })

    return sendCommand(command)

@mcp.tool()
def paint_brush_stroke(
    layer_id: int,
    points: list,
    color: dict,
    brush_size: int = 20,
    hardness: int = 100,
    opacity: int = 100):
    """Paints a brush stroke on the specified layer along a path defined by points.
    The stroke is drawn by creating a path through the points and stroking it with
    the brush tool, producing a smooth continuous stroke.

    The layer must be a pixel layer (not a text or adjustment layer).

    Args:
        layer_id (int): The ID of the pixel layer to paint on.
        points (list): List of at least 2 points defining the stroke path, each
            a dict with "x" and "y" pixel positions. More points create more
            complex stroke shapes.
        color (dict): Brush color with red, green and blue properties (0 to 255).
        brush_size (int): Brush diameter in pixels.
        hardness (int): Brush edge hardness (0 to 100). 100 is a hard edge,
            0 is very soft.
        opacity (int): Brush opacity (0 to 100).
    """

    command = createCommand("paintBrushStroke", {
        "layerId": layer_id,
        "points": points,
        "color": color,
        "brushSize": brush_size,
        "hardness": hardness,
        "opacity": opacity
    })

    return sendCommand(command)

@mcp.tool()
def eraser_stroke(
    layer_id: int,
    points: list,
    brush_size: int = 20,
    hardness: int = 100,
    opacity: int = 100):
    """Erases pixels on the specified layer along a path defined by points, using
    the eraser tool stroked along the path.

    Args:
        layer_id (int): The ID of the pixel layer to erase on.
        points (list): List of at least 2 points defining the stroke path, each
            a dict with "x" and "y" pixel positions.
        brush_size (int): Eraser diameter in pixels.
        hardness (int): Eraser edge hardness (0 to 100).
        opacity (int): Eraser strength (0 to 100).
    """

    command = createCommand("eraserStroke", {
        "layerId": layer_id,
        "points": points,
        "brushSize": brush_size,
        "hardness": hardness,
        "opacity": opacity
    })

    return sendCommand(command)

@mcp.tool()
def smudge_stroke(
    layer_id: int,
    points: list,
    brush_size: int = 20,
    hardness: int = 50,
    opacity: int = 100):
    """Smudges pixels on the specified layer along a path defined by points, using
    the smudge tool stroked along the path. Useful for blending and painterly effects.

    Args:
        layer_id (int): The ID of the pixel layer to smudge.
        points (list): List of at least 2 points defining the stroke path, each
            a dict with "x" and "y" pixel positions.
        brush_size (int): Smudge brush diameter in pixels.
        hardness (int): Brush edge hardness (0 to 100).
        opacity (int): Smudge strength (0 to 100).
    """

    command = createCommand("smudgeStroke", {
        "layerId": layer_id,
        "points": points,
        "brushSize": brush_size,
        "hardness": hardness,
        "opacity": opacity
    })

    return sendCommand(command)


# Neural filters (Phase 2, EXPERIMENTAL)
#
# Descriptor envelope verified against Adobe's official neural-filter-sample.
# Per-filter parameter keys are version-sensitive; the capture tools below
# record real descriptors from a manual filter run for exact replay.

NEURAL_PRESETS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "neural_filter_presets.json")


def _load_neural_presets() -> dict:
    try:
        with open(NEURAL_PRESETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_neural_presets(presets: dict):
    with open(NEURAL_PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=2)


@mcp.tool()
def apply_neural_filter(
    layer_id: int,
    raw_descriptor: dict = {},
    filter_id: str = "",
    values: dict = {},
    output_type: int = 2,
    filter_version: str = "1.0",
    raw_filter_stack: list = []):
    """
    EXPERIMENTAL. Applies a Photoshop Neural Filter to the specified layer via
    batchPlay. The filter MUST already be downloaded in Photoshop
    (Filter > Neural Filters gallery).

    IMPORTANT (verified live on Photoshop 2026): only raw_descriptor replay
    actually executes. Descriptors built from filter_id/values are accepted
    but silently do nothing, because modern Photoshop requires the compiled
    NF_SPL_GRAPH that only a captured descriptor contains. The working flow:
    start_neural_filter_capture -> apply the filter manually once ->
    save_captured_neural_filter -> apply_neural_filter_preset (or pass the
    captured descriptor here as raw_descriptor).

    The filter_id/values/raw_filter_stack forms are kept for older Photoshop
    builds (pre-2024) where the NF_UI_DATA envelope alone still executes.

    Args:
        layer_id (int): ID of the layer to apply the filter to.
        raw_descriptor (dict): A complete captured neuralGalleryFilters
            descriptor (from get_captured_neural_filters). Replayed exactly
            as recorded. Takes precedence over all other arguments.
        filter_id (str): LEGACY. Neural filter identifier (e.g.
            "internal.StyleTransfer").
        values (dict): LEGACY. Filter-specific spl:: parameter keys.
        output_type (int): LEGACY. NF_OUTPUT_TYPE for the built envelope.
        filter_version (str): LEGACY. Filter stack entry version.
        raw_filter_stack (list): LEGACY. A spl::filterStack array to wrap in
            a built envelope (which modern Photoshop ignores).
    """

    options = {
        "layerId": layer_id
    }

    if raw_descriptor:
        options["rawDescriptor"] = raw_descriptor
    elif raw_filter_stack:
        options["rawFilterStack"] = raw_filter_stack
        options["outputType"] = output_type
    else:
        options["filterId"] = filter_id
        options["values"] = values
        options["filterVersion"] = filter_version
        options["outputType"] = output_type

    command = createCommand("applyNeuralFilter", options)

    return sendCommand(command)


@mcp.tool()
def save_captured_neural_filter(preset_name: str, event_index: int = -1, description: str = ""):
    """
    Saves a Neural Filter descriptor captured with start_neural_filter_capture
    as a named preset that persists across restarts and can be replayed with
    apply_neural_filter_preset. Overwrites an existing preset with the same
    name.

    Workflow: start_neural_filter_capture -> user applies the filter manually
    once in Photoshop -> save_captured_neural_filter("my_preset").

    Args:
        preset_name (str): Name for the preset (e.g. "style_transfer_dixon").
        event_index (int): Which captured event to save (default -1, the most
            recent).
        description (str): Optional description of what the preset does.
    """

    command = createCommand("getCapturedNeuralFilters", {})
    r = sendCommand(command)

    events = r.get("response", {}).get("events", [])

    if not events:
        raise ValueError(
            "No captured neural filter events. Call start_neural_filter_capture, "
            "apply a filter manually in Photoshop, then retry."
        )

    try:
        descriptor = events[event_index]["descriptor"]
    except IndexError:
        raise ValueError(f"event_index {event_index} out of range; {len(events)} event(s) captured")

    presets = _load_neural_presets()
    presets[preset_name] = {
        "description": description,
        "descriptor": descriptor
    }
    _save_neural_presets(presets)

    filter_ids = [
        f.get("spl::id", "?")
        for f in descriptor.get("NF_UI_DATA", {}).get("spl::filterStack", [])
    ]

    return {
        "status": "SUCCESS",
        "preset_name": preset_name,
        "filters": filter_ids,
        "saved_to": NEURAL_PRESETS_FILE
    }


@mcp.tool()
def apply_neural_filter_preset(preset_name: str, layer_id: int):
    """
    Applies a saved Neural Filter preset (created with
    save_captured_neural_filter) to the specified layer by replaying the
    captured descriptor exactly. This is the reliable way to run neural
    filters programmatically on modern Photoshop. The preset's filter must
    still be downloaded in the Neural Filters gallery.

    Args:
        preset_name (str): Name of a saved preset (see list_neural_filter_presets).
        layer_id (int): ID of the layer to apply the preset to.
    """

    presets = _load_neural_presets()

    if preset_name not in presets:
        raise ValueError(
            f"Unknown preset '{preset_name}'. "
            f"Available: {', '.join(sorted(presets)) or '(none)'}"
        )

    command = createCommand("applyNeuralFilter", {
        "layerId": layer_id,
        "rawDescriptor": presets[preset_name]["descriptor"]
    })

    return sendCommand(command)


@mcp.tool()
def list_neural_filter_presets():
    """
    Lists saved Neural Filter presets with their descriptions and the filter
    ids they contain.
    """

    presets = _load_neural_presets()

    return {
        "presets": [
            {
                "name": name,
                "description": data.get("description", ""),
                "filters": [
                    f.get("spl::id", "?")
                    for f in data.get("descriptor", {}).get("NF_UI_DATA", {}).get("spl::filterStack", [])
                ]
            }
            for name, data in sorted(presets.items())
        ]
    }


@mcp.tool()
def delete_neural_filter_preset(preset_name: str):
    """
    Deletes a saved Neural Filter preset.

    Args:
        preset_name (str): Name of the preset to delete.
    """

    presets = _load_neural_presets()

    if preset_name not in presets:
        raise ValueError(
            f"Unknown preset '{preset_name}'. "
            f"Available: {', '.join(sorted(presets)) or '(none)'}"
        )

    del presets[preset_name]
    _save_neural_presets(presets)

    return {"status": "SUCCESS", "deleted": preset_name}


@mcp.tool()
def neural_style_transfer(
    layer_id: int,
    style: str = "style28_crop",
    preserve_color: bool = False,
    strength: int = 100,
    brush_size: int = 100,
    blur: int = 0):
    """
    LEGACY / pre-2024 Photoshop only. Applies the Style Transfer neural filter
    by building an NF_UI_DATA envelope. Verified live on Photoshop 2026: this
    form is accepted but SILENTLY DOES NOTHING (modern builds require the
    compiled graph only a captured descriptor contains). On modern Photoshop
    use the preset workflow instead: start_neural_filter_capture -> apply the
    filter manually once -> save_captured_neural_filter ->
    apply_neural_filter_preset.

    Args:
        layer_id (int): ID of the layer to apply style transfer to.
        style (str): Style preset name. Older builds use "style<N>_crop"
            names; modern builds use names like "ast-dixon".
        preserve_color (bool): Keep the original image colors.
        strength (int): Style strength / preserve weight (0 to 100).
        brush_size (int): Stroke size of the transferred style (0 to 100).
        blur (int): Amount of blur applied to the style (0 to 100).
    """

    command = createCommand("applyNeuralFilter", {
        "layerId": layer_id,
        "outputType": 2,
        "filterId": "internal.StyleTransfer",
        "filterVersion": "1.0",
        "values": {
            "spl::brushSize": brush_size,
            "spl::preserveColor": preserve_color,
            "spl::preserveWeight": strength,
            "spl::refImageAndCrop": None,
            "spl::sliderBlur": blur,
            "spl::sliderBrightness": None,
            "spl::sliderMultipleIterations": 0,
            "spl::sliderSaturation": None,
            "spl::style": style,
            "spl::style_transfer_option": "style_transfer"
        }
    })

    return sendCommand(command)


@mcp.tool()
def start_neural_filter_capture():
    """
    EXPERIMENTAL. Starts recording Neural Filter descriptors. After calling
    this, apply a neural filter manually in Photoshop (Filter > Neural
    Filters); every application fires an event whose descriptor is recorded.
    Read the recordings with get_captured_neural_filters and replay them via
    apply_neural_filter's raw_filter_stack argument. Calling this again clears
    previously captured events.
    """

    command = createCommand("startNeuralFilterCapture", {})

    return sendCommand(command)


@mcp.tool()
def get_captured_neural_filters():
    """
    EXPERIMENTAL. Returns Neural Filter descriptors recorded since
    start_neural_filter_capture was called. The spl::filterStack array inside
    a captured descriptor's NF_UI_DATA can be replayed exactly via
    apply_neural_filter(raw_filter_stack=...).
    """

    command = createCommand("getCapturedNeuralFilters", {})

    return sendCommand(command)


# Batch processing (Phase 2)
#
# Maps batch operation names to the UXP action they dispatch and the option
# key used to target a layer. Settings for each operation use the same
# camelCase option keys as the corresponding single-layer tool's command.
BATCH_OPERATIONS = {
    "gaussian_blur": ("applyGaussianBlur", "layerId"),
    "motion_blur": ("applyMotionBlur", "layerId"),
    "scale_layer": ("scaleLayer", "layerId"),
    "rotate_layer": ("rotateLayer", "layerId"),
    "flip_layer": ("flipLayer", "layerId"),
    "translate_layer": ("translateLayer", "layerId"),
    "set_layer_visibility": ("setLayerVisibility", "layerId"),
    "set_layer_properties": ("setLayerProperties", "layerId"),
    "rasterize_layer": ("rasterizeLayer", "layerId"),
    "delete_layer": ("deleteLayer", "layerId"),
    "duplicate_layer": ("duplicateLayer", "sourceLayerId"),
    "harmonize_layer": ("harmonizeLayer", "layerId"),
    "drop_shadow": ("addDropShadowLayerStyle", "layerId"),
    "stroke_style": ("addStrokeLayerStyle", "layerId"),
    "gradient_style": ("createGradientLayerStyle", "layerId"),
    "brightness_contrast": ("addBrightnessContrastAdjustmentLayer", "layerId"),
    "vibrance": ("addAdjustmentLayerVibrance", "layerId"),
    "black_and_white": ("addAdjustmentLayerBlackAndWhite", "layerId"),
    "color_balance": ("addColorBalanceAdjustmentLayer", "layerId"),
    "curves": ("addCurvesAdjustmentLayer", "layerId"),
    "levels": ("addLevelsAdjustmentLayer", "layerId"),
    "hue_saturation": ("addHueSaturationAdjustmentLayer", "layerId"),
    "selective_color": ("addSelectiveColorAdjustmentLayer", "layerId"),
    "paint_brush_stroke": ("paintBrushStroke", "layerId"),
    "eraser_stroke": ("eraserStroke", "layerId"),
    "smudge_stroke": ("smudgeStroke", "layerId"),
}

SEQUENCES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "action_sequences.json")


def _load_sequences() -> dict:
    try:
        with open(SEQUENCES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_sequences(sequences: dict):
    with open(SEQUENCES_FILE, "w", encoding="utf-8") as f:
        json.dump(sequences, f, indent=2)


def _run_operation(operation: str, layer_id: int, settings: dict):
    action, layer_key = BATCH_OPERATIONS[operation]
    options = dict(settings or {})
    options[layer_key] = layer_id
    return sendCommand(createCommand(action, options))


def _validate_operations(operations: list):
    for i, step in enumerate(operations):
        if not isinstance(step, dict) or "operation" not in step:
            raise ValueError(f"Step {i} must be a dict with an 'operation' key")
        if step["operation"] not in BATCH_OPERATIONS:
            raise ValueError(
                f"Step {i}: unknown operation '{step['operation']}'. "
                f"Valid operations: {', '.join(sorted(BATCH_OPERATIONS))}"
            )


@mcp.tool()
def batch_process_layers(operation: str, layer_ids: list, settings: dict = {}):
    """
    Applies a single operation to multiple layers in one call, collecting
    per-layer results. Layers that fail do not stop the batch; the error is
    recorded and processing continues with the next layer.

    Args:
        operation (str): Operation to apply. One of: gaussian_blur, motion_blur,
            scale_layer, rotate_layer, flip_layer, translate_layer,
            set_layer_visibility, set_layer_properties, rasterize_layer,
            delete_layer, duplicate_layer, harmonize_layer, drop_shadow,
            stroke_style, gradient_style, brightness_contrast, vibrance,
            black_and_white, color_balance, curves, levels, hue_saturation,
            selective_color, paint_brush_stroke, eraser_stroke, smudge_stroke.
        layer_ids (list): IDs of the layers to process, in order.
        settings (dict): Options for the operation, using the same camelCase
            keys as the corresponding single-layer tool's options (excluding
            the layer id, which is injected per layer). Examples:
            gaussian_blur -> {"radius": 4.0}
            motion_blur -> {"angle": 45, "distance": 30}
            set_layer_properties -> {"blendMode": "MULTIPLY", "layerOpacity": 80,
                "fillOpacity": 100, "isClippingMask": false}
            brightness_contrast -> {"brightness": 20, "contrast": 10}
    """

    if operation not in BATCH_OPERATIONS:
        raise ValueError(
            f"Unknown operation '{operation}'. "
            f"Valid operations: {', '.join(sorted(BATCH_OPERATIONS))}"
        )

    results = []
    succeeded = 0
    failed = 0

    for layer_id in layer_ids:
        try:
            response = _run_operation(operation, layer_id, settings)
            results.append({"layerId": layer_id, "status": "SUCCESS", "response": response})
            succeeded += 1
        except socket_client.AppError as e:
            results.append({"layerId": layer_id, "status": "FAILURE", "error": str(e)})
            failed += 1
        except RuntimeError as e:
            # Connection-level failure: remaining layers cannot succeed, abort
            results.append({"layerId": layer_id, "status": "FAILURE", "error": str(e)})
            failed += 1
            for remaining in layer_ids[layer_ids.index(layer_id) + 1:]:
                results.append({"layerId": remaining, "status": "SKIPPED",
                                "error": "Skipped: connection to Photoshop lost"})
            break

    return {
        "operation": operation,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": len(layer_ids) - succeeded - failed,
        "results": results
    }


@mcp.tool()
def create_action_sequence(sequence_name: str, operations: list, description: str = ""):
    """
    Saves a named, reusable sequence of operations that can later be replayed
    against one or more layers with play_action_sequence. Sequences persist
    across server restarts. If a sequence with the same name exists it is
    overwritten.

    Args:
        sequence_name (str): Name for the sequence (e.g. "vintage_look").
        operations (list): Ordered steps, each a dict with:
            - operation (str): An operation name (see batch_process_layers for
              the valid list).
            - settings (dict): Options for the operation, same camelCase keys
              as the corresponding single-layer tool (layer id excluded).
            Example: [{"operation": "brightness_contrast",
                       "settings": {"brightness": -10, "contrast": 15}},
                      {"operation": "vibrance",
                       "settings": {"vibrance": -30, "saturation": -20}}]
        description (str): Optional human-readable description of what the
            sequence does.
    """

    _validate_operations(operations)

    sequences = _load_sequences()
    sequences[sequence_name] = {
        "description": description,
        "operations": operations
    }
    _save_sequences(sequences)

    return {
        "status": "SUCCESS",
        "sequence_name": sequence_name,
        "steps": len(operations),
        "saved_to": SEQUENCES_FILE
    }


@mcp.tool()
def play_action_sequence(sequence_name: str, layer_ids: list):
    """
    Replays a saved action sequence against each of the specified layers, in
    order. All steps are applied to a layer before moving to the next layer.
    A failing step records an error and continues with the layer's next step;
    a lost connection aborts the run.

    Args:
        sequence_name (str): Name of a sequence created with create_action_sequence.
        layer_ids (list): IDs of the layers to run the sequence against.
    """

    sequences = _load_sequences()
    if sequence_name not in sequences:
        raise ValueError(
            f"Unknown sequence '{sequence_name}'. "
            f"Available: {', '.join(sorted(sequences)) or '(none)'}"
        )

    operations = sequences[sequence_name]["operations"]
    _validate_operations(operations)

    results = []
    aborted = False

    for layer_id in layer_ids:
        if aborted:
            results.append({"layerId": layer_id, "status": "SKIPPED",
                            "error": "Skipped: connection to Photoshop lost"})
            continue

        step_results = []
        for i, step in enumerate(operations):
            try:
                response = _run_operation(step["operation"], layer_id, step.get("settings", {}))
                step_results.append({"step": i, "operation": step["operation"],
                                     "status": "SUCCESS", "response": response})
            except socket_client.AppError as e:
                step_results.append({"step": i, "operation": step["operation"],
                                     "status": "FAILURE", "error": str(e)})
            except RuntimeError as e:
                step_results.append({"step": i, "operation": step["operation"],
                                     "status": "FAILURE", "error": str(e)})
                aborted = True
                break

        failed = sum(1 for s in step_results if s["status"] == "FAILURE")
        results.append({
            "layerId": layer_id,
            "status": "FAILURE" if failed else "SUCCESS",
            "steps": step_results
        })

    return {"sequence_name": sequence_name, "results": results}


@mcp.tool()
def list_action_sequences():
    """
    Lists all saved action sequences with their descriptions and steps.
    """

    sequences = _load_sequences()
    return {
        "sequences": [
            {
                "name": name,
                "description": data.get("description", ""),
                "operations": data.get("operations", [])
            }
            for name, data in sorted(sequences.items())
        ]
    }


@mcp.tool()
def delete_action_sequence(sequence_name: str):
    """
    Deletes a saved action sequence.

    Args:
        sequence_name (str): Name of the sequence to delete.
    """

    sequences = _load_sequences()
    if sequence_name not in sequences:
        raise ValueError(
            f"Unknown sequence '{sequence_name}'. "
            f"Available: {', '.join(sorted(sequences)) or '(none)'}"
        )

    del sequences[sequence_name]
    _save_sequences(sequences)

    return {"status": "SUCCESS", "deleted": sequence_name}


@mcp.resource("config://get_instructions")
def get_instructions() -> str:
    """Read this first! Returns information and instructions on how to use Photoshop and this API"""

    return f"""
    You are a photoshop expert who is creative and loves to help other people learn to use Photoshop and create. You are well versed in composition, design and color theory, and try to follow that theory when making decisions.

    Unless otherwise specified, all commands act on the currently active document in Photoshop

    Rules to follow:

    1. Think deeply about how to solve the task
    2. Always check your work
    3. You can view the current visible photoshop file by calling get_document_image
    4. Pay attention to font size (dont make it too big)
    5. Always use alignment (align_content()) to position your text.
    6. Read the info for the API calls to make sure you understand the requirements and arguments
    7. When you make a selection, clear it once you no longer need it

    Here are some general tips for when working with Photoshop.

    In general, layers are created from bottom up, so keep that in mind as you figure out the order or operations. If you want you have lower layers show through higher ones you must either change the opacity of the higher layers and / or blend modes.

    When using fonts there are a couple of things to keep in mind. First, the font origin is the bottom left of the font, not the top right.

    Suggestions for sizes:
    Paragraph text : 8 to 12 pts
    Headings : 14 - 20 pts
    Single Word Large : 20 to 25pt

    Pay attention to what layer names are needed for. Sometimes the specify the name of a newly created layer and sometimes they specify the name of the layer that the action should be performed on.

    As a general rule, you should not flatten files unless asked to do so, or its necessary to apply an effect or look.

    When generating an image, you do not need to first create a pixel layer. A layer will automatically be created when you generate the image.

    Colors are defined via a dict with red, green and blue properties with values between 0 and 255
    {{"red":255, "green":0, "blue":0}}

    Bounds is defined as a dict with top, left, bottom and right properties
    {{"top": 0, "left": 0, "bottom": 250, "right": 300}}

    Valid options for API calls:

    alignment_modes: {", ".join(alignment_modes)}

    justification_modes: {", ".join(justification_modes)}

    blend_modes: {", ".join(blend_modes)}

    anchor_positions: {", ".join(anchor_positions)}

    interpolation_methods: {", ".join(interpolation_methods)}

    fonts: {", ".join(font_names[:FONT_LIMIT])}
    """

font_names = list_all_fonts_postscript()

interpolation_methods = [
   "AUTOMATIC",
   "BICUBIC",
   "BICUBICSHARPER",
   "BICUBICSMOOTHER",
   "BILINEAR",
   "NEARESTNEIGHBOR"
]

anchor_positions = [
   "BOTTOMCENTER",
   "BOTTOMLEFT", 
   "BOTTOMRIGHT", 
   "MIDDLECENTER", 
   "MIDDLELEFT", 
   "MIDDLERIGHT", 
   "TOPCENTER", 
   "TOPLEFT", 
   "TOPRIGHT"
]

justification_modes = [
    "CENTER",
    "CENTERJUSTIFIED",
    "FULLYJUSTIFIED",
    "LEFT",
    "LEFTJUSTIFIED",
    "RIGHT",
    "RIGHTJUSTIFIED"
]

alignment_modes = [
    "LEFT",
    "CENTER_HORIZONTAL",
    "RIGHT",
    "TOP",
    "CENTER_VERTICAL",
    "BOTTOM"
]

blend_modes = [
    "COLOR",
    "COLORBURN",
    "COLORDODGE",
    "DARKEN",
    "DARKERCOLOR",
    "DIFFERENCE",
    "DISSOLVE",
    "DIVIDE",
    "EXCLUSION",
    "HARDLIGHT",
    "HARDMIX",
    "HUE",
    "LIGHTEN",
    "LIGHTERCOLOR",
    "LINEARBURN",
    "LINEARDODGE",
    "LINEARLIGHT",
    "LUMINOSITY",
    "MULTIPLY",
    "NORMAL",
    "OVERLAY",
    "PASSTHROUGH",
    "PINLIGHT",
    "SATURATION",
    "SCREEN",
    "SOFTLIGHT",
    "SUBTRACT",
    "VIVIDLIGHT"
]
