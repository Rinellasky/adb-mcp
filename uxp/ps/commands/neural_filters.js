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
const { findLayer, execute, selectLayer } = require("./utils");

// Descriptor envelope taken from Adobe's official neural-filter-sample:
// https://github.com/AdobeDocs/uxp-photoshop-plugin-samples/tree/main/neural-filter-sample
// The target filter must already be downloaded/enabled in the Neural Filters
// gallery (Filter > Neural Filters) or Photoshop will reject the command.

let capturedFilterEvents = [];
let captureListenerRegistered = false;

const onNeuralFilterEvent = (event, descriptor) => {
    capturedFilterEvents.push({ event: event, descriptor: descriptor });
};

const startNeuralFilterCapture = async (command) => {
    if (!captureListenerRegistered) {
        await action.addNotificationListener(
            ["neuralGalleryFilters"],
            onNeuralFilterEvent
        );
        captureListenerRegistered = true;
    }

    capturedFilterEvents = [];

    return {
        capturing: true,
        message:
            "Capture started. Apply a neural filter manually via " +
            "Filter > Neural Filters in Photoshop, then call " +
            "getCapturedNeuralFilters to read the recorded descriptor(s).",
    };
};

const getCapturedNeuralFilters = async (command) => {
    return {
        capturing: captureListenerRegistered,
        count: capturedFilterEvents.length,
        events: capturedFilterEvents,
    };
};

const buildFilterStack = (options) => {
    // A raw filter stack (e.g. captured via startNeuralFilterCapture) replays
    // exactly as recorded and takes precedence over filterId/values.
    if (options.rawFilterStack) {
        return options.rawFilterStack;
    }

    if (!options.filterId) {
        throw new Error(
            `applyNeuralFilter : Requires filterId (e.g. "internal.StyleTransfer") or rawFilterStack`
        );
    }

    let stackEntry = {
        _obj: "spl::filterStack",
        "spl::enabled": true,
        "spl::id": options.filterId,
        "spl::version": options.filterVersion || "1.0",
    };

    let values = options.values;

    if (values && Object.keys(values).length > 0) {
        stackEntry["spl::cropStates"] = [
            {
                _obj: "spl::cropStates",
                "spl::cropId": "layer1",
                "spl::values": {
                    _obj: "spl::values",
                    ...values,
                },
            },
        ];
    }

    return [stackEntry];
};

const applyNeuralFilter = async (command) => {
    let options = command.options;
    let layerId = options.layerId;

    let layer = findLayer(layerId);

    if (!layer) {
        throw new Error(
            `applyNeuralFilter : Could not find layerId : ${layerId}`
        );
    }

    // A full raw descriptor (a complete neuralGalleryFilters event captured
    // via startNeuralFilterCapture) replays exactly as recorded. On modern
    // Photoshop (2024+) this is the ONLY form that executes: the compiled
    // NF_SPL_GRAPH it contains is required, and envelope-only descriptors
    // built from NF_UI_DATA are accepted but silently do nothing.
    let descriptor;

    if (options.rawDescriptor) {
        descriptor = options.rawDescriptor;
    } else {
        descriptor = {
            _obj: "neuralGalleryFilters",
            NF_OUTPUT_TYPE:
                options.outputType !== undefined ? options.outputType : 2,
            _isCommand: true,
            NF_UI_DATA: {
                _obj: "NF_UI_DATA",
                "spl::version": "1.0.6",
                "spl::filterStack": buildFilterStack(options),
            },
        };
    }

    let result;
    await execute(async () => {
        selectLayer(layer, true);

        result = await action.batchPlay([descriptor], {});
    }, "Applying neural filter...");

    return { batchPlayResult: result };
};

const commandHandlers = {
    applyNeuralFilter,
    startNeuralFilterCapture,
    getCapturedNeuralFilters,
};

module.exports = {
    commandHandlers,
};
