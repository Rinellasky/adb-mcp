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
import tempfile
import os
import io


#logger.log(f"Python path: {sys.executable}")
#logger.log(f"PYTHONPATH: {os.environ.get('PYTHONPATH')}")
#logger.log(f"Current working directory: {os.getcwd()}")
#logger.log(f"Sys.path: {sys.path}")


mcp_name = "Adobe Premiere MCP Server"
mcp = FastMCP(mcp_name, log_level="ERROR")
print(f"{mcp_name} running on stdio", file=sys.stderr)

APPLICATION = "premiere"
PROXY_URL = 'http://localhost:3001'
PROXY_TIMEOUT = 20

socket_client.configure(
    app=APPLICATION, 
    url=PROXY_URL,
    timeout=PROXY_TIMEOUT
)

init(APPLICATION, socket_client)

@mcp.tool()
def get_project_info():
    """
    Returns info on the currently active project in Premiere Pro.
    """

    command = createCommand("getProjectInfo", {
    })

    return sendCommand(command)

@mcp.tool()
def save_project():
    """
    Saves the active project in Premiere Pro.
    """

    command = createCommand("saveProject", {
    })

    return sendCommand(command)

@mcp.tool()
def save_project_as(file_path: str):
    """Saves the current Premiere project to the specified location.
    
    Args:
        file_path (str): The absolute path (including filename) where the file will be saved.
            Example: "/Users/username/Documents/project.prproj"

    """
    
    command = createCommand("saveProjectAs", {
        "filePath":file_path
    })

    return sendCommand(command)

@mcp.tool()
def open_project(file_path: str):
    """Opens the Premiere project at the specified path.
    
    Args:
        file_path (str): The absolute path (including filename) of the Premiere Pro project to open.
            Example: "/Users/username/Documents/project.prproj"

    """
    
    command = createCommand("openProject", {
        "filePath":file_path
    })

    return sendCommand(command)


@mcp.tool()
def create_project(directory_path: str, project_name: str):
    """
    Create a new Premiere project.

    Creates a new Adobe Premiere project file, saves it to the specified location and then opens it in Premiere.

    The function initializes an empty project with default settings.

    Args:
        directory_path (str): The full path to the directory where the project file will be saved. This directory must exist before calling the function.
        project_name (str): The name to be given to the project file. The '.prproj' extension will be added.
    """

    command = createCommand("createProject", {
        "path":directory_path,
        "name":project_name
    })

    return sendCommand(command)


@mcp.tool()
def create_bin_in_active_project(bin_name:str):
    """
    Creates a new bin / folder in the root project.

    Args:
        name (str) : The name of the bin to be created
 

    """

    command = createCommand("createBinInActiveProject", {
        "binName": bin_name
    })

    return sendCommand(command)

@mcp.tool()
def export_sequence(sequence_id: str, output_path: str, preset_path: str):
    """
    Exports a Premiere Pro sequence to a video file using specified export settings.

    This function renders and exports the specified sequence from the active Premiere Pro project
    to a video file on the file system. The export process uses a preset file to determine
    encoding settings, resolution, format, and other export parameters.

    Args:
        sequence_id (str): The unique identifier of the sequence to export.
            This should be the ID of an existing sequence in the current Premiere Pro project.
            
        output_path (str): The complete file system path where the exported video will be saved.
            Must include the full directory path, filename, and appropriate file extension.
            
        preset_path (str): The file system path to the export preset file (.epr) that defines the export settings including codec, resolution, bitrate, and format.
        
        IMPORTANT: The export may take an extended period of time, so if the call times out, it most likely means the export is still in progress.
    """
    command = createCommand("exportSequence", {
        "sequenceId": sequence_id,
        "outputPath": output_path,
        "presetPath": preset_path
    })
    
    return sendCommand(command)

@mcp.tool()
def move_project_items_to_bin(item_names: list[str], bin_name: str):
    """
    Moves specified project items to an existing bin/folder in the project.

    Args:
        item_names (list[str]): A list of names of project items to move to the specified bin.
            These should be the exact names of items as they appear in the project.
        bin_name (str): The name of the existing bin to move the project items to.
            The bin must already exist in the project.
            
    Returns:
        dict: Response from the Premiere Pro operation indicating success status.
        
    Raises:
        RuntimeError: If the bin doesn't exist, items don't exist, or the operation fails.
        
    Example:
        move_project_items_to_bin(
            item_names=["video1.mp4", "audio1.wav", "image1.png"], 
            bin_name="Media Assets"
        )
    """
    command = createCommand("moveProjectItemsToBin", {
        "itemNames": item_names,
        "binName": bin_name
    })

    return sendCommand(command)

@mcp.tool()
def set_audio_track_mute(sequence_id:str, audio_track_index: int, mute: bool):
    """
    Sets the mute property on the specified audio track. If mute is true, all clips on the track will be muted and not played.

    Args:
        sequence_id (str) : The id of the sequence on which to set the audio track mute.
        audio_track_index (int): The index of the audio track to mute or unmute. Indices start at 0 for the first audio track.
        mute (bool): Whether the track should be muted.
            - True: Mutes the track (audio will not be played)
            - False: Unmutes the track (audio will be played normally)

    """

    command = createCommand("setAudioTrackMute", {
        "sequenceId": sequence_id,
        "audioTrackIndex":audio_track_index,
        "mute":mute
    })

    return sendCommand(command)


@mcp.tool()
def set_active_sequence(sequence_id: str):
    """
    Sets the sequence with the specified id as the active sequence within Premiere Pro (currently selected and visible in timeline)
    
    Args:
        sequence_id (str): ID for the sequence to be set as active
    """

    command = createCommand("setActiveSequence", {
        "sequenceId":sequence_id
    })

    return sendCommand(command)


@mcp.tool()
def create_sequence_from_media(item_names: list[str], sequence_name: str = "default"):
    """
    Creates a new sequence from the specified project items, placing clips on the timeline in the order they are provided.
    
    If there is not an active sequence the newly created sequence will be set as the active sequence when created.
    
    Args:
        item_names (list[str]): A list of project item names to include in the sequence in the desired order.
        sequence_name (str, optional): The name to give the new sequence. Defaults to "default".
    """


    command = createCommand("createSequenceFromMedia", {
        "itemNames":item_names,
        "sequenceName":sequence_name
    })

    return sendCommand(command)

@mcp.tool()
def close_gaps_on_sequence(sequence_id: str, track_index: int, track_type: str):
    """
    Closes gaps on the specified track(s) in a sequence's timeline.

    This function removes empty spaces (gaps) between clips on the timeline by moving
    clips leftward to fill any empty areas. This is useful for cleaning up the timeline
    after removing clips or when clips have been moved leaving gaps.

    Args:
        sequence_id (str): The ID of the sequence to close gaps on.
        track_index (int): The index of the track to close gaps on.
            Track indices start at 0 for the first track and increment upward.
            For video tracks, this refers to video track indices.
            For audio tracks, this refers to audio track indices.
        track_type (str): Specifies which type of tracks to close gaps on.
            Valid values:
            - "VIDEO": Close gaps only on the specified video track
            - "AUDIO": Close gaps only on the specified audio track  

    """
    
    command = createCommand("closeGapsOnSequence", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "trackType": track_type,
    })

    return sendCommand(command)


@mcp.tool()
def remove_item_from_sequence(sequence_id: str, track_index:int, track_item_index: int, track_type:str, ripple_delete:bool=True):
    """
    Removes a specified media item from the sequence's timeline.

    Args:
        sequence_id (str): The id for the sequence to remove the media from
        track_index (int): The index of the track containing the target clip.
            Track indices start at 0 for the first track and increment upward.
        track_item_index (int): The index of the clip within the track to remove.
            Clip indices start at 0 for the first clip in the track and increment from left to right.
        track_type (str): Specifies which type of tracks being removed.
            Valid values:
            - "VIDEO": Close gaps only on the specified video track
            - "AUDIO": Close gaps only on the specified audio track
        ripple_delete (bool, optional): Whether to perform a ripple delete operation. Defaults to True.
            - True: Removes the clip and shifts all subsequent clips leftward to close the gap
            - False: Removes the clip but leaves a gap in the timeline where the clip was located
    """
    
    command = createCommand("removeItemFromSequence", {
        "sequenceId": sequence_id,
        "trackItemIndex":track_item_index,
        "trackIndex":track_index,
        "trackType":track_type,
        "rippleDelete":ripple_delete
    })

    return sendCommand(command)

@mcp.tool()
def add_marker_to_sequence(sequence_id: str, 
                           marker_name: str, 
                           start_time_ticks: int, 
                           duration_ticks: int, 
                           comments: str,
                           marker_type: str = "Comment"):
    """
    Adds a marker to the specified sequence.

    Args:
        sequence_id (str): 
            The ID of the sequence to which the marker will be added.

        marker_name (str): 
            The name/title of the marker.

        start_time_ticks (int):
            The timeline position where the marker starts, in ticks.
            (1 second = 254016000000 ticks)

        duration_ticks (int):
            The length of the marker in ticks.

        comments (str):
            Optional text comment to store in the marker.

        marker_type (str, optional):
            The type of marker to add. Defaults to "Comment".

            Supported marker types:
                - "Comment"      → General-purpose note marker.
                - "Chapter"      → Chapter point (used on export/DVD authoring).
                - "Segmentation" → Segmentation marker.
                - "WebLink"      → Web link marker.

    """

    command = createCommand("addMarkerToSequence", {
        "sequenceId": sequence_id,
        "markerName": marker_name,
        "startTimeTicks": start_time_ticks,
        "durationTicks": duration_ticks,
        "comments": comments,
        "markerType": marker_type
    })

    return sendCommand(command)



@mcp.tool()
def add_media_to_sequence(sequence_id:str, item_name: str, video_track_index: int, audio_track_index: int, insertion_time_ticks: int = 0, overwrite: bool = True):
    """
    Adds a specified media item to the active sequence's timeline.

    Args:
        sequence_id (str) : The id for the sequence to add the media to
        item_name (str): The name or identifier of the media item to add.
        video_track_index (int): The index of the video track where the item should be inserted.
        audio_track_index (int): The index of the audio track where the item should be inserted.
        insertion_time_ticks (int): The position on the timeline in ticks, with 0 being the beginning. The API will return positions of existing clips in ticks
        overwrite (bool, optional): Whether to overwrite existing content at the insertion point. Defaults to True. If False, any existing clips that overlap will be split and item inserted.
    """


    command = createCommand("addMediaToSequence", {
        "sequenceId": sequence_id,
        "itemName":item_name,
        "videoTrackIndex":video_track_index,
        "audioTrackIndex":audio_track_index,
        "insertionTimeTicks":insertion_time_ticks,
        "overwrite":overwrite
    })

    return sendCommand(command)


@mcp.tool()
def set_clip_disabled(sequence_id:str, track_index: int, track_item_index: int, track_type:str, disabled: bool):
    """
    Enables or disables a clip in the timeline.
    
    Args:
        sequence_id (str): The id for the sequence to set the clip disabled property.
        track_index (int): The index of the track containing the target clip.
            Track indices start at 0 for the first track and increment upward.
            For video tracks, this refers to video track indices.
            For audio tracks, this refers to audio track indices.
        track_item_index (int): The index of the clip within the track to enable/disable.
            Clip indices start at 0 for the first clip in the track and increment from left to right.
        track_type (str): Specifies which type of track to modify.
            Valid values:
            - "VIDEO": Modify clips on the specified video track
            - "AUDIO": Modify clips on the specified audio track
        disabled (bool): Whether to disable the clip.
            - True: Disables the clip (clip will not be visible during playback or export)
            - False: Enables the clip (normal visibility)
    """

    command = createCommand("setClipDisabled", {
        "sequenceId": sequence_id,
        "trackIndex":track_index,
        "trackItemIndex":track_item_index,
        "trackType":track_type,
        "disabled":disabled
    })

    return sendCommand(command)


@mcp.tool()
def set_clip_start_end_times(
    sequence_id: str, track_index: int, track_item_index: int, start_time_ticks: int, 
        end_time_ticks: int, track_type: str):
    """
    Sets the start and end time boundaries for a specified clip in the timeline.
    
    This function allows you to modify the duration and timing of video clips, audio clips, 
    and images that are already placed in the timeline by adjusting their in and out points. 
    The clip can be trimmed to a shorter duration or extended to a longer duration.
    
    Args:
        sequence_id (str): The id for the sequence containing the clip to modify.
        track_index (int): The index of the track containing the target clip.
            Track indices start at 0 for the first track and increment upward.
            For video tracks, this refers to video track indices.
            For audio tracks, this refers to audio track indices.
        track_item_index (int): The index of the clip within the track to modify.
            Clip indices start at 0 for the first clip in the track and increment from left to right.
        start_time_ticks (int): The new start time for the clip in ticks.
        end_time_ticks (int): The new end time for the clip in ticks.
        track_type (str): Specifies which type of tracks to modify clips on.
            Valid values:
            - "VIDEO": Modify clips only on the specified video track
            - "AUDIO": Modify clips only on the specified audio track  
        
    Note:
        - To trim a clip: Set start/end times within the original clip's duration
        - To extend a clip: Set end time beyond the original clip's duration  
        - Works with video clips, audio clips, and image files (like PSD files)
        - Times are specified in ticks (Premiere Pro's internal time unit)
    """

    command = createCommand("setClipStartEndTimes", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "trackItemIndex": track_item_index,
        "startTimeTicks": start_time_ticks,
        "endTimeTicks": end_time_ticks,
        "trackType": track_type
    })

    return sendCommand(command)

@mcp.tool()
def add_black_and_white_effect(sequence_id:str, video_track_index: int, track_item_index: int):
    """
    DEPRECATED: Use add_video_effect with effect_match_name "AE.ADBE Black & White"
    instead. Kept as a thin wrapper for compatibility.

    Adds a black and white effect to a clip at the specified track and position.

    Args:
        sequence_id (str) : The id for the sequence to add the effect to
        video_track_index (int): The index of the video track containing the target clip.
            Track indices start at 0 for the first video track and increment upward.
        track_item_index (int): The index of the clip within the track to apply the effect to.
            Clip indices start at 0 for the first clip in the track and increment from left to right.
    """

    command = createCommand("appendVideoFilter", {
        "sequenceId": sequence_id,
        "videoTrackIndex":video_track_index,
        "trackItemIndex":track_item_index,
        "effectName":"AE.ADBE Black & White",
        "properties":[
        ]
    })

    return sendCommand(command)

