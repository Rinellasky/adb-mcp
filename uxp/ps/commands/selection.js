const { app, constants, action } = require("photoshop");
const { 
    findLayer, 
    execute, 
    parseColor, 
    selectLayer 
} = require("./utils");

const {hasActiveSelection} = require("./utils")

const clearSelection = async () => {
    await app.activeDocument.selection.selectRectangle(
        { top: 0, left: 0, bottom: 0, right: 0 },
        constants.SelectionType.REPLACE,
        0,
        true
    );
};

const createMaskFromSelection = async (command) => {

    let options = command.options;
    let layerId = options.layerId;

    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `createMaskFromSelection : Could not find layerId : ${layerId}`
        );
    }

    await execute(async () => {
        selectLayer(layer, true);

        let commands = [
            {
                _obj: "make",
                at: {
                    _enum: "channel",
                    _ref: "channel",
                    _value: "mask",
                },
                new: {
                    _class: "channel",
                },
                using: {
                    _enum: "userMaskEnabled",
                    _value: "revealSelection",
                },
            },
        ];

        await action.batchPlay(commands, {});
    });
};

const selectSubject = async (command) => {

    let options = command.options;
    let layerId = options.layerId;

    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `selectSubject : Could not find layerId : ${layerId}`
        );
    }

    return await execute(async () => {
        selectLayer(layer, true);

        let commands = [
            // Select Subject
            {
                _obj: "autoCutout",
                sampleAllLayers: false,
            },
        ];

        await action.batchPlay(commands, {});
    });
};

const selectSky = async (command) => {

    let options = command.options;
    let layerId = options.layerId;

    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(`selectSky : Could not find layerId : ${layerId}`);
    }

    return await execute(async () => {
        selectLayer(layer, true);

        let commands = [
            // Select Sky
            {
                _obj: "selectSky",
                sampleAllLayers: false,
            },
        ];

        await action.batchPlay(commands, {});

    });
};

const cutSelectionToClipboard = async (command) => {

    let options = command.options;
    let layerId = options.layerId;

    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `cutSelectionToClipboard : Could not find layerId : ${layerId}`
        );
    }

    if (!hasActiveSelection()) {
        throw new Error(
            "cutSelectionToClipboard : Requires an active selection"
        );
    }

    return await execute(async () => {
        selectLayer(layer, true);

        let commands = [
            {
                _obj: "cut",
            },
        ];

        await action.batchPlay(commands, {});
    });
};

const copyMergedSelectionToClipboard = async (command) => {

    let options = command.options;

    if (!hasActiveSelection()) {
        throw new Error(
            "copySelectionToClipboard : Requires an active selection"
        );
    }

    return await execute(async () => {
        let commands = [{
            _obj: "copyMerged",
        }];

        await action.batchPlay(commands, {});
    });
};

const copySelectionToClipboard = async (command) => {

    let options = command.options;
    let layerId = options.layerId;

    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `copySelectionToClipboard : Could not find layerId : ${layerId}`
        );
    }

    if (!hasActiveSelection()) {
        throw new Error(
            "copySelectionToClipboard : Requires an active selection"
        );
    }

    return await execute(async () => {
        selectLayer(layer, true);

        let commands = [{
            _obj: "copyEvent",
            copyHint: "pixels",
        }];

        await action.batchPlay(commands, {});
    });
};

const pasteFromClipboard = async (command) => {

    let options = command.options;
    let layerId = options.layerId;

    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `pasteFromClipboard : Could not find layerId : ${layerId}`
        );
    }

    return await execute(async () => {
        selectLayer(layer, true);

        let pasteInPlace = options.pasteInPlace;

        let commands = [
            {
                _obj: "paste",
                antiAlias: {
                    _enum: "antiAliasType",
                    _value: "antiAliasNone",
                },
                as: {
                    _class: "pixel",
                },
                inPlace: pasteInPlace,
            },
        ];

        await action.batchPlay(commands, {});
    });
};

const deleteSelection = async (command) => {

    let options = command.options;
    let layerId = options.layerId;
    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `deleteSelection : Could not find layerId : ${layerId}`
        );
    }

    if (!app.activeDocument.selection.bounds) {
        throw new Error(`invertSelection : Requires an active selection`);
    }

    await execute(async () => {
        selectLayer(layer, true);
        let commands = [
            {
                _obj: "delete",
            },
        ];
        await action.batchPlay(commands, {});
    });
};

const fillSelection = async (command) => {

    let options = command.options;
    let layerId = options.layerId;
    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `fillSelection : Could not find layerId : ${layerId}`
        );
    }

    if (!app.activeDocument.selection.bounds) {
        throw new Error(`invertSelection : Requires an active selection`);
    }

    await execute(async () => {
        selectLayer(layer, true);

        let c = parseColor(options.color).rgb;
        let commands = [
            // Fill
            {
                _obj: "fill",
                color: {
                    _obj: "RGBColor",
                    blue: c.blue,
                    grain: c.green,
                    red: c.red,
                },
                mode: {
                    _enum: "blendMode",
                    _value: options.blendMode.toLowerCase(),
                },
                opacity: {
                    _unit: "percentUnit",
                    _value: options.opacity,
                },
                using: {
                    _enum: "fillContents",
                    _value: "color",
                },
            },
        ];
        await action.batchPlay(commands, {});
    });
};

const selectPolygon = async (command) => {

    let options = command.options;
    let layerId = options.layerId;
    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `selectPolygon : Could not find layerId : ${layerId}`
        );
    }

    await execute(async () => {

        selectLayer(layer, true);

        await app.activeDocument.selection.selectPolygon(
            options.points,
            constants.SelectionType.REPLACE,
            options.feather,
            options.antiAlias
        );
    });
};

