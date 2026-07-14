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

/* Phase 2 / Priority 4 : Keyframe animation engine
 * Roadmap: Technical_Roadmap_Premiere.md
 *
 * Keyframe positions are in SEQUENCE time (verified in Phase 1 audio fades).
 * Batch keyframes are applied in ONE transaction (one Undo step).
 */

const app = require("premierepro");
const constants = require("premierepro").Constants;

const {
    _getSequenceFromId,
    execute,
    getTrack,
    ticksFromSeconds,
    findParamOnComponent,
    sanitizeParamValue,
} = require("./utils.js");

/* ------------------------------------------------------------------ */
/* Param resolution                                                    */
/* ------------------------------------------------------------------ */

//Finds a component by matchName, falling back to displayName so callers can
//say "Volume" or "Motion" as well as "AE.ADBE Motion".
const findComponent = async (trackItem, effectName) => {
    const chain = await trackItem.getComponentChain();
    const count = chain.getComponentCount();

    let byDisplayName = null;

    for (let i = 0; i < count; i++) {
        const component = chain.getComponentAtIndex(i);
        const matchName = await component.getMatchName();

        if (matchName === effectName) {
            return component;
        }

        if (!byDisplayName) {
            try {
                const displayName = await component.getDisplayName();
                if (displayName === effectName) {
                    byDisplayName = component;
                }
            } catch (e) {}
        }
    }

    return byDisplayName;
};

const resolveParam = async (options) => {
    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);

    const trackItem = await getTrack(
        sequence,
        options.trackIndex,
        options.trackItemIndex,
        options.trackType
    );

    const component = await findComponent(trackItem, options.effectMatchName);

    if (!component) {
        throw new Error(
            `Component [${options.effectMatchName}] not found on clip. Use get_clip_effects to inspect the component chain.`
        );
    }

    const param = findParamOnComponent(component, options.paramName);

    if (!param) {
        throw new Error(
            `Param [${options.paramName}] not found on component [${options.effectMatchName}]. Use get_clip_effects to list params.`
        );
    }

    return { project, sequence, trackItem, component, param };
};

const toParamValue = (value) => {
    if (
        value !== null &&
        typeof value === "object" &&
        typeof value.x === "number" &&
        typeof value.y === "number"
    ) {
        try {
            return new app.PointF(value.x, value.y);
        } catch (e) {}
        try {
            return app.PointF(value.x, value.y);
        } catch (e) {}
        return { x: value.x, y: value.y };
    }
    return value;
};

const interpolationModeFromName = (name) => {
    const mode = constants.InterpolationMode[name];
    if (mode === undefined) {
        throw new Error(
            `Unknown interpolation mode [${name}]. Valid: LINEAR, BEZIER, HOLD, TIME, TIME_TRANSITION_START, TIME_TRANSITION_END`
        );
    }
    return mode;
};

/* ------------------------------------------------------------------ */
/* Core handlers                                                       */
/* ------------------------------------------------------------------ */

const setParamTimeVarying = async (command) => {
    const options = command.options;
    const { project, param } = await resolveParam(options);

    execute(() => {
        const action = param.createSetTimeVaryingAction(options.timeVarying);
        return [action];
    }, project);

    return { success: true };
};

//The batch engine: enables time-varying, then adds ALL keyframes in a single
//transaction, then applies non-LINEAR interpolation modes.
const addKeyframes = async (command) => {
    const options = command.options;
    const { project, param } = await resolveParam(options);

    const keyframes = options.keyframes || [];

    if (keyframes.length === 0) {
        throw new Error("addKeyframes : keyframes list is empty");
    }

    //1. stopwatch on
    execute(() => {
        const action = param.createSetTimeVaryingAction(true);
        return [action];
    }, project);

    //2. all keyframes in ONE transaction (one Undo step, fast)
    execute(() => {
        const out = [];
        for (const kf of keyframes) {
            const keyframe = param.createKeyframe(toParamValue(kf.value));
            keyframe.position = ticksFromSeconds(kf.timeSeconds);
            out.push(param.createAddKeyframeAction(keyframe));
        }
        return out;
    }, project);

    //3. interpolation modes (only for non-LINEAR)
    const nonLinear = keyframes.filter(
        (kf) => kf.interpolation && kf.interpolation !== "LINEAR"
    );

    if (nonLinear.length > 0) {
        execute(() => {
            const out = [];
            for (const kf of nonLinear) {
                out.push(
                    param.createSetInterpolationAtKeyframeAction(
                        ticksFromSeconds(kf.timeSeconds),
                        interpolationModeFromName(kf.interpolation),
                        true
                    )
                );
            }
            return out;
        }, project);
    }

    return { success: true, keyframeCount: keyframes.length };
};

