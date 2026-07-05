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
const { execute } = require("./utils");

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

const silentPlay = async (descriptors, context) => {
    for (const d of descriptors) {
        d._options = { dialogOptions: "silent" };
    }

    let results = await action.batchPlay(descriptors, {});
    throwOnBatchPlayError(results, context);
    return results;
};

const createFrameAnimation = async (command) => {
    await execute(async () => {
        // "make animationClass" is rejected (-25920) on PS 2026; the
        // Timeline panel's Create Frame Animation records this event instead
        await silentPlay(
            [
                {
                    _obj: "makeFrameAnimation",
                },
            ],
            "createFrameAnimation"
        );
    });
};

const addAnimationFrame = async (command) => {
    let options = command.options;

    await execute(async () => {
        // The timeline's new-frame button duplicates the current frame;
        // "make animationFrameClass" is rejected (-25920) on PS 2026
        let commands = [
            {
                _obj: "duplicate",
                _target: [
                    {
                        _ref: "animationFrameClass",
                        _enum: "ordinal",
                        _value: "targetEnum",
                    },
                ],
            },
        ];

        if (options.duration !== undefined && options.duration !== null) {
            commands.push({
                _obj: "set",
                _target: [
                    {
                        _ref: "animationFrameClass",
                        _enum: "ordinal",
                        _value: "targetEnum",
                    },
                ],
                to: {
                    _obj: "animationFrameClass",
                    animationFrameDelay: options.duration,
                },
            });
        }

        await silentPlay(commands, "addAnimationFrame");
    });
};

const selectAnimationFrame = async (command) => {
    let options = command.options;

    await execute(async () => {
        await silentPlay(
            [
                {
                    _obj: "select",
                    _target: [
                        {
                            _ref: "animationFrameClass",
                            _index: options.frameIndex,
                        },
                    ],
                },
            ],
            "selectAnimationFrame"
        );
    });
};

const setAnimationFrameDelay = async (command) => {
    let options = command.options;

    await execute(async () => {
        let commands = [];

        if (options.frameIndex !== undefined && options.frameIndex !== null) {
            commands.push({
                _obj: "select",
                _target: [
                    {
                        _ref: "animationFrameClass",
                        _index: options.frameIndex,
                    },
                ],
            });
        }

        commands.push({
            _obj: "set",
            _target: [
                {
                    _ref: "animationFrameClass",
                    _enum: "ordinal",
                    _value: "targetEnum",
                },
            ],
            to: {
                _obj: "animationFrameClass",
                animationFrameDelay: options.delay,
            },
        });

        await silentPlay(commands, "setAnimationFrameDelay");
    });
};

const createAnimationFramesFromLayers = async (command) => {
    await execute(async () => {
        await silentPlay(
            [
                {
                    _obj: "animationFramesFromLayers",
                },
            ],
            "createAnimationFramesFromLayers"
        );
    });
};

const commandHandlers = {
    createFrameAnimation,
    addAnimationFrame,
    selectAnimationFrame,
    setAnimationFrameDelay,
    createAnimationFramesFromLayers,
};

module.exports = {
    commandHandlers,
};
