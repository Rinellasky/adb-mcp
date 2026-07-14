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

/* Phase 1 / Priority 3 : Audio essentials
 * Roadmap: Technical_Roadmap_Premiere.md
 *
 * NOTES:
 * - Clip gain (set_clip_audio_gain) is descoped: no UXP API surface exists
 *   for project-item/clip gain as of 25.x. set_clip_volume covers the use case.
 * - Audio transitions are not documented in TransitionFactory (video only),
 *   so addAudioTransition feature-detects createAudioTransition at runtime.
 * - dB mapping: the Volume "Level" param stores an amplitude-style value, not
 *   dB. We convert with amplitude = 10^(dB/20). VERIFY EMPIRICALLY against the
 *   UI during live testing (see roadmap Priority 3 note); the rawValue escape
 *   hatch lets you calibrate without code changes.
 */

const app = require("premierepro");

const { TRACK_TYPE } = require("./consts.js");

const {
    _getSequenceFromId,
    execute,
    getTrack,
    ticksFromSeconds,
    findParamOnComponent,
    readComponentChain,
    sanitizeParamValue,
} = require("./utils.js");

/* ------------------------------------------------------------------ */
/* Internal helpers                                                    */
/* ------------------------------------------------------------------ */

//LIVE-VERIFIED (2026-07-08, Premiere 25.x): the volume component matchName is
//"Internal Volume Mono" (mono) / "Internal Volume Stereo" (stereo) with a
//displayName of "Volume" and params Mute + Level. Mono clips have NO panner
//component at all.
const VOLUME_COMPONENT_CANDIDATES = [
    "Internal Volume Mono",
    "Internal Volume Stereo",
    "AE.ADBE Audio Levels",
    "ADBE Audio Levels",
];
//LIVE-VERIFIED (2026-07-08): the intrinsic panner is NOT exposed via
//getComponentChain in 25.x (stereo clips show only Volume + Channel Volume).
//Panning is done by applying the "Balance" audio filter, which appears as
//"Internal Audio Balance" with a "Balance" param normalized 0..1 (0.5=center).
const PAN_COMPONENT_CANDIDATES = [
    "Internal Audio Balance",
    "AE.ADBE Audio Pan",
    "ADBE Audio Pan",
];

const BALANCE_FILTER_DISPLAY_NAME = "Balance";

//UI balance -100..100  <->  param 0..1
const balanceToParam = (balance) => (balance + 100) / 200;
const paramToBalance = (value) => value * 200 - 100;

//LIVE-VERIFIED (2026-07-08): the Level param stores 10^((dB_UI - 15) / 20) -
//a clip at the UI default of 0.0 dB reads 0.17782794 (= 10^(-15/20)).
//So UI dB = 20*log10(raw) + 15.
const dbToAmplitude = (db) => Math.pow(10, (db - 15) / 20);
const amplitudeToDb = (amplitude) =>
    amplitude > 0 ? 20 * Math.log10(amplitude) + 15 : -Infinity;

//Finds a component on an audio clip by matchName candidates, falling back to
//the component displayName (e.g. "Volume", "Panner") for version resilience.
const findAudioComponent = async (
    trackItem,
    matchNameCandidates,
    displayNameFallback
) => {
    const chain = await trackItem.getComponentChain();
    const count = chain.getComponentCount();

    let fallback = null;

    for (let i = 0; i < count; i++) {
        const component = chain.getComponentAtIndex(i);
        const matchName = await component.getMatchName();

        if (matchNameCandidates.includes(matchName)) {
            return component;
        }

        if (!fallback && displayNameFallback) {
            try {
                const displayName = await component.getDisplayName();
                if (displayName === displayNameFallback) {
                    fallback = component;
                }
            } catch (e) {}
        }
    }

    return fallback;
};

const getVolumeParam = async (trackItem) => {
    const component = await findAudioComponent(
        trackItem,
        VOLUME_COMPONENT_CANDIDATES,
        "Volume"
    );

    if (!component) {
        throw new Error(
            "Could not find the Volume component on this audio clip. Use get_audio_clip_info to inspect the component chain."
        );
    }

    const param = findParamOnComponent(component, "Level");

    if (!param) {
        throw new Error(
            "Could not find the Level param on the Volume component. Use get_audio_clip_info to inspect the params."
        );
    }

    return param;
};

