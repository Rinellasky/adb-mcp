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

/* Phase 2 / Priority 5 : Lumetri color suite
 * One generic handler (setLumetriParams) sets any batch of Lumetri params;
 * the section-specific tools (basic/creative/vignette/LUT) are Python-side
 * wrappers that pass the right param names. Param display names are set with
 * per-param try/catch and reported back so live testing can calibrate them
 * (same capture-first philosophy as the Photoshop neural filter work).
 */

const app = require("premierepro");

const { TRACK_TYPE } = require("./consts.js");

const {
    _getSequenceFromId,
    execute,
    getTrack,
} = require("./utils.js");

const {
    ensureEffect,
    setParamValueOnComponent,
} = require("./effects.js");

const LUMETRI_MATCH_NAME = "AE.ADBE Lumetri";

const getVideoTrackItem = async (options) => {
    const sequence = await _getSequenceFromId(options.sequenceId);

    return getTrack(
        sequence,
        options.videoTrackIndex,
        options.trackItemIndex,
        TRACK_TYPE.VIDEO
    );
};

const listParamNames = (component) => {
    const names = [];
    const pCount = component.getParamCount();
    for (let j = 0; j < pCount; j++) {
        const name = component.getParam(j).displayName;
        if (name) {
            names.push(name);
        }
    }
    return names;
};

//LIVE FINDING (2026-07-08): Lumetri param display names repeat across
//sections ("Saturation" in Basic + Creative, "Input LUT" twice, vignette
//"Amount"), and section headers appear as params. Resolution supports:
//  - paramIndex (exact index from get_lumetri_settings)
//  - occurrence: nth match of the display name (1-based), or -1 = last match
const findLumetriParam = (component, spec) => {
    if (spec.paramIndex !== null && spec.paramIndex !== undefined) {
        const param = component.getParam(spec.paramIndex);
        if (!param) {
            throw new Error(`No param at index [${spec.paramIndex}]`);
        }
        return param;
    }

    const occurrence = spec.occurrence || 1;
    const matches = [];

    const pCount = component.getParamCount();
    for (let j = 0; j < pCount; j++) {
        const param = component.getParam(j);
        if (param.displayName === spec.name) {
            matches.push(param);
        }
    }

    if (matches.length === 0) {
        throw new Error(`Param [${spec.name}] not found on Lumetri`);
    }

    if (occurrence === -1) {
        return matches[matches.length - 1];
    }

    if (occurrence > matches.length) {
        throw new Error(
            `Param [${spec.name}] has only ${matches.length} occurrence(s); requested #${occurrence}`
        );
    }

    return matches[occurrence - 1];
};

//Ensures a single Lumetri instance on the clip and sets the given params.
//Params that fail (wrong name / wrong type) are reported, not fatal.
const setLumetriParams = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const trackItem = await getVideoTrackItem(options);

    const component = await ensureEffect(project, trackItem, LUMETRI_MATCH_NAME);

    const applied = [];
    const failed = [];

    for (const p of options.params || []) {
        try {
            const param = findLumetriParam(component, p);
            const keyframe = param.createKeyframe(p.value);

            execute(() => {
                const action = param.createSetValueAction(keyframe, true);
                return [action];
            }, project);

            applied.push(p.name !== undefined ? p.name : p.paramIndex);
        } catch (e) {
            failed.push({ name: p.name, error: String(e) });
        }
    }

    const result = { success: failed.length === 0, applied, failed };

    //when something missed, return the actual param names to calibrate against
    if (failed.length > 0) {
        result.availableParams = listParamNames(component);
    }

    return result;
};

//Reads back the Lumetri component's params (current values) for iteration
//("make it warmer" workflows need a read-modify-write loop).
const getLumetriSettings = async (command) => {
    const options = command.options;
    const trackItem = await getVideoTrackItem(options);

    const { readComponentChain } = require("./utils.js");
    const chain = await readComponentChain(trackItem);

    const lumetri = chain.find((c) => c.matchName === LUMETRI_MATCH_NAME);

    if (!lumetri) {
        return { present: false, params: [] };
    }

    return { present: true, params: lumetri.params };
};

const commandHandlers = {
    setLumetriParams,
    getLumetriSettings,
};

module.exports = {
    commandHandlers,
};
