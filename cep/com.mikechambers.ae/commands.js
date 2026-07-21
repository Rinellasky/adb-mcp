/* commands.js
 * After Effects command handlers
 */

// Execute After Effects command via ExtendScript
function executeAECommand(script) {
    return new Promise((resolve, reject) => {
        const csInterface = new CSInterface();
        csInterface.evalScript(script, (result) => {
            if (result === 'EvalScript error.') {
                reject(new Error('ExtendScript execution failed'));
            } else {
                try {
                    resolve(JSON.parse(result));
                } catch (e) {
                    resolve(result);
                }
            }
        });
    });
}

// Shared ES3 helpers injected into command scripts.
// NOTE: ES3 only - var, no arrow functions, no template literals.
const AE_HELPERS = `
    function findItemById(id) {
        for (var _i = 1; _i <= app.project.numItems; _i++) {
            if (app.project.item(_i).id === id) { return app.project.item(_i); }
        }
        return null;
    }
    function findFolderById(id) {
        var _item = findItemById(id);
        if (_item !== null && _item instanceof FolderItem) { return _item; }
        return null;
    }
    function findCompById(id) {
        var _item = findItemById(id);
        if (_item !== null && _item instanceof CompItem) { return _item; }
        return null;
    }
    function propValue(group, matchName) {
        var _p = (group !== null) ? group.property(matchName) : null;
        return (_p !== null && _p !== undefined) ? _p.value : null;
    }
    function summarizeItem(item) {
        var typeName = "Unknown";
        if (item instanceof CompItem) { typeName = "Composition"; }
        else if (item instanceof FolderItem) { typeName = "Folder"; }
        else if (item instanceof FootageItem) { typeName = "Footage"; }
        return {
            id: item.id,
            name: item.name,
            type: typeName,
            parentFolderId: (item.parentFolder && item.parentFolder !== app.project.rootFolder)
                ? item.parentFolder.id : null
        };
    }
`;

// Get project information (lightweight - used by main.js for the response envelope)
async function getProjectInfo() {
    const script = `
        (function() {
            var info = {
                numItems: app.project.numItems,
                activeItemIndex: app.project.activeItem ? app.project.activeItem.id : null,
                projectName: app.project.file ? app.project.file.name : "Untitled"
            };
            return JSON.stringify(info);
        })();
    `;
    return await executeAECommand(script);
}

// Get all compositions
async function getCompositions() {
    const script = `
        (function() {
            var comps = [];
            for (var i = 1; i <= app.project.numItems; i++) {
                var item = app.project.item(i);
                if (item instanceof CompItem) {
                    comps.push({
                        id: item.id,
                        name: item.name,
                        width: item.width,
                        height: item.height,
                        duration: item.duration,
                        frameRate: item.frameRate
                    });
                }
            }
            return JSON.stringify(comps);
        })();
    `;
    return await executeAECommand(script);
}

async function executeExtendScript(command) {
    console.log(command)
    const options = command.options
    const scriptString = options.scriptString;

    const script = `
        (function() {
            try {
                var result = (function() {
                    ${scriptString}
                })();

                // If result is undefined, return null
                if (result === undefined) {
                    return 'null';
                }

                // Return stringified result
                return JSON.stringify(result);
            } catch(e) {
                return JSON.stringify({
                    error: e.toString(),
                    line: e.line || 'unknown'
                });
            }
        })();
    `;

    const result = await executeAECommand(script);

    return createPacket(result);
}


async function getLayers() {
    const script = `
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            JSON.stringify({error: "No active composition"});
        } else {
            var layers = [];
            for (var i = 1; i <= comp.numLayers; i++) {
                var layer = comp.layer(i);
                layers.push({
                    index: layer.index,
                    name: layer.name,
                    enabled: layer.enabled,
                    selected: layer.selected,
                    startTime: layer.startTime,
                    inPoint: layer.inPoint,
                    outPoint: layer.outPoint
                });
            }
            JSON.stringify(layers);
        }
    `;

    const result = await executeAECommand(script);
    return createPacket(result);
}

// ---------------------------------------------------------------------
// Priority 1: Project & Import Foundation
// ---------------------------------------------------------------------
// SAFETY RULE: never let AE show a modal dialog from a scripted call
// (save prompts etc.) - a modal hangs evalScript, which hangs the proxy
// call, which can kill the entire Claude Desktop local-tool bridge.
// All dirty-project paths are therefore explicitly guarded.