const getAudioTrackItem = async (options) => {
    const sequence = await _getSequenceFromId(options.sequenceId);

    return getTrack(
        sequence,
        options.audioTrackIndex,
        options.trackItemIndex,
        TRACK_TYPE.AUDIO
    );
};

/* ------------------------------------------------------------------ */
/* Volume / pan                                                        */
/* ------------------------------------------------------------------ */

const setClipVolume = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const trackItem = await getAudioTrackItem(options);

    const param = await getVolumeParam(trackItem);

    const value =
        options.rawValue !== null && options.rawValue !== undefined
            ? options.rawValue
            : dbToAmplitude(options.levelDb);

    const keyframe = param.createKeyframe(value);

    execute(() => {
        const action = param.createSetValueAction(keyframe, true);
        return [action];
    }, project);

    return { success: true, appliedValue: value };
};

const setClipPan = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const trackItem = await getAudioTrackItem(options);

    let component = await findAudioComponent(
        trackItem,
        PAN_COMPONENT_CANDIDATES,
        "Balance"
    );

    //Apply the "Balance" audio filter if not already present
    if (!component) {
        const effect = await app.AudioFilterFactory.createComponentByDisplayName(
            BALANCE_FILTER_DISPLAY_NAME,
            trackItem
        );

        if (!effect) {
            throw new Error(
                "setClipPan : could not create the Balance audio filter for this clip."
            );
        }

        const componentChain = await trackItem.getComponentChain();

        execute(() => {
            const action = componentChain.createAppendComponentAction(effect);
            return [action];
        }, project);

        component = await findAudioComponent(
            trackItem,
            PAN_COMPONENT_CANDIDATES,
            "Balance"
        );
    }

    if (!component) {
        throw new Error(
            "setClipPan : the Balance filter was not found on the clip after applying it. Use get_audio_clip_info to inspect the component chain."
        );
    }

    const param = findParamOnComponent(component, "Balance");

    if (!param) {
        throw new Error(
            "setClipPan : Could not find the Balance param on the Balance component."
        );
    }

    const keyframe = param.createKeyframe(balanceToParam(options.balance));

    execute(() => {
        const action = param.createSetValueAction(keyframe, true);
        return [action];
    }, project);

    return { success: true, appliedValue: balanceToParam(options.balance) };
};

/* ------------------------------------------------------------------ */
/* Fades (volume keyframe composites)                                  */
/* ------------------------------------------------------------------ */

//Shared implementation: two Level keyframes across the fade window.
const _fadeAudio = async (options, fadeIn) => {
    const project = await app.Project.getActiveProject();
    const trackItem = await getAudioTrackItem(options);

    const param = await getVolumeParam(trackItem);

    const start = await trackItem.getStartTime();
    const end = await trackItem.getEndTime();

    const duration = options.durationSeconds;
    const clipLengthSeconds = end.seconds - start.seconds;

    if (duration <= 0 || duration > clipLengthSeconds) {
        throw new Error(
            `fadeAudio : durationSeconds [${duration}] must be > 0 and <= the clip length [${clipLengthSeconds}]`
        );
    }

    //current level = fade target (in) / fade source (out)
    let level;
    try {
        const kf = await param.getStartValue();
        level = sanitizeParamValue(kf.value);
    } catch (e) {
        level = dbToAmplitude(0);
    }

    if (typeof level !== "number") {
        level = dbToAmplitude(0);
    }

    const silence = 0;

    //keyframe times are in sequence time
    let points;
    if (fadeIn) {
        points = [
            { seconds: start.seconds, value: silence },
            { seconds: start.seconds + duration, value: level },
        ];
    } else {
        points = [
            { seconds: end.seconds - duration, value: level },
            { seconds: end.seconds, value: silence },
        ];
    }

    //1. enable time-varying (the "stopwatch")
    execute(() => {
        const action = param.createSetTimeVaryingAction(true);
        return [action];
    }, project);

    //2. both keyframes in one transaction
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

const fadeAudioIn = async (command) => {
    return _fadeAudio(command.options, true);
};

const fadeAudioOut = async (command) => {
    return _fadeAudio(command.options, false);
};

/* ------------------------------------------------------------------ */
/* Audio transitions (feature-detected)                                */
/* ------------------------------------------------------------------ */

const addAudioTransition = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const trackItem = await getAudioTrackItem(options);

    if (typeof app.TransitionFactory.createAudioTransition !== "function") {
        throw new Error(
            "addAudioTransition : TransitionFactory.createAudioTransition is not available in this Premiere version. Use fade_audio_in / fade_audio_out (volume keyframes) instead."
        );
    }

    const transition = await app.TransitionFactory.createAudioTransition(
        options.transitionName
    );

    if (typeof trackItem.createAddAudioTransitionAction !== "function") {
        throw new Error(
            "addAudioTransition : createAddAudioTransitionAction is not available on audio track items in this Premiere version. Use fade_audio_in / fade_audio_out instead."
        );
    }

    const transitionOptions = new app.AddTransitionOptions();
    transitionOptions.setApplyToStart(options.applyToStart === true);

    const time = ticksFromSeconds(options.durationSeconds);
    transitionOptions.setDuration(time);
    transitionOptions.setTransitionAlignment(options.clipAlignment);

    execute(() => {
        const action = trackItem.createAddAudioTransitionAction(
            transition,
            transitionOptions
        );
        return [action];
    }, project);

    return { success: true };
};