@mcp.tool()
def get_sequence_frame_image(sequence_id: str, seconds: int):
    """Returns a jpeg of the specified timestamp in the specified sequence in Premiere pro as an MCP Image object that can be displayed."""
    
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, f"frame_{sequence_id}_{seconds}.png")
    
    command = createCommand("exportFrame", {
        "sequenceId": sequence_id,
        "filePath": file_path,
        "seconds": seconds
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
def export_frame(sequence_id:str, file_path: str, seconds: int):
    """Captures a specific frame from the sequence at the given timestamp
    and exports it as a PNG or JPG (depending on file extension) image file to the specified path.
    
    Args:
        sequence_id (str) : The id for the sequence to export the frame from
        file_path (str): The destination path where the exported PNG / JPG image will be saved.
            Must include the full directory path and filename with .png or .jpg extension.
        seconds (int): The timestamp in seconds from the beginning of the sequence
            where the frame should be captured. The frame closest to this time position
            will be extracted.
    """
    
    command = createCommand("exportFrame", {
        "sequenceId": sequence_id,
        "filePath": file_path,
        "seconds":seconds
        }
    )

    return sendCommand(command)


@mcp.tool()
def add_gaussian_blur_effect(sequence_id: str, video_track_index: int, track_item_index: int, blurriness: float, blur_dimensions: str = "HORIZONTAL_VERTICAL"):
    """
    DEPRECATED: Use add_video_effect with effect_match_name "AE.ADBE Gaussian Blur 2"
    instead. Kept as a thin wrapper for compatibility.

    Adds a gaussian blur effect to a clip at the specified track and position.

    Args:
        sequence_id (str) : The id for the sequence to add the effect to
        video_track_index (int): The index of the video track containing the target clip.
            Track indices start at 0 for the first video track and increment upward.
            
        track_item_index (int): The index of the clip within the track to apply the effect to.
            Clip indices start at 0 for the first clip in the track and increment from left to right.
            
        blurriness (float): The intensity of the blur effect. Higher values create stronger blur.
            Recommended range is between 0.0 and 100.0 (Max 3000).
            
        blur_dimensions (str, optional): The direction of the blur effect. Defaults to "HORIZONTAL_VERTICAL".
            Valid options are:
            - "HORIZONTAL_VERTICAL": Blur in all directions
            - "HORIZONTAL": Blur only horizontally
            - "VERTICAL": Blur only vertically
    """
    dimensions = {"HORIZONTAL_VERTICAL": 0, "HORIZONTAL": 1, "VERTICAL": 2}
    
    # Validate blur_dimensions parameter
    if blur_dimensions not in dimensions:
        raise ValueError(f"Invalid blur_dimensions. ")

    command = createCommand("appendVideoFilter", {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "effectName": "AE.ADBE Gaussian Blur 2",
        "properties": [
            {"name": "Blur Dimensions", "value": dimensions[blur_dimensions]},
            {"name": "Blurriness", "value": blurriness}
        ]
    })

    return sendCommand(command)

def rgb_to_premiere_color3(rgb_color, alpha=1.0):
    """Converts RGB (0–255) dict to Premiere Pro color format [r, g, b, a] with floats (0.0–1.0)."""
    return [
        rgb_color["red"] / 255.0,
        rgb_color["green"] / 255.0,
        rgb_color["blue"] / 255.0,
        alpha
    ]

def rgb_to_premiere_color(rgb_color, alpha=255):
    """
    Converts an RGB(A) dict (0–255) to a 64-bit Premiere Pro color parameter (as int).
    Matches Adobe's internal ARGB 16-bit fixed-point format.
    """
    def to16bit(value):
        return int(round(value * 256))

    r16 = to16bit(rgb_color["red"] / 255.0)
    g16 = to16bit(rgb_color["green"] / 255.0)
    b16 = to16bit(rgb_color["blue"] / 255.0)
    a16 = to16bit(alpha / 255.0)

    high = (a16 << 16) | r16       # top 32 bits: A | R
    low = (g16 << 16) | b16        # bottom 32 bits: G | B

    packed_color = (high << 32) | low
    return packed_color



@mcp.tool()
def add_tint_effect(sequence_id: str, video_track_index: int, track_item_index: int, black_map:dict = {"red":0, "green":0, "blue":0}, white_map:dict = {"red":255, "green":255, "blue":255}, amount:int = 100):
    """
    DEPRECATED: Use add_video_effect with effect_match_name "AE.ADBE Tint"
    instead. Kept as a thin wrapper for compatibility.

    Adds the tint effect to a clip at the specified track and position.

    This function applies a tint effect that maps the dark and light areas of the clip to specified colors.

    Args:
        sequence_id (str) : The id for the sequence to add the effect to
        video_track_index (int): The index of the video track containing the target clip.
            Track indices start at 0 for the first video track and increment upward.
            
        track_item_index (int): The index of the clip within the track to apply the effect to.
            Clip indices start at 0 for the first clip in the track and increment from left to right.
            
        black_map (dict): The RGB color values to map black/dark areas to, with keys "red", "green", and "blue".
            Default is {"red":0, "green":0, "blue":0} (pure black).
            
        white_map (dict): The RGB color values to map white/light areas to, with keys "red", "green", and "blue".
            Default is {"red":255, "green":255, "blue":255} (pure white).
            
        amount (int): The intensity of the tint effect as a percentage, ranging from 0 to 100.
            Default is 100 (full tint effect).
    """

    command = createCommand("appendVideoFilter", {
        "sequenceId": sequence_id,
        "videoTrackIndex":video_track_index,
        "trackItemIndex":track_item_index,
        "effectName":"AE.ADBE Tint",
        "properties":[
            {"name":"Map Black To", "value":rgb_to_premiere_color(black_map)},
            {"name":"Map White To", "value":rgb_to_premiere_color(white_map)},
            {"name":"Amount to Tint", "value":amount / 100}
        ]
    })

    return sendCommand(command)



@mcp.tool()
def add_motion_blur_effect(sequence_id: str, video_track_index: int, track_item_index: int, direction: int, length: int):
    """
    DEPRECATED: Use add_video_effect with effect_match_name "AE.ADBE Motion Blur"
    instead. Kept as a thin wrapper for compatibility.

    Adds the directional blur effect to a clip at the specified track and position.

    This function applies a motion blur effect that simulates movement in a specific direction.

    Args:
        sequence_id (str) : The id for the sequence to add the effect to
        video_track_index (int): The index of the video track containing the target clip.
            Track indices start at 0 for the first video track and increment upward.
            
        track_item_index (int): The index of the clip within the track to apply the effect to.
            Clip indices start at 0 for the first clip in the track and increment from left to right.
            
        direction (int): The angle of the directional blur in degrees, ranging from 0 to 360.
            - 0/360: Vertical blur upward
            - 90: Horizontal blur to the right 
            - 180: Vertical blur downward
            - 270: Horizontal blur to the left
            
        length (int): The intensity or distance of the blur effect, ranging from 0 to 1000.
    """

    command = createCommand("appendVideoFilter", {
        "sequenceId": sequence_id,
        "videoTrackIndex":video_track_index,
        "trackItemIndex":track_item_index,
        "effectName":"AE.ADBE Motion Blur",
        "properties":[
            {"name":"Direction", "value":direction},
            {"name":"Blur Length", "value":length}
        ]
    })

    return sendCommand(command)

@mcp.tool()
def append_video_transition(sequence_id: str, video_track_index: int, track_item_index: int, transition_name: str, duration: float = 1.0, clip_alignment: float = 0.5):
    """
    Creates a transition between the specified clip and the adjacent clip on the timeline.
    
    In general, you should keep transitions short (no more than 2 seconds is a good rule).

    Args:
        sequence_id (str) : The id for the sequence to add the transition to
        video_track_index (int): The index of the video track containing the target clips.
        track_item_index (int): The index of the clip within the track to apply the transition to.
        transition_name (str): The name of the transition to apply. Must be a valid transition name (see below).
        duration (float): The duration of the transition in seconds.
        clip_alignment (float): Controls how the transition is distributed between the two clips.
                                Range: 0.0 to 1.0, where:
                                - 0.0 places transition entirely on the right (later) clip
                                - 0.5 centers the transition equally between both clips (default)
                                - 1.0 places transition entirely on the left (earlier) clip
 
    Valid Transition Names:
        Basic Transitions (ADBE):
            - "ADBE Additive Dissolve"
            - "ADBE Cross Zoom"
            - "ADBE Cube Spin"
            - "ADBE Film Dissolve"
            - "ADBE Flip Over"
            - "ADBE Gradient Wipe"
            - "ADBE Iris Cross"
            - "ADBE Iris Diamond"
            - "ADBE Iris Round"
            - "ADBE Iris Square"
            - "ADBE Page Peel"
            - "ADBE Push"
            - "ADBE Slide"
            - "ADBE Wipe"
            
        After Effects Transitions (AE.ADBE):
            - "AE.ADBE Center Split"
            - "AE.ADBE Inset"
            - "AE.ADBE Cross Dissolve New"
            - "AE.ADBE Dip To White"
            - "AE.ADBE Split"
            - "AE.ADBE Whip"
            - "AE.ADBE Non-Additive Dissolve"
            - "AE.ADBE Dip To Black"
            - "AE.ADBE Barn Doors"
            - "AE.ADBE MorphCut"
    """

    command = createCommand("appendVideoTransition", {
        "sequenceId": sequence_id,
        "videoTrackIndex":video_track_index,
        "trackItemIndex":track_item_index,
        "transitionName":transition_name,
        "clipAlignment":clip_alignment,
        "duration":duration
    })

    return sendCommand(command)


@mcp.tool()
def set_video_clip_properties(sequence_id: str, video_track_index: int, track_item_index: int, opacity: int = 100, blend_mode: str = "NORMAL"):
    """
    Sets opacity and blend mode properties for a video clip in the timeline.

    This function modifies the visual properties of a specific clip located on a specific video track
    in the active Premiere Pro sequence. The clip is identified by its track index and item index
    within that track.

    Args:
        sequence_id (str) : The id for the sequence to set the video clip properties
        video_track_index (int): The index of the video track containing the target clip.
            Track indices start at 0 for the first video track.
        track_item_index (int): The index of the clip within the track to modify.
            Clip indices start at 0 for the first clip on the track.
        opacity (int, optional): The opacity value to set for the clip, as a percentage.
            Valid values range from 0 (completely transparent) to 100 (completely opaque).
            Defaults to 100.
        blend_mode (str, optional): The blend mode to apply to the clip.
            Must be one of the valid blend modes supported by Premiere Pro.
            Defaults to "NORMAL".
    """

    command = createCommand("setVideoClipProperties", {
        "sequenceId": sequence_id,
        "videoTrackIndex":video_track_index,
        "trackItemIndex":track_item_index,
        "opacity":opacity,
        "blendMode":blend_mode
    })

    return sendCommand(command)

@mcp.tool()
def import_media(file_paths:list):
    """
    Imports a list of media files into the active Premiere project.

    Args:
        file_paths (list): A list of file paths (strings) to import into the project.
            Each path should be a complete, valid path to a media file supported by Premiere Pro.
    """

    command = createCommand("importMedia", {
        "filePaths":file_paths
    })

    return sendCommand(command)

# ---------------------------------------------------------------------------
# Phase 1 / Priority 1 : SequenceEditor operations
# Roadmap: Technical_Roadmap_Premiere.md
# ---------------------------------------------------------------------------

@mcp.tool()
def get_sequence_details(sequence_id: str, include_effects: bool = True):
    """
    Returns a full inventory of the specified sequence: every video and audio
    track with per-clip name, start/end times (seconds and ticks), duration,
    in/out points, disabled state, selection state, and (optionally) the full
    effect/component chain with parameter values.

    This is the keystone read tool - call it before editing so you know exactly
    what is on the timeline.

    Args:
        sequence_id (str): The id of the sequence to describe.
        include_effects (bool): Include each clip's effects/component chain with
            parameter values. Defaults to True. Set False for a faster,
            lighter-weight read on large sequences.
    """

    command = createCommand("getSequenceDetails", {
        "sequenceId": sequence_id,
        "includeEffects": include_effects
    })

    return sendCommand(command)


@mcp.tool()
def get_track_count(sequence_id: str):
    """
    Returns the video, audio, and (when available) caption track counts for the
    specified sequence.

    Args:
        sequence_id (str): The id of the sequence.
    """

    command = createCommand("getTrackCount", {
        "sequenceId": sequence_id
    })

    return sendCommand(command)


@mcp.tool()
def insert_clip_at_time(sequence_id: str, item_name: str, insertion_time_seconds: float,
                        video_track_index: int = 0, audio_track_index: int = 0,
                        limited_shift: bool = True):
    """
    Performs an INSERT edit: places the project item on the timeline at the
    specified time, shifting downstream clips rightward to make room (unlike
    overwrite_clip_at_time, which destroys overlapping content).

    If the track index is greater than the number of existing tracks, a new
    track is created.

    Args:
        sequence_id (str): The id of the sequence to insert into.
        item_name (str): The name of the project item to insert.
        insertion_time_seconds (float): Timeline position in seconds.
        video_track_index (int): Target video track (0-based).
        audio_track_index (int): Target audio track (0-based).
        limited_shift (bool): If True, only shifts clips on the target tracks.
            If False, all tracks shift to preserve sync.
    """

    command = createCommand("insertClipAtTime", {
        "sequenceId": sequence_id,
        "itemName": item_name,
        "insertionTimeSeconds": insertion_time_seconds,
        "videoTrackIndex": video_track_index,
        "audioTrackIndex": audio_track_index,
        "limitedShift": limited_shift
    })

    return sendCommand(command)


@mcp.tool()
def overwrite_clip_at_time(sequence_id: str, item_name: str, insertion_time_seconds: float,
                           video_track_index: int = 0, audio_track_index: int = 0):
    """
    Performs an OVERWRITE edit: places the project item on the timeline at the
    specified time, replacing any existing content it overlaps. Downstream
    clips do not shift.

    Args:
        sequence_id (str): The id of the sequence to overwrite into.
        item_name (str): The name of the project item to place.
        insertion_time_seconds (float): Timeline position in seconds.
        video_track_index (int): Target video track (0-based).
        audio_track_index (int): Target audio track (0-based).
    """

    command = createCommand("overwriteClipAtTime", {
        "sequenceId": sequence_id,
        "itemName": item_name,
        "insertionTimeSeconds": insertion_time_seconds,
        "videoTrackIndex": video_track_index,
        "audioTrackIndex": audio_track_index
    })

    return sendCommand(command)


@mcp.tool()
def clone_clip(sequence_id: str, track_index: int, track_item_index: int, track_type: str,
               time_offset_seconds: float, video_track_offset: int = 0,
               audio_track_offset: int = 0, insert: bool = False):
    """
    Duplicates a clip already on the timeline. The copy's position is expressed
    as offsets from the original clip: a time offset in seconds and a vertical
    track offset (e.g. video_track_offset=1 places the copy one video track above).

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the source clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based, left to right).
        track_type (str): "VIDEO" or "AUDIO" - the type of the source track.
        time_offset_seconds (float): Time offset of the copy relative to the
            original clip's start. 0 places it at the same time (use a track
            offset to avoid overwriting the original).
        video_track_offset (int): Vertical offset in video tracks for the copy.
        audio_track_offset (int): Vertical offset in audio tracks for the copy.
        insert (bool): If True performs an insert edit (shifts downstream clips);
            if False performs an overwrite edit at the target position.
    """

    command = createCommand("cloneClip", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "trackItemIndex": track_item_index,
        "trackType": track_type,
        "timeOffsetSeconds": time_offset_seconds,
        "videoTrackOffset": video_track_offset,
        "audioTrackOffset": audio_track_offset,
        "insert": insert
    })

    return sendCommand(command)


@mcp.tool()
def move_clip(sequence_id: str, track_index: int, track_item_index: int, track_type: str,
              new_start_time_seconds: float):
    """
    Moves a clip to a new start time on its own track (shifting it in time).

    NOTE: The underlying API has no native cross-track move. To move a clip to a
    different track, use clone_clip (with a track offset) followed by
    remove_clips on the original.

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        track_type (str): "VIDEO" or "AUDIO".
        new_start_time_seconds (float): The new start time for the clip, in seconds.
    """

    command = createCommand("moveClip", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "trackItemIndex": track_item_index,
        "trackType": track_type,
        "newStartTimeSeconds": new_start_time_seconds
    })

    return sendCommand(command)


