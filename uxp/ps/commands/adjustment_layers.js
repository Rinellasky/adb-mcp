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

const { action } = require("photoshop");

const {
    selectLayer,
    findLayer,
    execute
} = require("./utils")

const addAdjustmentLayerBlackAndWhite = async (command) => {

    let options = command.options;
    let layerId = options.layerId;

    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `addAdjustmentLayerBlackAndWhite : Could not find layerId : ${layerId}`
        );
    }

    let colors = options.colors;
    let tintColor = options.tintColor

    await execute(async () => {
        selectLayer(layer, true);

        let commands = [
            // Make adjustment layer
            {
                _obj: "make",
                _target: [
                    {
                        _ref: "adjustmentLayer",
                    },
                ],
                using: {
                    _obj: "adjustmentLayer",
                    type: {
                        _obj: "blackAndWhite",
                        blue: colors.blue,
                        cyan: colors.cyan,
                        grain: colors.green,
                        magenta: colors.magenta,
                        presetKind: {
                            _enum: "presetKindType",
                            _value: "presetKindDefault",
                        },
                        red: colors.red,
                        tintColor: {
                            _obj: "RGBColor",
                            blue: tintColor.blue,
                            grain: tintColor.green,
                            red: tintColor.red,
                        },
                        useTint: options.tint,
                        yellow: colors.yellow,
                    },
                },
            },
        ];

        await action.batchPlay(commands, {});
    });
};

const addBrightnessContrastAdjustmentLayer = async (command) => {

    let options = command.options;
    let layerId = options.layerId;

    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `addBrightnessContrastAdjustmentLayer : Could not find layerId : ${layerId}`
        );
    }

    await execute(async () => {
        selectLayer(layer, true);

        let commands = [
            // Make adjustment layer
            {
                _obj: "make",
                _target: [
                    {
                        _ref: "adjustmentLayer",
                    },
                ],
                using: {
                    _obj: "adjustmentLayer",
                    type: {
                        _obj: "brightnessEvent",
                        useLegacy: false,
                    },
                },
            },
            // Set current adjustment layer
            {
                _obj: "set",
                _target: [
                    {
                        _enum: "ordinal",
                        _ref: "adjustmentLayer",
                        _value: "targetEnum",
                    },
                ],
                to: {
                    _obj: "brightnessEvent",
                    brightness: options.brightness,
                    center: options.contrast,
                    useLegacy: false,
                },
            },
        ];

        await action.batchPlay(commands, {});
    });
};

const addAdjustmentLayerVibrance = async (command) => {

    let options = command.options;
    let layerId = options.layerId;

    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `addAdjustmentLayerVibrance : Could not find layerId : ${layerId}`
        );
    }

    let colors = options.colors;

    await execute(async () => {
        selectLayer(layer, true);

        let commands = [
            // Make adjustment layer
            {
                _obj: "make",
                _target: [
                    {
                        _ref: "adjustmentLayer",
                    },
                ],
                using: {
                    _obj: "adjustmentLayer",
                    type: {
                        _class: "vibrance",
                    },
                },
            },
            // Set current adjustment layer
            {
                _obj: "set",
                _target: [
                    {
                        _enum: "ordinal",
                        _ref: "adjustmentLayer",
                        _value: "targetEnum",
                    },
                ],
                to: {
                    _obj: "vibrance",
                    saturation: options.saturation,
                    vibrance: options.vibrance,
                },
            },
        ];

        await action.batchPlay(commands, {});
    });
};

const addColorBalanceAdjustmentLayer = async (command) => {

    let options = command.options;

    let layerId = options.layerId;
    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `addColorBalanceAdjustmentLayer : Could not find layer named : [${layerId}]`
        );
    }

    await execute(async () => {
        let commands = [
            // Make adjustment layer
            {
                _obj: "make",
                _target: [
                    {
                        _ref: "adjustmentLayer",
                    },
                ],
                using: {
                    _obj: "adjustmentLayer",
                    type: {
                        _obj: "colorBalance",
                        highlightLevels: [0, 0, 0],
                        midtoneLevels: [0, 0, 0],
                        preserveLuminosity: true,
                        shadowLevels: [0, 0, 0],
                    },
                },
            },
            // Set current adjustment layer
            {
                _obj: "set",
                _target: [
                    {
                        _enum: "ordinal",
                        _ref: "adjustmentLayer",
                        _value: "targetEnum",
                    },
                ],
                to: {
                    _obj: "colorBalance",
                    highlightLevels: options.highlights,
                    midtoneLevels: options.midtones,
                    shadowLevels: options.shadows,
                },
            },
        ];
        await action.batchPlay(commands, {});
    });
};

