/* MIT License
 *
 * Copyright (c) 2025 Mike Chambers
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

/* Phase 2 / Priority 6 : Markers, metadata & project intelligence
 * Roadmap: Technical_Roadmap_Premiere.md
 */

const app = require("premierepro");
const constants = require("premierepro").Constants;

const {
    _getSequenceFromId,
    findProjectItem,
    execute,
    ticksFromSeconds,
} = require("./utils.js");

/* ------------------------------------------------------------------ */
/* Marker helpers                                                      */
/* ------------------------------------------------------------------ */

const readMarker = async (marker, index) => {
    const start = await marker.getStart();
    const duration = await marker.getDuration();

    let colorIndex = null;
    try {
        colorIndex = await marker.getColorIndex();
    } catch (e) {}

    let url = null;
    let target = null;
    try {
        url = await marker.getUrl();
        target = await marker.getTarget();
    } catch (e) {}

    return {
        index,
        name: await marker.getName(),
        type: await marker.getType(),
        comments: await marker.getComments(),
        startSeconds: start.seconds,
        startTicks: start.ticks,
        durationSeconds: duration.seconds,
        colorIndex,
        url,
        target,
    };
};

const getSequenceMarkersObject = async (sequenceId) => {
    const sequence = await _getSequenceFromId(sequenceId);
    return app.Markers.getMarkers(sequence);
};

//Identify a marker by its index within the current marker list (as returned
//by getSequenceMarkers).
const getMarkerByIndex = async (markersObject, markerIndex) => {
    const markers = await markersObject.getMarkers();

    if (markerIndex < 0 || markerIndex >= markers.length) {
        throw new Error(
            `Marker index [${markerIndex}] out of range (0-${markers.length - 1}). Call get_sequence_markers first.`
        );
    }

    return markers[markerIndex];
};

/* ------------------------------------------------------------------ */
/* Sequence markers                                                    */
/* ------------------------------------------------------------------ */

const getSequenceMarkers = async (command) => {
    const options = command.options;
    const markersObject = await getSequenceMarkersObject(options.sequenceId);

    const markers = await markersObject.getMarkers();

    const out = [];
    for (const [i, marker] of markers.entries()) {
        out.push(await readMarker(marker, i));
    }

    return { markers: out };
};

const removeMarker = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const markersObject = await getSequenceMarkersObject(options.sequenceId);
    const marker = await getMarkerByIndex(markersObject, options.markerIndex);

    execute(() => {
        const action = markersObject.createRemoveMarkerAction(marker);
        return [action];
    }, project);

    return { success: true };
};

const updateMarker = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const markersObject = await getSequenceMarkersObject(options.sequenceId);
    const marker = await getMarkerByIndex(markersObject, options.markerIndex);

    const updated = [];

    execute(() => {
        const out = [];

        if (options.name !== null && options.name !== undefined) {
            out.push(marker.createSetNameAction(options.name));
            updated.push("name");
        }

        if (options.comments !== null && options.comments !== undefined) {
            out.push(marker.createSetCommentsAction(options.comments));
            updated.push("comments");
        }

        if (
            options.durationSeconds !== null &&
            options.durationSeconds !== undefined
        ) {
            out.push(
                marker.createSetDurationAction(
                    ticksFromSeconds(options.durationSeconds)
                )
            );
            updated.push("duration");
        }

        if (options.markerType !== null && options.markerType !== undefined) {
            out.push(marker.createSetTypeAction(options.markerType));
            updated.push("type");
        }

        if (options.colorIndex !== null && options.colorIndex !== undefined) {
            out.push(marker.createSetColorByIndexAction(options.colorIndex));
            updated.push("color");
        }

        if (
            options.startTimeSeconds !== null &&
            options.startTimeSeconds !== undefined
        ) {
            out.push(
                markersObject.createMoveMarkerAction(
                    marker,
                    ticksFromSeconds(options.startTimeSeconds)
                )
            );
            updated.push("start");
        }

        if (out.length === 0) {
            throw new Error("updateMarker : no fields provided to update");
        }

        return out;
    }, project);

    return { success: true, updated };
};

//Batch add - used by create_markers_from_transcript to add all hits in one
//undoable transaction.
const addMarkersBatch = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const markersObject = await getSequenceMarkersObject(options.sequenceId);

    execute(() => {
        const out = [];
        for (const mk of options.markers) {
            out.push(
                markersObject.createAddMarkerAction(
                    mk.name,
                    mk.markerType || "Comment",
                    ticksFromSeconds(mk.startTimeSeconds),
                    ticksFromSeconds(mk.durationSeconds || 0),
                    mk.comments || ""
                )
            );
        }
        return out;
    }, project);

    return { success: true, addedCount: options.markers.length };
};

/* ------------------------------------------------------------------ */
/* Clip (project item) markers                                         */
/* ------------------------------------------------------------------ */

const addClipMarker = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const item = await findProjectItem(options.itemName, project);

    const clipItem = app.ClipProjectItem.cast(item);
    if (!clipItem) {
        throw new Error(
            `addClipMarker : [${options.itemName}] is not a clip project item`
        );
    }

    const markersObject = await app.Markers.getMarkers(clipItem);

    execute(() => {
        const action = markersObject.createAddMarkerAction(
            options.markerName,
            options.markerType || "Comment",
            ticksFromSeconds(options.startTimeSeconds),
            ticksFromSeconds(options.durationSeconds || 0),
            options.comments || ""
        );
        return [action];
    }, project);

    return { success: true };
};

