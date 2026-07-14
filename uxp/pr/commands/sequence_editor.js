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

/* Phase 1 / Priority 1 : SequenceEditor operations
 * Roadmap: Technical_Roadmap_Premiere.md
 */

const app = require("premierepro");
const constants = require("premierepro").Constants;

const { TRACK_TYPE } = require("./consts.js");

const {
    _getSequenceFromId,
    findProjectItem,
    execute,
    getTrack,
    getTrackItems,
    ticksFromSeconds,
    readComponentChain,
    readTrackItem,
} = require("./utils.js");

/* ------------------------------------------------------------------ */
/* Read tools                                                          */
/* ------------------------------------------------------------------ */

//The keystone read tool: full track/clip inventory including effects.
const getSequenceDetails = async (command) => {
    const options = command.options;
    const sequence = await _getSequenceFromId(options.sequenceId);
    const includeEffects = options.includeEffects !== false;

    const readTrack = async (track, trackType, trackIndex) => {
        const trackItems = await track.getTrackItems(
            constants.TrackItemType.CLIP,
            false
        );

        const clips = [];
        for (const [i, item] of trackItems.entries()) {
            const clip = await readTrackItem(item, i);

            if (includeEffects) {
                try {
                    clip.effects = await readComponentChain(item);
                } catch (e) {
                    clip.effects = null;
                }
            }

            clips.push(clip);
        }

        let muted = null;
        if (trackType === TRACK_TYPE.AUDIO) {
            try {
                muted = await track.isMuted();
            } catch (e) {}
        }

        return {
            trackType,
            trackIndex,
            name: track.name,
            muted,
            clips,
        };
    };

    const tracks = [];

    const vCount = await sequence.getVideoTrackCount();
    for (let i = 0; i < vCount; i++) {
        tracks.push(
            await readTrack(await sequence.getVideoTrack(i), TRACK_TYPE.VIDEO, i)
        );
    }

    const aCount = await sequence.getAudioTrackCount();
    for (let i = 0; i < aCount; i++) {
        tracks.push(
            await readTrack(await sequence.getAudioTrack(i), TRACK_TYPE.AUDIO, i)
        );
    }

    const size = await sequence.getFrameSize();
    const endTime = await sequence.getEndTime();

    return {
        name: sequence.name,
        id: sequence.guid.toString(),
        frameSize: { width: size.width, height: size.height },
        durationSeconds: endTime.seconds,
        videoTrackCount: vCount,
        audioTrackCount: aCount,
        tracks,
    };
};

const getTrackCount = async (command) => {
    const options = command.options;
    const sequence = await _getSequenceFromId(options.sequenceId);

    const videoTrackCount = await sequence.getVideoTrackCount();
    const audioTrackCount = await sequence.getAudioTrackCount();

    let captionTrackCount = null;
    try {
        captionTrackCount = await sequence.getCaptionTrackCount();
    } catch (e) {
        //caption APIs may not be available on all versions
    }

    return { videoTrackCount, audioTrackCount, captionTrackCount };
};

/* ------------------------------------------------------------------ */
/* Insert / overwrite / clone / move / split / remove                  */
/* ------------------------------------------------------------------ */

const insertClipAtTime = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);
    const projectItem = await findProjectItem(options.itemName, project);

    const editor = await app.SequenceEditor.getEditor(sequence);
    const time = await app.TickTime.createWithSeconds(options.insertionTimeSeconds);

    execute(() => {
        const action = editor.createInsertProjectItemAction(
            projectItem,
            time,
            options.videoTrackIndex,
            options.audioTrackIndex,
            options.limitedShift
        );
        return [action];
    }, project);

    return { success: true };
};

const overwriteClipAtTime = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);
    const projectItem = await findProjectItem(options.itemName, project);

    const editor = await app.SequenceEditor.getEditor(sequence);
    const time = await app.TickTime.createWithSeconds(options.insertionTimeSeconds);

    execute(() => {
        const action = editor.createOverwriteItemAction(
            projectItem,
            time,
            options.videoTrackIndex,
            options.audioTrackIndex
        );
        return [action];
    }, project);

    return { success: true };
};