const commandHandlers = {
    addAdjustmentLayerBlackAndWhite,
    addBrightnessContrastAdjustmentLayer,
    addAdjustmentLayerVibrance,
    addColorBalanceAdjustmentLayer,
    addCurvesAdjustmentLayer: (command) => addCurvesAdjustmentLayer(command),
    addLevelsAdjustmentLayer: (command) => addLevelsAdjustmentLayer(command),
    addHueSaturationAdjustmentLayer: (command) => addHueSaturationAdjustmentLayer(command),
    addSelectiveColorAdjustmentLayer: (command) => addSelectiveColorAdjustmentLayer(command)
}

const CHANNEL_MAP = {
    composite: "composite",
    red: "red",
    green: "grain",
    blue: "blue",
};

const addCurvesAdjustmentLayer = async (command) => {
    let options = command.options;
    let layerId = options.layerId;
    let channelCurves = options.channelCurves;

    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `addCurvesAdjustmentLayer : Could not find layerId : ${layerId}`
        );
    }

    let adjustments = [];

    for (let c of channelCurves) {
        let channelValue = CHANNEL_MAP[c.channel];

        if (!channelValue) {
            throw new Error(
                `addCurvesAdjustmentLayer : Unknown channel : ${c.channel}`
            );
        }

        let curvePoints = c.points.map((p) => {
            return {
                _obj: "paint",
                horizontal: p.input,
                vertical: p.output,
            };
        });

        adjustments.push({
            _obj: "curvesAdjustment",
            channel: {
                _ref: "channel",
                _enum: "channel",
                _value: channelValue,
            },
            curve: curvePoints,
        });
    }

    await execute(async () => {
        selectLayer(layer, true);

        let commands = [
            {
                _obj: "make",
                _target: [
                    {
                        _ref: "adjustmentLayer",
                    },
                ],
                using: {
                    _obj: "adjustmentLayer",
                    type: {
                        _obj: "curves",
                        presetKind: {
                            _enum: "presetKindType",
                            _value: "presetKindDefault",
                        },
                    },
                },
            },
            {
                _obj: "set",
                _target: [
                    {
                        _ref: "adjustmentLayer",
                        _enum: "ordinal",
                        _value: "targetEnum",
                    },
                ],
                to: {
                    _obj: "curves",
                    presetKind: {
                        _enum: "presetKindType",
                        _value: "presetKindCustom",
                    },
                    adjustment: adjustments,
                },
            },
        ];

        await action.batchPlay(commands, {});
    });
};

const addLevelsAdjustmentLayer = async (command) => {
    let options = command.options;
    let layerId = options.layerId;
    let channel = options.channel;
    let inputBlack = options.inputBlack;
    let inputWhite = options.inputWhite;
    let gamma = options.gamma;
    let outputBlack = options.outputBlack;
    let outputWhite = options.outputWhite;

    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `addLevelsAdjustmentLayer : Could not find layerId : ${layerId}`
        );
    }

    let channelValue = CHANNEL_MAP[channel];

    if (!channelValue) {
        throw new Error(
            `addLevelsAdjustmentLayer : Unknown channel : ${channel}`
        );
    }

    await execute(async () => {
        selectLayer(layer, true);

        let commands = [
            {
                _obj: "make",
                _target: [
                    {
                        _ref: "adjustmentLayer",
                    },
                ],
                using: {
                    _obj: "adjustmentLayer",
                    type: {
                        _obj: "levels",
                        presetKind: {
                            _enum: "presetKindType",
                            _value: "presetKindDefault",
                        },
                    },
                },
            },
            {
                _obj: "set",
                _target: [
                    {
                        _ref: "adjustmentLayer",
                        _enum: "ordinal",
                        _value: "targetEnum",
                    },
                ],
                to: {
                    _obj: "levels",
                    presetKind: {
                        _enum: "presetKindType",
                        _value: "presetKindCustom",
                    },
                    adjustment: [
                        {
                            _obj: "levelsAdjustment",
                            channel: {
                                _ref: "channel",
                                _enum: "channel",
                                _value: channelValue,
                            },
                            input: [inputBlack, inputWhite],
                            gamma: gamma,
                            output: [outputBlack, outputWhite],
                        },
                    ],
                },
            },
        ];

        await action.batchPlay(commands, {});
    });
};

