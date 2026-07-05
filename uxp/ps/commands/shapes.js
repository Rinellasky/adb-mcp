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
const { execute } = require("./utils");

const pixels = (value) => {
    return {
        _unit: "pixelsUnit",
        _value: value,
    };
};

const rgbColor = (color) => {
    return {
        _obj: "RGBColor",
        red: color.red,
        grain: color.green,
        blue: color.blue,
    };
};

const buildStrokeStyle = (stroke) => {
    let strokeEnabled = !!stroke;

    let style = {
        _obj: "strokeStyle",
        strokeStyleVersion: 2,
        strokeEnabled: strokeEnabled,
        fillEnabled: true,
        strokeStyleLineWidth: pixels(strokeEnabled ? stroke.size : 1),
        strokeStyleLineDashOffset: {
            _unit: "pointsUnit",
            _value: 0,
        },
        strokeStyleMiterLimit: 100.0,
        strokeStyleLineCapType: {
            _enum: "strokeStyleLineCapType",
            _value: "strokeStyleButtCap",
        },
        strokeStyleLineJoinType: {
            _enum: "strokeStyleLineJoinType",
            _value: "strokeStyleMiterJoin",
        },
        strokeStyleLineAlignment: {
            _enum: "strokeStyleLineAlignment",
            _value: "strokeStyleAlignCenter",
        },
        strokeStyleScaleLock: false,
        strokeStyleStrokeAdjust: false,
        strokeStyleLineDashSet: [],
        strokeStyleBlendMode: {
            _enum: "blendMode",
            _value: "normal",
        },
        strokeStyleOpacity: {
            _unit: "percentUnit",
            _value: 100.0,
        },
        strokeStyleResolution: 72.0,
    };

    if (strokeEnabled) {
        style.strokeStyleContent = {
            _obj: "solidColorLayer",
            color: rgbColor(stroke.color),
        };
    }

    return style;
};

const buildShape = (options) => {
    let shapeType = options.shapeType;
    let bounds = options.bounds;

    if (shapeType === "RECTANGLE") {
        let shape = {
            _obj: "rectangle",
            top: pixels(bounds.top),
            left: pixels(bounds.left),
            bottom: pixels(bounds.bottom),
            right: pixels(bounds.right),
        };

        let radius = options.cornerRadius;

        if (radius && radius > 0) {
            shape.unitValueQuadVersion = 1;
            shape.topLeft = pixels(radius);
            shape.topRight = pixels(radius);
            shape.bottomLeft = pixels(radius);
            shape.bottomRight = pixels(radius);
        }

        return shape;
    }

    if (shapeType === "ELLIPSE") {
        return {
            _obj: "ellipse",
            top: pixels(bounds.top),
            left: pixels(bounds.left),
            bottom: pixels(bounds.bottom),
            right: pixels(bounds.right),
        };
    }

    if (shapeType === "LINE") {
        return {
            _obj: "line",
            start: {
                _obj: "paint",
                horizontal: pixels(bounds.left),
                vertical: pixels(bounds.top),
            },
            end: {
                _obj: "paint",
                horizontal: pixels(bounds.right),
                vertical: pixels(bounds.bottom),
            },
            width: pixels(options.lineWidth || 1),
        };
    }

    throw new Error(`createShapeLayer : Unknown shapeType : ${shapeType}`);
};

const createShapeLayer = async (command) => {
    let options = command.options;

    let shape = buildShape(options);

    let using = {
        _obj: "contentLayer",
        type: {
            _obj: "solidColorLayer",
            color: rgbColor(options.fillColor),
        },
        shape: shape,
    };

    if (options.stroke) {
        using.strokeStyle = buildStrokeStyle(options.stroke);
    }

    let layerId;
    await execute(async () => {
        await action.batchPlay(
            [
                {
                    _obj: "make",
                    _target: [
                        {
                            _ref: "contentLayer",
                        },
                    ],
                    using: using,
                    _options: {
                        dialogOptions: "dontDisplay",
                    },
                },
            ],
            {}
        );

        let layer = app.activeDocument.activeLayers[0];

        if (layer && options.layerName) {
            layer.name = options.layerName;
        }

        layerId = layer ? layer.id : null;
    });

    return { layerId: layerId };
};

const makePathPoint = (p) => {
    let point = {
        _obj: "pathPoint",
        anchor: {
            _obj: "paint",
            horizontal: pixels(p.x),
            vertical: pixels(p.y),
        },
    };

    // Optional bezier handles. forward = handle leaving the anchor,
    // backward = handle entering it.
    if (p.forward) {
        point.forward = {
            _obj: "paint",
            horizontal: pixels(p.forward.x),
            vertical: pixels(p.forward.y),
        };
    }

    if (p.backward) {
        point.backward = {
            _obj: "paint",
            horizontal: pixels(p.backward.x),
            vertical: pixels(p.backward.y),
        };
    }

    if (p.forward || p.backward) {
        point.smooth = p.smooth !== false;
    }

    return point;
};

const createPathFromPoints = async (command) => {
    let options = command.options;
    let points = options.points;

    if (!points || points.length < 2) {
        throw new Error(
            `createPathFromPoints : Requires at least 2 points`
        );
    }

    await execute(async () => {
        await action.batchPlay(
            [
                // Build the work path from the points
                {
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
                                    closedSubpath: options.closed === true,
                                    points: points.map(makePathPoint),
                                },
                            ],
                        },
                    ],
                },
                // Save the work path as a named path
                {
                    _obj: "make",
                    _target: [
                        {
                            _ref: "path",
                        },
                    ],
                    from: {
                        _ref: "path",
                        _property: "workPath",
                    },
                    name: options.pathName,
                },
            ],
            {}
        );
    });
};

const commandHandlers = {
    createShapeLayer,
    createPathFromPoints,
};

module.exports = {
    commandHandlers,
};
