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

/* Phase 2 / Priority 7 : Transcripts & captions
 * Transcript APIs (app.Transcript) may be beta-channel only - every entry
 * point feature-detects and returns a clear error if unavailable.
 * Transcripts attach to ClipProjectItems; for a sequence we go through
 * sequence.getProjectItem(). Search / marker generation over the transcript
 * JSON happens server-side in Python (find_in_transcript,
 * create_markers_from_transcript).
 */

const app = require("premierepro");
const constants = require("premierepro").Constants;

const {
    _getSequenceFromId,
    findProjectItem,
    execute,
} = require("./utils.js");

const requireTranscriptAPI = () => {
    if (!app.Transcript) {
        throw new Error(
            "Transcript APIs (app.Transcript) are not available in this Premiere version. They may require the Beta channel."
        );
    }
};

//Resolve the ClipProjectItem that owns the transcript: either a named project
//item, or the project item behind a sequence.
const resolveTranscriptOwner = async (options) => {
    const project = await app.Project.getActiveProject();

    let item;
    if (options.itemName) {
        item = await findProjectItem(options.itemName, project);
    } else if (options.sequenceId) {
        const sequence = await _getSequenceFromId(options.sequenceId);
        item = await sequence.getProjectItem();
    } else {
        throw new Error("Provide itemName or sequenceId");
    }

    const clipItem = app.ClipProjectItem.cast(item);
    if (!clipItem) {
        throw new Error("Target is not a clip project item");
    }

    return { project, clipItem };
};

const getTranscript = async (command) => {
    requireTranscriptAPI();

    const options = command.options;
    const { clipItem } = await resolveTranscriptOwner(options);

    const json = await app.Transcript.exportToJSON(clipItem);

    if (!json) {
        throw new Error(
            "No transcript exists for this item. Run Speech-to-Text in Premiere first (Window > Text > Transcript)."
        );
    }

    //return as string; parsing/search happens server-side
    return { transcriptJson: json, length: json.length };
};

const importTranscript = async (command) => {
    requireTranscriptAPI();

    if (typeof app.Transcript.importFromJSON !== "function") {
        throw new Error(
            "Transcript.importFromJSON is not available in this Premiere version."
        );
    }

    const options = command.options;
    const { project, clipItem } = await resolveTranscriptOwner(options);

    const textSegments = await app.Transcript.importFromJSON(
        options.transcriptJson
    );

    if (!textSegments) {
        throw new Error(
            "importTranscript : could not parse the transcript JSON (see transcript_format_spec.json in Adobe's samples repo for the format)."
        );
    }

    execute(() => {
        const action = app.Transcript.createImportTextSegmentsAction(
            textSegments,
            clipItem
        );
        return [action];
    }, project);

    return { success: true };
};

//Best-effort caption reader: enumerates caption tracks and their items.
//The caption item text API is not fully documented in 25.x - we read what is
//available (name commonly holds the caption text) and report per-item.
const getCaptions = async (command) => {
    const options = command.options;
    const sequence = await _getSequenceFromId(options.sequenceId);

    let trackCount = 0;
    try {
        trackCount = await sequence.getCaptionTrackCount();
    } catch (e) {
        throw new Error(
            "Caption track APIs are not available in this Premiere version."
        );
    }

    const tracks = [];

    for (let i = 0; i < trackCount; i++) {
        const track = await sequence.getCaptionTrack(i);

        const items = await track.getTrackItems(
            constants.TrackItemType.CLIP,
            false
        );

        const captions = [];
        for (const [k, item] of items.entries()) {
            const entry = { index: k };

            try {
                const start = await item.getStartTime();
                const end = await item.getEndTime();
                entry.startSeconds = start.seconds;
                entry.endSeconds = end.seconds;
            } catch (e) {}

            try {
                entry.text = await item.getName();
            } catch (e) {}

            captions.push(entry);
        }

        tracks.push({
            trackIndex: i,
            name: track.name,
            captionCount: captions.length,
            captions,
        });
    }

    return { captionTrackCount: trackCount, tracks };
};

const commandHandlers = {
    getTranscript,
    importTranscript,
    getCaptions,
};

module.exports = {
    commandHandlers,
};
