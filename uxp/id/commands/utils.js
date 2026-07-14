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

const { app, MeasurementUnits } = require("indesign");

/**
 * Normalize the scripting measurement unit to POINTS so every number we
 * send/receive means the same thing regardless of the document's UI units.
 * Call at the top of every handler that touches geometry.
 * (Architecture Note 3 in the roadmap.)
 */
const usePoints = () => {
    app.scriptPreferences.measurementUnit = MeasurementUnits.POINTS;
};

const getActiveDocument = () => {
    if (app.documents.length === 0) {
        throw new Error("No open InDesign document");
    }
    return app.activeDocument;
};

/**
 * Pages are 1-based in the tool API.
 */
const getPage = (doc, pageNumber) => {
    const n = parseInt(pageNumber);
    if (isNaN(n) || n < 1 || n > doc.pages.length) {
        throw new Error(
            `Invalid pageNumber [${pageNumber}]. Document has ${doc.pages.length} page(s), and pages are 1-based.`
        );
    }
    return doc.pages.item(n - 1);
};

const getItemById = (doc, itemId) => {
    const item = doc.pageItems.itemByID(parseInt(itemId));
    if (!item.isValid) {
        throw new Error(`No page item with id [${itemId}]`);
    }
    return item.getElements()[0];
};

const getStoryById = (doc, storyId) => {
    const id = parseInt(storyId);
    let story = doc.stories.itemByID(id);
    if (story && story.isValid) {
        return story.getElements()[0];
    }
    // fallback: linear search (itemByID on stories is flaky in some versions)
    const match = doc.stories.everyItem().getElements().find((s) => s.id === id);
    if (!match) {
        throw new Error(`No story with id [${storyId}]`);
    }
    return match;
};

const getSwatch = (doc, name) => {
    const swatch = doc.swatches.itemByName(name);
    if (!swatch.isValid) {
        const names = doc.swatches.everyItem().getElements().map((s) => s.name);
        throw new Error(
            `No swatch named [${name}]. Available swatches: ${names.join(", ")}`
        );
    }
    return swatch;
};

const getLayerByName = (doc, name) => {
    const layer = doc.layers.itemByName(name);
    if (!layer.isValid) {
        throw new Error(`No layer named [${name}]`);
    }
    return layer;
};

/**
 * Tool signatures accept bounds as {top, left, bottom, right} objects;
 * the DOM wants geometricBounds arrays ordered [y1, x1, y2, x2] =
 * [top, left, bottom, right]. (Architecture Note 4.)
 */
const boundsToArray = (bounds) => {
    if (Array.isArray(bounds)) {
        return bounds;
    }
    for (const k of ["top", "left", "bottom", "right"]) {
        if (typeof bounds[k] !== "number") {
            throw new Error(
                `bounds requires numeric top/left/bottom/right. Got: ${JSON.stringify(bounds)}`
            );
        }
    }
    return [bounds.top, bounds.left, bounds.bottom, bounds.right];
};

const boundsToObject = (gb) => {
    return { top: gb[0], left: gb[1], bottom: gb[2], right: gb[3] };
};

/**
 * Standard status blob returned by every text-mutating handler so the AI
 * can react to overset text. (Architecture Note 6.)
 */
const textFrameStatus = (frame) => {
    return {
        frameId: frame.id,
        storyId: frame.parentStory.id,
        overflows: frame.overflows,
    };
};

const describePageItem = (item) => {
    const info = {
        id: item.id,
        type: item.constructor.name, // TextFrame, Rectangle, Oval, ...
        name: item.name,
        bounds: boundsToObject(item.geometricBounds),
    };

    try {
        info.layer = item.itemLayer.name;
    } catch (e) {
        info.layer = null;
    }

    if (info.type === "TextFrame") {
        try {
            info.storyId = item.parentStory.id;
            info.overflows = item.overflows;
            const c = item.contents;
            info.contentsPreview =
                typeof c === "string" ? c.substring(0, 200) : String(c);
            info.threadedToId = item.nextTextFrame ? item.nextTextFrame.id : null;
        } catch (e) {
            info.textError = String(e);
        }
    }

    return info;
};

module.exports = {
    usePoints,
    getActiveDocument,
    getPage,
    getItemById,
    getStoryById,
    getSwatch,
    getLayerByName,
    boundsToArray,
    boundsToObject,
    textFrameStatus,
    describePageItem,
};