@mcp.tool()
def split_clip(sequence_id: str, track_index: int, track_item_index: int, track_type: str,
               split_time_seconds: float):
    """
    Splits (razors) a clip at the specified sequence time, producing two
    independent clips that together play back identically to the original.

    IMPORTANT LIMITATION: This is a composite operation (the UXP API has no
    native razor). The intermediate step temporarily extends past the clip's
    end by (split_time - clip_start) seconds on the same track. If another clip
    starts within that window after this clip's end, it will be damaged. In
    that case: move_clip the downstream clip out of the way, split, then move
    it back - or split before assembling downstream clips.

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        track_type (str): "VIDEO" or "AUDIO".
        split_time_seconds (float): The sequence time at which to split. Must
            fall strictly inside the clip.
    """

    command = createCommand("splitClip", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "trackItemIndex": track_item_index,
        "trackType": track_type,
        "splitTimeSeconds": split_time_seconds
    })

    return sendCommand(command)


@mcp.tool()
def remove_clips(sequence_id: str, clips: list[dict], ripple_delete: bool = True):
    """
    Removes multiple clips from the timeline in a single undoable operation.
    Supersedes remove_item_from_sequence for multi-clip removal.

    Args:
        sequence_id (str): The id of the sequence.
        clips (list[dict]): The clips to remove. Each dict requires:
            - "trackIndex" (int): track index (0-based)
            - "trackItemIndex" (int): clip index within the track (0-based)
            - "trackType" (str): "VIDEO" or "AUDIO"
            Example: [{"trackIndex": 0, "trackItemIndex": 2, "trackType": "VIDEO"}]
        ripple_delete (bool): If True, shifts subsequent clips left to close the
            gaps. If False, leaves gaps where the clips were.
    """

    command = createCommand("removeClips", {
        "sequenceId": sequence_id,
        "clips": clips,
        "rippleDelete": ripple_delete
    })

    return sendCommand(command)


@mcp.tool()
def select_clips(sequence_id: str, clips: list[dict]):
    """
    Sets the timeline selection to the specified clips (replacing any existing
    selection), so the user can see and act on them in the Premiere UI.

    Args:
        sequence_id (str): The id of the sequence.
        clips (list[dict]): The clips to select. Each dict requires:
            - "trackIndex" (int): track index (0-based)
            - "trackItemIndex" (int): clip index within the track (0-based)
            - "trackType" (str): "VIDEO" or "AUDIO"
    """

    command = createCommand("selectClips", {
        "sequenceId": sequence_id,
        "clips": clips
    })

    return sendCommand(command)


@mcp.tool()
def get_selected_clips(sequence_id: str):
    """
    Returns the clips currently selected in the timeline (name, times, track
    index), letting the user point at clips in the UI and say "these".

    Args:
        sequence_id (str): The id of the sequence.
    """

    command = createCommand("getSelectedClips", {
        "sequenceId": sequence_id
    })

    return sendCommand(command)


@mcp.tool()
def create_subsequence(sequence_id: str, ignore_track_targeting: bool = True):
    """
    Creates a new sequence from the current in/out range (or selection) of the
    specified sequence and returns its name and id.

    Set the sequence in/out points in the Premiere UI (or via markers) before
    calling this.

    Args:
        sequence_id (str): The id of the source sequence.
        ignore_track_targeting (bool): If True, includes all tracks regardless
            of the track targeting toggles in the timeline header.
    """

    command = createCommand("createSubsequence", {
        "sequenceId": sequence_id,
        "ignoreTrackTargeting": ignore_track_targeting
    })

    return sendCommand(command)


@mcp.tool()
def insert_mogrt(sequence_id: str, mogrt_path: str, insertion_time_seconds: float,
                 video_track_index: int = 0, audio_track_index: int = 0):
    """
    Inserts a Motion Graphics template (.mogrt) into the sequence. This is the
    reliable path to programmatic titles and text graphics.

    Args:
        sequence_id (str): The id of the sequence.
        mogrt_path (str): Absolute file path to the .mogrt file.
        insertion_time_seconds (float): Timeline position in seconds.
        video_track_index (int): Target video track (0-based).
        audio_track_index (int): Target audio track (0-based).
    """

    command = createCommand("insertMogrt", {
        "sequenceId": sequence_id,
        "mogrtPath": mogrt_path,
        "insertionTimeSeconds": insertion_time_seconds,
        "videoTrackIndex": video_track_index,
        "audioTrackIndex": audio_track_index
    })

    return sendCommand(command)


# ---------------------------------------------------------------------------
# Phase 1 / Priority 2 : Generic effects engine
# ---------------------------------------------------------------------------

@mcp.tool()
def list_video_effects():
    """
    Returns all video effect matchNames available in this Premiere installation
    (e.g. "AE.ADBE Gaussian Blur 2", "AE.ADBE Lumetri"). Use these matchNames
    with add_video_effect / set_effect_parameter / remove_effect.
    """

    command = createCommand("listVideoEffects", {})

    return sendCommand(command)


@mcp.tool()
def list_audio_effects():
    """
    Returns all audio effect display names available in this Premiere
    installation (e.g. "Parametric Equalizer", "DeNoise", "DeReverb",
    "Vocal Enhancer"). Use these names with add_audio_effect.
    """

    command = createCommand("listAudioEffects", {})

    return sendCommand(command)


@mcp.tool()
def add_video_effect(sequence_id: str, video_track_index: int, track_item_index: int,
                     effect_match_name: str, properties: list[dict] = []):
    """
    Adds any video effect to a clip by matchName, optionally setting initial
    parameter values. This generalizes the legacy hardcoded effect tools
    (add_black_and_white_effect, add_gaussian_blur_effect, etc.).

    Workflow: list_video_effects to discover matchNames -> add_video_effect ->
    get_clip_effects to read back parameter names/values -> set_effect_parameter
    to iterate.

    Args:
        sequence_id (str): The id of the sequence.
        video_track_index (int): The index of the video track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        effect_match_name (str): The effect matchName (from list_video_effects).
        properties (list[dict], optional): Initial parameter values. Each dict:
            - "name" (str): the parameter display name (as shown by get_clip_effects)
            - "value": number, string, bool, or {"x": float, "y": float} for
              point parameters.
            Example: [{"name": "Blurriness", "value": 40}]
    """

    command = createCommand("addVideoEffect", {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "effectMatchName": effect_match_name,
        "properties": properties
    })

    return sendCommand(command)


@mcp.tool()
def add_audio_effect(sequence_id: str, audio_track_index: int, track_item_index: int,
                     effect_display_name: str):
    """
    Adds any audio effect to an audio clip by display name (e.g. "Parametric
    Equalizer", "DeNoise", "DeReverb", "Vocal Enhancer").

    After adding, use get_clip_effects (trackType "AUDIO") to read the effect's
    parameter names, then set_effect_parameter to configure it.

    Args:
        sequence_id (str): The id of the sequence.
        audio_track_index (int): The index of the audio track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        effect_display_name (str): The effect display name (from list_audio_effects).
    """

    command = createCommand("addAudioEffect", {
        "sequenceId": sequence_id,
        "audioTrackIndex": audio_track_index,
        "trackItemIndex": track_item_index,
        "effectDisplayName": effect_display_name
    })

    return sendCommand(command)


@mcp.tool()
def get_clip_effects(sequence_id: str, track_index: int, track_item_index: int,
                     track_type: str):
    """
    Reads a clip's full component chain: every effect (including intrinsics
    like Motion, Opacity, Volume) with its matchName and each parameter's
    display name and current value. Use this to discover parameter names for
    set_effect_parameter and to verify applied values.

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        track_type (str): "VIDEO" or "AUDIO".
    """

    command = createCommand("getClipEffects", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "trackItemIndex": track_item_index,
        "trackType": track_type
    })

    return sendCommand(command)


@mcp.tool()
def set_effect_parameter(sequence_id: str, track_index: int, track_item_index: int,
                         track_type: str, effect_match_name: str, param_name: str,
                         value):
    """
    Sets a parameter value on an effect already applied to a clip.

    Use get_clip_effects first to see the effect matchNames and exact parameter
    display names/current values on the clip.

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        track_type (str): "VIDEO" or "AUDIO".
        effect_match_name (str): The matchName of the applied effect
            (e.g. "AE.ADBE Gaussian Blur 2", "AE.ADBE Motion").
        param_name (str): The parameter display name (e.g. "Blurriness").
        value: The value to set - number, string, bool, or
            {"x": float, "y": float} for point parameters like Position.
    """

    command = createCommand("setEffectParameter", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "trackItemIndex": track_item_index,
        "trackType": track_type,
        "effectMatchName": effect_match_name,
        "paramName": param_name,
        "value": value
    })

    return sendCommand(command)


@mcp.tool()
def remove_effect(sequence_id: str, track_index: int, track_item_index: int,
                  track_type: str, effect_match_name: str):
    """
    Removes an applied effect from a clip by matchName.

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        track_type (str): "VIDEO" or "AUDIO".
        effect_match_name (str): The matchName of the effect to remove
            (from get_clip_effects).
    """

    command = createCommand("removeEffect", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "trackItemIndex": track_item_index,
        "trackType": track_type,
        "effectMatchName": effect_match_name
    })

    return sendCommand(command)


@mcp.tool()
def set_clip_transform(sequence_id: str, video_track_index: int, track_item_index: int,
                       position: dict = None, scale: float = None,
                       rotation: float = None, anchor_point: dict = None):
    """
    Sets the intrinsic Motion properties (position / scale / rotation / anchor
    point) of a video clip. Only the provided values are changed.

    Args:
        sequence_id (str): The id of the sequence.
        video_track_index (int): The index of the video track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        position (dict, optional): {"x": float, "y": float} normalized frame
            coordinates where {"x": 0.5, "y": 0.5} is centered.
        scale (float, optional): Scale percentage (100 = original size).
        rotation (float, optional): Rotation in degrees (clockwise).
        anchor_point (dict, optional): {"x": float, "y": float} anchor point.
    """

    command = createCommand("setClipTransform", {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "position": position,
        "scale": scale,
        "rotation": rotation,
        "anchorPoint": anchor_point
    })

    return sendCommand(command)


@mcp.tool()
def set_clip_crop(sequence_id: str, video_track_index: int, track_item_index: int,
                  left: float = None, top: float = None, right: float = None,
                  bottom: float = None):
    """
    Crops a video clip's edges (applies the Crop effect if not already present).
    Values are percentages from 0 to 100 per edge. Only provided edges change.

    Args:
        sequence_id (str): The id of the sequence.
        video_track_index (int): The index of the video track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        left (float, optional): Percent to crop from the left edge (0-100).
        top (float, optional): Percent to crop from the top edge (0-100).
        right (float, optional): Percent to crop from the right edge (0-100).
        bottom (float, optional): Percent to crop from the bottom edge (0-100).
    """

    command = createCommand("setClipCrop", {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom
    })

    return sendCommand(command)


@mcp.tool()
def copy_clip_effects(sequence_id: str, source: dict, targets: list[dict]):
    """
    Copies all non-intrinsic effects (and their current parameter values) from
    a source clip to one or more target clips - "match the look".

    Args:
        sequence_id (str): The id of the sequence.
        source (dict): The clip to copy from:
            - "trackIndex" (int), "trackItemIndex" (int), "trackType" (str: "VIDEO"/"AUDIO")
        targets (list[dict]): The clips to copy to, same shape as source.

    Returns:
        A report of copied effects and any failures (some parameters are not
        writable and are skipped).
    """

    command = createCommand("copyClipEffects", {
        "sequenceId": sequence_id,
        "source": source,
        "targets": targets
    })

    return sendCommand(command)


# ---------------------------------------------------------------------------
# Phase 1 / Priority 3 : Audio essentials
# Note: set_clip_audio_gain is descoped - no UXP API surface for clip gain
# exists in 25.x. set_clip_volume covers the use case.
# ---------------------------------------------------------------------------

@mcp.tool()
def set_clip_volume(sequence_id: str, audio_track_index: int, track_item_index: int,
                    level_db: float = 0.0, raw_value: float = None):
    """
    Sets the volume (the intrinsic Volume component's Level parameter) of an
    audio clip.

    The level is expressed in UI decibels exactly as shown in Premiere's
    Effect Controls: 0 dB = the clip default (no change), negative = quieter,
    positive = louder, -60 dB and below is effectively silent.
    (Live-verified mapping: the Level param stores 10^((dB - 15)/20); a clip
    at UI 0.0 dB reads 0.1778.) Pass raw_value to set the parameter's native
    value directly, bypassing the dB conversion.

    Args:
        sequence_id (str): The id of the sequence.
        audio_track_index (int): The index of the audio track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        level_db (float): Volume in dB. 0 = unity gain; negative = quieter;
            positive = louder. Ignored if raw_value is provided.
        raw_value (float, optional): Escape hatch - sets the Level parameter's
            native value directly, bypassing dB conversion.
    """

    command = createCommand("setClipVolume", {
        "sequenceId": sequence_id,
        "audioTrackIndex": audio_track_index,
        "trackItemIndex": track_item_index,
        "levelDb": level_db,
        "rawValue": raw_value
    })

    return sendCommand(command)


@mcp.tool()
def set_clip_pan(sequence_id: str, audio_track_index: int, track_item_index: int,
                 balance: float):
    """
    Pans an audio clip by applying the "Balance" audio filter (added
    automatically if not already on the clip) and setting its Balance
    parameter. The intrinsic panner is not exposed by the UXP API.

    Args:
        sequence_id (str): The id of the sequence.
        audio_track_index (int): The index of the audio track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        balance (float): Pan position from -100 (full left) to 100 (full right),
            0 = center. (Internally mapped to the filter's 0..1 range.)

    Note: intended for stereo clips; on mono clips/tracks the Balance filter
    may have no audible effect.
    """

    command = createCommand("setClipPan", {
        "sequenceId": sequence_id,
        "audioTrackIndex": audio_track_index,
        "trackItemIndex": track_item_index,
        "balance": balance
    })

    return sendCommand(command)