/* ------------------------------------------------------------------ */
/* Track lock (feature-detected)                                       */
/* ------------------------------------------------------------------ */

const setAudioTrackLocked = async (command) => {
    const options = command.options;
    const sequence = await _getSequenceFromId(options.sequenceId);

    const track = await sequence.getAudioTrack(options.audioTrackIndex);

    if (!track) {
        throw new Error(
            `setAudioTrackLocked : audio track [${options.audioTrackIndex}] does not exist`
        );
    }

    //Not in the documented 25.x API (only EVENT_TRACK_LOCK_CHANGED exists);
    //feature-detect so this starts working when Adobe ships the setter.
    const setter =
        (typeof track.setLocked === "function" && track.setLocked) ||
        (typeof track.setLock === "function" && track.setLock);

    if (!setter) {
        throw new Error(
            "setAudioTrackLocked : track locking is not exposed by the UXP API in this Premiere version."
        );
    }

    await setter.call(track, options.locked);

    return { success: true };
};

/* ------------------------------------------------------------------ */
/* Read                                                                */
/* ------------------------------------------------------------------ */

const getAudioClipInfo = async (command) => {
    const options = command.options;
    const trackItem = await getAudioTrackItem(options);

    const start = await trackItem.getStartTime();
    const end = await trackItem.getEndTime();
    const name = await trackItem.getName();

    let disabled = null;
    try {
        disabled = await trackItem.isDisabled();
    } catch (e) {}

    const effects = await readComponentChain(trackItem);

    //surface volume/pan values directly for convenience
    let volume = null;
    try {
        const param = await getVolumeParam(trackItem);
        const kfv = await param.getStartValue();
        const amplitude = sanitizeParamValue(kfv.value);

        volume = {
            rawValue: amplitude,
            approxDb:
                typeof amplitude === "number" ? amplitudeToDb(amplitude) : null,
            timeVarying: param.isTimeVarying(),
        };
    } catch (e) {}

    let pan = null;
    try {
        const component = await findAudioComponent(
            trackItem,
            PAN_COMPONENT_CANDIDATES,
            "Balance"
        );
        if (component) {
            const param = findParamOnComponent(component, "Balance");
            if (param) {
                const kf = await param.getStartValue();
                const raw = sanitizeParamValue(kf.value);
                pan = {
                    rawValue: raw,
                    balance:
                        typeof raw === "number" ? paramToBalance(raw) : null,
                };
            }
        }
    } catch (e) {}

    return {
        name,
        startSeconds: start.seconds,
        endSeconds: end.seconds,
        disabled,
        volume,
        pan,
        effects,
    };
};

const commandHandlers = {
    setClipVolume,
    setClipPan,
    fadeAudioIn,
    fadeAudioOut,
    addAudioTransition,
    setAudioTrackLocked,
    getAudioClipInfo,
};

module.exports = {
    commandHandlers,
};