const getKeyframes = async (command) => {
    const options = command.options;
    const { param } = await resolveParam(options);

    let timeVarying = null;
    try {
        timeVarying = param.isTimeVarying();
    } catch (e) {}

    const out = [];

    try {
        const times = await param.getKeyframeListAsTickTimes();

        for (const t of times) {
            const entry = { timeSeconds: t.seconds, ticks: t.ticks };

            try {
                const kf = await param.getKeyframePtr(t);
                if (kf) {
                    entry.value = sanitizeParamValue(kf.value);
                    try {
                        //returns a Promise despite docs saying number
                        entry.temporalInterpolationMode =
                            await kf.getTemporalInterpolationMode();
                    } catch (e) {}
                }
            } catch (e) {}

            out.push(entry);
        }
    } catch (e) {
        //param has no keyframes / not time varying
    }

    return { timeVarying, keyframes: out };
};

const removeKeyframe = async (command) => {
    const options = command.options;
    const { project, param } = await resolveParam(options);

    execute(() => {
        const action = param.createRemoveKeyframeAction(
            ticksFromSeconds(options.timeSeconds),
            true
        );
        return [action];
    }, project);

    return { success: true };
};

const clearKeyframes = async (command) => {
    const options = command.options;
    const { project, param, trackItem } = await resolveParam(options);

    //remove everything across the clip's full extent (sequence time),
    //with margin on both sides
    const start = await trackItem.getStartTime();
    const end = await trackItem.getEndTime();

    const from = ticksFromSeconds(Math.max(0, start.seconds - 1));
    const to = ticksFromSeconds(end.seconds + 1);

    execute(() => {
        const action = param.createRemoveKeyframeRangeAction(from, to, true);
        return [action];
    }, project);

    if (options.resetTimeVarying) {
        execute(() => {
            const action = param.createSetTimeVaryingAction(false);
            return [action];
        }, project);
    }

    return { success: true };
};

const setKeyframeInterpolation = async (command) => {
    const options = command.options;
    const { project, param } = await resolveParam(options);

    execute(() => {
        const action = param.createSetInterpolationAtKeyframeAction(
            ticksFromSeconds(options.timeSeconds),
            interpolationModeFromName(options.interpolation),
            true
        );
        return [action];
    }, project);

    return { success: true };
};

/* ------------------------------------------------------------------ */
/* Video fade / Ken Burns composites                                   */
/* ------------------------------------------------------------------ */

const OPACITY_MATCH_NAME = "AE.ADBE Opacity";
const MOTION_MATCH_NAME = "AE.ADBE Motion";