@mcp.tool()
def fade_audio_in(sequence_id: str, audio_track_index: int, track_item_index: int,
                  duration_seconds: float = 1.0):
    """
    Fades an audio clip in from silence over the specified duration, using two
    volume keyframes starting at the clip's beginning. The fade target is the
    clip's current volume level.

    Args:
        sequence_id (str): The id of the sequence.
        audio_track_index (int): The index of the audio track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        duration_seconds (float): Fade length in seconds (must fit inside the clip).
    """

    command = createCommand("fadeAudioIn", {
        "sequenceId": sequence_id,
        "audioTrackIndex": audio_track_index,
        "trackItemIndex": track_item_index,
        "durationSeconds": duration_seconds
    })

    return sendCommand(command)


@mcp.tool()
def fade_audio_out(sequence_id: str, audio_track_index: int, track_item_index: int,
                   duration_seconds: float = 1.0):
    """
    Fades an audio clip out to silence over the specified duration, using two
    volume keyframes ending at the clip's end. The fade source is the clip's
    current volume level.

    Args:
        sequence_id (str): The id of the sequence.
        audio_track_index (int): The index of the audio track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        duration_seconds (float): Fade length in seconds (must fit inside the clip).
    """

    command = createCommand("fadeAudioOut", {
        "sequenceId": sequence_id,
        "audioTrackIndex": audio_track_index,
        "trackItemIndex": track_item_index,
        "durationSeconds": duration_seconds
    })

    return sendCommand(command)


@mcp.tool()
def add_audio_transition(sequence_id: str, audio_track_index: int, track_item_index: int,
                         transition_name: str = "Constant Power",
                         duration_seconds: float = 1.0, clip_alignment: float = 0.5,
                         apply_to_start: bool = False):
    """
    Adds an audio crossfade transition to an audio clip (e.g. between two
    adjacent clips on the same track).

    NOTE: Audio transitions are not documented in the UXP API for all Premiere
    versions - if this reports the API as unavailable, use fade_audio_in /
    fade_audio_out (volume keyframes) instead.

    Args:
        sequence_id (str): The id of the sequence.
        audio_track_index (int): The index of the audio track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        transition_name (str): The transition name, e.g. "Constant Power",
            "Constant Gain", "Exponential Fade".
        duration_seconds (float): Transition length in seconds (keep short; <= 2s).
        clip_alignment (float): 0.0 = entirely on the later clip,
            0.5 = centered, 1.0 = entirely on the earlier clip.
        apply_to_start (bool): If True, applies at the clip's start edge instead
            of its end edge.
    """

    command = createCommand("addAudioTransition", {
        "sequenceId": sequence_id,
        "audioTrackIndex": audio_track_index,
        "trackItemIndex": track_item_index,
        "transitionName": transition_name,
        "durationSeconds": duration_seconds,
        "clipAlignment": clip_alignment,
        "applyToStart": apply_to_start
    })

    return sendCommand(command)


@mcp.tool()
def set_audio_track_locked(sequence_id: str, audio_track_index: int, locked: bool):
    """
    Locks or unlocks an audio track (preventing edits to its clips).

    NOTE: Track locking is not exposed by the documented UXP API as of
    Premiere 25.x; this tool feature-detects the setter and reports clearly if
    it is unavailable in the installed version.

    Args:
        sequence_id (str): The id of the sequence.
        audio_track_index (int): The index of the audio track (0-based).
        locked (bool): True to lock, False to unlock.
    """

    command = createCommand("setAudioTrackLocked", {
        "sequenceId": sequence_id,
        "audioTrackIndex": audio_track_index,
        "locked": locked
    })

    return sendCommand(command)


@mcp.tool()
def get_audio_clip_info(sequence_id: str, audio_track_index: int, track_item_index: int):
    """
    Returns an audio clip's volume (raw value + approximate dB), pan balance,
    disabled state, timing, and full effect/component chain.

    Args:
        sequence_id (str): The id of the sequence.
        audio_track_index (int): The index of the audio track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
    """

    command = createCommand("getAudioClipInfo", {
        "sequenceId": sequence_id,
        "audioTrackIndex": audio_track_index,
        "trackItemIndex": track_item_index
    })

    return sendCommand(command)


# ---------------------------------------------------------------------------
# Phase 2 / Priority 4 : Keyframe animation engine
# ---------------------------------------------------------------------------

@mcp.tool()
def set_param_time_varying(sequence_id: str, track_index: int, track_item_index: int,
                           track_type: str, effect_match_name: str, param_name: str,
                           time_varying: bool):
    """
    Toggles keyframing (the "stopwatch") on an effect parameter. Enabling this
    is a prerequisite for keyframing a parameter; add_keyframes does it
    automatically, so you rarely need this directly. Disabling removes
    time-variance (the parameter returns to a single static value).

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        track_type (str): "VIDEO" or "AUDIO".
        effect_match_name (str): The effect matchName (e.g. "AE.ADBE Motion") or
            its display name (e.g. "Volume").
        param_name (str): The parameter display name (e.g. "Scale", "Level").
        time_varying (bool): True to enable keyframing, False to disable.
    """

    command = createCommand("setParamTimeVarying", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "trackItemIndex": track_item_index,
        "trackType": track_type,
        "effectMatchName": effect_match_name,
        "paramName": param_name,
        "timeVarying": time_varying
    })

    return sendCommand(command)


@mcp.tool()
def add_keyframes(sequence_id: str, track_index: int, track_item_index: int,
                  track_type: str, effect_match_name: str, param_name: str,
                  keyframes: list[dict]):
    """
    Adds a batch of keyframes to an effect parameter in a single undoable
    transaction (fast, one Undo step - always prefer this over repeated
    add_keyframe calls). Automatically enables keyframing on the parameter.

    Keyframe times are in SEQUENCE seconds (not clip-relative).

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        track_type (str): "VIDEO" or "AUDIO".
        effect_match_name (str): The effect matchName (e.g. "AE.ADBE Motion",
            "AE.ADBE Opacity") or display name (e.g. "Volume").
        param_name (str): The parameter display name (e.g. "Scale", "Opacity",
            "Level", "Blurriness").
        keyframes (list[dict]): Each dict:
            - "timeSeconds" (float): sequence time
            - "value": number, or {"x": float, "y": float} for point params
            - "interpolation" (str, optional): "LINEAR" (default), "BEZIER",
              "HOLD", "TIME", "TIME_TRANSITION_START", "TIME_TRANSITION_END"
            Example: [{"timeSeconds": 10.0, "value": 100},
                      {"timeSeconds": 12.0, "value": 150, "interpolation": "BEZIER"}]
    """

    command = createCommand("addKeyframes", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "trackItemIndex": track_item_index,
        "trackType": track_type,
        "effectMatchName": effect_match_name,
        "paramName": param_name,
        "keyframes": keyframes
    })

    return sendCommand(command)


@mcp.tool()
def add_keyframe(sequence_id: str, track_index: int, track_item_index: int,
                 track_type: str, effect_match_name: str, param_name: str,
                 time_seconds: float, value, interpolation: str = "LINEAR"):
    """
    Adds a single keyframe to an effect parameter at the given sequence time.
    For multiple keyframes use add_keyframes (batched, single Undo step).

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        track_type (str): "VIDEO" or "AUDIO".
        effect_match_name (str): The effect matchName or display name.
        param_name (str): The parameter display name.
        time_seconds (float): Sequence time for the keyframe.
        value: The keyframe value - number, or {"x": float, "y": float}.
        interpolation (str): "LINEAR", "BEZIER", "HOLD", "TIME",
            "TIME_TRANSITION_START", or "TIME_TRANSITION_END".
    """

    command = createCommand("addKeyframes", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "trackItemIndex": track_item_index,
        "trackType": track_type,
        "effectMatchName": effect_match_name,
        "paramName": param_name,
        "keyframes": [{"timeSeconds": time_seconds, "value": value,
                       "interpolation": interpolation}]
    })

    return sendCommand(command)


@mcp.tool()
def get_keyframes(sequence_id: str, track_index: int, track_item_index: int,
                  track_type: str, effect_match_name: str, param_name: str):
    """
    Returns all keyframes on an effect parameter: time (seconds + ticks),
    value, and temporal interpolation mode, plus whether the parameter is
    time-varying at all.

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        track_type (str): "VIDEO" or "AUDIO".
        effect_match_name (str): The effect matchName or display name.
        param_name (str): The parameter display name.
    """

    command = createCommand("getKeyframes", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "trackItemIndex": track_item_index,
        "trackType": track_type,
        "effectMatchName": effect_match_name,
        "paramName": param_name
    })

    return sendCommand(command)


@mcp.tool()
def remove_keyframe(sequence_id: str, track_index: int, track_item_index: int,
                    track_type: str, effect_match_name: str, param_name: str,
                    time_seconds: float):
    """
    Removes the keyframe at the given sequence time from an effect parameter.
    Use get_keyframes first to see exact keyframe times.

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        track_type (str): "VIDEO" or "AUDIO".
        effect_match_name (str): The effect matchName or display name.
        param_name (str): The parameter display name.
        time_seconds (float): The sequence time of the keyframe to remove.
    """

    command = createCommand("removeKeyframe", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "trackItemIndex": track_item_index,
        "trackType": track_type,
        "effectMatchName": effect_match_name,
        "paramName": param_name,
        "timeSeconds": time_seconds
    })

    return sendCommand(command)


@mcp.tool()
def clear_keyframes(sequence_id: str, track_index: int, track_item_index: int,
                    track_type: str, effect_match_name: str, param_name: str,
                    reset_time_varying: bool = True):
    """
    Removes ALL keyframes from an effect parameter (across the clip's full
    extent) and optionally turns keyframing off again.

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        track_type (str): "VIDEO" or "AUDIO".
        effect_match_name (str): The effect matchName or display name.
        param_name (str): The parameter display name.
        reset_time_varying (bool): If True (default), also disables the
            parameter's stopwatch after clearing.
    """

    command = createCommand("clearKeyframes", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "trackItemIndex": track_item_index,
        "trackType": track_type,
        "effectMatchName": effect_match_name,
        "paramName": param_name,
        "resetTimeVarying": reset_time_varying
    })

    return sendCommand(command)


@mcp.tool()
def set_keyframe_interpolation(sequence_id: str, track_index: int, track_item_index: int,
                               track_type: str, effect_match_name: str, param_name: str,
                               time_seconds: float, interpolation: str):
    """
    Sets the temporal interpolation mode of an existing keyframe.

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        track_type (str): "VIDEO" or "AUDIO".
        effect_match_name (str): The effect matchName or display name.
        param_name (str): The parameter display name.
        time_seconds (float): The sequence time of the keyframe.
        interpolation (str): "LINEAR", "BEZIER", "HOLD", "TIME",
            "TIME_TRANSITION_START", or "TIME_TRANSITION_END".
    """

    command = createCommand("setKeyframeInterpolation", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "trackItemIndex": track_item_index,
        "trackType": track_type,
        "effectMatchName": effect_match_name,
        "paramName": param_name,
        "timeSeconds": time_seconds,
        "interpolation": interpolation
    })

    return sendCommand(command)


@mcp.tool()
def fade_video_in(sequence_id: str, video_track_index: int, track_item_index: int,
                  duration_seconds: float = 1.0):
    """
    Fades a video clip in from transparent over the specified duration, using
    two Opacity keyframes starting at the clip's beginning.

    Args:
        sequence_id (str): The id of the sequence.
        video_track_index (int): The index of the video track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        duration_seconds (float): Fade length in seconds (must fit inside the clip).
    """

    command = createCommand("fadeVideoIn", {
        "sequenceId": sequence_id,
        "trackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "durationSeconds": duration_seconds
    })

    return sendCommand(command)


@mcp.tool()
def fade_video_out(sequence_id: str, video_track_index: int, track_item_index: int,
                   duration_seconds: float = 1.0):
    """
    Fades a video clip out to transparent over the specified duration, using
    two Opacity keyframes ending at the clip's end.

    Args:
        sequence_id (str): The id of the sequence.
        video_track_index (int): The index of the video track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        duration_seconds (float): Fade length in seconds (must fit inside the clip).
    """

    command = createCommand("fadeVideoOut", {
        "sequenceId": sequence_id,
        "trackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "durationSeconds": duration_seconds
    })

    return sendCommand(command)


@mcp.tool()
def ken_burns(sequence_id: str, video_track_index: int, track_item_index: int,
              start_scale: float = None, end_scale: float = None,
              start_position: dict = None, end_position: dict = None,
              ease: bool = True):
    """
    Applies a Ken Burns (slow zoom/pan) move to a video clip: scale and/or
    position keyframes on the Motion component spanning the clip's full
    duration, with optional bezier easing.

    Provide start_scale+end_scale for a zoom, start_position+end_position for
    a pan, or both for a combined move.

    Args:
        sequence_id (str): The id of the sequence.
        video_track_index (int): The index of the video track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        start_scale (float, optional): Scale percent at clip start (100 = original).
        end_scale (float, optional): Scale percent at clip end.
        start_position (dict, optional): {"x": float, "y": float} normalized
            position at clip start ({"x": 0.5, "y": 0.5} = centered).
        end_position (dict, optional): {"x": float, "y": float} at clip end.
        ease (bool): If True (default), keyframes use BEZIER interpolation for
            a smooth ramp.
    """

    command = createCommand("kenBurns", {
        "sequenceId": sequence_id,
        "trackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "startScale": start_scale,
        "endScale": end_scale,
        "startPosition": start_position,
        "endPosition": end_position,
        "ease": ease
    })

    return sendCommand(command)


# friendly property name -> (effect name, param name, track type)
ANIMATABLE_PROPERTIES = {
    "scale": ("AE.ADBE Motion", "Scale", "VIDEO"),
    "position": ("AE.ADBE Motion", "Position", "VIDEO"),
    "rotation": ("AE.ADBE Motion", "Rotation", "VIDEO"),
    "anchor_point": ("AE.ADBE Motion", "Anchor Point", "VIDEO"),
    "opacity": ("AE.ADBE Opacity", "Opacity", "VIDEO"),
    "volume": ("Volume", "Level", "AUDIO"),
}


