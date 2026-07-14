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

const { app, ExportFormat, FitOptions } = require("indesign");

const {
    usePoints,
    getActiveDocument,
    getPage,
    getStoryById,
    getItemById,
} = require("./utils.js");

/* -------------------------------------------------------------------------
 * Data merge (feature-detected — verify exposure in UXP live)
 * ---------------------------------------------------------------------- */

const requireDataMerge = (doc) => {
    if (!doc.dataMergeProperties ||
        typeof doc.dataMergeProperties.selectDataSource !== "function") {
        throw new Error(
            "The Data Merge API (dataMergeProperties) is not exposed in this InDesign UXP build"
        );
    }
    return doc.dataMergeProperties;
};

const setDataMergeSource = async (command) => {
    const { filePath } = command.options;
    const doc = getActiveDocument();
    const dm = requireDataMerge(doc);

    dm.selectDataSource(filePath);

    const fields = dm.dataMergeFields.everyItem().getElements()
        .map((f) => {
            try { return f.fieldName ?? f.name; } catch (e) { return String(f); }
        });

    return { source: filePath, fields };
};

const placeMergeField = async (command) => {
    const { fieldName, storyId, characterIndex } = command.options;
    const doc = getActiveDocument();
    const dm = requireDataMerge(doc);

    const fields = dm.dataMergeFields.everyItem().getElements();
    const field = fields.find((f) => {
        try { return (f.fieldName ?? f.name) === fieldName; } catch (e) { return false; }
    });
    if (!field) {
        throw new Error(
            `No merge field [${fieldName}]. Available: ${fields.map((f) => f.fieldName ?? f.name).join(", ")}`
        );
    }

    const story = getStoryById(doc, storyId);
    const ip = story.insertionPoints.item(characterIndex ?? -1);
    doc.dataMergeTextPlaceholders.add(story, ip, field);

    return { placed: fieldName, storyId: story.id };
};

const mergeRecords = async (command) => {
    const { recordNumber } = command.options;
    const doc = getActiveDocument();
    const dm = requireDataMerge(doc);

    if (recordNumber != null && doc.dataMergePreferences) {
        try {
            const { RecordSelection } = require("indesign");
            doc.dataMergePreferences.recordSelection = RecordSelection.ONE_RECORD;
            doc.dataMergePreferences.recordNumber = recordNumber;
        } catch (e) { /* preference shape differs — merge all */ }
    }

    const before = app.documents.length;
    dm.mergeRecords();
    const after = app.documents.length;

    // the merged result opens as a new document and becomes active
    const merged = app.activeDocument;
    return {
        mergedDocument: after > before ? merged.name : null,
        newDocumentCreated: after > before,
        pages: merged ? merged.pages.length : null,
    };
};

/* -------------------------------------------------------------------------
 * Templates
 * ---------------------------------------------------------------------- */

const openAsTemplate = async (command) => {
    const { filePath } = command.options;

    let doc;
    try {
        const { OpenOptions } = require("indesign");
        doc = await app.open(filePath, true, OpenOptions.OPEN_COPY);
    } catch (e) {
        // fallback: plain open (an .indt opens untitled by default)
        doc = await app.open(filePath);
    }

    return { name: doc.name, saved: doc.saved, pages: doc.pages.length };
};

const populateTemplate = async (command) => {
    usePoints();
    const { contentMap, fitOption } = command.options;

    const doc = getActiveDocument();
    if (!contentMap || typeof contentMap !== "object") {
        throw new Error(
            'populateTemplate requires contentMap: {"frameName": "text" | {"imagePath": "..."}}'
        );
    }

    // index every named page item (documents pages + all items incl. groups)
    const byName = {};
    for (const page of doc.pages.everyItem().getElements()) {
        for (const item of page.allPageItems) {
            if (item.name) {
                byName[item.name] = item;
            }
        }
    }

    const fitMap = {
        PROPORTIONALLY: FitOptions.PROPORTIONALLY,
        FILL_PROPORTIONALLY: FitOptions.FILL_PROPORTIONALLY,
        CONTENT_TO_FRAME: FitOptions.CONTENT_TO_FRAME,
        CENTER_CONTENT: FitOptions.CENTER_CONTENT,
    };
    const fit = fitMap[fitOption ?? "FILL_PROPORTIONALLY"] ??
        FitOptions.FILL_PROPORTIONALLY;

    const results = {};
    for (const [frameName, value] of Object.entries(contentMap)) {
        const item = byName[frameName];
        if (!item) {
            results[frameName] = { status: "NOT_FOUND" };
            continue;
        }
        try {
            if (value && typeof value === "object" && value.imagePath) {
                item.place(value.imagePath);
                item.fit(fit);
                results[frameName] = { status: "IMAGE_PLACED" };
            } else {
                item.contents = String(value);
                results[frameName] = {
                    status: "TEXT_SET",
                    overflows: item.overflows === true,
                };
            }
        } catch (e) {
            results[frameName] = { status: "ERROR", error: String(e) };
        }
    }

    const availableNames = Object.keys(byName);
    return { results, availableFrameNames: availableNames };
};

/* -------------------------------------------------------------------------
 * Snippets
 * ---------------------------------------------------------------------- */

const saveSnippet = async (command) => {
    const { itemId, filePath } = command.options;

    const doc = getActiveDocument();
    const item = getItemById(doc, itemId);

    await item.exportFile(ExportFormat.INDESIGN_SNIPPET, filePath);

    return { snippet: filePath, sourceItemId: item.id };
};

const placeSnippet = async (command) => {
    usePoints();
    const { filePath, pageNumber, position } = command.options;

    const doc = getActiveDocument();
    const page = getPage(doc, pageNumber ?? 1);

    const placed = page.place(filePath);
    const items = Array.isArray(placed) ? placed : [placed];

    if (position && items.length) {
        // move the placed item(s) so the first one's top-left lands at position
        const first = items[0];
        const gb = first.geometricBounds;
        const dx = position.x - gb[1];
        const dy = position.y - gb[0];
        for (const it of items) {
            it.move(undefined, [dx, dy]);
        }
    }

    return {
        placedItemIds: items.map((i) => i.id),
        types: items.map((i) => i.constructor.name),
    };
};

const commandHandlers = {
    setDataMergeSource,
    placeMergeField,
    mergeRecords,
    openAsTemplate,
    populateTemplate,
    saveSnippet,
    placeSnippet,
};

module.exports = { commandHandlers };