let selectEllipse = async (command) => {

    let options = command.options;
    let layerId = options.layerId;
    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `selectEllipse : Could not find layerId : ${layerId}`
        );
    }

    await execute(async () => {

        selectLayer(layer, true);

        await app.activeDocument.selection.selectEllipse(
            options.bounds,
            constants.SelectionType.REPLACE,
            options.feather,
            options.antiAlias
        );
    });
};

const selectRectangle = async (command) => {
    let options = command.options;
    let layerId = options.layerId;
    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `selectRectangle : Could not find layerId : ${layerId}`
        );
    }

    await execute(async () => {
        selectLayer(layer, true);

        await app.activeDocument.selection.selectRectangle(
            options.bounds,
            constants.SelectionType.REPLACE,
            options.feather,
            options.antiAlias
        );
    });
};

const invertSelection = async (command) => {

    if (!app.activeDocument.selection.bounds) {
        throw new Error(`invertSelection : Requires an active selection`);
    }

    await execute(async () => {
        let commands = [
            {
                _obj: "inverse",
            },
        ];
        await action.batchPlay(commands, {});
    });
};

const selectColorRange = async (command) => {
    let options = command.options;
    let layerId = options.layerId;
    let color = options.color;
    let fuzziness = options.fuzziness;

    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `selectColorRange : Could not find layerId : ${layerId}`
        );
    }

    await execute(async () => {
        selectLayer(layer, true);

        let commands = [
            {
                _obj: "colorRange",
                colorModel: 0,
                fuzziness: fuzziness,
                maximum: {
                    _obj: "labColor",
                    luminance: 100.0,
                    a: 0.0,
                    b: 0.0,
                },
                minimum: {
                    _obj: "RGBColor",
                    red: color.red,
                    grain: color.green,
                    blue: color.blue,
                },
            },
        ];

        await action.batchPlay(commands, {});
    });
};

const magicWandSelect = async (command) => {
    let options = command.options;
    let layerId = options.layerId;
    let point = options.point;
    let tolerance = options.tolerance;
    let antiAlias = options.antiAlias;
    let contiguous = options.contiguous;
    let sampleAllLayers = options.sampleAllLayers;

    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `magicWandSelect : Could not find layerId : ${layerId}`
        );
    }

    await execute(async () => {
        selectLayer(layer, true);

        let commands = [
            {
                _obj: "set",
                _target: [
                    {
                        _ref: "channel",
                        _property: "selection",
                    },
                ],
                to: {
                    _obj: "paint",
                    horizontal: {
                        _unit: "pixelsUnit",
                        _value: point.x,
                    },
                    vertical: {
                        _unit: "pixelsUnit",
                        _value: point.y,
                    },
                },
                tolerance: tolerance,
                antiAlias: antiAlias,
                contiguous: contiguous,
                merged: sampleAllLayers,
            },
        ];

        await action.batchPlay(commands, {});
    });
};

const MODIFY_SELECTION_MODES = {
    expand: "expand",
    contract: "contract",
    feather: "feather",
    smooth: "smoothness",
    border: "border",
};

const modifySelection = async (command) => {
    let options = command.options;
    let mode = options.mode;
    let amount = options.amount;

    let eventName = MODIFY_SELECTION_MODES[mode];

    if (!eventName) {
        throw new Error(
            `modifySelection : Unknown mode : ${mode}. Must be one of ${Object.keys(
                MODIFY_SELECTION_MODES
            ).join(", ")}`
        );
    }

    if (!(await hasActiveSelection())) {
        throw new Error(
            `modifySelection : Requires an active selection`
        );
    }

    await execute(async () => {
        let key = mode === "feather" ? "radius" : "by";

        let c = {
            _obj: eventName,
        };

        c[key] = {
            _unit: "pixelsUnit",
            _value: amount,
        };

        // border / smooth use "width" / "radius" respectively
        if (mode === "border") {
            c = {
                _obj: "border",
                width: { _unit: "pixelsUnit", _value: amount },
            };
        } else if (mode === "smooth") {
            c = {
                _obj: "smoothness",
                radius: { _unit: "pixelsUnit", _value: amount },
            };
        }

        await action.batchPlay([c], {});
    });
};

const growSelection = async (command) => {
    let options = command.options;
    let tolerance = options.tolerance;

    if (!(await hasActiveSelection())) {
        throw new Error(`growSelection : Requires an active selection`);
    }

    await execute(async () => {
        let commands = [
            {
                _obj: "grow",
                tolerance: tolerance,
                antiAlias: true,
            },
        ];
        await action.batchPlay(commands, {});
    });
};

const selectSimilar = async (command) => {
    let options = command.options;
    let tolerance = options.tolerance;

    if (!(await hasActiveSelection())) {
        throw new Error(`selectSimilar : Requires an active selection`);
    }

    await execute(async () => {
        let commands = [
            {
                _obj: "similar",
                tolerance: tolerance,
                antiAlias: true,
            },
        ];
        await action.batchPlay(commands, {});
    });
};

const commandHandlers = {
    selectColorRange,
    magicWandSelect,
    modifySelection,
    growSelection,
    selectSimilar,
    clearSelection,
    createMaskFromSelection,
    selectSubject,
    selectSky,
    cutSelectionToClipboard,
    copyMergedSelectionToClipboard,
    copySelectionToClipboard,
    pasteFromClipboard,
    deleteSelection,
    fillSelection,
    selectPolygon,
    selectEllipse,
    selectRectangle,
    invertSelection
};

module.exports = {
    commandHandlers
};