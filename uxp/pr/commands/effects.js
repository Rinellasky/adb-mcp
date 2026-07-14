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

/* Phase 1 / Priority 2 : Generic effects engine
 * Replaces the "one tool per hardcoded effect" pattern with a discoverable
 * engine built on VideoFilterFactory.getMatchNames().
 * Roadmap: Technical_Roadmap_Premiere.md
 */

const app = require("premierepro");

const { TRACK_TYPE } = require("./consts.js");

const {
    _getSequenceFromId,
    execute,
    getTrack,
    findComponentByMatchName,
    findParamOnComponent,
    readComponentChain,
    sanitizeParamValue,
} = require("./utils.js");

/* ------------------------------------------------------------------ */
/* Internal helpers                                                    */
/* ------------------------------------------------------------------ */

const MOTION_MATCH_NAME = "AE.ADBE Motion";
//Live-verified 2026-07-08: the crop effect's matchName is "AE.ADBE AECrop"
//(there is no "AE.ADBE Crop" in Premiere 25.x)
const CROP_MATCH_NAME = "AE.ADBE AECrop";

const makePoint = (x, y) => {
    //PointF construction is version-sensitive; try the class then fall back
    try {
        return new app.PointF(x, y);
    } catch (e) {}

    try {
        return app.PointF(x, y);
    } catch (e) {}

    return { x, y };
};

const toParamValue = (value) => {
    //Allow point params to be passed from the MCP side as {x, y}
    if (
        value !== null &&
        typeof value === "object" &&
        typeof value.x === "number" &&
        typeof value.y === "number"
    ) {
        return makePoint(value.x, value.y);
    }
    return value;
};

const setParamValueOnComponent = (project, component, paramName, value) => {
    const param = findParamOnComponent(component, paramName);

    if (!param) {
        throw new Error(
            `setParamValueOnComponent : param [${paramName}] not found on component`
        );
    }

    const keyframe = param.createKeyframe(toParamValue(value));

    execute(() => {
        const action = param.createSetValueAction(keyframe, true);
        return [action];
    }, project);
};

const requireComponent = async (trackItem, matchName) => {
    const component = await findComponentByMatchName(trackItem, matchName);

    if (!component) {
        throw new Error(
            `Component [${matchName}] not found on clip. Use get_clip_effects to inspect the component chain.`
        );
    }

    return component;
};

//Adds the effect if it is not already on the clip; returns the component
const ensureEffect = async (project, trackItem, matchName) => {
    let component = await findComponentByMatchName(trackItem, matchName);

    if (component) {
        return component;
    }

    const effect = await app.VideoFilterFactory.createComponent(matchName);

    if (!effect) {
        throw new Error(
            `ensureEffect : could not create effect [${matchName}]. Use list_video_effects for valid matchNames.`
        );
    }

    const componentChain = await trackItem.getComponentChain();

    execute(() => {
        const action = componentChain.createAppendComponentAction(effect);
        return [action];
    }, project);

    component = await findComponentByMatchName(trackItem, matchName);

    if (!component) {
        throw new Error(
            `ensureEffect : effect [${matchName}] was not found on the clip after applying it`
        );
    }

    return component;
};

/* ------------------------------------------------------------------ */
/* Discovery                                                           */
/* ------------------------------------------------------------------ */

const listVideoEffects = async (command) => {
    const matchNames = await app.VideoFilterFactory.getMatchNames();
    return { effects: matchNames };
};

const listAudioEffects = async (command) => {
    const displayNames = await app.AudioFilterFactory.getDisplayNames();
    return { effects: displayNames };
};

/* ------------------------------------------------------------------ */
/* Apply / read / modify / remove                                      */
/* ------------------------------------------------------------------ */

const addVideoEffect = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);

    const trackItem = await getTrack(
        sequence,
        options.videoTrackIndex,
        options.trackItemIndex,
        TRACK_TYPE.VIDEO
    );

    const effect = await app.VideoFilterFactory.createComponent(
        options.effectMatchName
    );

    if (!effect) {
        throw new Error(
            `addVideoEffect : could not create effect [${options.effectMatchName}]. Use list_video_effects for valid matchNames.`
        );
    }

    const componentChain = await trackItem.getComponentChain();

    execute(() => {
        const action = componentChain.createAppendComponentAction(effect);
        return [action];
    }, project);

    //apply initial parameter values
    if (options.properties && options.properties.length > 0) {
        const component = await requireComponent(
            trackItem,
            options.effectMatchName
        );

        for (const p of options.properties) {
            setParamValueOnComponent(project, component, p.name, p.value);
        }
    }

    return { success: true };
};

const addAudioEffect = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);

    const trackItem = await getTrack(
        sequence,
        options.audioTrackIndex,
        options.trackItemIndex,
        TRACK_TYPE.AUDIO
    );

    const effect = await app.AudioFilterFactory.createComponentByDisplayName(
        options.effectDisplayName,
        trackItem
    );

    if (!effect) {
        throw new Error(
            `addAudioEffect : could not create effect [${options.effectDisplayName}]. Use list_audio_effects for valid display names.`
        );
    }

    const componentChain = await trackItem.getComponentChain();

    execute(() => {
        const action = componentChain.createAppendComponentAction(effect);
        return [action];
    }, project);

    return { success: true };
};

