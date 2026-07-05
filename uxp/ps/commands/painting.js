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

const { app, action } = require("photoshop");
const { findLayer, execute, selectLayer } = require("./utils");

const TOOL_CLASSES = {
    brush: "paintbrushTool",
    eraser: "eraserTool",
    smudge: "smudgeTool",
};

const setForegroundColor = (color) => {
    return {
        _obj: "set",
        _target: [
            {
                _ref: "color",
                _property: "foregroundColor",
            },
        ],
        to: {
            _obj: "RGBColor",
            red: color.red,
            grain: color.green,
            blue: color.blue,
        },
        source: "photoshopPicker",
    };
};

const setToolOptions = (toolClass, size, hardness, opacity) => {
    return {
        _obj: "set",
        _target: [
            {
                _ref: toolClass,
            },
        ],
        to: {
            _obj: "currentToolOptions",
            opacity: opacity,
            brush: {
                _obj: "computedBrush",
                diameter: {
                    _unit: "pixelsUnit",
                    _value: size,
                },
                hardness: {
                    _unit: "percentUnit",
                    _value: hardness,
                },
            },
        },
    };
};

const makeWorkPathFromPoints = (points) => {
    let pathPoints = points.map((p) => {
        return {
            _obj: "pathPoint",
            anchor: {
                _obj: "paint",
                horizontal: {
                    _unit: "pixelsUnit",
                    _value: p.x,
                },
                vertical: {
                    _unit: "pixelsUnit",
                    _value: p.y,
                },
            },
        };
    });

    return {
        _obj: "set",
        _target: [
            {
                _ref: "path",
                _property: "workPath",
            },
        ],
        to: [
            {
                _obj: "pathComponent",
                shapeOperation: {
                    _enum: "shapeOperation",
                    _value: "xor",
                },
                subpathListKey: [
                    {
                        _obj: "subpathsList",
                        closedSubpath: false,
                        points: pathPoints,
                    },
                ],
            },
        ],
    };
};

const strokeWorkPathWithTool = (toolClass) => {
    return {
        _obj: "stroke",
        _target: [
            {
                _ref: "path",
                _property: "workPath",
            },
        ],
        using: {
            _class: toolClass,
        },
    };
};

const deleteWorkPath = () => {
    return {
        _obj: "delete",
        _target: [
            {
                _ref: "path",
                _property: "workPath",
            },
        ],
    };
};

const strokeWithTool = async (command, tool) => {
    let options = command.options;
    let layerId = options.layerId;
    let points = options.points;
    let brushSize = options.brushSize;
    let hardness = options.hardness;
    let opacity = options.opacity;
    let color = options.color;

    let toolClass = TOOL_CLASSES[tool];

    if (!toolClass) {
        throw new Error(`strokeWithTool : Unknown tool : ${tool}`);
    }

    if (!points || points.length < 2) {
        throw new Error(
            `strokeWithTool : Requires at least 2 points to create a stroke`
        );
    }

    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `strokeWithTool : Could not find layerId : ${layerId}`
        );
    }

    await execute(async () => {
        selectLayer(layer, true);

        let commands = [];

        if (color) {
            commands.push(setForegroundColor(color));
        }

        commands.push(setToolOptions(toolClass, brushSize, hardness, opacity));
        commands.push(makeWorkPathFromPoints(points));
        commands.push(strokeWorkPathWithTool(toolClass));
        commands.push(deleteWorkPath());

        await action.batchPlay(commands, {});
    });
};

const paintBrushStroke = async (command) => {
    return strokeWithTool(command, "brush");
};

const eraserStroke = async (command) => {
    return strokeWithTool(command, "eraser");
};

const smudgeStroke = async (command) => {
    return strokeWithTool(command, "smudge");
};

const commandHandlers = {
    paintBrushStroke,
    eraserStroke,
    smudgeStroke,
};

module.exports = {
    commandHandlers,
};