const _fadeVideo = async (options, fadeIn) => {
    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);

    const trackItem = await getTrack(
        sequence,
        options.trackIndex,
        options.trackItemIndex,
        "VIDEO"
    );

    const component = await findComponent(trackItem, OPACITY_MATCH_NAME);
    if (!component) {
        throw new Error("fadeVideo : Opacity component not found on clip");
    }

    const param = findParamOnComponent(component, "Opacity");
    if (!param) {
        throw new Error("fadeVideo : Opacity param not found");
    }

    const start = await trackItem.getStartTime();
    const end = await trackItem.getEndTime();

    const duration = options.durationSeconds;
    const clipLength = end.seconds - start.seconds;

    if (duration <= 0 || duration > clipLength) {
        throw new Error(
            `fadeVideo : durationSeconds [${duration}] must be > 0 and <= the clip length [${clipLength}]`
        );
    }

    //current opacity = fade target/source
    let level = 100;
    try {
        const kf = await param.getStartValue();
        const v = sanitizeParamValue(kf.value);
        if (typeof v === "number") {
            level = v;
        }
    } catch (e) {}

    let points;
    if (fadeIn) {
        points = [
            { seconds: start.seconds, value: 0 },
            { seconds: start.seconds + duration, value: level },
        ];
    } else {
        points = [
            { seconds: end.seconds - duration, value: level },
            { seconds: end.seconds, value: 0 },
        ];
    }

    execute(() => {
        const action = param.createSetTimeVaryingAction(true);
        return [action];
    }, project);

    execute(() => {
        const out = [];
        for (const p of points) {
            const keyframe = param.createKeyframe(p.value);
            keyframe.position = ticksFromSeconds(p.seconds);
            out.push(param.createAddKeyframeAction(keyframe));
        }
        return out;
    }, project);

    return { success: true, keyframes: points };
};

const fadeVideoIn = async (command) => {
    return _fadeVideo(command.options, true);
};

const fadeVideoOut = async (command) => {
    return _fadeVideo(command.options, false);
};

//Ken Burns: scale + position keyframes on the Motion component across the
//clip's duration, with optional BEZIER ease.
const kenBurns = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);

    const trackItem = await getTrack(
        sequence,
        options.trackIndex,
        options.trackItemIndex,
        "VIDEO"
    );

    const component = await findComponent(trackItem, MOTION_MATCH_NAME);
    if (!component) {
        throw new Error("kenBurns : Motion component not found on clip");
    }

    const start = await trackItem.getStartTime();
    const end = await trackItem.getEndTime();

    const t0 = start.seconds;
    const t1 = end.seconds;

    const interpolation = options.ease ? "BEZIER" : null;

    const plans = [];

    if (
        options.startScale !== null &&
        options.startScale !== undefined &&
        options.endScale !== null &&
        options.endScale !== undefined
    ) {
        const param = findParamOnComponent(component, "Scale");
        if (!param) {
            throw new Error("kenBurns : Scale param not found on Motion");
        }
        plans.push({
            param,
            keyframes: [
                { timeSeconds: t0, value: options.startScale },
                { timeSeconds: t1, value: options.endScale },
            ],
        });
    }

    if (options.startPosition && options.endPosition) {
        const param = findParamOnComponent(component, "Position");
        if (!param) {
            throw new Error("kenBurns : Position param not found on Motion");
        }
        plans.push({
            param,
            keyframes: [
                { timeSeconds: t0, value: options.startPosition },
                { timeSeconds: t1, value: options.endPosition },
            ],
        });
    }

    if (plans.length === 0) {
        throw new Error(
            "kenBurns : provide startScale/endScale and/or startPosition/endPosition"
        );
    }

    for (const plan of plans) {
        execute(() => {
            const action = plan.param.createSetTimeVaryingAction(true);
            return [action];
        }, project);

        execute(() => {
            const out = [];
            for (const kf of plan.keyframes) {
                const keyframe = plan.param.createKeyframe(
                    toParamValue(kf.value)
                );
                keyframe.position = ticksFromSeconds(kf.timeSeconds);
                out.push(plan.param.createAddKeyframeAction(keyframe));
            }
            return out;
        }, project);

        if (interpolation) {
            execute(() => {
                const out = [];
                for (const kf of plan.keyframes) {
                    out.push(
                        plan.param.createSetInterpolationAtKeyframeAction(
                            ticksFromSeconds(kf.timeSeconds),
                            interpolationModeFromName(interpolation),
                            true
                        )
                    );
                }
                return out;
            }, project);
        }
    }

    return {
        success: true,
        animatedParams: plans.length,
        startSeconds: t0,
        endSeconds: t1,
    };
};

const commandHandlers = {
    setParamTimeVarying,
    addKeyframes,
    getKeyframes,
    removeKeyframe,
    clearKeyframes,
    setKeyframeInterpolation,
    fadeVideoIn,
    fadeVideoOut,
    kenBurns,
};

module.exports = {
    commandHandlers,
};