const getClipEffects = async (command) => {
    const options = command.options;
    const sequence = await _getSequenceFromId(options.sequenceId);

    const trackItem = await getTrack(
        sequence,
        options.trackIndex,
        options.trackItemIndex,
        options.trackType
    );

    const effects = await readComponentChain(trackItem);

    return { effects };
};

const setEffectParameter = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);

    const trackItem = await getTrack(
        sequence,
        options.trackIndex,
        options.trackItemIndex,
        options.trackType
    );

    const component = await requireComponent(
        trackItem,
        options.effectMatchName
    );

    setParamValueOnComponent(
        project,
        component,
        options.paramName,
        options.value
    );

    return { success: true };
};

const removeEffect = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);

    const trackItem = await getTrack(
        sequence,
        options.trackIndex,
        options.trackItemIndex,
        options.trackType
    );

    const component = await requireComponent(
        trackItem,
        options.effectMatchName
    );

    const componentChain = await trackItem.getComponentChain();

    execute(() => {
        const action = componentChain.createRemoveComponentAction(component);
        return [action];
    }, project);

    return { success: true };
};

/* ------------------------------------------------------------------ */
/* Intrinsic Motion / Crop convenience tools                           */
/* ------------------------------------------------------------------ */

//Position is a normalized point (0.5, 0.5 = centered). Scale/rotation are
//numbers matching the Effect Controls panel values.
const setClipTransform = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);

    const trackItem = await getTrack(
        sequence,
        options.videoTrackIndex,
        options.trackItemIndex,
        TRACK_TYPE.VIDEO
    );

    const component = await requireComponent(trackItem, MOTION_MATCH_NAME);

    const applied = [];

    if (options.position) {
        setParamValueOnComponent(project, component, "Position", {
            x: options.position.x,
            y: options.position.y,
        });
        applied.push("Position");
    }

    if (options.scale !== null && options.scale !== undefined) {
        setParamValueOnComponent(project, component, "Scale", options.scale);
        applied.push("Scale");
    }

    if (options.rotation !== null && options.rotation !== undefined) {
        setParamValueOnComponent(
            project,
            component,
            "Rotation",
            options.rotation
        );
        applied.push("Rotation");
    }

    if (options.anchorPoint) {
        setParamValueOnComponent(project, component, "Anchor Point", {
            x: options.anchorPoint.x,
            y: options.anchorPoint.y,
        });
        applied.push("Anchor Point");
    }

    if (applied.length === 0) {
        throw new Error(
            "setClipTransform : no transform values provided (position, scale, rotation, anchorPoint)"
        );
    }

    return { success: true, applied };
};

const setClipCrop = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);

    const trackItem = await getTrack(
        sequence,
        options.videoTrackIndex,
        options.trackItemIndex,
        TRACK_TYPE.VIDEO
    );

    const component = await ensureEffect(project, trackItem, CROP_MATCH_NAME);

    const edges = [
        ["Left", options.left],
        ["Top", options.top],
        ["Right", options.right],
        ["Bottom", options.bottom],
    ];

    const applied = [];
    for (const [name, value] of edges) {
        if (value !== null && value !== undefined) {
            setParamValueOnComponent(project, component, name, value);
            applied.push(name);
        }
    }

    if (applied.length === 0) {
        throw new Error(
            "setClipCrop : no crop values provided (left, top, right, bottom)"
        );
    }

    return { success: true, applied };
};

/* ------------------------------------------------------------------ */
/* Copy effects ("match the look")                                     */
/* ------------------------------------------------------------------ */

//Intrinsic components present on every clip; not copied
const INTRINSIC_MATCH_NAMES = [
    "AE.ADBE Motion",
    "AE.ADBE Opacity",
    "AE.ADBE Time Remapping",
    "AE.ADBE Audio Levels",
    "AE.ADBE Audio Pan",
];

const copyClipEffects = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);

    const source = options.source;
    const sourceItem = await getTrack(
        sequence,
        source.trackIndex,
        source.trackItemIndex,
        source.trackType
    );

    const chain = await readComponentChain(sourceItem);

    const toCopy = chain.filter(
        (c) => !INTRINSIC_MATCH_NAMES.includes(c.matchName)
    );

    const copied = [];
    const failed = [];

    for (const target of options.targets) {
        const targetItem = await getTrack(
            sequence,
            target.trackIndex,
            target.trackItemIndex,
            target.trackType
        );

        for (const effectInfo of toCopy) {
            try {
                const component = await ensureEffect(
                    project,
                    targetItem,
                    effectInfo.matchName
                );

                for (const p of effectInfo.params) {
                    if (p.value === null || p.value === undefined) {
                        continue;
                    }

                    try {
                        setParamValueOnComponent(
                            project,
                            component,
                            p.name,
                            sanitizeParamValue(p.value)
                        );
                    } catch (e) {
                        //some params are not writable; continue with the rest
                    }
                }

                copied.push({
                    matchName: effectInfo.matchName,
                    target,
                });
            } catch (e) {
                failed.push({
                    matchName: effectInfo.matchName,
                    target,
                    error: String(e),
                });
            }
        }
    }

    return { success: failed.length === 0, copied, failed };
};

const commandHandlers = {
    listVideoEffects,
    listAudioEffects,
    addVideoEffect,
    addAudioEffect,
    getClipEffects,
    setEffectParameter,
    removeEffect,
    setClipTransform,
    setClipCrop,
    copyClipEffects,
};

module.exports = {
    commandHandlers,
    ensureEffect,
    setParamValueOnComponent,
};