@mcp.tool()
def animate_clip_property(sequence_id: str, track_index: int, track_item_index: int,
                          property_name: str, keyframes: list[dict]):
    """
    High-level animation: keyframes a clip property by friendly name in one
    call (single undoable transaction).

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        property_name (str): One of:
            - "scale" (percent), "position" ({"x","y"} normalized),
              "rotation" (degrees), "anchor_point" ({"x","y"}),
              "opacity" (0-100)  [video clips]
            - "volume" (raw Level value; for UI dB use 10^((dB-15)/20))  [audio clips]
        keyframes (list[dict]): Each dict:
            - "timeSeconds" (float): sequence time
            - "value": number or {"x","y"} matching the property
            - "interpolation" (str, optional): "LINEAR"/"BEZIER"/"HOLD"/...
    """

    if property_name not in ANIMATABLE_PROPERTIES:
        raise ValueError(
            f"Unknown property '{property_name}'. Valid: {', '.join(ANIMATABLE_PROPERTIES)}. "
            "For anything else, use add_keyframes with the effect matchName and param name."
        )

    effect_name, param_name, track_type = ANIMATABLE_PROPERTIES[property_name]

    command = createCommand("addKeyframes", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "trackItemIndex": track_item_index,
        "trackType": track_type,
        "effectMatchName": effect_name,
        "paramName": param_name,
        "keyframes": keyframes
    })

    return sendCommand(command)


# ---------------------------------------------------------------------------
# Phase 2 / Priority 5 : Lumetri color suite
# All wrappers route through the setLumetriParams handler, which ensures a
# single Lumetri instance and reports applied/failed param names (plus the
# component's actual param list on a miss, for calibration).
# set_lumetri_curves is descoped: the curves param encoding requires a
# hand-captured ground truth first (see roadmap Priority 5 note).
# ---------------------------------------------------------------------------

def _lumetri_params_command(sequence_id, video_track_index, track_item_index, params):
    # params: list of (name, value) or (name, value, occurrence).
    # occurrence disambiguates duplicated Lumetri display names
    # (e.g. "Saturation" exists in Basic and Creative): 1-based nth, -1 = last.
    filtered = []
    for p in params:
        name, value = p[0], p[1]
        if value is None:
            continue
        entry = {"name": name, "value": value}
        if len(p) > 2:
            entry["occurrence"] = p[2]
        filtered.append(entry)

    if not filtered:
        raise ValueError("No parameter values provided.")

    command = createCommand("setLumetriParams", {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "params": filtered
    })

    return sendCommand(command)


@mcp.tool()
def add_lumetri_basic(sequence_id: str, video_track_index: int, track_item_index: int,
                      exposure: float = None, contrast: float = None,
                      highlights: float = None, shadows: float = None,
                      whites: float = None, blacks: float = None,
                      temperature: float = None, tint: float = None,
                      saturation: float = None):
    """
    Applies Lumetri Basic Correction to a video clip (adds the Lumetri effect
    if not present). Only the provided values are set.

    Typical ranges match the Lumetri panel: exposure -5..5; contrast,
    highlights, shadows, whites, blacks, temperature, tint -100..100;
    saturation 0..200 (100 = unchanged).

    The response reports which params applied; on a miss it includes the
    effect's actual parameter names (use those with set_effect_parameter).

    Args:
        sequence_id (str): The id of the sequence.
        video_track_index (int): The index of the video track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        exposure (float, optional): Exposure in stops.
        contrast (float, optional): Contrast.
        highlights (float, optional): Highlights.
        shadows (float, optional): Shadows.
        whites (float, optional): Whites.
        blacks (float, optional): Blacks.
        temperature (float, optional): Color temperature (negative = cooler/blue,
            positive = warmer/orange).
        tint (float, optional): Green-magenta tint.
        saturation (float, optional): Saturation (100 = unchanged).
    """

    return _lumetri_params_command(sequence_id, video_track_index, track_item_index, [
        ("Exposure", exposure),
        ("Contrast", contrast),
        ("Highlights", highlights),
        ("Shadows", shadows),
        ("Whites", whites),
        ("Blacks", blacks),
        ("Temperature", temperature),
        ("Tint", tint),
        ("Saturation", saturation),
    ])


@mcp.tool()
def add_lumetri_creative(sequence_id: str, video_track_index: int, track_item_index: int,
                         intensity: float = None, faded_film: float = None,
                         sharpen: float = None, vibrance: float = None,
                         creative_saturation: float = None):
    """
    Applies Lumetri Creative-section adjustments to a video clip (adds the
    Lumetri effect if not present). Only the provided values are set.

    The response reports which params applied; on a miss it includes the
    effect's actual parameter names (use those with set_effect_parameter).

    Args:
        sequence_id (str): The id of the sequence.
        video_track_index (int): The index of the video track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        intensity (float, optional): Look intensity (0-200, 100 = default).
        faded_film (float, optional): Faded film amount (0-100).
        sharpen (float, optional): Sharpen amount (-100..100).
        vibrance (float, optional): Vibrance (-100..100).
        creative_saturation (float, optional): Creative-section saturation (0-200).
    """

    return _lumetri_params_command(sequence_id, video_track_index, track_item_index, [
        ("Intensity", intensity),
        ("Faded Film", faded_film),
        ("Sharpen", sharpen),
        ("Vibrance", vibrance),
        # 2nd "Saturation" = Creative section (1st is Basic Correction)
        ("Saturation", creative_saturation, 2),
    ])


@mcp.tool()
def apply_lut(sequence_id: str, video_track_index: int, track_item_index: int,
              lut_path: str, param_name: str = "Input LUT"):
    """
    Applies a LUT (.cube / .look) to a video clip via the Lumetri effect
    (added if not present).

    NOTE: The Lumetri LUT parameter's exact display name and accepted value
    format (file path vs registered name) vary by version - if this fails,
    the response lists the effect's actual parameter names; retry with
    param_name set accordingly.

    Args:
        sequence_id (str): The id of the sequence.
        video_track_index (int): The index of the video track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        lut_path (str): Absolute path to the .cube/.look file.
        param_name (str): The Lumetri parameter to set. Defaults to "Input LUT";
            use "Look" for a Creative-section LUT.
    """

    return _lumetri_params_command(sequence_id, video_track_index, track_item_index, [
        (param_name, lut_path),
    ])


@mcp.tool()
def add_vignette(sequence_id: str, video_track_index: int, track_item_index: int,
                 amount: float = -1.5, midpoint: float = None,
                 roundness: float = None, feather: float = None):
    """
    Adds a vignette to a video clip via the Lumetri effect's Vignette section
    (Lumetri added if not present).

    The response reports which params applied; on a miss it includes the
    effect's actual parameter names.

    Args:
        sequence_id (str): The id of the sequence.
        video_track_index (int): The index of the video track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
        amount (float): Vignette amount (-5..5; negative darkens edges). Default -1.5.
        midpoint (float, optional): Vignette midpoint (0-100).
        roundness (float, optional): Vignette roundness (-100..100).
        feather (float, optional): Vignette feather (0-100).
    """

    # Vignette is the last Lumetri section - use the LAST occurrence of each
    # name to avoid hitting same-named params in earlier sections.
    return _lumetri_params_command(sequence_id, video_track_index, track_item_index, [
        ("Amount", amount, -1),
        ("Midpoint", midpoint, -1),
        ("Roundness", roundness, -1),
        ("Feather", feather, -1),
    ])


@mcp.tool()
def get_lumetri_settings(sequence_id: str, video_track_index: int, track_item_index: int):
    """
    Reads back the Lumetri effect's parameters and current values from a video
    clip - the read half of the color grading loop ("make it warmer" =
    get_lumetri_settings -> adjust Temperature -> add_lumetri_basic).

    Returns present=False if the clip has no Lumetri effect.

    Args:
        sequence_id (str): The id of the sequence.
        video_track_index (int): The index of the video track containing the clip (0-based).
        track_item_index (int): The index of the clip within the track (0-based).
    """

    command = createCommand("getLumetriSettings", {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "trackItemIndex": track_item_index
    })

    return sendCommand(command)


# ---------------------------------------------------------------------------
# Phase 2 / Priority 6 : Markers, metadata & project intelligence
# ---------------------------------------------------------------------------

@mcp.tool()
def get_sequence_markers(sequence_id: str):
    """
    Returns all markers on a sequence: index, name, type, comments, start time,
    duration, color index, and URL/target for WebLink markers. The index is
    used by update_marker / remove_marker.

    Args:
        sequence_id (str): The id of the sequence.
    """

    command = createCommand("getSequenceMarkers", {
        "sequenceId": sequence_id
    })

    return sendCommand(command)


@mcp.tool()
def remove_marker(sequence_id: str, marker_index: int):
    """
    Removes a marker from a sequence by its index (from get_sequence_markers).

    Args:
        sequence_id (str): The id of the sequence.
        marker_index (int): The marker's index in the get_sequence_markers list.
    """

    command = createCommand("removeMarker", {
        "sequenceId": sequence_id,
        "markerIndex": marker_index
    })

    return sendCommand(command)


@mcp.tool()
def update_marker(sequence_id: str, marker_index: int, name: str = None,
                  comments: str = None, duration_seconds: float = None,
                  marker_type: str = None, color_index: int = None,
                  start_time_seconds: float = None):
    """
    Updates fields of an existing sequence marker (identified by index from
    get_sequence_markers). Only provided fields change; all changes apply in
    one undoable transaction.

    Args:
        sequence_id (str): The id of the sequence.
        marker_index (int): The marker's index in the get_sequence_markers list.
        name (str, optional): New marker name.
        comments (str, optional): New comments text.
        duration_seconds (float, optional): New duration.
        marker_type (str, optional): "Comment", "Chapter", "Segmentation", or "WebLink".
        color_index (int, optional): Marker color index.
        start_time_seconds (float, optional): New start time (moves the marker).
    """

    command = createCommand("updateMarker", {
        "sequenceId": sequence_id,
        "markerIndex": marker_index,
        "name": name,
        "comments": comments,
        "durationSeconds": duration_seconds,
        "markerType": marker_type,
        "colorIndex": color_index,
        "startTimeSeconds": start_time_seconds
    })

    return sendCommand(command)


@mcp.tool()
def add_clip_marker(item_name: str, marker_name: str, start_time_seconds: float,
                    duration_seconds: float = 0.0, comments: str = "",
                    marker_type: str = "Comment"):
    """
    Adds a marker to a PROJECT ITEM (source clip in the Project panel), as
    opposed to add_marker_to_sequence which marks the timeline. Clip markers
    travel with the source clip.

    Args:
        item_name (str): The name of the project item to mark.
        marker_name (str): The marker name/title.
        start_time_seconds (float): Marker position in the clip's own time, in seconds.
        duration_seconds (float): Marker duration in seconds. Default 0.
        comments (str): Optional comment text.
        marker_type (str): "Comment", "Chapter", "Segmentation", or "WebLink".
    """

    command = createCommand("addClipMarker", {
        "itemName": item_name,
        "markerName": marker_name,
        "startTimeSeconds": start_time_seconds,
        "durationSeconds": duration_seconds,
        "comments": comments,
        "markerType": marker_type
    })

    return sendCommand(command)


@mcp.tool()
def get_project_item_metadata(item_name: str, include_xmp: bool = False):
    """
    Returns a project item's metadata: the Project-panel column metadata and
    project metadata (both XML strings), and optionally the full XMP blob.

    Args:
        item_name (str): The name of the project item.
        include_xmp (bool): If True, also returns the raw XMP metadata (can be
            large). Defaults to False.
    """

    command = createCommand("getProjectItemMetadata", {
        "itemName": item_name,
        "includeXmp": include_xmp
    })

    return sendCommand(command)


@mcp.tool()
def set_project_item_metadata(item_name: str, metadata: str, updated_fields: list[str]):
    """
    Sets project metadata on a project item.

    The metadata argument is the XML metadata string in the same format
    returned by get_project_item_metadata (read it first, modify the fields,
    and pass the result back along with the list of field names you changed).

    Args:
        item_name (str): The name of the project item.
        metadata (str): The project metadata XML string.
        updated_fields (list[str]): Names of the fields being updated.
    """

    command = createCommand("setProjectItemMetadata", {
        "itemName": item_name,
        "metadata": metadata,
        "updatedFields": updated_fields
    })

    return sendCommand(command)


@mcp.tool()
def batch_rename_project_items(item_names: list[str] = None, prefix: str = None,
                               suffix: str = None, find: str = None,
                               replace: str = None, base_name: str = None,
                               start_number: int = 1, number_padding: int = 2):
    """
    Renames multiple project items in one undoable transaction. Operations
    combine in this order: find/replace -> base_name+numbering -> prefix ->
    suffix.

    Args:
        item_names (list[str], optional): Items to rename. If omitted, all
            root-level (non-bin) project items are targeted.
        prefix (str, optional): Text prepended to each name.
        suffix (str, optional): Text appended to each name.
        find (str, optional): Substring to find (with replace).
        replace (str, optional): Replacement for find.
        base_name (str, optional): If set, names become base_name + sequential
            number (e.g. "shot_01", "shot_02"), replacing the original name.
        start_number (int): First number for base_name numbering. Default 1.
        number_padding (int): Zero-padding width for numbering. Default 2.

    Returns:
        The list of {from, to} renames performed.
    """

    command = createCommand("batchRenameProjectItems", {
        "itemNames": item_names,
        "prefix": prefix,
        "suffix": suffix,
        "find": find,
        "replace": replace,
        "baseName": base_name,
        "startNumber": start_number,
        "numberPadding": number_padding
    })

    return sendCommand(command)


@mcp.tool()
def get_media_info(item_name: str):
    """
    Returns technical media info for a project item: file path, duration,
    frame rate, pixel aspect ratio, field type, offline/sequence/merged/
    multicam flags, and color label index.

    Args:
        item_name (str): The name of the project item.
    """

    command = createCommand("getMediaInfo", {
        "itemName": item_name
    })

    return sendCommand(command)


@mcp.tool()
def set_clip_label_color(item_name: str, color_index: int = None, color_name: str = None):
    """
    Sets the color label of a project item (visible in the Project panel and
    on its timeline instances). Provide either a color index or a color name.

    Args:
        item_name (str): The name of the project item.
        color_index (int, optional): The label color index.
        color_name (str, optional): A Constants.ProjectItemColorLabel name:
            VIOLET, IRIS, LAVENDER, CERULEAN, FOREST, ROSE, MANGO, PURPLE,
            BLUE, TEAL, MAGENTA, TAN, GREEN, BROWN, YELLOW.
    """

    command = createCommand("setClipLabelColor", {
        "itemName": item_name,
        "colorIndex": color_index,
        "colorName": color_name
    })

    return sendCommand(command)


# ---------------------------------------------------------------------------
# Phase 2 / Priority 7 : Transcripts & captions
# Transcript APIs may be beta-only; the plugin feature-detects and returns a
# clear error if unavailable. Search and marker generation happen server-side
# over the transcript JSON.
# ---------------------------------------------------------------------------

import json as _json
import re as _re

_TICKS_PER_SECOND = 254016000000