/* ------------------------------------------------------------------ */
/* Project item metadata / rename / label / media info                 */
/* ------------------------------------------------------------------ */

const getProjectItemMetadata = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const item = await findProjectItem(options.itemName, project);

    let columns = null;
    try {
        columns = await app.Metadata.getProjectColumnsMetadata(item);
    } catch (e) {}

    let projectMetadata = null;
    try {
        projectMetadata = await app.Metadata.getProjectMetadata(item);
    } catch (e) {}

    let xmp = null;
    if (options.includeXmp) {
        try {
            xmp = await app.Metadata.getXMPMetadata(item);
        } catch (e) {}
    }

    return { columns, projectMetadata, xmp };
};

const setProjectItemMetadata = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const item = await findProjectItem(options.itemName, project);

    execute(() => {
        const action = app.Metadata.createSetProjectMetadataAction(
            item,
            options.metadata,
            options.updatedFields
        );
        return [action];
    }, project);

    return { success: true };
};

//prefix/suffix/find-replace/sequential numbering over project items,
//all renames in one transaction.
const batchRenameProjectItems = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();

    //resolve targets: explicit list, or all root-level items
    let targets = [];
    if (options.itemNames && options.itemNames.length > 0) {
        for (const name of options.itemNames) {
            targets.push(await findProjectItem(name, project));
        }
    } else {
        const root = await project.getRootItem();
        const items = await root.getItems();
        for (const item of items) {
            //skip bins
            if (!app.FolderItem.cast(item)) {
                targets.push(item);
            }
        }
    }

    if (targets.length === 0) {
        throw new Error("batchRenameProjectItems : no items to rename");
    }

    const renames = [];
    let counter = options.startNumber !== undefined ? options.startNumber : 1;

    for (const item of targets) {
        let newName = item.name;

        if (options.find !== null && options.find !== undefined) {
            newName = newName.split(options.find).join(options.replace || "");
        }

        if (options.baseName) {
            const pad = options.numberPadding || 2;
            newName = `${options.baseName}${String(counter).padStart(pad, "0")}`;
            counter++;
        }

        if (options.prefix) {
            newName = options.prefix + newName;
        }

        if (options.suffix) {
            newName = newName + options.suffix;
        }

        if (newName !== item.name) {
            renames.push({ item, from: item.name, to: newName });
        }
    }

    execute(() => {
        const out = [];
        for (const r of renames) {
            out.push(r.item.createSetNameAction(r.to));
        }
        return out;
    }, project);

    return {
        success: true,
        renamed: renames.map((r) => ({ from: r.from, to: r.to })),
    };
};

const getMediaInfo = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const item = await findProjectItem(options.itemName, project);

    const clipItem = app.ClipProjectItem.cast(item);
    if (!clipItem) {
        throw new Error(
            `getMediaInfo : [${options.itemName}] is not a clip project item`
        );
    }

    const out = { name: item.name };

    try {
        out.mediaFilePath = await clipItem.getMediaFilePath();
    } catch (e) {}

    try {
        out.isSequence = await clipItem.isSequence();
        out.isOffline = await clipItem.isOffline();
        out.isMergedClip = await clipItem.isMergedClip();
        out.isMulticamClip = await clipItem.isMulticamClip();
    } catch (e) {}

    try {
        const media = await clipItem.getMedia();
        if (media) {
            out.durationSeconds = media.duration.seconds;
            out.startSeconds = media.start.seconds;
        }
    } catch (e) {}

    try {
        const interp = await clipItem.getFootageInterpretation();
        if (interp) {
            out.frameRate = await interp.getFrameRate();
            out.pixelAspectRatio = await interp.getPixelAspectRatio();
            out.fieldType = await interp.getFieldType();
        }
    } catch (e) {}

    try {
        out.colorLabelIndex = await item.getColorLabelIndex();
    } catch (e) {}

    return out;
};

const setClipLabelColor = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const item = await findProjectItem(options.itemName, project);

    let colorIndex = options.colorIndex;

    //allow color by name via Constants.ProjectItemColorLabel
    if (
        (colorIndex === null || colorIndex === undefined) &&
        options.colorName
    ) {
        const c = constants.ProjectItemColorLabel[options.colorName];
        if (c === undefined) {
            throw new Error(
                `setClipLabelColor : unknown color name [${options.colorName}]. Valid: ${Object.keys(constants.ProjectItemColorLabel).join(", ")}`
            );
        }
        colorIndex = c;
    }

    if (colorIndex === null || colorIndex === undefined) {
        throw new Error(
            "setClipLabelColor : provide colorIndex or colorName"
        );
    }

    execute(() => {
        const action = item.createSetColorLabelAction(colorIndex);
        return [action];
    }, project);

    return { success: true, colorIndex };
};

const commandHandlers = {
    getSequenceMarkers,
    removeMarker,
    updateMarker,
    addMarkersBatch,
    addClipMarker,
    getProjectItemMetadata,
    setProjectItemMetadata,
    batchRenameProjectItems,
    getMediaInfo,
    setClipLabelColor,
};

module.exports = {
    commandHandlers,
};