async function createProject(command) {
    const o = command.options || {};
    const force = o.force === true;
    const script = `
        (function() {
            try {
                if (app.project.dirty === true && ${force} !== true) {
                    return JSON.stringify({error: "Current project has unsaved changes. Save it first, or pass force=true to discard changes."});
                }
                if (app.project.dirty === true) {
                    app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
                } else {
                    app.newProject();
                }
                return JSON.stringify({success: true, message: "New project created."});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function openProject(command) {
    const o = command.options || {};
    const force = o.force === true;
    const script = `
        (function() {
            try {
                var f = new File(${JSON.stringify(o.path)});
                if (!f.exists) {
                    return JSON.stringify({error: "File not found: " + ${JSON.stringify(o.path)}});
                }
                if (app.project.dirty === true && ${force} !== true) {
                    return JSON.stringify({error: "Current project has unsaved changes. Save it first, or pass force=true to discard changes."});
                }
                if (app.project.dirty === true) {
                    app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
                }
                app.open(f);
                return JSON.stringify({
                    success: true,
                    name: app.project.file ? app.project.file.name : null,
                    path: app.project.file ? app.project.file.fsName : null
                });
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function saveProject(command) {
    const script = `
        (function() {
            try {
                if (!app.project.file) {
                    return JSON.stringify({error: "Project has never been saved (no file path). Use save_project_as instead."});
                }
                app.project.save();
                return JSON.stringify({success: true, path: app.project.file.fsName});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function saveProjectAs(command) {
    const o = command.options || {};
    const script = `
        (function() {
            try {
                var f = new File(${JSON.stringify(o.path)});
                app.project.save(f);
                return JSON.stringify({success: true, path: app.project.file.fsName});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

// Rich project inventory - registered as the "getProjectInfo" command,
// superseding the lightweight envelope helper above (which main.js still
// uses directly).
async function getProjectInfoRich(command) {
    const script = `
        (function() {
            ${AE_HELPERS}
            try {
                var items = [];
                for (var i = 1; i <= app.project.numItems; i++) {
                    items.push(summarizeItem(app.project.item(i)));
                }
                return JSON.stringify({
                    success: true,
                    name: app.project.file ? app.project.file.name : "(unsaved project)",
                    path: app.project.file ? app.project.file.fsName : null,
                    dirty: app.project.dirty === true,
                    numItems: app.project.numItems,
                    items: items
                });
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function importFile(command) {
    const o = command.options || {};
    const folderId = (o.folderId === undefined || o.folderId === null) ? "null" : JSON.stringify(o.folderId);
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Import File");
            try {
                var f = new File(${JSON.stringify(o.path)});
                if (!f.exists) {
                    return JSON.stringify({error: "File not found: " + ${JSON.stringify(o.path)}});
                }
                var io = new ImportOptions(f);
                var item = app.project.importFile(io);
                var folderId = ${folderId};
                if (folderId !== null) {
                    var folder = findFolderById(folderId);
                    if (folder === null) {
                        return JSON.stringify({error: "folderId " + folderId + " not found or is not a folder."});
                    }
                    item.parentFolder = folder;
                }
                return JSON.stringify(summarizeItem(item));
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function importImageSequence(command) {
    const o = command.options || {};
    const folderId = (o.folderId === undefined || o.folderId === null) ? "null" : JSON.stringify(o.folderId);
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Import Image Sequence");
            try {
                var f = new File(${JSON.stringify(o.path)});
                if (!f.exists) {
                    return JSON.stringify({error: "File not found: " + ${JSON.stringify(o.path)}});
                }
                var io = new ImportOptions(f);
                io.sequence = true;
                var item = app.project.importFile(io);
                var folderId = ${folderId};
                if (folderId !== null) {
                    var folder = findFolderById(folderId);
                    if (folder === null) {
                        return JSON.stringify({error: "folderId " + folderId + " not found or is not a folder."});
                    }
                    item.parentFolder = folder;
                }
                return JSON.stringify(summarizeItem(item));
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function createProjectFolder(command) {
    const o = command.options || {};
    const parentFolderId = (o.parentFolderId === undefined || o.parentFolderId === null) ? "null" : JSON.stringify(o.parentFolderId);
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Create Project Folder");
            try {
                var folder = app.project.items.addFolder(${JSON.stringify(o.name)});
                var parentFolderId = ${parentFolderId};
                if (parentFolderId !== null) {
                    var parent = findFolderById(parentFolderId);
                    if (parent === null) {
                        return JSON.stringify({error: "parentFolderId " + parentFolderId + " not found or is not a folder."});
                    }
                    folder.parentFolder = parent;
                }
                return JSON.stringify(summarizeItem(folder));
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function moveItemsToFolder(command) {
    const o = command.options || {};
    const folderId = (o.folderId === undefined || o.folderId === null) ? "null" : JSON.stringify(o.folderId);
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Move Items To Folder");
            try {
                var folderId = ${folderId};
                var targetFolder = null;
                if (folderId !== null) {
                    targetFolder = findFolderById(folderId);
                    if (targetFolder === null) {
                        return JSON.stringify({error: "folderId " + folderId + " not found or is not a folder."});
                    }
                }
                var itemIds = ${JSON.stringify(o.itemIds || [])};
                var moved = [];
                var failed = [];
                for (var i = 0; i < itemIds.length; i++) {
                    var item = findItemById(itemIds[i]);
                    if (item === null) { failed.push(itemIds[i]); continue; }
                    item.parentFolder = (targetFolder !== null) ? targetFolder : app.project.rootFolder;
                    moved.push(itemIds[i]);
                }
                return JSON.stringify({success: true, moved: moved, failed: failed});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

// ---------------------------------------------------------------------
// Priority 2: Compositions & Visual Feedback
// ---------------------------------------------------------------------

async function createComposition(command) {
    const o = command.options || {};
    const script = `
        (function() {
            app.beginUndoGroup("MCP: Create Composition");
            try {
                var comp = app.project.items.addComp(
                    ${JSON.stringify(o.name)},
                    ${JSON.stringify(o.width)},
                    ${JSON.stringify(o.height)},
                    ${JSON.stringify(o.pixelAspect)},
                    ${JSON.stringify(o.durationSeconds)},
                    ${JSON.stringify(o.frameRate)}
                );
                comp.openInViewer();
                return JSON.stringify({
                    success: true, id: comp.id, name: comp.name,
                    width: comp.width, height: comp.height,
                    duration: comp.duration, frameRate: comp.frameRate
                });
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

// THE keystone read tool — full layer tree with transforms, parenting,
// switches, and applied effects. Camera/Light layers lack Opacity (and
// 2D layers lack Z rotation), so every property read goes through the
// null-safe propValue helper instead of assuming presence.
async function getCompositionDetails(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layers = [];
                for (var i = 1; i <= comp.numLayers; i++) {
                    var layer = comp.layer(i);
                    var layerType = "AV";
                    if (layer instanceof TextLayer) { layerType = "Text"; }
                    else if (layer instanceof ShapeLayer) { layerType = "Shape"; }
                    else if (layer instanceof CameraLayer) { layerType = "Camera"; }
                    else if (layer instanceof LightLayer) { layerType = "Light"; }
                    else if (layer.nullLayer === true) { layerType = "Null"; }

                    var t = layer.property("ADBE Transform Group");
                    var effects = [];
                    var fx = layer.property("ADBE Effect Parade");
                    if (fx !== null && fx !== undefined) {
                        for (var j = 1; j <= fx.numProperties; j++) {
                            effects.push({
                                index: j,
                                matchName: fx.property(j).matchName,
                                name: fx.property(j).name,
                                enabled: fx.property(j).enabled
                            });
                        }
                    }

                    layers.push({
                        index: layer.index,
                        name: layer.name,
                        type: layerType,
                        sourceId: (layer.source !== null && layer.source !== undefined) ? layer.source.id : null,
                        enabled: layer.enabled,
                        selected: layer.selected,
                        solo: layer.solo === true,
                        shy: layer.shy === true,
                        locked: layer.locked === true,
                        threeD: layer.threeDLayer === true,
                        hasAudio: layer.hasAudio === true,
                        audioEnabled: layer.audioEnabled === true,
                        startTime: layer.startTime,
                        inPoint: layer.inPoint,
                        outPoint: layer.outPoint,
                        parentIndex: (layer.parent !== null && layer.parent !== undefined) ? layer.parent.index : null,
                        anchorPoint: propValue(t, "ADBE Anchor Point"),
                        position: propValue(t, "ADBE Position"),
                        scale: propValue(t, "ADBE Scale"),
                        rotation: propValue(t, "ADBE Rotate Z"),
                        rotationX: propValue(t, "ADBE Rotate X"),
                        rotationY: propValue(t, "ADBE Rotate Y"),
                        opacity: propValue(t, "ADBE Opacity"),
                        effects: effects
                    });
                }
                return JSON.stringify({
                    success: true,
                    id: comp.id, name: comp.name,
                    width: comp.width, height: comp.height,
                    duration: comp.duration, frameRate: comp.frameRate,
                    pixelAspect: comp.pixelAspect,
                    bgColor: comp.bgColor,
                    workAreaStart: comp.workAreaStart,
                    workAreaDuration: comp.workAreaDuration,
                    numLayers: comp.numLayers,
                    layers: layers
                });
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

// CRITICAL — the visual feedback loop. Renders one frame to a temp PNG
// via comp.saveFrameToPng (AE 23+; AE Beta 26.x has it) and returns the
// file path; the Python side reads the file and returns an MCP Image,
// mirroring pr-mcp's get_sequence_frame_image.
async function getFrameImage(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                if (typeof comp.saveFrameToPng !== "function") {
                    return JSON.stringify({error: "saveFrameToPng not available in this AE version (requires AE 23+); render-queue fallback not implemented yet."});
                }
                var time = ${JSON.stringify(o.timeSeconds)};
                var maxTime = comp.duration - comp.frameDuration;
                if (time < 0) { time = 0; }
                if (time > maxTime) { time = maxTime; }
                var f = new File(Folder.temp.fsName + "/ae_mcp_frame_" + comp.id + "_" + (new Date().getTime()) + ".png");
                comp.saveFrameToPng(time, f);
                // AE 26 quirk (live-verified 2026-07-20): saveFrameToPng is
                // ASYNCHRONOUS - it returns before the PNG hits disk (~1s
                // later). Poll instead of failing instantly.
                var waited = 0;
                while ((!f.exists || f.length === 0) && waited < 15000) {
                    $.sleep(100);
                    waited += 100;
                }
                if (!f.exists || f.length === 0) {
                    return JSON.stringify({error: "saveFrameToPng did not write a file within 15s: " + f.fsName});
                }
                return JSON.stringify({
                    success: true,
                    path: f.fsName,
                    time: time,
                    width: comp.width,
                    height: comp.height
                });
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function openComposition(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                comp.openInViewer();
                return JSON.stringify({success: true, id: comp.id, name: comp.name});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

// Only fields provided in options are applied; everything else is left
// untouched. bgColor is [r, g, b] with 0-1 floats.
async function setCompositionSettings(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Set Composition Settings");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var opts = ${JSON.stringify({
                    name: o.name === undefined ? null : o.name,
                    width: o.width === undefined ? null : o.width,
                    height: o.height === undefined ? null : o.height,
                    durationSeconds: o.durationSeconds === undefined ? null : o.durationSeconds,
                    frameRate: o.frameRate === undefined ? null : o.frameRate,
                    bgColor: o.bgColor === undefined ? null : o.bgColor
                })};
                if (opts.name !== null) { comp.name = opts.name; }
                if (opts.width !== null) { comp.width = opts.width; }
                if (opts.height !== null) { comp.height = opts.height; }
                if (opts.durationSeconds !== null) { comp.duration = opts.durationSeconds; }
                if (opts.frameRate !== null) { comp.frameRate = opts.frameRate; }
                if (opts.bgColor !== null) { comp.bgColor = opts.bgColor; }
                return JSON.stringify({
                    success: true,
                    id: comp.id, name: comp.name,
                    width: comp.width, height: comp.height,
                    duration: comp.duration, frameRate: comp.frameRate,
                    bgColor: comp.bgColor
                });
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function setWorkArea(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Set Work Area");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                comp.workAreaStart = ${JSON.stringify(o.startSeconds)};
                comp.workAreaDuration = ${JSON.stringify(o.durationSeconds)};
                return JSON.stringify({
                    success: true,
                    workAreaStart: comp.workAreaStart,
                    workAreaDuration: comp.workAreaDuration
                });
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function addCompositionMarker(command) {
    const o = command.options || {};
    const durationSeconds = (o.durationSeconds === undefined || o.durationSeconds === null) ? "null" : JSON.stringify(o.durationSeconds);
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Add Composition Marker");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var mv = new MarkerValue(${JSON.stringify(o.comment)});
                var dur = ${durationSeconds};
                if (dur !== null) { mv.duration = dur; }
                comp.markerProperty.setValueAtTime(${JSON.stringify(o.timeSeconds)}, mv);
                return JSON.stringify({
                    success: true,
                    time: ${JSON.stringify(o.timeSeconds)},
                    comment: ${JSON.stringify(o.comment)},
                    numMarkers: comp.markerProperty.numKeys
                });
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

const createPacket = (result) => {
    return {
        content: [{
            type: "text",
            text: JSON.stringify(result, null, 2)
        }]
    };
}

const parseAndRouteCommand = async (command) => {
    let action = command.action;

    let f = commandHandlers[action];

    if (typeof f !== "function") {
        throw new Error(`Unknown Command: ${action}`);
    }

    console.log(f.name)
    return await f(command);
};

const commandHandlers = {
    getLayers,
    executeExtendScript,
    createProject,
    openProject,
    saveProject,
    saveProjectAs,
    getProjectInfo: getProjectInfoRich,
    importFile,
    importImageSequence,
    createProjectFolder,
    moveItemsToFolder,
    createComposition,
    getCompositionDetails,
    getFrameImage,
    openComposition,
    setCompositionSettings,
    setWorkArea,
    addCompositionMarker,
    getCompositions: async (command) => createPacket(await getCompositions())
};