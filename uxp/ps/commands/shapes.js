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
        // Since Photoshop v22 the line tool creates thin rectangles; a
        // 'line' shape class is rejected with -25920. Build an axis-aligned
        // thin rectangle along the line's length, centered on the midpoint;
        // the caller rotates it into place afterwards.
        let dx = bounds.right - bounds.left;
        let dy = bounds.bottom - bounds.top;
        let length = Math.sqrt(dx * dx + dy * dy);
        let width = options.lineWidth || 1;
        let midX = (bounds.left + bounds.right) / 2;
        let midY = (bounds.top + bounds.bottom) / 2;

        return {
            _obj: "rectangle",
            top: pixels(midY - width / 2),
            left: pixels(midX - length / 2),
            bottom: pixels(midY + width / 2),
            right: pixels(midX + length / 2),
        };
    }

    throw new Error(`createShapeLayer : Unknown shapeType : ${shapeType}`);
};

// With dialogOptions "silent", failed batchPlay commands come back as
// {_obj: "error"} result descriptors instead of throwing
const throwOnBatchPlayError = (results, context) => {
    for (const r of results || []) {
        if (r && r._obj === "error") {
            throw new Error(
                `${context} : batchPlay error ${r.result} : ${r.message}`
            );
        }
    }
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

    let makeDescriptor = {
        _obj: "make",
        _target: [
            {
                _ref: "contentLayer",
            },
        ],
        using: using,
        // "silent" suppresses Photoshop's scripting error dialog,
        // which otherwise blocks batchPlay until dismissed
        _options: {
            dialogOptions: "silent",
        },
    };

    let layerId;
    await execute(async () => {
        let layerIdsBefore = new Set(
            app.activeDocument.layers.map((l) => l.id)
        );

        // "make" transiently reports "not currently available" when the host
        // is busy; one delayed retry rides out that state
        let results = await action.batchPlay([makeDescriptor], {});
        try {
            throwOnBatchPlayError(results, "createShapeLayer");
        } catch (e) {
            await new Promise((resolve) => setTimeout(resolve, 500));
            results = await action.batchPlay([makeDescriptor], {});
            throwOnBatchPlayError(results, "createShapeLayer");
        }

        let layer = app.activeDocument.activeLayers[0];

        if (!layer || layerIdsBefore.has(layer.id)) {
            throw new Error(
                `createShapeLayer : make succeeded but no new layer was created`
            );
        }

        // LINE is built as an axis-aligned thin rectangle; rotate it to the
        // requested angle around its center
        if (options.shapeType === "LINE") {
            let dx = options.bounds.right - options.bounds.left;
            let dy = options.bounds.bottom - options.bounds.top;
            let angle = (Math.atan2(dy, dx) * 180) / Math.PI;

            if (Math.abs(angle) > 0.01) {
                let rotateResults = await action.batchPlay(
                    [
                        {
                            _obj: "transform",
                            _target: [
                                {
                                    _enum: "ordinal",
                                    _ref: "layer",
                                    _value: "targetEnum",
                                },
                            ],
                            freeTransformCenterState: {
                                _enum: "quadCenterState",
                                _value: "QCSAverage",
                            },
                            angle: {
                                _unit: "angleUnit",
                                _value: angle,
                            },
                            _options: {
                                dialogOptions: "silent",
                            },
                        },
                    ],
                    {}
                );
                throwOnBatchPlayError(rotateResults, "createShapeLayer:rotate");
            }
        }

        if (options.layerName) {
            layer.name = options.layerName;
        }

        layerId = layer.id;
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
