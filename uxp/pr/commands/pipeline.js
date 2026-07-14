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

/* Phase 3 / Priorities 8-10 : Multi-sequence, source monitor, MOGRT
 * parameters, encoder & project interchange.
 * Interchange (AAF/FCPXML/OTIO) and MOGRT component APIs are not in the
 * public 25.x reference - they are feature-detected with clean errors.
 */

const app = require("premierepro");
const constants = require("premierepro").Constants;

const {
    _getSequenceFromId,
    _setActiveSequence,
    findProjectItem,
    execute,
    getTrack,
    ticksFromSeconds,
    readComponentChain,
    findParamOnComponent,
} = require("./utils.js");

/* ------------------------------------------------------------------ */
/* P8 : Multi-sequence & source monitor                                */
/* ------------------------------------------------------------------ */

const getSequenceList = async (command) => {
    const project = await app.Project.getActiveProject();
    const active = await project.getActiveSequence();
    const sequences = await project.getSequences();

    const out = [];
    for (const s of sequences) {
        out.push({
            name: s.name,
            id: s.guid.toString(),
            isActive: active ? s.guid.toString() === active.guid.toString() : false,
        });
    }

    return { sequences: out };
};

const createEmptySequence = async (command) => {
    const options = command.options;
    const project = await app.Project.getActiveProject();

    let sequence;
    if (options.presetPath) {
        if (typeof project.createSequenceWithPresetPath === "function") {
            sequence = await project.createSequenceWithPresetPath(
                options.name,
                options.presetPath
            );
        } else {
            sequence = await project.createSequence(
                options.name,
                options.presetPath
            );
        }
    } else {
        sequence = await project.createSequence(options.name);
    }

    if (!sequence) {
        throw new Error(
            `createEmptySequence : Premiere did not return a sequence for [${options.name}]`
        );
    }

    if (options.setActive) {
        try {
            await _setActiveSequence(sequence);
        } catch (e) {}
    }

    return { name: sequence.name, id: sequence.guid.toString() };
};

const duplicateSequence = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);

    const before = await project.getSequences();
    const beforeIds = new Set(before.map((s) => s.guid.toString()));

    execute(() => {
        const action = sequence.createCloneAction();
        return [action];
    }, project);

    const after = await project.getSequences();
    let clone = null;
    for (const s of after) {
        if (!beforeIds.has(s.guid.toString())) {
            clone = s;
            break;
        }
    }

    if (!clone) {
        throw new Error(
            "duplicateSequence : clone action executed but no new sequence was found"
        );
    }

    if (options.newName) {
        try {
            const item = await clone.getProjectItem();
            execute(() => {
                const action = item.createSetNameAction(options.newName);
                return [action];
            }, project);
        } catch (e) {
            //rename is best-effort; the clone still exists
        }
    }

    return { name: clone.name, id: clone.guid.toString() };
};

//No documented nest API in 25.x - feature-detect so this lights up when
//Adobe ships it.
const nestClips = async (command) => {
    const options = command.options;
    const sequence = await _getSequenceFromId(options.sequenceId);
    const editor = app.SequenceEditor.getEditor(sequence);

    const candidates = [
        "createNestSequenceAction",
        "createNestAction",
        "nestSelection",
    ];

    for (const name of candidates) {
        if (typeof editor[name] === "function") {
            return {
                available: true,
                note: `Nest API [${name}] exists in this version - implement against it.`,
            };
        }
    }

    throw new Error(
        "nestClips : no nest API is exposed by UXP in this Premiere version. Workaround: create_subsequence from an in/out range, then overwrite_clip_at_time with the new sequence's project item."
    );
};

const openInSourceMonitor = async (command) => {
    const options = command.options;

    if (options.filePath) {
        const ok = await app.SourceMonitor.openFilePath(options.filePath);
        if (!ok) {
            throw new Error(
                `openInSourceMonitor : could not open [${options.filePath}]`
            );
        }
        return { success: true };
    }

    const project = await app.Project.getActiveProject();
    const item = await findProjectItem(options.itemName, project);
    const ok = await app.SourceMonitor.openProjectItem(item);

    if (!ok) {
        throw new Error(
            `openInSourceMonitor : could not open [${options.itemName}]`
        );
    }

    return { success: true };
};

