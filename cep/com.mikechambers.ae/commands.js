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
    function findLayerByIndex(comp, index) {
        if (index < 1 || index > comp.numLayers) { return null; }
        return comp.layer(index);
    }
    function summarizeLayer(layer) {
        return { index: layer.index, name: layer.name };
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
    function resolvePropertyPath(layer, path) {
        var node = layer;
        for (var _p = 0; _p < path.length; _p++) {
            var seg = path[_p];
            var next = null;
            if (/^[0-9]+$/.test(String(seg))) {
                var idx = parseInt(String(seg), 10);
                if (node.numProperties !== undefined && idx >= 1 && idx <= node.numProperties) {
                    next = node.property(idx);
                }
            } else {
                try { next = node.property(seg); } catch (eSeg) { next = null; }
            }
            if (next === null || next === undefined) {
                return { error: "Property path failed at segment " + (_p + 1) + " ('" + seg + "')" +
                    ((node.matchName !== undefined) ? " under '" + node.matchName + "'" : "") };
            }
            node = next;
        }
        if (node.setValueAtTime === undefined && node.numKeys === undefined) {
            return { error: "Path resolved to a property GROUP ('" + node.matchName + "'), not a keyframeable property. Add the leaf property matchName." };
        }
        return { prop: node };
    }
    function easeCountFor(prop) {
        var vt = prop.propertyValueType;
        if (vt === PropertyValueType.TwoD_SPATIAL || vt === PropertyValueType.ThreeD_SPATIAL) { return 1; }
        if (vt === PropertyValueType.TwoD) { return 2; }
        if (vt === PropertyValueType.ThreeD) { return 3; }
        return 1;
    }
    function buildEaseArray(prop, speed, influence) {
        var n = easeCountFor(prop);
        var arr = [];
        for (var _e = 0; _e < n; _e++) { arr.push(new KeyframeEase(speed, influence)); }
        return arr;
    }
    function interpTypeFromString(s) {
        if (s === "LINEAR") { return KeyframeInterpolationType.LINEAR; }
        if (s === "BEZIER") { return KeyframeInterpolationType.BEZIER; }
        if (s === "HOLD") { return KeyframeInterpolationType.HOLD; }
        return null;
    }
    function interpTypeToString(t) {
        if (t === KeyframeInterpolationType.LINEAR) { return "LINEAR"; }
        if (t === KeyframeInterpolationType.BEZIER) { return "BEZIER"; }
        if (t === KeyframeInterpolationType.HOLD) { return "HOLD"; }
        return String(t);
    }
    function valueTypeToString(vt) {
        if (vt === PropertyValueType.NO_VALUE) { return "NO_VALUE"; }
        if (vt === PropertyValueType.ThreeD_SPATIAL) { return "ThreeD_SPATIAL"; }
        if (vt === PropertyValueType.ThreeD) { return "ThreeD"; }
        if (vt === PropertyValueType.TwoD_SPATIAL) { return "TwoD_SPATIAL"; }
        if (vt === PropertyValueType.TwoD) { return "TwoD"; }
        if (vt === PropertyValueType.OneD) { return "OneD"; }
        if (vt === PropertyValueType.COLOR) { return "COLOR"; }
        if (vt === PropertyValueType.CUSTOM_VALUE) { return "CUSTOM_VALUE"; }
        if (vt === PropertyValueType.MARKER) { return "MARKER"; }
        if (vt === PropertyValueType.LAYER_INDEX) { return "LAYER_INDEX"; }
        if (vt === PropertyValueType.MASK_INDEX) { return "MASK_INDEX"; }
        if (vt === PropertyValueType.SHAPE) { return "SHAPE"; }
        if (vt === PropertyValueType.TEXT_DOCUMENT) { return "TEXT_DOCUMENT"; }
        return String(vt);
    }
`;

// Shared JS-side prologue: comp + layer + property resolution.
// Emits ES3 that leaves `comp`, `layer`, and `prop` in scope or returns
// an error JSON early.
function resolvePrologue(o) {
    return `
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layer = findLayerByIndex(comp, ${JSON.stringify(o.layerIndex)});
                if (layer === null) {
                    return JSON.stringify({error: "Layer not found: index " + ${JSON.stringify(o.layerIndex)} + " (comp has " + comp.numLayers + " layers)"});
                }
                var resolved = resolvePropertyPath(layer, ${JSON.stringify(o.propertyPath || [])});
                if (resolved.error !== undefined) {
                    return JSON.stringify({error: resolved.error});
                }
                var prop = resolved.prop;
    `;
}

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

// ---------------------------------------------------------------------
// Priority 3: The Layer System
// ---------------------------------------------------------------------
// - Layers are addressed by (compId, layerIndex). AE layer indices are
//   1-based and SHIFT when layers are added/removed/reordered — every
//   mutation returns enough state to re-anchor, and agents should re-read
//   getCompositionDetails after structural changes.
// - set_layer_transform refuses to setValue on a property that has
//   keyframes (AE throws anyway; we return a clear error pointing to the
//   Phase 2 keyframe tools instead of a raw ExtendScript exception).
// - New layers land at index 1 (top of stack) per AE behavior.

async function addSolidLayer(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Add Solid Layer");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var w = ${JSON.stringify(o.width)} !== null ? ${JSON.stringify(o.width)} : comp.width;
                var h = ${JSON.stringify(o.height)} !== null ? ${JSON.stringify(o.height)} : comp.height;
                var dur = ${JSON.stringify(o.durationSeconds)} !== null ? ${JSON.stringify(o.durationSeconds)} : comp.duration;
                var layer = comp.layers.addSolid(
                    ${JSON.stringify(o.color)},
                    ${JSON.stringify(o.name)},
                    w, h, comp.pixelAspect, dur
                );
                return JSON.stringify({success: true, index: layer.index, name: layer.name, sourceId: layer.source.id});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function addTextLayer(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Add Text Layer");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layer = comp.layers.addText(${JSON.stringify(o.text)});
                return JSON.stringify({success: true, index: layer.index, name: layer.name});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function addNullLayer(command) {
    const o = command.options || {};
    const durationSeconds = (o.durationSeconds === undefined || o.durationSeconds === null) ? "null" : JSON.stringify(o.durationSeconds);
    const name = (o.name === undefined || o.name === null) ? "null" : JSON.stringify(o.name);
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Add Null Layer");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var dur = ${durationSeconds};
                var layer = (dur !== null) ? comp.layers.addNull(dur) : comp.layers.addNull();
                var nm = ${name};
                if (nm !== null) { layer.name = nm; }
                return JSON.stringify({success: true, index: layer.index, name: layer.name});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function addAdjustmentLayer(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Add Adjustment Layer");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layer = comp.layers.addSolid([1, 1, 1], ${JSON.stringify(o.name)},
                    comp.width, comp.height, comp.pixelAspect, comp.duration);
                layer.adjustmentLayer = true;
                return JSON.stringify({success: true, index: layer.index, name: layer.name});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function addShapeLayer(command) {
    const o = command.options || {};
    const name = (o.name === undefined || o.name === null) ? "null" : JSON.stringify(o.name);
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Add Shape Layer");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layer = comp.layers.addShape();
                var nm = ${name};
                if (nm !== null) { layer.name = nm; }
                return JSON.stringify({success: true, index: layer.index, name: layer.name});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function addFootageLayer(command) {
    const o = command.options || {};
    const durationSeconds = (o.durationSeconds === undefined || o.durationSeconds === null) ? "null" : JSON.stringify(o.durationSeconds);
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Add Footage Layer");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var item = findItemById(${JSON.stringify(o.itemId)});
                if (item === null || item instanceof FolderItem) {
                    return JSON.stringify({error: "Footage/comp item not found: id " + ${JSON.stringify(o.itemId)}});
                }
                var dur = ${durationSeconds};
                var layer = (dur !== null) ? comp.layers.add(item, dur) : comp.layers.add(item);
                return JSON.stringify({success: true, index: layer.index, name: layer.name, sourceId: item.id});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function addCameraLayer(command) {
    const o = command.options || {};
    const centerPoint = (o.centerPoint === undefined || o.centerPoint === null) ? "null" : JSON.stringify(o.centerPoint);
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Add Camera Layer");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var cp = ${centerPoint};
                if (cp === null) { cp = [comp.width / 2, comp.height / 2]; }
                var layer = comp.layers.addCamera(${JSON.stringify(o.name)}, cp);
                return JSON.stringify({success: true, index: layer.index, name: layer.name});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function addLightLayer(command) {
    const o = command.options || {};
    const centerPoint = (o.centerPoint === undefined || o.centerPoint === null) ? "null" : JSON.stringify(o.centerPoint);
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Add Light Layer");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var cp = ${centerPoint};
                if (cp === null) { cp = [comp.width / 2, comp.height / 2]; }
                var layer = comp.layers.addLight(${JSON.stringify(o.name)}, cp);
                return JSON.stringify({success: true, index: layer.index, name: layer.name, lightType: String(layer.lightType)});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

// Partial update: only provided switches are touched.
async function setLayerProperties(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Set Layer Properties");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layer = findLayerByIndex(comp, ${JSON.stringify(o.layerIndex)});
                if (layer === null) {
                    return JSON.stringify({error: "Layer not found: index " + ${JSON.stringify(o.layerIndex)} + " (comp has " + comp.numLayers + " layers)"});
                }
                var opts = ${JSON.stringify({
                    name: o.name === undefined ? null : o.name,
                    enabled: o.enabled === undefined ? null : o.enabled,
                    solo: o.solo === undefined ? null : o.solo,
                    locked: o.locked === undefined ? null : o.locked,
                    shy: o.shy === undefined ? null : o.shy
                })};
                // AE 26.x: solo cannot coexist with a disabled layer - a
                // combined solo=true + enabled=false either throws ("Solo
                // flag can not be set on a layer if the layer is not
                // enabled") or is silently cleared. Refuse it explicitly.
                if (opts.solo === true && (opts.enabled === false ||
                        (opts.enabled === null && layer.enabled !== true))) {
                    return JSON.stringify({error: "solo=true requires an enabled layer (AE constraint) - pass enabled=true or enable the layer first."});
                }
                if (opts.name !== null) { layer.name = opts.name; }
                if (opts.enabled === true) { layer.enabled = true; }
                if (opts.solo !== null) { layer.solo = opts.solo; }
                if (opts.shy !== null) { layer.shy = opts.shy; }
                if (opts.enabled === false) { layer.enabled = false; }
                if (opts.locked !== null) { layer.locked = opts.locked; }
                return JSON.stringify({
                    success: true, index: layer.index, name: layer.name,
                    enabled: layer.enabled, solo: layer.solo === true,
                    locked: layer.locked === true, shy: layer.shy === true
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

// NOTE: locked layers throw on remove(); unlock first via
// set_layer_properties. The error message says so.
async function deleteLayer(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Delete Layer");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layer = findLayerByIndex(comp, ${JSON.stringify(o.layerIndex)});
                if (layer === null) {
                    return JSON.stringify({error: "Layer not found: index " + ${JSON.stringify(o.layerIndex)} + " (comp has " + comp.numLayers + " layers)"});
                }
                if (layer.locked === true) {
                    return JSON.stringify({error: "Layer '" + layer.name + "' is locked. Unlock it first with set_layer_properties."});
                }
                var deletedName = layer.name;
                layer.remove();
                return JSON.stringify({success: true, deletedName: deletedName, numLayers: comp.numLayers});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function duplicateLayer(command) {
    const o = command.options || {};
    const name = (o.name === undefined || o.name === null) ? "null" : JSON.stringify(o.name);
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Duplicate Layer");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layer = findLayerByIndex(comp, ${JSON.stringify(o.layerIndex)});
                if (layer === null) {
                    return JSON.stringify({error: "Layer not found: index " + ${JSON.stringify(o.layerIndex)} + " (comp has " + comp.numLayers + " layers)"});
                }
                var dup = layer.duplicate();
                var nm = ${name};
                if (nm !== null) { dup.name = nm; }
                return JSON.stringify({success: true, index: dup.index, name: dup.name, sourceLayerIndex: layer.index});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

// position: "before" | "after" (relative to targetIndex), or
// "top" | "bottom" (targetIndex ignored).
async function reorderLayer(command) {
    const o = command.options || {};
    const targetIndex = (o.targetIndex === undefined || o.targetIndex === null) ? "null" : JSON.stringify(o.targetIndex);
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Reorder Layer");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layer = findLayerByIndex(comp, ${JSON.stringify(o.layerIndex)});
                if (layer === null) {
                    return JSON.stringify({error: "Layer not found: index " + ${JSON.stringify(o.layerIndex)} + " (comp has " + comp.numLayers + " layers)"});
                }
                var position = ${JSON.stringify(o.position)};
                var targetIndex = ${targetIndex};
                if (position === "top") {
                    layer.moveToBeginning();
                } else if (position === "bottom") {
                    layer.moveToEnd();
                } else {
                    if (targetIndex === null) {
                        return JSON.stringify({error: "targetIndex is required for position '" + position + "'"});
                    }
                    var target = findLayerByIndex(comp, targetIndex);
                    if (target === null) {
                        return JSON.stringify({error: "Target layer not found: index " + targetIndex});
                    }
                    if (position === "before") { layer.moveBefore(target); }
                    else if (position === "after") { layer.moveAfter(target); }
                    else {
                        return JSON.stringify({error: "position must be 'before', 'after', 'top', or 'bottom' - got '" + position + "'"});
                    }
                }
                return JSON.stringify({success: true, index: layer.index, name: layer.name});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

// Partial update of inPoint / outPoint / startTime (seconds).
async function setLayerTimes(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Set Layer Times");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layer = findLayerByIndex(comp, ${JSON.stringify(o.layerIndex)});
                if (layer === null) {
                    return JSON.stringify({error: "Layer not found: index " + ${JSON.stringify(o.layerIndex)} + " (comp has " + comp.numLayers + " layers)"});
                }
                var opts = ${JSON.stringify({
                    startTime: o.startTime === undefined ? null : o.startTime,
                    inPoint: o.inPoint === undefined ? null : o.inPoint,
                    outPoint: o.outPoint === undefined ? null : o.outPoint
                })};
                if (opts.startTime !== null) { layer.startTime = opts.startTime; }
                if (opts.inPoint !== null) { layer.inPoint = opts.inPoint; }
                if (opts.outPoint !== null) { layer.outPoint = opts.outPoint; }
                return JSON.stringify({
                    success: true, index: layer.index,
                    startTime: layer.startTime, inPoint: layer.inPoint, outPoint: layer.outPoint
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

// Partial transform update. Refuses properties that carry keyframes
// (setValue would throw); those belong to the Phase 2 keyframe tools.
async function setLayerTransform(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Set Layer Transform");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layer = findLayerByIndex(comp, ${JSON.stringify(o.layerIndex)});
                if (layer === null) {
                    return JSON.stringify({error: "Layer not found: index " + ${JSON.stringify(o.layerIndex)} + " (comp has " + comp.numLayers + " layers)"});
                }
                var t = layer.property("ADBE Transform Group");
                var opts = ${JSON.stringify({
                    anchorPoint: o.anchorPoint === undefined ? null : o.anchorPoint,
                    position: o.position === undefined ? null : o.position,
                    scale: o.scale === undefined ? null : o.scale,
                    rotation: o.rotation === undefined ? null : o.rotation,
                    rotationX: o.rotationX === undefined ? null : o.rotationX,
                    rotationY: o.rotationY === undefined ? null : o.rotationY,
                    opacity: o.opacity === undefined ? null : o.opacity
                })};
                var map = [
                    ["anchorPoint", "ADBE Anchor Point"],
                    ["position", "ADBE Position"],
                    ["scale", "ADBE Scale"],
                    ["rotation", "ADBE Rotate Z"],
                    ["rotationX", "ADBE Rotate X"],
                    ["rotationY", "ADBE Rotate Y"],
                    ["opacity", "ADBE Opacity"]
                ];
                var applied = [];
                var errors = [];
                for (var i = 0; i < map.length; i++) {
                    var key = map[i][0];
                    var matchName = map[i][1];
                    if (opts[key] === null) { continue; }
                    var prop = t.property(matchName);
                    if (prop === null || prop === undefined) {
                        errors.push(key + ": property not available on this layer type");
                        continue;
                    }
                    if (prop.numKeys > 0) {
                        errors.push(key + ": property has " + prop.numKeys + " keyframes - use the keyframe tools instead of setValue");
                        continue;
                    }
                    prop.setValue(opts[key]);
                    applied.push(key);
                }
                if (errors.length > 0 && applied.length === 0) {
                    return JSON.stringify({error: errors.join("; ")});
                }
                return JSON.stringify({
                    success: true, index: layer.index,
                    applied: applied, skipped: errors,
                    anchorPoint: propValue(t, "ADBE Anchor Point"),
                    position: propValue(t, "ADBE Position"),
                    scale: propValue(t, "ADBE Scale"),
                    rotation: propValue(t, "ADBE Rotate Z"),
                    opacity: propValue(t, "ADBE Opacity")
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

// parentIndex: layer index to parent to, or null to unparent.
async function setLayerParent(command) {
    const o = command.options || {};
    const parentIndex = (o.parentIndex === undefined || o.parentIndex === null) ? "null" : JSON.stringify(o.parentIndex);
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Set Layer Parent");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layer = findLayerByIndex(comp, ${JSON.stringify(o.layerIndex)});
                if (layer === null) {
                    return JSON.stringify({error: "Layer not found: index " + ${JSON.stringify(o.layerIndex)} + " (comp has " + comp.numLayers + " layers)"});
                }
                var parentIndex = ${parentIndex};
                if (parentIndex === null) {
                    layer.parent = null;
                    return JSON.stringify({success: true, index: layer.index, parentIndex: null});
                }
                if (parentIndex === layer.index) {
                    return JSON.stringify({error: "A layer cannot be parented to itself."});
                }
                var parent = findLayerByIndex(comp, parentIndex);
                if (parent === null) {
                    return JSON.stringify({error: "Parent layer not found: index " + parentIndex});
                }
                layer.parent = parent;
                return JSON.stringify({success: true, index: layer.index, parentIndex: layer.parent.index});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

// Precomposes the given layer indices into a new comp. moveAllAttributes
// must be true when precomposing multiple layers (AE API constraint).
async function precomposeLayers(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Precompose Layers");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var indices = ${JSON.stringify(o.layerIndices || [])};
                if (indices.length === 0) {
                    return JSON.stringify({error: "layerIndices must contain at least one layer index."});
                }
                for (var i = 0; i < indices.length; i++) {
                    if (findLayerByIndex(comp, indices[i]) === null) {
                        return JSON.stringify({error: "Layer not found: index " + indices[i] + " (comp has " + comp.numLayers + " layers)"});
                    }
                }
                var moveAll = ${JSON.stringify(o.moveAllAttributes === undefined ? true : o.moveAllAttributes)};
                if (indices.length > 1 && moveAll !== true) {
                    return JSON.stringify({error: "moveAllAttributes must be true when precomposing multiple layers (AE API constraint)."});
                }
                var newComp = comp.layers.precompose(indices, ${JSON.stringify(o.name)}, moveAll);
                var precompLayerIndex = null;
                for (var j = 1; j <= comp.numLayers; j++) {
                    if (comp.layer(j).source !== null && comp.layer(j).source !== undefined && comp.layer(j).source.id === newComp.id) {
                        precompLayerIndex = j;
                        break;
                    }
                }
                return JSON.stringify({
                    success: true,
                    newCompId: newComp.id,
                    newCompName: newComp.name,
                    precompLayerIndex: precompLayerIndex,
                    numLayersInNewComp: newComp.numLayers
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

// -------------------------------------------------------------------
// Priority 4: Keyframe Engine
// - Property addressing: propertyPath is an array of matchName strings
//   walked from the layer, e.g. ["ADBE Transform Group", "ADBE Position"].
//   A segment that is all digits is a 1-based numeric property index
//   (for duplicate effects: ["ADBE Effect Parade", "2", "..."]).
// - Key indices are AE's native 1-based key indices.
// - Temporal ease array length must match the property's dimensionality
//   (1 for 1D and spatial props, N for non-spatial multi-D) —
//   buildEaseArray fans one speed/influence pair out.

async function addKeyframe(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Add Keyframe");
            try {
                ${resolvePrologue(o)}
                prop.setValueAtTime(${JSON.stringify(o.timeSeconds)}, ${JSON.stringify(o.value)});
                var k = prop.nearestKeyIndex(${JSON.stringify(o.timeSeconds)});
                return JSON.stringify({
                    success: true,
                    keyIndex: k,
                    time: prop.keyTime(k),
                    numKeys: prop.numKeys
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

// Batch — one undo group for N keys. times and values must be equal length.
async function addKeyframes(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Add Keyframes");
            try {
                ${resolvePrologue(o)}
                var times = ${JSON.stringify(o.times || [])};
                var values = ${JSON.stringify(o.values || [])};
                if (times.length === 0 || times.length !== values.length) {
                    return JSON.stringify({error: "times and values must be non-empty arrays of equal length (got " + times.length + " / " + values.length + ")"});
                }
                prop.setValuesAtTimes(times, values);
                return JSON.stringify({
                    success: true,
                    keysSet: times.length,
                    numKeys: prop.numKeys
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

// keyIndices omitted/empty = remove ALL keys. Iterates descending.
async function removeKeyframes(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Remove Keyframes");
            try {
                ${resolvePrologue(o)}
                var indices = ${JSON.stringify(o.keyIndices || [])};
                var removed = 0;
                if (indices.length === 0) {
                    for (var i = prop.numKeys; i >= 1; i--) {
                        prop.removeKey(i);
                        removed++;
                    }
                } else {
                    indices.sort(function(a, b) { return b - a; });
                    for (var j = 0; j < indices.length; j++) {
                        if (indices[j] < 1 || indices[j] > prop.numKeys) {
                            return JSON.stringify({error: "Key index out of range: " + indices[j] + " (property has " + prop.numKeys + " keys); removed " + removed + " before failing"});
                        }
                        prop.removeKey(indices[j]);
                        removed++;
                    }
                }
                return JSON.stringify({success: true, removed: removed, numKeys: prop.numKeys});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function getKeyframes(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            try {
                ${resolvePrologue(o)}
                var keys = [];
                for (var i = 1; i <= prop.numKeys; i++) {
                    var easeIn = [];
                    var easeOut = [];
                    try {
                        var tin = prop.keyInTemporalEase(i);
                        var tout = prop.keyOutTemporalEase(i);
                        for (var a = 0; a < tin.length; a++) { easeIn.push({speed: tin[a].speed, influence: tin[a].influence}); }
                        for (var b = 0; b < tout.length; b++) { easeOut.push({speed: tout[b].speed, influence: tout[b].influence}); }
                    } catch (eEase) { /* non-temporal-easable property */ }
                    keys.push({
                        keyIndex: i,
                        time: prop.keyTime(i),
                        value: prop.keyValue(i),
                        inInterpolation: interpTypeToString(prop.keyInInterpolationType(i)),
                        outInterpolation: interpTypeToString(prop.keyOutInterpolationType(i)),
                        easeIn: easeIn,
                        easeOut: easeOut
                    });
                }
                return JSON.stringify({
                    success: true,
                    matchName: prop.matchName,
                    name: prop.name,
                    numKeys: prop.numKeys,
                    hasExpression: (prop.expression !== undefined && prop.expression !== null && prop.expression !== ""),
                    keys: keys
                });
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function getPropertyValue(command) {
    const o = command.options || {};
    const timeSeconds = (o.timeSeconds === undefined || o.timeSeconds === null) ? "null" : JSON.stringify(o.timeSeconds);
    const script = `
        (function() {
            ${AE_HELPERS}
            try {
                ${resolvePrologue(o)}
                var t = ${timeSeconds};
                var value = (t !== null)
                    ? prop.valueAtTime(t, ${JSON.stringify(o.preExpression === true)})
                    : prop.value;
                return JSON.stringify({
                    success: true,
                    matchName: prop.matchName,
                    name: prop.name,
                    time: t,
                    value: value,
                    numKeys: prop.numKeys,
                    hasExpression: (prop.expression !== undefined && prop.expression !== null && prop.expression !== "")
                });
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

// keyIndices omitted/empty = apply to ALL keys.
// inType/outType: "LINEAR" | "BEZIER" | "HOLD". outType omitted = inType.
async function setKeyframeInterpolation(command) {
    const o = command.options || {};
    const outType = (o.outType === undefined || o.outType === null) ? "null" : JSON.stringify(o.outType);
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Set Keyframe Interpolation");
            try {
                ${resolvePrologue(o)}
                var inT = interpTypeFromString(${JSON.stringify(o.inType)});
                if (inT === null) {
                    return JSON.stringify({error: "inType must be LINEAR, BEZIER, or HOLD - got '" + ${JSON.stringify(o.inType)} + "'"});
                }
                var outStr = ${outType};
                var outT = (outStr !== null) ? interpTypeFromString(outStr) : inT;
                if (outT === null) {
                    return JSON.stringify({error: "outType must be LINEAR, BEZIER, or HOLD - got '" + outStr + "'"});
                }
                var indices = ${JSON.stringify(o.keyIndices || [])};
                if (indices.length === 0) {
                    for (var i = 1; i <= prop.numKeys; i++) { indices.push(i); }
                }
                for (var j = 0; j < indices.length; j++) {
                    if (indices[j] < 1 || indices[j] > prop.numKeys) {
                        return JSON.stringify({error: "Key index out of range: " + indices[j] + " (property has " + prop.numKeys + " keys)"});
                    }
                    prop.setInterpolationTypeAtKey(indices[j], inT, outT);
                }
                return JSON.stringify({success: true, applied: indices.length, numKeys: prop.numKeys});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

// easy_ease shorthand: speed 0 / influence 33.3333 both sides (and
// forces BEZIER interpolation, matching F9 behavior).
// keyIndices omitted/empty = apply to ALL keys.
async function setKeyframeEase(command) {
    const o = command.options || {};
    const easyEase = o.easyEase === true;
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Set Keyframe Ease");
            try {
                ${resolvePrologue(o)}
                var easy = ${JSON.stringify(easyEase)};
                var inSpeed = easy ? 0 : ${JSON.stringify(o.inSpeed === undefined ? 0 : o.inSpeed)};
                var inInfluence = easy ? 33.3333 : ${JSON.stringify(o.inInfluence === undefined ? 33.3333 : o.inInfluence)};
                var outSpeed = easy ? 0 : ${JSON.stringify(o.outSpeed === undefined ? 0 : o.outSpeed)};
                var outInfluence = easy ? 33.3333 : ${JSON.stringify(o.outInfluence === undefined ? 33.3333 : o.outInfluence)};
                if (inInfluence < 0.1 || inInfluence > 100 || outInfluence < 0.1 || outInfluence > 100) {
                    return JSON.stringify({error: "influence must be between 0.1 and 100"});
                }
                var indices = ${JSON.stringify(o.keyIndices || [])};
                if (indices.length === 0) {
                    for (var i = 1; i <= prop.numKeys; i++) { indices.push(i); }
                }
                for (var j = 0; j < indices.length; j++) {
                    var k = indices[j];
                    if (k < 1 || k > prop.numKeys) {
                        return JSON.stringify({error: "Key index out of range: " + k + " (property has " + prop.numKeys + " keys)"});
                    }
                    prop.setTemporalEaseAtKey(k,
                        buildEaseArray(prop, inSpeed, inInfluence),
                        buildEaseArray(prop, outSpeed, outInfluence));
                    prop.setInterpolationTypeAtKey(k,
                        KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);
                }
                return JSON.stringify({success: true, applied: indices.length, numKeys: prop.numKeys});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

// -------------------------------------------------------------------
// Priority 5: Expressions Engine
// - Validation-with-revert: AE can reject an expression two ways —
//   throwing on assignment, or accepting the assignment but disabling it
//   with prop.expressionError set. setExpression handles BOTH: on either
//   failure the previous expression is restored and AE's own error
//   message is returned. The property is never left with a broken
//   expression.
// - canSetExpression is checked before assignment for a clean error on
//   non-expressible properties.

async function setExpression(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Set Expression");
            try {
                ${resolvePrologue(o)}
                if (prop.canSetExpression !== true) {
                    return JSON.stringify({error: "Property '" + prop.name + "' (" + prop.matchName + ") cannot hold an expression."});
                }
                var prev = prop.expression;
                try {
                    prop.expression = ${JSON.stringify(o.expression)};
                } catch (eSet) {
                    try { prop.expression = prev; } catch (eRevert) {}
                    return JSON.stringify({error: "Expression rejected on assignment: " + eSet.toString()});
                }
                var exprError = "";
                try { exprError = prop.expressionError; } catch (eRead) {}
                if (prop.expressionEnabled !== true || (exprError !== "" && exprError !== null && exprError !== undefined)) {
                    var msg = (exprError !== "" && exprError !== null && exprError !== undefined)
                        ? exprError : "expression was disabled by After Effects";
                    try { prop.expression = prev; } catch (eRevert2) {}
                    return JSON.stringify({error: "Expression rejected: " + msg});
                }
                return JSON.stringify({
                    success: true,
                    matchName: prop.matchName,
                    name: prop.name,
                    expressionEnabled: prop.expressionEnabled === true
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

async function getExpression(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            try {
                ${resolvePrologue(o)}
                var expr = "";
                var exprError = "";
                try { expr = prop.expression; } catch (eE) {}
                try { exprError = prop.expressionError; } catch (eEE) {}
                return JSON.stringify({
                    success: true,
                    matchName: prop.matchName,
                    name: prop.name,
                    canSetExpression: prop.canSetExpression === true,
                    hasExpression: (expr !== "" && expr !== null && expr !== undefined),
                    expression: expr,
                    expressionEnabled: prop.expressionEnabled === true,
                    expressionError: exprError
                });
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function removeExpression(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Remove Expression");
            try {
                ${resolvePrologue(o)}
                var had = "";
                try { had = prop.expression; } catch (eE) {}
                if (had === "" || had === null || had === undefined) {
                    return JSON.stringify({success: true, removed: false, message: "Property had no expression."});
                }
                prop.expression = "";
                return JSON.stringify({success: true, removed: true, matchName: prop.matchName});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

// Priority 6: Generic Effects Engine & Layer Switches
// - Effects are addressed by (compId, layerIndex, effectIndex) where
//   effectIndex is the 1-based index within the Effect Parade — indices
//   SHIFT on remove_effect (re-read get_layer_effects after structural
//   changes).
// - set_effect_property refuses keyframed params; the P4 keyframe tools
//   address effect params via propertyPath ["ADBE Effect Parade", ...].
// - CUSTOM_VALUE / NO_VALUE params (curves, buttons) are listed with
//   value: null — readable inventory, not writable through this tool.

// Enumerate installed effects. Filters applied panel-side to keep the
// payload sane (~400 effects unfiltered).
async function listEffectMatchNames(command) {
    const o = command.options || {};
    const category = (o.category === undefined || o.category === null) ? "null" : JSON.stringify(o.category);
    const search = (o.search === undefined || o.search === null) ? "null" : JSON.stringify(String(o.search).toLowerCase());
    const script = `
        (function() {
            try {
                var category = ${category};
                var search = ${search};
                var out = [];
                var total = app.effects.length;
                for (var i = 0; i < total; i++) {
                    var e = app.effects[i];
                    if (category !== null && e.category !== category) { continue; }
                    if (search !== null) {
                        var dn = String(e.displayName).toLowerCase();
                        var mn = String(e.matchName).toLowerCase();
                        if (dn.indexOf(search) === -1 && mn.indexOf(search) === -1) { continue; }
                    }
                    out.push({
                        displayName: e.displayName,
                        matchName: e.matchName,
                        category: e.category
                    });
                }
                return JSON.stringify({
                    success: true,
                    totalInstalled: total,
                    matched: out.length,
                    effects: out
                });
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function addEffect(command) {
    const o = command.options || {};
    const effectName = (o.effectName === undefined || o.effectName === null) ? "null" : JSON.stringify(o.effectName);
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Add Effect");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layer = findLayerByIndex(comp, ${JSON.stringify(o.layerIndex)});
                if (layer === null) {
                    return JSON.stringify({error: "Layer not found: index " + ${JSON.stringify(o.layerIndex)} + " (comp has " + comp.numLayers + " layers)"});
                }
                var parade = layer.property("ADBE Effect Parade");
                if (parade === null || parade === undefined) {
                    return JSON.stringify({error: "Layer '" + layer.name + "' cannot hold effects (no Effect Parade)."});
                }
                var matchName = ${JSON.stringify(o.matchName)};
                if (parade.canAddProperty(matchName) !== true) {
                    return JSON.stringify({error: "Effect matchName not addable: '" + matchName + "'. Use list_effect_match_names to find valid matchNames."});
                }
                var fx = parade.addProperty(matchName);
                var name = ${effectName};
                if (name !== null) { fx.name = name; }
                return JSON.stringify({
                    success: true,
                    effectIndex: fx.propertyIndex,
                    matchName: fx.matchName,
                    name: fx.name,
                    numEffects: parade.numProperties
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

// The round-trip read that makes "make it blurrier" possible: every
// applied effect with every parameter's matchName, type, and value.
async function getLayerEffects(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layer = findLayerByIndex(comp, ${JSON.stringify(o.layerIndex)});
                if (layer === null) {
                    return JSON.stringify({error: "Layer not found: index " + ${JSON.stringify(o.layerIndex)} + " (comp has " + comp.numLayers + " layers)"});
                }
                var parade = layer.property("ADBE Effect Parade");
                var effects = [];
                if (parade !== null && parade !== undefined) {
                    for (var i = 1; i <= parade.numProperties; i++) {
                        var fx = parade.property(i);
                        var params = [];
                        for (var j = 1; j <= fx.numProperties; j++) {
                            var p = fx.property(j);
                            var value = null;
                            var vt = "UNKNOWN";
                            if (p.propertyType !== PropertyType.PROPERTY) {
                                // Nested group (e.g. Compositing Options): no
                                // valueType/value - ExtendScript JSON.stringify
                                // emits literal undefined for them, which
                                // breaks JSON.parse panel-side.
                                vt = "GROUP";
                            } else {
                                try { vt = valueTypeToString(p.propertyValueType); } catch (eVT) {}
                                if (vt !== "NO_VALUE" && vt !== "CUSTOM_VALUE" && vt !== "MARKER") {
                                    try { value = p.value; } catch (eVal) { value = null; }
                                }
                                if (value === undefined) { value = null; }
                            }
                            params.push({
                                matchName: p.matchName,
                                name: p.name,
                                valueType: vt,
                                value: value,
                                numKeys: (p.numKeys !== undefined) ? p.numKeys : 0,
                                hasExpression: (p.expression !== undefined && p.expression !== null && p.expression !== "")
                            });
                        }
                        effects.push({
                            effectIndex: i,
                            matchName: fx.matchName,
                            name: fx.name,
                            enabled: fx.enabled,
                            numParams: fx.numProperties,
                            params: params
                        });
                    }
                }
                return JSON.stringify({
                    success: true,
                    layerName: layer.name,
                    numEffects: effects.length,
                    effects: effects
                });
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

async function setEffectProperty(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Set Effect Property");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layer = findLayerByIndex(comp, ${JSON.stringify(o.layerIndex)});
                if (layer === null) {
                    return JSON.stringify({error: "Layer not found: index " + ${JSON.stringify(o.layerIndex)} + " (comp has " + comp.numLayers + " layers)"});
                }
                var parade = layer.property("ADBE Effect Parade");
                if (parade === null || parade === undefined || parade.numProperties === 0) {
                    return JSON.stringify({error: "Layer '" + layer.name + "' has no effects."});
                }
                var effectIndex = ${JSON.stringify(o.effectIndex)};
                if (effectIndex < 1 || effectIndex > parade.numProperties) {
                    return JSON.stringify({error: "Effect index out of range: " + effectIndex + " (layer has " + parade.numProperties + " effects)"});
                }
                var fx = parade.property(effectIndex);
                var p = null;
                try { p = fx.property(${JSON.stringify(o.paramMatchName)}); } catch (eP) { p = null; }
                if (p === null || p === undefined) {
                    return JSON.stringify({error: "Parameter not found on '" + fx.name + "': '" + ${JSON.stringify(o.paramMatchName)} + "'. Use get_layer_effects for valid param matchNames."});
                }
                if (p.numKeys !== undefined && p.numKeys > 0) {
                    return JSON.stringify({error: "Parameter '" + p.name + "' has " + p.numKeys + " keyframes - use the keyframe tools (propertyPath: [\\"ADBE Effect Parade\\", \\"" + fx.matchName + "\\", \\"" + p.matchName + "\\"])"});
                }
                p.setValue(${JSON.stringify(o.value)});
                return JSON.stringify({
                    success: true,
                    effectIndex: effectIndex,
                    effectName: fx.name,
                    param: p.matchName,
                    value: p.value
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

async function removeEffect(command) {
    const o = command.options || {};
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Remove Effect");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layer = findLayerByIndex(comp, ${JSON.stringify(o.layerIndex)});
                if (layer === null) {
                    return JSON.stringify({error: "Layer not found: index " + ${JSON.stringify(o.layerIndex)} + " (comp has " + comp.numLayers + " layers)"});
                }
                var parade = layer.property("ADBE Effect Parade");
                if (parade === null || parade === undefined || parade.numProperties === 0) {
                    return JSON.stringify({error: "Layer '" + layer.name + "' has no effects."});
                }
                var effectIndex = ${JSON.stringify(o.effectIndex)};
                if (effectIndex < 1 || effectIndex > parade.numProperties) {
                    return JSON.stringify({error: "Effect index out of range: " + effectIndex + " (layer has " + parade.numProperties + " effects)"});
                }
                var fx = parade.property(effectIndex);
                var removedName = fx.name;
                fx.remove();
                return JSON.stringify({success: true, removedName: removedName, numEffects: parade.numProperties});
            } catch(e) {
                return JSON.stringify({error: e.toString(), line: e.line || 'unknown'});
            } finally {
                app.endUndoGroup();
            }
        })();
    `;
    return createPacket(await executeAECommand(script));
}

// Layer switch and/or comp master toggle in one call — motion blur only
// renders when BOTH are on. Only provided args are touched.
async function setMotionBlur(command) {
    const o = command.options || {};
    const layerIndex = (o.layerIndex === undefined || o.layerIndex === null) ? "null" : JSON.stringify(o.layerIndex);
    const layerEnabled = (o.layerEnabled === undefined || o.layerEnabled === null) ? "null" : JSON.stringify(o.layerEnabled);
    const compEnabled = (o.compEnabled === undefined || o.compEnabled === null) ? "null" : JSON.stringify(o.compEnabled);
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Set Motion Blur");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layerIndex = ${layerIndex};
                var layerEnabled = ${layerEnabled};
                var compEnabled = ${compEnabled};
                if (layerEnabled !== null && layerIndex === null) {
                    return JSON.stringify({error: "layerIndex is required when layerEnabled is provided."});
                }
                var layerState = null;
                if (layerEnabled !== null) {
                    var layer = findLayerByIndex(comp, layerIndex);
                    if (layer === null) {
                        return JSON.stringify({error: "Layer not found: index " + layerIndex + " (comp has " + comp.numLayers + " layers)"});
                    }
                    layer.motionBlur = layerEnabled;
                    layerState = layer.motionBlur === true;
                }
                if (compEnabled !== null) {
                    comp.motionBlur = compEnabled;
                }
                return JSON.stringify({
                    success: true,
                    compMotionBlur: comp.motionBlur === true,
                    layerMotionBlur: layerState
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

// blendType: "OFF" | "FRAME_MIX" | "PIXEL_MOTION" (layer), compEnabled
// toggles the comp master. Frame blending renders when both are on.
async function setFrameBlending(command) {
    const o = command.options || {};
    const layerIndex = (o.layerIndex === undefined || o.layerIndex === null) ? "null" : JSON.stringify(o.layerIndex);
    const blendType = (o.blendType === undefined || o.blendType === null) ? "null" : JSON.stringify(o.blendType);
    const compEnabled = (o.compEnabled === undefined || o.compEnabled === null) ? "null" : JSON.stringify(o.compEnabled);
    const script = `
        (function() {
            ${AE_HELPERS}
            app.beginUndoGroup("MCP: Set Frame Blending");
            try {
                var comp = findCompById(${JSON.stringify(o.compId)});
                if (comp === null) {
                    return JSON.stringify({error: "Composition not found: id " + ${JSON.stringify(o.compId)}});
                }
                var layerIndex = ${layerIndex};
                var blendType = ${blendType};
                var compEnabled = ${compEnabled};
                if (blendType !== null && layerIndex === null) {
                    return JSON.stringify({error: "layerIndex is required when blendType is provided."});
                }
                var layerState = null;
                if (blendType !== null) {
                    var layer = findLayerByIndex(comp, layerIndex);
                    if (layer === null) {
                        return JSON.stringify({error: "Layer not found: index " + layerIndex + " (comp has " + comp.numLayers + " layers)"});
                    }
                    var bt = null;
                    if (blendType === "OFF") { bt = FrameBlendingType.NO_FRAME_BLEND; }
                    else if (blendType === "FRAME_MIX") { bt = FrameBlendingType.FRAME_MIX; }
                    else if (blendType === "PIXEL_MOTION") { bt = FrameBlendingType.PIXEL_MOTION; }
                    else {
                        return JSON.stringify({error: "blendType must be OFF, FRAME_MIX, or PIXEL_MOTION - got '" + blendType + "'"});
                    }
                    layer.frameBlendingType = bt;
                    layerState = blendType;
                }
                if (compEnabled !== null) {
                    comp.frameBlending = compEnabled;
                }
                return JSON.stringify({
                    success: true,
                    compFrameBlending: comp.frameBlending === true,
                    layerFrameBlending: layerState
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
    addSolidLayer,
    addTextLayer,
    addNullLayer,
    addAdjustmentLayer,
    addShapeLayer,
    addFootageLayer,
    addCameraLayer,
    addLightLayer,
    setLayerProperties,
    deleteLayer,
    duplicateLayer,
    reorderLayer,
    setLayerTimes,
    setLayerTransform,
    setLayerParent,
    precomposeLayers,
    addKeyframe,
    addKeyframes,
    removeKeyframes,
    getKeyframes,
    getPropertyValue,
    setKeyframeInterpolation,
    setKeyframeEase,
    setExpression,
    getExpression,
    removeExpression,
    listEffectMatchNames,
    addEffect,
    getLayerEffects,
    setEffectProperty,
    removeEffect,
    setMotionBlur,
    setFrameBlending,
    getCompositions: async (command) => createPacket(await getCompositions())
};