def _to_seconds(value):
    """Normalizes a transcript time value (seconds, ms, or ticks) to seconds."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v > 1e9:          # ticks
        return v / _TICKS_PER_SECOND
    if v > 100000:       # milliseconds (heuristic: > ~27h in seconds)
        return v / 1000.0
    return v


def _extract_transcript_words(node, out):
    """
    Tolerant walker: collects {text, startSeconds, endSeconds} from any dict
    that carries word text + timing, regardless of the exact schema version
    (see transcript_format_spec.json in Adobe's samples repo).
    """
    if isinstance(node, dict):
        text = node.get("text") or node.get("word")
        start = node.get("start")
        if start is None:
            start = node.get("startTime") or node.get("inTime") or node.get("st")
        end = node.get("end")
        if end is None:
            end = node.get("endTime") or node.get("outTime") or node.get("et")

        if isinstance(text, str) and text.strip() and start is not None:
            s = _to_seconds(start)
            e = _to_seconds(end) if end is not None else s
            if s is not None:
                out.append({"text": text.strip(), "startSeconds": s, "endSeconds": e})
                # don't recurse into a word's children
                return

        for v in node.values():
            _extract_transcript_words(v, out)
    elif isinstance(node, list):
        for v in node:
            _extract_transcript_words(v, out)


def _fetch_transcript_words(sequence_id=None, item_name=None):
    command = createCommand("getTranscript", {
        "sequenceId": sequence_id,
        "itemName": item_name
    })
    result = sendCommand(command)

    if not isinstance(result, dict) or result.get("status") != "SUCCESS":
        return result, None

    raw = result["response"]["transcriptJson"]
    data = _json.loads(raw)

    words = []
    _extract_transcript_words(data, words)
    words.sort(key=lambda w: w["startSeconds"])

    return result, words


def _search_words(words, query, case_sensitive=False):
    """Finds a word or multi-word phrase in the word list; returns match dicts."""
    q_tokens = query.split()
    if not q_tokens:
        return []

    def norm(s):
        s = _re.sub(r"[^\w']+", "", s)
        return s if case_sensitive else s.lower()

    targets = [norm(t) for t in q_tokens]
    matches = []

    for i in range(len(words) - len(targets) + 1):
        if all(norm(words[i + j]["text"]) == targets[j] for j in range(len(targets))):
            first, last = words[i], words[i + len(targets) - 1]
            ctx_start = max(0, i - 5)
            ctx_end = min(len(words), i + len(targets) + 5)
            matches.append({
                "startSeconds": first["startSeconds"],
                "endSeconds": last["endSeconds"],
                "matchedText": " ".join(w["text"] for w in words[i:i + len(targets)]),
                "context": " ".join(w["text"] for w in words[ctx_start:ctx_end]),
            })

    return matches


@mcp.tool()
def get_sequence_transcript(sequence_id: str = None, item_name: str = None,
                            include_raw: bool = False):
    """
    Returns the Speech-to-Text transcript with word-level timings for a
    sequence (or a named project item). The transcript must already exist -
    run Speech-to-Text in Premiere first (Window > Text > Transcript).

    NOTE: Transcript APIs may be beta-channel only; a clear error is returned
    if unavailable.

    Args:
        sequence_id (str, optional): The sequence whose transcript to fetch.
        item_name (str, optional): Alternatively, a project item name.
        include_raw (bool): If True, also returns the raw transcript JSON string.
    """

    result, words = _fetch_transcript_words(sequence_id, item_name)

    if words is None:
        return result

    out = {
        "wordCount": len(words),
        "words": words,
        "fullText": " ".join(w["text"] for w in words),
    }
    if include_raw:
        out["rawJson"] = result["response"]["transcriptJson"]

    return out


@mcp.tool()
def export_transcript(file_path: str, sequence_id: str = None, item_name: str = None):
    """
    Exports the raw transcript JSON of a sequence (or project item) to a file.

    Args:
        file_path (str): Destination path for the .json file.
        sequence_id (str, optional): The sequence whose transcript to export.
        item_name (str, optional): Alternatively, a project item name.
    """

    command = createCommand("getTranscript", {
        "sequenceId": sequence_id,
        "itemName": item_name
    })
    result = sendCommand(command)

    if not isinstance(result, dict) or result.get("status") != "SUCCESS":
        return result

    raw = result["response"]["transcriptJson"]

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(raw)

    return {"success": True, "filePath": file_path, "bytes": len(raw)}


@mcp.tool()
def find_in_transcript(query: str, sequence_id: str = None, item_name: str = None,
                       case_sensitive: bool = False):
    """
    Searches the transcript for a word or phrase and returns each occurrence
    with start/end timecodes and surrounding context - the foundation for
    "cut to where she says X" workflows.

    Args:
        query (str): The word or phrase to find.
        sequence_id (str, optional): The sequence whose transcript to search.
        item_name (str, optional): Alternatively, a project item name.
        case_sensitive (bool): Match case exactly. Defaults to False.
    """

    result, words = _fetch_transcript_words(sequence_id, item_name)

    if words is None:
        return result

    matches = _search_words(words, query, case_sensitive)

    return {"query": query, "matchCount": len(matches), "matches": matches}


@mcp.tool()
def create_markers_from_transcript(sequence_id: str, query: str,
                                   marker_type: str = "Comment",
                                   case_sensitive: bool = False,
                                   marker_name: str = None):
    """
    Searches the sequence transcript for a word/phrase and creates a sequence
    marker at every occurrence (all in one undoable transaction). Pairs with
    transcript-driven rough-cut workflows.

    Args:
        sequence_id (str): The id of the sequence.
        query (str): The word or phrase to find.
        marker_type (str): Marker type for the created markers. Default "Comment".
        case_sensitive (bool): Match case exactly. Defaults to False.
        marker_name (str, optional): Name for the markers. Defaults to the query.
    """

    result, words = _fetch_transcript_words(sequence_id, None)

    if words is None:
        return result

    matches = _search_words(words, query, case_sensitive)

    if not matches:
        return {"success": True, "matchCount": 0, "markersCreated": 0}

    markers = []
    for m in matches:
        markers.append({
            "name": marker_name or query,
            "markerType": marker_type,
            "startTimeSeconds": m["startSeconds"],
            "durationSeconds": max(0.0, (m["endSeconds"] or m["startSeconds"]) - m["startSeconds"]),
            "comments": m["context"],
        })

    command = createCommand("addMarkersBatch", {
        "sequenceId": sequence_id,
        "markers": markers
    })
    r = sendCommand(command)

    if isinstance(r, dict):
        r["matchCount"] = len(matches)

    return r


@mcp.tool()
def import_transcript(transcript_json_path: str, sequence_id: str = None,
                      item_name: str = None):
    """
    Imports an external transcript (JSON in Adobe's transcript format - see
    transcript_format_spec.json in the uxp-premiere-pro-samples repo) onto a
    sequence or project item.

    Args:
        transcript_json_path (str): Path to the transcript .json file.
        sequence_id (str, optional): Target sequence.
        item_name (str, optional): Alternatively, a target project item name.
    """

    with open(transcript_json_path, "r", encoding="utf-8") as f:
        raw = f.read()

    command = createCommand("importTranscript", {
        "sequenceId": sequence_id,
        "itemName": item_name,
        "transcriptJson": raw
    })

    return sendCommand(command)


@mcp.tool()
def get_captions(sequence_id: str):
    """
    Returns the sequence's caption tracks and their caption items (times and
    best-effort text). Caption items created by Premiere's captioning UI or
    imported SRT files appear here.

    Args:
        sequence_id (str): The id of the sequence.
    """

    command = createCommand("getCaptions", {
        "sequenceId": sequence_id
    })

    return sendCommand(command)


# ---------------------------------------------------------------------------
# Phase 3 / Priority 8 : Multi-sequence & source monitor
# ---------------------------------------------------------------------------

@mcp.tool()
def get_sequence_list():
    """
    Returns all sequences in the project (name, id, and which is active).
    Lightweight alternative to get_project_info when you only need sequence ids.
    """

    command = createCommand("getSequenceList", {})

    return sendCommand(command)


@mcp.tool()
def create_empty_sequence(name: str, preset_path: str = None, set_active: bool = True):
    """
    Creates a new empty sequence, optionally from a .sqpreset file. Without a
    preset, Premiere's default sequence preset is used.

    Args:
        name (str): Name for the new sequence.
        preset_path (str, optional): Absolute path to a .sqpreset file defining
            resolution/frame rate/track layout.
        set_active (bool): Make the new sequence active. Defaults to True.
    """

    command = createCommand("createEmptySequence", {
        "name": name,
        "presetPath": preset_path,
        "setActive": set_active
    })

    return sendCommand(command)


@mcp.tool()
def duplicate_sequence(sequence_id: str, new_name: str = None):
    """
    Duplicates a sequence (full clone including all tracks, clips, and
    effects) and returns the new sequence's name and id.

    Args:
        sequence_id (str): The id of the sequence to duplicate.
        new_name (str, optional): Rename the duplicate (best-effort).
    """

    command = createCommand("duplicateSequence", {
        "sequenceId": sequence_id,
        "newName": new_name
    })

    return sendCommand(command)


@mcp.tool()
def nest_clips(sequence_id: str):
    """
    Nests the selected clips into a nested sequence.

    NOTE: No nest API is exposed by UXP as of Premiere 25.x - this tool
    feature-detects and reports clearly if unavailable. Workaround: set
    sequence in/out over the region, create_subsequence, then place the
    resulting sequence project item with overwrite_clip_at_time.

    Args:
        sequence_id (str): The id of the sequence.
    """

    command = createCommand("nestClips", {
        "sequenceId": sequence_id
    })

    return sendCommand(command)


@mcp.tool()
def open_in_source_monitor(item_name: str = None, file_path: str = None):
    """
    Opens a project item (or a file from disk) in the Source Monitor for
    preview and three-point editing.

    Args:
        item_name (str, optional): The name of a project item to open.
        file_path (str, optional): Alternatively, an absolute file path.
    """

    command = createCommand("openInSourceMonitor", {
        "itemName": item_name,
        "filePath": file_path
    })

    return sendCommand(command)


@mcp.tool()
def set_source_in_out(item_name: str, in_point_seconds: float = None,
                      out_point_seconds: float = None, clear: bool = False):
    """
    Sets (or clears) a project item's source in/out points - the source side
    of three-point editing. After marking in/out, insert_clip_at_time /
    overwrite_clip_at_time place only the marked range on the timeline.

    Args:
        item_name (str): The name of the project item.
        in_point_seconds (float): Source in point, in seconds.
        out_point_seconds (float): Source out point, in seconds.
        clear (bool): If True, clears the item's in/out points instead.
    """

    if not clear and (in_point_seconds is None or out_point_seconds is None):
        raise ValueError("Provide in_point_seconds and out_point_seconds, or clear=True.")

    command = createCommand("setSourceInOut", {
        "itemName": item_name,
        "inPointSeconds": in_point_seconds,
        "outPointSeconds": out_point_seconds,
        "clear": clear
    })

    return sendCommand(command)


# ---------------------------------------------------------------------------
# Phase 3 / Priority 9 : Graphics & titles via MOGRT
# ---------------------------------------------------------------------------

@mcp.tool()
def list_mogrt_library(folder_path: str = None):
    """
    Lists .mogrt files available for insert_mogrt. Scans the given folder
    (recursively), or Premiere's installed MOGRT directory if none is given.

    Args:
        folder_path (str, optional): Folder to scan for .mogrt files. If
            omitted, uses Premiere's installed MOGRT path.
    """

    folder = folder_path

    if folder is None:
        result = sendCommand(createCommand("getInstalledMogrtPath", {}))
        if not isinstance(result, dict) or result.get("status") != "SUCCESS":
            return result
        folder = result["response"]["path"]

    if not folder or not os.path.isdir(folder):
        return {"folder": folder, "mogrts": [],
                "note": "Folder does not exist or is not accessible from the MCP server."}

    mogrts = []
    for root, _dirs, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(".mogrt"):
                mogrts.append(os.path.join(root, f))

    return {"folder": folder, "count": len(mogrts), "mogrts": sorted(mogrts)}


@mcp.tool()
def get_mogrt_parameters(sequence_id: str, video_track_index: int, track_item_index: int):
    """
    Reads the editable parameters of an inserted MOGRT clip (text content,
    colors, etc.). Uses the dedicated MGT component API when this Premiere
    version exposes it; otherwise returns the clip's full component chain
    (MOGRT params appear among the components).

    Args:
        sequence_id (str): The id of the sequence.
        video_track_index (int): The video track containing the MOGRT clip (0-based).
        track_item_index (int): The clip index within the track (0-based).
    """

    command = createCommand("getMogrtParameters", {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "trackItemIndex": track_item_index
    })

    return sendCommand(command)


@mcp.tool()
def set_mogrt_parameter(sequence_id: str, video_track_index: int, track_item_index: int,
                        param_name: str, value):
    """
    Sets an editable parameter on an inserted MOGRT clip (e.g. "Source Text").
    Use get_mogrt_parameters first to see the available parameter names.

    Args:
        sequence_id (str): The id of the sequence.
        video_track_index (int): The video track containing the MOGRT clip (0-based).
        track_item_index (int): The clip index within the track (0-based).
        param_name (str): The parameter display name.
        value: The value to set (string for text params, number, bool, or
            {"x","y"} for points).
    """

    command = createCommand("setMogrtParameter", {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "paramName": param_name,
        "value": value
    })

    return sendCommand(command)


@mcp.tool()
def create_title(sequence_id: str, text: str, mogrt_path: str,
                 insertion_time_seconds: float, video_track_index: int = 1,
                 audio_track_index: int = 0, text_param_name: str = "Source Text"):
    """
    Creates a title: inserts a title MOGRT at the given time and sets its text.
    (UXP has no direct text-layer API - MOGRT parameter injection is the
    reliable path to programmatic titles.)

    Args:
        sequence_id (str): The id of the sequence.
        text (str): The title text.
        mogrt_path (str): Path to a title .mogrt file (see list_mogrt_library).
        insertion_time_seconds (float): Timeline position in seconds.
        video_track_index (int): Target video track (default 1 - above the footage).
        audio_track_index (int): Target audio track (default 0).
        text_param_name (str): The MOGRT's text parameter name. Defaults to
            "Source Text"; use get_mogrt_parameters if the MOGRT names it
            differently.
    """

    insert_result = sendCommand(createCommand("insertMogrt", {
        "sequenceId": sequence_id,
        "mogrtPath": mogrt_path,
        "insertionTimeSeconds": insertion_time_seconds,
        "videoTrackIndex": video_track_index,
        "audioTrackIndex": audio_track_index
    }))

    if not isinstance(insert_result, dict) or insert_result.get("status") != "SUCCESS":
        return insert_result

    # find the inserted clip's index on the track: the item whose start matches
    details = sendCommand(createCommand("getSequenceDetails", {
        "sequenceId": sequence_id, "includeEffects": False
    }))

    track_item_index = None
    try:
        tracks = details["response"]["tracks"]
        v = next(t for t in tracks
                 if t["trackType"] == "VIDEO" and t["trackIndex"] == video_track_index)
        for c in v["clips"]:
            if abs(c["startSeconds"] - insertion_time_seconds) < 0.01:
                track_item_index = c["index"]
                break
    except (KeyError, StopIteration, TypeError):
        pass

    if track_item_index is None:
        return {"status": "PARTIAL", "inserted": True, "textSet": False,
                "message": "MOGRT inserted but its clip could not be located to set the text. Set it with set_mogrt_parameter."}

    set_result = sendCommand(createCommand("setMogrtParameter", {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "paramName": text_param_name,
        "value": text
    }))

    return {"inserted": True, "trackItemIndex": track_item_index, "textSet": set_result}


# ---------------------------------------------------------------------------
# Phase 3 / Priority 10 : Encoder & project interchange
# ---------------------------------------------------------------------------

@mcp.tool()
def list_export_presets(extra_folders: list[str] = []):
    """
    Lists export preset (.epr) files found in the standard Adobe preset
    locations on this machine (plus any extra folders provided). Use a
    returned path as preset_path for export_with_encoder / export_sequence.

    Args:
        extra_folders (list[str], optional): Additional folders to scan.
    """

    candidates = list(extra_folders)

    program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    adobe_root = os.path.join(program_files, "Adobe")
    if os.path.isdir(adobe_root):
        for app_dir in os.listdir(adobe_root):
            base = os.path.join(adobe_root, app_dir)
            candidates.append(os.path.join(base, "MediaIO", "systempresets"))
            candidates.append(os.path.join(base, "Settings", "EncoderPresets"))

    docs = os.path.join(os.path.expanduser("~"), "Documents", "Adobe")
    if os.path.isdir(docs):
        for sub in os.listdir(docs):
            candidates.append(os.path.join(docs, sub))

    presets = []
    seen = set()
    for folder in candidates:
        if not os.path.isdir(folder):
            continue
        for root, _dirs, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(".epr"):
                    p = os.path.join(root, f)
                    if p not in seen:
                        seen.add(p)
                        presets.append(p)

    return {"count": len(presets), "presets": sorted(presets)}


@mcp.tool()
def export_with_encoder(sequence_id: str, output_file: str, preset_file: str,
                        export_type: str = "IMMEDIATELY", export_full: bool = True):
    """
    Exports a sequence through the Encoder Manager with an explicit output
    path and preset, either rendering immediately in Premiere or queueing to
    Adobe Media Encoder.

    IMPORTANT: Immediate exports can take a long time; a timeout usually means
    the export is still running, not that it failed.

    Args:
        sequence_id (str): The id of the sequence to export.
        output_file (str): Full output file path (extension should match the
            preset; check with get_export_file_extension).
        preset_file (str): Path to the .epr export preset (see list_export_presets).
        export_type (str): "IMMEDIATELY" (render in Premiere, blocking),
            "QUEUE_TO_AME" (queue in Adobe Media Encoder), or "QUEUE_TO_APP".
        export_full (bool): Export the full sequence (True) or the in/out
            range (False).
    """

    command = createCommand("exportWithEncoder", {
        "sequenceId": sequence_id,
        "outputFile": output_file,
        "presetFile": preset_file,
        "exportType": export_type,
        "exportFull": export_full
    })

    return sendCommand(command)


@mcp.tool()
def get_export_file_extension(sequence_id: str, preset_path: str):
    """
    Returns the output file extension a given export preset produces (e.g.
    "mp4", "wav") so output paths can be built correctly.

    Args:
        sequence_id (str): The id of the sequence (required by the API).
        preset_path (str): Path to the .epr preset file.
    """

    command = createCommand("getExportFileExtension", {
        "sequenceId": sequence_id,
        "presetPath": preset_path
    })

    return sendCommand(command)


@mcp.tool()
def export_audio_only(sequence_id: str, output_file: str, preset_file: str = None):
    """
    Exports only the audio of a sequence (podcast/music workflows) using an
    audio export preset.

    Args:
        sequence_id (str): The id of the sequence.
        output_file (str): Full output file path (e.g. .wav / .mp3 matching the preset).
        preset_file (str, optional): Path to an audio .epr preset. If omitted,
            searches the standard preset folders for a WAV preset.
    """

    preset = preset_file

    if preset is None:
        found = list_export_presets()
        for p in found.get("presets", []):
            name = os.path.basename(p).lower()
            if "wav" in name or "waveform" in name:
                preset = p
                break

    if preset is None:
        raise ValueError(
            "No audio preset found automatically. Pass preset_file with the path "
            "to an audio .epr preset (see list_export_presets)."
        )

    command = createCommand("exportWithEncoder", {
        "sequenceId": sequence_id,
        "outputFile": output_file,
        "presetFile": preset,
        "exportType": "IMMEDIATELY",
        "exportFull": True
    })

    result = sendCommand(command)
    if isinstance(result, dict):
        result["presetUsed"] = preset
    return result


@mcp.tool()
def batch_export_sequences(jobs: list[dict], preset_file: str = None,
                           export_type: str = "QUEUE_TO_AME", start_queue: bool = True):
    """
    Exports multiple sequences: queues each job to Adobe Media Encoder (or
    renders immediately) and optionally starts the AME batch queue.

    Args:
        jobs (list[dict]): One per sequence:
            - "sequenceId" (str)
            - "outputFile" (str)
            - "presetFile" (str, optional): overrides the shared preset_file
        preset_file (str, optional): Shared preset for jobs without their own.
        export_type (str): "QUEUE_TO_AME" (default) or "IMMEDIATELY" (renders
            each sequentially, blocking).
        start_queue (bool): Start the AME queue after adding jobs (needs
            Premiere 26.3+; reported in the response).
    """

    command = createCommand("batchExportSequences", {
        "jobs": jobs,
        "presetFile": preset_file,
        "exportType": export_type,
        "startQueue": start_queue
    })

    return sendCommand(command)


@mcp.tool()
def export_aaf(output_file: str, sequence_id: str = None):
    """
    Exports the project/sequence as AAF for interchange with other NLEs/DAWs.

    NOTE: Interchange exports are not exposed by UXP in all Premiere versions -
    this feature-detects and reports clearly if unavailable (fall back to
    File > Export in the Premiere UI).

    Args:
        output_file (str): Destination .aaf path.
        sequence_id (str, optional): Sequence to export; defaults to the active one.
    """

    command = createCommand("exportProjectInterchange", {
        "format": "AAF",
        "outputFile": output_file,
        "sequenceId": sequence_id
    })

    return sendCommand(command)


@mcp.tool()
def export_fcpxml(output_file: str, sequence_id: str = None):
    """
    Exports the project/sequence as Final Cut Pro XML for interchange.

    NOTE: Interchange exports are not exposed by UXP in all Premiere versions -
    this feature-detects and reports clearly if unavailable.

    Args:
        output_file (str): Destination .xml path.
        sequence_id (str, optional): Sequence to export; defaults to the active one.
    """

    command = createCommand("exportProjectInterchange", {
        "format": "FCPXML",
        "outputFile": output_file,
        "sequenceId": sequence_id
    })

    return sendCommand(command)


@mcp.tool()
def export_otio(output_file: str, sequence_id: str = None):
    """
    Exports the sequence as OpenTimelineIO for interchange with the wider
    post-production pipeline.

    NOTE: Interchange exports are not exposed by UXP in all Premiere versions -
    this feature-detects and reports clearly if unavailable.

    Args:
        output_file (str): Destination .otio path.
        sequence_id (str, optional): Sequence to export; defaults to the active one.
    """

    command = createCommand("exportProjectInterchange", {
        "format": "OTIO",
        "outputFile": output_file,
        "sequenceId": sequence_id
    })

    return sendCommand(command)


# ---------------------------------------------------------------------------
# Phase 3 / Priority 11 : Batch orchestration & auto-editing
# (architecture ported from ps-mcp.py action sequences)
# ---------------------------------------------------------------------------

# operation -> (action, track index key, include trackType, forced track type)
PR_BATCH_OPERATIONS = {
    "add_video_effect": ("addVideoEffect", "videoTrackIndex", False, "VIDEO"),
    "set_effect_parameter": ("setEffectParameter", "trackIndex", True, None),
    "remove_effect": ("removeEffect", "trackIndex", True, None),
    "set_clip_transform": ("setClipTransform", "videoTrackIndex", False, "VIDEO"),
    "set_clip_crop": ("setClipCrop", "videoTrackIndex", False, "VIDEO"),
    "lumetri": ("setLumetriParams", "videoTrackIndex", False, "VIDEO"),
    "fade_video_in": ("fadeVideoIn", "trackIndex", False, "VIDEO"),
    "fade_video_out": ("fadeVideoOut", "trackIndex", False, "VIDEO"),
    "ken_burns": ("kenBurns", "trackIndex", False, "VIDEO"),
    "add_keyframes": ("addKeyframes", "trackIndex", True, None),
    "set_clip_volume": ("setClipVolume", "audioTrackIndex", False, "AUDIO"),
    "set_clip_pan": ("setClipPan", "audioTrackIndex", False, "AUDIO"),
    "fade_audio_in": ("fadeAudioIn", "audioTrackIndex", False, "AUDIO"),
    "fade_audio_out": ("fadeAudioOut", "audioTrackIndex", False, "AUDIO"),
    "set_clip_disabled": ("setClipDisabled", "trackIndex", True, None),
    "add_video_transition": ("appendVideoTransition", "videoTrackIndex", False, "VIDEO"),
    "set_video_clip_properties": ("setVideoClipProperties", "videoTrackIndex", False, "VIDEO"),
}

PR_SEQUENCES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "pr_action_sequences.json")


def _pr_load_sequences() -> dict:
    try:
        with open(PR_SEQUENCES_FILE, "r", encoding="utf-8") as f:
            return _json.load(f)
    except (FileNotFoundError, _json.JSONDecodeError):
        return {}


def _pr_save_sequences(sequences: dict):
    with open(PR_SEQUENCES_FILE, "w", encoding="utf-8") as f:
        _json.dump(sequences, f, indent=2)


def _pr_run_operation(sequence_id: str, operation: str, clip: dict, settings: dict):
    action, track_key, include_type, forced_type = PR_BATCH_OPERATIONS[operation]

    options = dict(settings or {})
    options["sequenceId"] = sequence_id
    options[track_key] = clip["trackIndex"]
    options["trackItemIndex"] = clip["trackItemIndex"]
    if include_type:
        options["trackType"] = clip.get("trackType") or forced_type or "VIDEO"

    return sendCommand(createCommand(action, options))


def _pr_validate_operations(operations: list):
    for i, step in enumerate(operations):
        if not isinstance(step, dict) or "operation" not in step:
            raise ValueError(f"Step {i} must be a dict with an 'operation' key")
        if step["operation"] not in PR_BATCH_OPERATIONS:
            raise ValueError(
                f"Step {i}: unknown operation '{step['operation']}'. "
                f"Valid operations: {', '.join(sorted(PR_BATCH_OPERATIONS))}"
            )


@mcp.tool()
def create_action_sequence(sequence_name: str, operations: list, description: str = ""):
    """
    Saves a named, reusable sequence of clip operations that can be replayed
    against one or more timeline clips with play_action_sequence (e.g. a
    "vintage look" = lumetri + vignette + fade in). Sequences persist across
    server restarts; same-name sequences are overwritten.

    Args:
        sequence_name (str): Name for the action sequence (e.g. "vintage_look").
        operations (list): Ordered steps, each a dict with:
            - operation (str): one of: add_video_effect, set_effect_parameter,
              remove_effect, set_clip_transform, set_clip_crop, lumetri,
              fade_video_in, fade_video_out, ken_burns, add_keyframes,
              set_clip_volume, set_clip_pan, fade_audio_in, fade_audio_out,
              set_clip_disabled, add_video_transition, set_video_clip_properties.
            - settings (dict): The operation's options using the same camelCase
              keys as the matching tool's command options (clip addressing is
              injected per clip). Example:
              [{"operation": "lumetri",
                "settings": {"params": [{"name": "Temperature", "value": 30}]}},
               {"operation": "fade_video_in", "settings": {"durationSeconds": 1.0}}]
        description (str): Optional human-readable description.
    """

    _pr_validate_operations(operations)

    sequences = _pr_load_sequences()
    sequences[sequence_name] = {
        "description": description,
        "operations": operations
    }
    _pr_save_sequences(sequences)

    return {
        "status": "SUCCESS",
        "sequence_name": sequence_name,
        "steps": len(operations),
        "saved_to": PR_SEQUENCES_FILE
    }


@mcp.tool()
def play_action_sequence(sequence_name: str, sequence_id: str, clips: list[dict]):
    """
    Replays a saved action sequence against each of the specified timeline
    clips, in order. A failing step records the error and continues; a lost
    connection aborts and marks remaining clips SKIPPED.

    Args:
        sequence_name (str): Name of a sequence from create_action_sequence.
        sequence_id (str): The id of the timeline sequence containing the clips.
        clips (list[dict]): Clips to process, each:
            - "trackIndex" (int), "trackItemIndex" (int)
            - "trackType" (str): "VIDEO"/"AUDIO" (needed for track-type-generic
              operations)
    """

    sequences = _pr_load_sequences()
    if sequence_name not in sequences:
        raise ValueError(
            f"Unknown sequence '{sequence_name}'. "
            f"Available: {', '.join(sorted(sequences)) or '(none)'}"
        )

    operations = sequences[sequence_name]["operations"]
    _pr_validate_operations(operations)

    results = []
    aborted = False

    for clip in clips:
        if aborted:
            results.append({"clip": clip, "status": "SKIPPED",
                            "error": "Skipped: connection to Premiere lost"})
            continue

        step_results = []
        for i, step in enumerate(operations):
            try:
                response = _pr_run_operation(sequence_id, step["operation"],
                                             clip, step.get("settings", {}))
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
            "clip": clip,
            "status": "FAILURE" if failed else "SUCCESS",
            "steps": step_results
        })

    return {"sequence_name": sequence_name, "results": results}


@mcp.tool()
def list_action_sequences():
    """
    Lists all saved action sequences with their descriptions and steps.
    """

    sequences = _pr_load_sequences()
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
        sequence_name (str): Name of the action sequence to delete.
    """

    sequences = _pr_load_sequences()
    if sequence_name not in sequences:
        raise ValueError(
            f"Unknown sequence '{sequence_name}'. "
            f"Available: {', '.join(sorted(sequences)) or '(none)'}"
        )

    del sequences[sequence_name]
    _pr_save_sequences(sequences)

    return {"status": "SUCCESS", "deleted": sequence_name}