//Sets a project item's in/out points (source-side three-point editing:
//set in/out, then insert_clip_at_time / overwrite_clip_at_time place only
//the marked range).
const setSourceInOut = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const item = await findProjectItem(options.itemName, project);

    const clipItem = app.ClipProjectItem.cast(item);
    if (!clipItem) {
        throw new Error(
            `setSourceInOut : [${options.itemName}] is not a clip project item`
        );
    }

    if (options.clear) {
        execute(() => {
            const action = clipItem.createClearInOutPointsAction();
            return [action];
        }, project);
        return { success: true, cleared: true };
    }

    const inTick = await app.TickTime.createWithSeconds(options.inPointSeconds);
    const outTick = await app.TickTime.createWithSeconds(options.outPointSeconds);
    execute(() => {
        const action = clipItem.createSetInOutPointsAction(inTick, outTick);
        return [action];
    }, project);

    return { success: true };
};

/* ------------------------------------------------------------------ */
/* P9 : MOGRT parameters                                               */
/* ------------------------------------------------------------------ */

const getInstalledMogrtPath = async (command) => {
    if (typeof app.SequenceEditor.getInstalledMogrtPath !== "function") {
        throw new Error(
            "getInstalledMogrtPath is not available in this Premiere version."
        );
    }
    const path = await app.SequenceEditor.getInstalledMogrtPath();
    return { path };
};

//Reads the parameters of a MOGRT clip. Prefers the dedicated MGT component
//API when present; otherwise returns the full component chain (MOGRT params
//appear as components like "Graphic" with Source Text etc.).
const getMogrtParameters = async (command) => {
    const options = command.options;
    const sequence = await _getSequenceFromId(options.sequenceId);

    const trackItem = await getTrack(
        sequence,
        options.videoTrackIndex,
        options.trackItemIndex,
        "VIDEO"
    );

    if (typeof trackItem.getMGTComponent === "function") {
        try {
            const component = await trackItem.getMGTComponent();
            if (component) {
                const params = [];
                const pCount = component.getParamCount();
                for (let j = 0; j < pCount; j++) {
                    const param = component.getParam(j);
                    let value = null;
                    try {
                        const kf = await param.getStartValue();
                        value = kf.value;
                    } catch (e) {}
                    params.push({ index: j, name: param.displayName, value });
                }
                return { source: "mgtComponent", params };
            }
        } catch (e) {
            //fall through to chain read
        }
    }

    const chain = await readComponentChain(trackItem);
    return { source: "componentChain", effects: chain };
};

const setMogrtParameter = async (command) => {
    const options = command.options;

    const project = await app.Project.getActiveProject();
    const sequence = await _getSequenceFromId(options.sequenceId);

    const trackItem = await getTrack(
        sequence,
        options.videoTrackIndex,
        options.trackItemIndex,
        "VIDEO"
    );

    //candidate components: the MGT component if available, else every
    //component in the chain (searching for the param by display name)
    const components = [];

    if (typeof trackItem.getMGTComponent === "function") {
        try {
            const c = await trackItem.getMGTComponent();
            if (c) {
                components.push(c);
            }
        } catch (e) {}
    }

    if (components.length === 0) {
        const chain = await trackItem.getComponentChain();
        const count = chain.getComponentCount();
        for (let i = 0; i < count; i++) {
            components.push(chain.getComponentAtIndex(i));
        }
    }

    for (const component of components) {
        const param = findParamOnComponent(component, options.paramName);
        if (!param) {
            continue;
        }

        const keyframe = param.createKeyframe(options.value);

        execute(() => {
            const action = param.createSetValueAction(keyframe, true);
            return [action];
        }, project);

        return { success: true };
    }

    throw new Error(
        `setMogrtParameter : param [${options.paramName}] not found on this clip. Use get_mogrt_parameters to inspect.`
    );
};

/* ------------------------------------------------------------------ */
/* P10 : Encoder & interchange                                         */
/* ------------------------------------------------------------------ */