const cloneClip = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);

    const trackItem = await getTrack(
        sequence,
        options.trackIndex,
        options.trackItemIndex,
        options.trackType
    );

    const editor = await app.SequenceEditor.getEditor(sequence);
    const timeOffset = await app.TickTime.createWithSeconds(options.timeOffsetSeconds);
    const alignToVideo = options.trackType === TRACK_TYPE.VIDEO;

    execute(() => {
        const action = editor.createCloneTrackItemAction(
            trackItem,
            timeOffset,
            options.videoTrackOffset,
            options.audioTrackOffset,
            alignToVideo,
            options.insert
        );
        return [action];
    }, project);

    return { success: true };
};

//Note: createMoveAction shifts a clip in time on its own track. Moving a clip
//across tracks is a clone + remove composite (use clone_clip + remove_clips).
const moveClip = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);

    const trackItem = await getTrack(
        sequence,
        options.trackIndex,
        options.trackItemIndex,
        options.trackType
    );

    const currentStart = await trackItem.getStartTime();

    const targetTicks = ticksFromSeconds(options.newStartTimeSeconds);
    const shift =
        Number(targetTicks.ticksNumber) - Number(currentStart.ticksNumber);

    const shiftTick = app.TickTime.createWithTicks(shift.toString());

    execute(() => {
        const action = trackItem.createMoveAction(shiftTick);
        return [action];
    }, project);

    return { success: true, shiftedTicks: shift };
};