@mcp.tool()
def assemble_timeline_from_plan(plan: dict, sequence_id: str = None):
    """
    Builds an edit from a single JSON plan: places clips, then applies
    transitions, effects, audio settings, and markers - one call instead of a
    long tool-call chain. Steps that fail are recorded and assembly continues;
    a lost connection aborts.

    Args:
        plan (dict): The edit decision list:
            {
              "newSequenceName": str (optional - creates an empty sequence; else
                                      pass sequence_id),
              "clips": [{"itemName": str, "timeSeconds": float,
                         "videoTrackIndex": int (default 0),
                         "audioTrackIndex": int (default 0),
                         "mode": "overwrite"|"insert" (default "overwrite"),
                         "sourceInSeconds": float (optional),
                         "sourceOutSeconds": float (optional)}],
              "transitions": [{"videoTrackIndex": int, "trackItemIndex": int,
                               "name": str, "durationSeconds": float,
                               "clipAlignment": float}],
              "effects": [{"videoTrackIndex": int, "trackItemIndex": int,
                           "matchName": str, "properties": [{"name","value"}]}],
              "lumetri": [{"videoTrackIndex": int, "trackItemIndex": int,
                           "params": [{"name","value"}]}],
              "audio": [{"audioTrackIndex": int, "trackItemIndex": int,
                         "volumeDb": float (optional), "pan": float (optional),
                         "fadeInSeconds": float (optional),
                         "fadeOutSeconds": float (optional)}],
              "markers": [{"name": str, "startTimeSeconds": float,
                           "durationSeconds": float, "comments": str,
                           "markerType": str}]
            }
        sequence_id (str, optional): Build into an existing sequence (ignored
            if plan.newSequenceName is set).
    """

    steps = []

    def run(label, action, options):
        try:
            r = sendCommand(createCommand(action, options))
            steps.append({"step": label, "status": "SUCCESS"})
            return r
        except socket_client.AppError as e:
            steps.append({"step": label, "status": "FAILURE", "error": str(e)})
            return None
        except RuntimeError as e:
            steps.append({"step": label, "status": "ABORTED", "error": str(e)})
            raise

    try:
        seq = sequence_id
        if plan.get("newSequenceName"):
            r = run("create sequence", "createEmptySequence",
                    {"name": plan["newSequenceName"], "presetPath": None,
                     "setActive": True})
            if not r:
                return {"status": "FAILURE", "steps": steps,
                        "error": "Could not create the sequence."}
            seq = r["response"]["id"]

        if not seq:
            raise ValueError("Provide sequence_id or plan.newSequenceName")

        for i, c in enumerate(plan.get("clips", [])):
            if c.get("sourceInSeconds") is not None and c.get("sourceOutSeconds") is not None:
                run(f"clip {i}: source in/out", "setSourceInOut",
                    {"itemName": c["itemName"],
                     "inPointSeconds": c["sourceInSeconds"],
                     "outPointSeconds": c["sourceOutSeconds"], "clear": False})

            mode = c.get("mode", "overwrite")
            action = "insertClipAtTime" if mode == "insert" else "overwriteClipAtTime"
            options = {
                "sequenceId": seq,
                "itemName": c["itemName"],
                "insertionTimeSeconds": c["timeSeconds"],
                "videoTrackIndex": c.get("videoTrackIndex", 0),
                "audioTrackIndex": c.get("audioTrackIndex", 0),
            }
            if mode == "insert":
                options["limitedShift"] = True
            run(f"clip {i}: {mode} {c['itemName']} @ {c['timeSeconds']}s", action, options)

        for i, t in enumerate(plan.get("transitions", [])):
            run(f"transition {i}: {t['name']}", "appendVideoTransition", {
                "sequenceId": seq,
                "videoTrackIndex": t.get("videoTrackIndex", 0),
                "trackItemIndex": t["trackItemIndex"],
                "transitionName": t["name"],
                "durationSeconds": t.get("durationSeconds", 1.0),
                "duration": t.get("durationSeconds", 1.0),
                "clipAlignment": t.get("clipAlignment", 0.5),
            })

        for i, e in enumerate(plan.get("effects", [])):
            run(f"effect {i}: {e['matchName']}", "addVideoEffect", {
                "sequenceId": seq,
                "videoTrackIndex": e.get("videoTrackIndex", 0),
                "trackItemIndex": e["trackItemIndex"],
                "effectMatchName": e["matchName"],
                "properties": e.get("properties", []),
            })

        for i, l in enumerate(plan.get("lumetri", [])):
            run(f"lumetri {i}", "setLumetriParams", {
                "sequenceId": seq,
                "videoTrackIndex": l.get("videoTrackIndex", 0),
                "trackItemIndex": l["trackItemIndex"],
                "params": l.get("params", []),
            })

        for i, a in enumerate(plan.get("audio", [])):
            base = {"sequenceId": seq,
                    "audioTrackIndex": a.get("audioTrackIndex", 0),
                    "trackItemIndex": a["trackItemIndex"]}
            if a.get("volumeDb") is not None:
                run(f"audio {i}: volume", "setClipVolume",
                    dict(base, levelDb=a["volumeDb"], rawValue=None))
            if a.get("pan") is not None:
                run(f"audio {i}: pan", "setClipPan", dict(base, balance=a["pan"]))
            if a.get("fadeInSeconds"):
                run(f"audio {i}: fade in", "fadeAudioIn",
                    dict(base, durationSeconds=a["fadeInSeconds"]))
            if a.get("fadeOutSeconds"):
                run(f"audio {i}: fade out", "fadeAudioOut",
                    dict(base, durationSeconds=a["fadeOutSeconds"]))

        if plan.get("markers"):
            run("markers", "addMarkersBatch",
                {"sequenceId": seq, "markers": plan["markers"]})

    except RuntimeError:
        return {"status": "ABORTED", "sequenceId": seq, "steps": steps}

    failed = sum(1 for s in steps if s["status"] == "FAILURE")
    return {
        "status": "SUCCESS" if failed == 0 else "PARTIAL",
        "sequenceId": seq,
        "totalSteps": len(steps),
        "failedSteps": failed,
        "steps": steps
    }