const exportWithEncoder = async (command) => {
    const options = command.options;

    const sequence = await _getSequenceFromId(options.sequenceId);
    const manager = await app.EncoderManager.getManager();

    const exportType = constants.ExportType[options.exportType || "IMMEDIATELY"];
    if (exportType === undefined) {
        throw new Error(
            `exportWithEncoder : unknown exportType [${options.exportType}]. Valid: IMMEDIATELY, QUEUE_TO_AME, QUEUE_TO_APP`
        );
    }

    const ok = await manager.exportSequence(
        sequence,
        exportType,
        options.outputFile,
        options.presetFile,
        options.exportFull !== false
    );

    return { success: !!ok };
};

const getExportFileExtension = async (command) => {
    const options = command.options;
    const sequence = await _getSequenceFromId(options.sequenceId);

    if (typeof app.EncoderManager.getExportFileExtension !== "function") {
        throw new Error(
            "getExportFileExtension is not available in this Premiere version."
        );
    }

    const ext = await app.EncoderManager.getExportFileExtension(
        sequence,
        options.presetPath
    );

    return { extension: ext };
};

const batchExportSequences = async (command) => {
    const options = command.options;
    const manager = await app.EncoderManager.getManager();

    const results = [];

    for (const job of options.jobs) {
        try {
            const sequence = await _getSequenceFromId(job.sequenceId);
            const exportType =
                constants.ExportType[options.exportType || "QUEUE_TO_AME"];

            const ok = await manager.exportSequence(
                sequence,
                exportType,
                job.outputFile,
                job.presetFile || options.presetFile,
                true
            );
            results.push({ sequenceId: job.sequenceId, success: !!ok });
        } catch (e) {
            results.push({
                sequenceId: job.sequenceId,
                success: false,
                error: String(e),
            });
        }
    }

    //kick the AME queue if requested and available (26.3+)
    let queueStarted = null;
    if (options.startQueue) {
        if (typeof manager.startBatchEncode === "function") {
            try {
                queueStarted = await manager.startBatchEncode();
            } catch (e) {
                queueStarted = false;
            }
        } else {
            queueStarted = false;
        }
    }

    return { results, queueStarted };
};

//Interchange formats are not in the public 25.x UXP reference. Probe likely
//API names at runtime; error cleanly with what was probed.
const exportProjectInterchange = async (command) => {
    const options = command.options;
    const format = options.format; // "AAF" | "FCPXML" | "OTIO"

    const project = await app.Project.getActiveProject();
    const sequence = options.sequenceId
        ? await _getSequenceFromId(options.sequenceId)
        : await project.getActiveSequence();

    const candidates = {
        AAF: [
            [project, "exportAAF"],
            [app, "AAFExporter"],
            [sequence, "exportAAF"],
        ],
        FCPXML: [
            [project, "exportFCPXML"],
            [project, "exportFinalCutProXML"],
            [sequence, "exportFCPXML"],
        ],
        OTIO: [
            [project, "exportOTIO"],
            [sequence, "exportOTIO"],
        ],
    };

    const list = candidates[format];
    if (!list) {
        throw new Error(
            `exportProjectInterchange : unknown format [${format}]. Valid: AAF, FCPXML, OTIO`
        );
    }

    const probed = [];
    for (const [target, name] of list) {
        probed.push(name);
        if (target && typeof target[name] === "function") {
            const ok = await target[name](options.outputFile);
            return { success: !!ok, api: name };
        }
    }

    throw new Error(
        `exportProjectInterchange : ${format} export is not exposed by UXP in this Premiere version (probed: ${probed.join(", ")}). Use Premiere's File > Export menu for interchange formats.`
    );
};

const commandHandlers = {
    getSequenceList,
    createEmptySequence,
    duplicateSequence,
    nestClips,
    openInSourceMonitor,
    setSourceInOut,
    getInstalledMogrtPath,
    getMogrtParameters,
    setMogrtParameter,
    exportWithEncoder,
    getExportFileExtension,
    batchExportSequences,
    exportProjectInterchange,
};

module.exports = {
    commandHandlers,
};