const addHueSaturationAdjustmentLayer = async (command) => {
    let options = command.options;
    let layerId = options.layerId;
    let hue = options.hue;
    let saturation = options.saturation;
    let lightness = options.lightness;
    let colorize = options.colorize;

    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `addHueSaturationAdjustmentLayer : Could not find layerId : ${layerId}`
        );
    }

    await execute(async () => {
        selectLayer(layer, true);

        let commands = [
            {
                _obj: "make",
                _target: [
                    {
                        _ref: "adjustmentLayer",
                    },
                ],
                using: {
                    _obj: "adjustmentLayer",
                    type: {
                        _obj: "hueSaturation",
                        colorize: false,
                        presetKind: {
                            _enum: "presetKindType",
                            _value: "presetKindDefault",
                        },
                    },
                },
            },
            {
                _obj: "set",
                _target: [
                    {
                        _ref: "adjustmentLayer",
                        _enum: "ordinal",
                        _value: "targetEnum",
                    },
                ],
                to: {
                    _obj: "hueSaturation",
                    presetKind: {
                        _enum: "presetKindType",
                        _value: "presetKindCustom",
                    },
                    colorize: colorize,
                    adjustment: [
                        {
                            _obj: "hueSatAdjustmentV2",
                            hue: hue,
                            saturation: saturation,
                            lightness: lightness,
                        },
                    ],
                },
            },
        ];

        await action.batchPlay(commands, {});
    });
};

const SELECTIVE_COLOR_TARGETS = [
    "reds",
    "yellows",
    "greens",
    "cyans",
    "blues",
    "magentas",
    "whites",
    "neutrals",
    "blacks",
];

const addSelectiveColorAdjustmentLayer = async (command) => {
    let options = command.options;
    let layerId = options.layerId;
    let method = options.method;
    let corrections = options.corrections;

    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `addSelectiveColorAdjustmentLayer : Could not find layerId : ${layerId}`
        );
    }

    let colorCorrections = [];

    for (let c of corrections) {
        if (!SELECTIVE_COLOR_TARGETS.includes(c.target)) {
            throw new Error(
                `addSelectiveColorAdjustmentLayer : Unknown target : ${c.target}`
            );
        }

        colorCorrections.push({
            _obj: "colorCorrection",
            colors: {
                _enum: "colors",
                _value: c.target,
            },
            cyan: { _unit: "percentUnit", _value: c.cyan },
            magenta: { _unit: "percentUnit", _value: c.magenta },
            yellowColor: { _unit: "percentUnit", _value: c.yellow },
            black: { _unit: "percentUnit", _value: c.black },
        });
    }

    await execute(async () => {
        selectLayer(layer, true);

        let commands = [
            {
                _obj: "make",
                _target: [
                    {
                        _ref: "adjustmentLayer",
                    },
                ],
                using: {
                    _obj: "adjustmentLayer",
                    type: {
                        _obj: "selectiveColor",
                        presetKind: {
                            _enum: "presetKindType",
                            _value: "presetKindDefault",
                        },
                    },
                },
            },
            {
                _obj: "set",
                _target: [
                    {
                        _ref: "adjustmentLayer",
                        _enum: "ordinal",
                        _value: "targetEnum",
                    },
                ],
                to: {
                    _obj: "selectiveColor",
                    presetKind: {
                        _enum: "presetKindType",
                        _value: "presetKindCustom",
                    },
                    method: {
                        _enum: "correctionMethod",
                        _value: method,
                    },
                    colorCorrection: colorCorrections,
                },
            },
        ];

        await action.batchPlay(commands, {});
    });
};

module.exports = {
    commandHandlers
};