@mcp.tool()
def auto_cut_at_markers(sequence_id: str, track_index: int, track_type: str = "VIDEO",
                        marker_type: str = None):
    """
    Splits clips on a track at every sequence marker whose time falls inside a
    clip - pairs with create_markers_from_transcript for transcript-driven
    rough cuts. Markers are processed right-to-left; each split re-reads the
    timeline so indices stay correct.

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The track whose clips get split (0-based).
        track_type (str): "VIDEO" (default) or "AUDIO".
        marker_type (str, optional): Only cut at markers of this type
            (e.g. "Comment", "Chapter"). All markers if omitted.
    """

    markers_result = sendCommand(createCommand("getSequenceMarkers", {
        "sequenceId": sequence_id
    }))

    if not isinstance(markers_result, dict) or markers_result.get("status") != "SUCCESS":
        return markers_result

    markers = markers_result["response"]["markers"]
    if marker_type:
        markers = [mk for mk in markers if mk.get("type") == marker_type]

    times = sorted({mk["startSeconds"] for mk in markers}, reverse=True)

    cuts = []
    for t in times:
        details = sendCommand(createCommand("getSequenceDetails", {
            "sequenceId": sequence_id, "includeEffects": False
        }))

        clip_index = None
        try:
            tracks = details["response"]["tracks"]
            track = next(tr for tr in tracks
                         if tr["trackType"] == track_type and tr["trackIndex"] == track_index)
            for c in track["clips"]:
                if c["startSeconds"] + 0.01 < t < c["endSeconds"] - 0.01:
                    clip_index = c["index"]
                    break
        except (KeyError, StopIteration, TypeError):
            pass

        if clip_index is None:
            cuts.append({"timeSeconds": t, "status": "SKIPPED",
                         "reason": "no clip spans this time"})
            continue

        try:
            r = sendCommand(createCommand("splitClip", {
                "sequenceId": sequence_id,
                "trackIndex": track_index,
                "trackItemIndex": clip_index,
                "trackType": track_type,
                "splitTimeSeconds": t
            }))
            cuts.append({"timeSeconds": t, "status": "SUCCESS",
                         "path": (r.get("response") or {}).get("path")})
        except socket_client.AppError as e:
            cuts.append({"timeSeconds": t, "status": "FAILURE", "error": str(e)})
        except RuntimeError as e:
            cuts.append({"timeSeconds": t, "status": "ABORTED", "error": str(e)})
            break

    succeeded = sum(1 for c in cuts if c["status"] == "SUCCESS")
    return {"markerCount": len(times), "cutsMade": succeeded, "cuts": cuts}


@mcp.resource("config://get_instructions")
def get_instructions() -> str:
    """Read this first! Returns information and instructions on how to use Photoshop and this API"""

    return f"""
    You are a Premiere Pro and video expert who is creative and loves to help other people learn to use Premiere and create.

    Rules to follow:

    1. Think deeply about how to solve the task
    2. Always check your work
    3. Read the info for the API calls to make sure you understand the requirements and arguments
    4. In general, add clips first, then effects, then transitions
    5. As a general rule keep transitions short (no more that 2 seconds is a good rule), and there should not be a gap between clips (or else the transition may not work)

    IMPORTANT: To create a new project and add clips:
    1. Create new project (create_project)
    2. Add media to the project (import_media)
    3. Create a new sequence with media (should always add video / image clips before audio.(create_sequence_from_media). This will create a sequence with the clips.
    4. The first clip you add will determine the dimensions / resolution of the sequence

    READING THE TIMELINE (do this before editing):
    Call get_sequence_details to see every track and clip (names, times in both
    seconds and ticks, disabled state, effects). You cannot edit reliably what
    you have not read. get_selected_clips shows what the user has selected in
    the timeline UI.

    TIME UNITS:
    Premiere internally uses ticks: 1 second = 254,016,000,000 ticks (ticks per
    SECOND, not per day). Newer tools take seconds directly; some legacy tools
    (add_media_to_sequence, add_marker_to_sequence, set_clip_start_end_times)
    take ticks. get_sequence_details returns both.

    INSERT vs OVERWRITE:
    - insert_clip_at_time performs an insert edit: downstream clips shift right
      to make room.
    - overwrite_clip_at_time replaces whatever it overlaps; nothing shifts.
    - clone_clip duplicates a clip already on the timeline (offsets from the
      original position); move_clip shifts a clip in time on its own track;
      split_clip razors a clip in two; remove_clips deletes in batch with an
      optional ripple.

    EFFECTS (generic engine):
    Any video effect can be applied by matchName: list_video_effects enumerates
    what is installed (e.g. "AE.ADBE Gaussian Blur 2", "AE.ADBE Lumetri"),
    add_video_effect applies one with optional initial parameters,
    get_clip_effects reads back parameter names and current values,
    set_effect_parameter adjusts them, remove_effect removes them. Audio
    effects use display names via list_audio_effects / add_audio_effect.
    The intrinsic Motion component is exposed via set_clip_transform
    (position/scale/rotation) and cropping via set_clip_crop.
    copy_clip_effects transfers a look from one clip to others.
    (The add_*_effect tools for black & white, gaussian blur, tint, and motion
    blur are deprecated wrappers around this engine.)

    AUDIO:
    set_clip_volume (dB), set_clip_pan, fade_audio_in / fade_audio_out (volume
    keyframes), add_audio_transition (crossfades, when available), and
    get_audio_clip_info for reading levels back. Track-level: set_audio_track_mute.

    KEYFRAME ANIMATION:
    Any effect parameter can be animated: add_keyframes (batch, one Undo step,
    preferred) / add_keyframe, get_keyframes, remove_keyframe, clear_keyframes,
    set_keyframe_interpolation (LINEAR/BEZIER/HOLD). Keyframe times are in
    SEQUENCE seconds. High-level composites: fade_video_in / fade_video_out
    (opacity), ken_burns (scale+position pan/zoom with easing), and
    animate_clip_property for friendly names (scale, position, rotation,
    opacity, volume).

    COLOR (Lumetri):
    add_lumetri_basic (exposure/contrast/highlights/shadows/temperature/tint/
    saturation), add_lumetri_creative, add_vignette, apply_lut, and
    get_lumetri_settings to read values back for iterative grading. All manage
    a single Lumetri instance per clip. If a parameter name misses, the
    response lists the actual parameter names - retry with set_effect_parameter.

    MARKERS & METADATA:
    get_sequence_markers / update_marker / remove_marker (by index),
    add_marker_to_sequence (timeline), add_clip_marker (source clips),
    get/set_project_item_metadata, batch_rename_project_items, get_media_info,
    set_clip_label_color.

    MULTI-SEQUENCE & THREE-POINT EDITING:
    get_sequence_list, create_empty_sequence, duplicate_sequence,
    open_in_source_monitor, set_source_in_out (mark a source range, then
    insert/overwrite places only that range), create_subsequence.

    TITLES & GRAPHICS (MOGRT):
    list_mogrt_library -> insert_mogrt -> get_mogrt_parameters ->
    set_mogrt_parameter ("Source Text" for text). create_title does
    insert+set-text in one call. There is no direct text-layer API.

    EXPORT & INTERCHANGE:
    list_export_presets (.epr files on disk), get_export_file_extension,
    export_with_encoder (immediate or queue to AME), export_audio_only,
    batch_export_sequences, export_sequence (legacy path). AAF/FCPXML/OTIO
    exports feature-detect (not exposed by UXP in all versions).

    BATCH ORCHESTRATION:
    create_action_sequence / play_action_sequence / list_action_sequences /
    delete_action_sequence save reusable per-clip operation chains (looks,
    fades, audio treatments). assemble_timeline_from_plan builds a whole edit
    from one JSON plan (clips + transitions + effects + lumetri + audio +
    markers). auto_cut_at_markers splits clips at every marker (pairs with
    create_markers_from_transcript for transcript-driven rough cuts).

    TRANSCRIPTS & CAPTIONS (may require Premiere Beta):
    get_sequence_transcript (word-level timings), find_in_transcript (phrase ->
    timecodes), create_markers_from_transcript (search hits -> markers),
    export_transcript / import_transcript, get_captions. The transcript must
    already exist (run Speech-to-Text in Premiere first).

    Here are some general tips for when working with Premiere.

    Audio and Video clips are added on separate Audio / Video tracks, which you can access via their index. Track indices and clip (track item) indices are 0-based; clip indices count left to right.

    When adding a video clip that contains audio, the audio will be placed on a separate audio track.

    To remove clips use remove_clips (batch, with optional ripple delete); you can also disable clips with set_clip_disabled.

    If you want to do a transition between two clips, the clips must be on the same track and there should not be a gap between them. Place the transition of the first clip.

    Video clips with a higher track index will overlap and hide those with lower index if they overlap.

    When adding images to a sequence, they will have a duration of 5 seconds.

    Titles / text graphics: use insert_mogrt with a .mogrt file - there is no
    direct text-layer API.

    blend_modes: {", ".join(BLEND_MODES)}
    """


BLEND_MODES = [
    "COLOR",
    "COLORBURN",
    "COLORDODGE",
    "DARKEN",
    "DARKERCOLOR",
    "DIFFERENCE",
    "DISSOLVE",
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
    "PINLIGHT",
    "SATURATION",
    "SCREEN",
    "SOFTLIGHT",
    "VIVIDLIGHT",
    "SUBTRACT",
    "DIVIDE"
]