//Composite razor. No native split/razor exists in the UXP API.
//
//FAST PATH (same-track): overwrite-clone at the split offset truncates the
//original to [S, T) and leaves the clone at [T, T+dur); setInPoint(+D) then
//move(-D) turns the clone into the right piece [T, E). Safe ONLY when no clip
//occupies [E, T+dur) on the same track (the untrimmed clone would overwrite it).
//
//SAFE PATH (temp-track, used automatically when a downstream clip is in the
//danger window): clone to another track whose [T, T+dur) region is empty,
//trim it into the right piece there, trim the original to [S, T), overwrite-
//clone the piece back into the now-empty [T, E), and remove the temp copy.
//
//LIVE-VERIFIED (2026-07-08): createSetInPointAction shifts the clip's
//TIMELINE START by the in-point delta and leaves the end unchanged; do NOT
//combine it with setEnd (collapses the clip to zero length).
const splitClip = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);
    const trackIndex = options.trackIndex;
    const trackType = options.trackType;

    const trackItem = await getTrack(
        sequence,
        trackIndex,
        options.trackItemIndex,
        trackType
    );

    const start = await trackItem.getStartTime();
    const end = await trackItem.getEndTime();
    const inPoint = await trackItem.getInPoint();
    const duration = await trackItem.getDuration();

    const startSeconds = start.seconds;
    const endSeconds = end.seconds;
    const durSeconds = duration.seconds;
    const splitSeconds = options.splitTimeSeconds;

    if (splitSeconds <= startSeconds || splitSeconds >= endSeconds) {
        throw new Error(
            `splitClip : splitTimeSeconds [${splitSeconds}] must fall inside the clip [${startSeconds} - ${endSeconds}]`
        );
    }

    const offsetSeconds = splitSeconds - startSeconds;
    const alignToVideo = trackType === TRACK_TYPE.VIDEO;
    const editor = await app.SequenceEditor.getEditor(sequence);

    const EPS = 0.0001;

    //does any OTHER clip on a track intersect [fromS, toS)?
    const trackRegionOccupied = async (tIndex, fromS, toS, excludeItem) => {
        const items = await getTrackItems(sequence, tIndex, trackType);
        for (const item of items) {
            if (excludeItem) {
                const s0 = await item.getStartTime();
                const os = await excludeItem.getStartTime();
                if (Math.abs(s0.seconds - os.seconds) < EPS) {
                    const e0 = await item.getEndTime();
                    const oe = await excludeItem.getEndTime();
                    if (Math.abs(e0.seconds - oe.seconds) < EPS) {
                        continue;
                    }
                }
            }
            const s = (await item.getStartTime()).seconds;
            const e = (await item.getEndTime()).seconds;
            if (s < toS - EPS && e > fromS + EPS) {
                return true;
            }
        }
        return false;
    };

    //LIVE FINDING (2026-07-09): clone placement is snapped to the sequence's
    //frame grid (e.g. a requested 15.0s lands at 15.015 on a 29.97 timebase),
    //so locating the clone needs frame-level tolerance, and the trim must be
    //computed from the clone's ACTUAL snapped start.
    const FRAME_EPS = 0.06; //> one frame at 23.976

    const findItemAt = async (tIndex, atSeconds) => {
        const items = await getTrackItems(sequence, tIndex, trackType);
        let best = null;
        let bestDelta = FRAME_EPS;
        for (const item of items) {
            const s = await item.getStartTime();
            const delta = Math.abs(s.seconds - atSeconds);
            if (delta < bestDelta) {
                best = item;
                bestDelta = delta;
            }
        }
        return best;
    };

    //trim a full clone [T', T'+dur) into the right piece [T', E), where T' is
    //the clone's actual (frame-snapped) start
    const trimCloneToRightPiece = async (clone) => {
        const actualStart = await clone.getStartTime();
        const actualOffsetSeconds = actualStart.seconds - startSeconds;

        const newInPointSeconds = inPoint.seconds + actualOffsetSeconds;
        const shiftBackTicks = (
            -Number(ticksFromSeconds(actualOffsetSeconds).ticksNumber)
        ).toString();

        execute(() => {
            const out = [];
            out.push(
                clone.createSetInPointAction(
                    ticksFromSeconds(newInPointSeconds)
                )
            );
            out.push(
                clone.createMoveAction(
                    app.TickTime.createWithTicks(shiftBackTicks)
                )
            );
            return out;
        }, project);
    };

    const dangerFree = !(await trackRegionOccupied(
        trackIndex,
        endSeconds,
        splitSeconds + durSeconds,
        trackItem
    ));

    if (dangerFree) {
        //FAST PATH
        execute(() => {
            const action = editor.createCloneTrackItemAction(
                trackItem,
                ticksFromSeconds(offsetSeconds),
                0,
                0,
                alignToVideo,
                false
            );
            return [action];
        }, project);

        const clone = await findItemAt(trackIndex, splitSeconds);
        if (!clone) {
            throw new Error(
                "splitClip : could not locate the cloned right-hand piece. Undo and retry."
            );
        }

        await trimCloneToRightPiece(clone);
    } else {
        //SAFE PATH via temp track
        const trackCount =
            trackType === TRACK_TYPE.VIDEO
                ? await sequence.getVideoTrackCount()
                : await sequence.getAudioTrackCount();

        let tempIndex = -1;
        for (let i = 0; i < trackCount; i++) {
            if (i === trackIndex) continue;
            const occupied = await trackRegionOccupied(
                i,
                splitSeconds,
                splitSeconds + durSeconds,
                null
            );
            if (!occupied) {
                tempIndex = i;
                break;
            }
        }

        if (tempIndex === -1) {
            throw new Error(
                `splitClip : a downstream clip sits within ${offsetSeconds.toFixed(2)}s after this clip's end, and no other ${trackType} track has free space at [${splitSeconds} - ${(splitSeconds + durSeconds).toFixed(2)}]s to use as a working area. Add an empty ${trackType} track and retry.`
            );
        }

        const vOff = trackType === TRACK_TYPE.VIDEO ? tempIndex - trackIndex : 0;
        const aOff = trackType === TRACK_TYPE.AUDIO ? tempIndex - trackIndex : 0;

        //1. clone to temp track at [T, T+dur)
        execute(() => {
            const action = editor.createCloneTrackItemAction(
                trackItem,
                ticksFromSeconds(offsetSeconds),
                vOff,
                aOff,
                alignToVideo,
                false
            );
            return [action];
        }, project);

        const tempClone = await findItemAt(tempIndex, splitSeconds);
        if (!tempClone) {
            throw new Error(
                "splitClip : could not locate the temp-track clone. Undo and retry."
            );
        }

        //2. trim it into the right piece [T, E)
        await trimCloneToRightPiece(tempClone);

        //3. trim the original to [S, T)
        execute(() => {
            const action = trackItem.createSetEndAction(
                ticksFromSeconds(splitSeconds)
            );
            return [action];
        }, project);

        //4. clone the piece back into the freed [T, E) on the original track
        execute(() => {
            const action = editor.createCloneTrackItemAction(
                tempClone,
                ticksFromSeconds(0),
                -vOff,
                -aOff,
                alignToVideo,
                false
            );
            return [action];
        }, project);

        //5. remove the temp copy (no ripple)
        const selection = await sequence.getSelection();
        const existing = await selection.getTrackItems();
        for (const t of existing) {
            selection.removeItem(t);
        }
        selection.addItem(tempClone, true);

        execute(() => {
            const action = editor.createRemoveItemsAction(
                selection,
                false,
                constants.MediaType.ANY,
                false
            );
            return [action];
        }, project);

        try {
            await sequence.clearSelection();
        } catch (e) {}
    }

    return {
        success: true,
        path: dangerFree ? "fast" : "temp-track",
        leftClip: { startSeconds, endSeconds: splitSeconds },
        rightClip: { startSeconds: splitSeconds, endSeconds },
    };
};

//Batch removal with ripple option. Supersedes single-clip removeItemFromSequence.
const removeClips = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);

    const editor = await app.SequenceEditor.getEditor(sequence);

    //resolve all target trackItems first
    const targets = [];
    for (const c of options.clips) {
        const item = await getTrack(
            sequence,
            c.trackIndex,
            c.trackItemIndex,
            c.trackType
        );
        targets.push(item);
    }

    //build the selection (reuse the sequence selection object, cleared first)
    const selection = await sequence.getSelection();
    const existing = await selection.getTrackItems();

    for (const t of existing) {
        selection.removeItem(t);
    }

    for (const t of targets) {
        selection.addItem(t, true);
    }

    execute(() => {
        const shiftOverlapping = false;
        const action = editor.createRemoveItemsAction(
            selection,
            options.rippleDelete,
            constants.MediaType.ANY,
            shiftOverlapping
        );
        return [action];
    }, project);

    try {
        await sequence.clearSelection();
    } catch (e) {}

    return { success: true, removedCount: targets.length };
};

/* ------------------------------------------------------------------ */
/* Selection bridge                                                    */
/* ------------------------------------------------------------------ */

const selectClips = async (command) => {
    const options = command.options;
    const sequence = await _getSequenceFromId(options.sequenceId);

    const targets = [];
    for (const c of options.clips) {
        const item = await getTrack(
            sequence,
            c.trackIndex,
            c.trackItemIndex,
            c.trackType
        );
        targets.push(item);
    }

    const selection = await sequence.getSelection();
    const existing = await selection.getTrackItems();

    for (const t of existing) {
        selection.removeItem(t);
    }

    for (const t of targets) {
        selection.addItem(t, true);
    }

    sequence.setSelection(selection);

    return { success: true, selectedCount: targets.length };
};

const getSelectedClips = async (command) => {
    const options = command.options;
    const sequence = await _getSequenceFromId(options.sequenceId);

    const selection = await sequence.getSelection();
    const items = await selection.getTrackItems();

    const clips = [];
    for (const item of items) {
        const info = await readTrackItem(item, null);

        try {
            info.trackIndex = await item.getTrackIndex();
        } catch (e) {}

        try {
            //type index: differentiates video/audio track items
            info.type = await item.getType();
        } catch (e) {}

        clips.push(info);
    }

    return { clips };
};

/* ------------------------------------------------------------------ */
/* Subsequence / MOGRT                                                 */
/* ------------------------------------------------------------------ */

const createSubsequence = async (command) => {
    const options = command.options;
    const sequence = await _getSequenceFromId(options.sequenceId);

    const ignoreTrackTargeting = options.ignoreTrackTargeting !== false;

    const sub = await sequence.createSubsequence(ignoreTrackTargeting);

    if (!sub) {
        throw new Error(
            "createSubsequence : Premiere did not return a subsequence. Set sequence in/out points (or a selection) first."
        );
    }

    return { name: sub.name, id: sub.guid.toString() };
};

//The only reliable path to programmatic titles/text (see roadmap Phase 3).
const insertMogrt = async (command) => {
    const options = command.options;
    const sequence = await _getSequenceFromId(options.sequenceId);

    const editor = await app.SequenceEditor.getEditor(sequence);
    const time = await app.TickTime.createWithSeconds(options.insertionTimeSeconds);

    const items = await editor.insertMogrtFromPath(
        options.mogrtPath,
        time,
        options.videoTrackIndex,
        options.audioTrackIndex
    );

    if (!items || items.length === 0) {
        throw new Error(
            `insertMogrt : Premiere returned no track items for [${options.mogrtPath}]. Check the path points to a valid .mogrt file.`
        );
    }

    const out = [];
    for (const item of items) {
        out.push(await readTrackItem(item, null));
    }

    return { insertedItems: out };
};

const commandHandlers = {
    getSequenceDetails,
    getTrackCount,
    insertClipAtTime,
    overwriteClipAtTime,
    cloneClip,
    moveClip,
    splitClip,
    removeClips,
    selectClips,
    getSelectedClips,
    createSubsequence,
    insertMogrt,
};

module.exports = {
    commandHandlers,
};
