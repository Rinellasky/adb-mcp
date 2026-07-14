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

const { app, NothingEnum } = require("indesign");

const { usePoints, getActiveDocument, getItemById, boundsToObject } =
    require("./utils.js");

/* -------------------------------------------------------------------------
 * Align / distribute (computed geometry — no selection or window needed)
 * ---------------------------------------------------------------------- */

const shiftItem = (item, dx, dy) => {
    if (dx === 0 && dy === 0) return;
    item.move(undefined, [dx, dy]);
};

const alignItems = async (command) => {
    usePoints();
    const { itemIds, mode, reference } = command.options;

    const doc = getActiveDocument();
    if (!Array.isArray(itemIds) || itemIds.length < 1) {
        throw new Error("alignItems requires an itemIds array");
    }
    const items = itemIds.map((id) => getItemById(doc, id));

    // reference bounds: FIRST item (default) or the PAGE of the first item
    let ref;
    const refMode = String(reference ?? "FIRST").toUpperCase();
    if (refMode === "PAGE") {
        const page = items[0].parentPage;
        if (!page) throw new Error("First item has no parent page");
        ref = page.bounds; // [top, left, bottom, right]
    } else {
        ref = items[0].geometricBounds;
    }

    const m = String(mode).toUpperCase();
    const moved = [];
    for (const item of items) {
        const gb = item.geometricBounds;
        const w = gb[3] - gb[1];
        const h = gb[2] - gb[0];
        let dx = 0, dy = 0;
        switch (m) {
            case "LEFT": dx = ref[1] - gb[1]; break;
            case "RIGHT": dx = ref[3] - gb[3]; break;
            case "TOP": dy = ref[0] - gb[0]; break;
            case "BOTTOM": dy = ref[2] - gb[2]; break;
            case "CENTER_HORIZONTAL":
                dx = (ref[1] + ref[3]) / 2 - (gb[1] + w / 2); break;
            case "CENTER_VERTICAL":
                dy = (ref[0] + ref[2]) / 2 - (gb[0] + h / 2); break;
            default:
                throw new Error(
                    `Unknown mode [${mode}]. Valid: LEFT, RIGHT, TOP, BOTTOM, CENTER_HORIZONTAL, CENTER_VERTICAL`
                );
        }
        shiftItem(item, dx, dy);
        moved.push({ itemId: item.id, bounds: boundsToObject(item.geometricBounds) });
    }

    return { mode: m, reference: refMode, items: moved };
};

const distributeItems = async (command) => {
    usePoints();
    const { itemIds, axis, spacing } = command.options;

    const doc = getActiveDocument();
    if (!Array.isArray(itemIds) || itemIds.length < 2) {
        throw new Error("distributeItems requires an itemIds array of >= 2 items");
    }
    if (itemIds.length < 3 && spacing == null) {
        throw new Error(
            "distributeItems with equal gaps needs >= 3 items — pass explicit spacing for 2 items"
        );
    }
    const items = itemIds.map((id) => getItemById(doc, id));

    const horizontal = String(axis ?? "HORIZONTAL").toUpperCase() === "HORIZONTAL";
    const lo = horizontal ? 1 : 0; // left or top index in bounds
    const hi = horizontal ? 3 : 2; // right or bottom

    const sorted = [...items].sort(
        (a, b) => a.geometricBounds[lo] - b.geometricBounds[lo]);

    const moved = [];
    if (spacing != null) {
        // fixed gap stacking from the first item
        let cursor = sorted[0].geometricBounds[hi];
        for (const item of sorted.slice(1)) {
            const gb = item.geometricBounds;
            const delta = (cursor + spacing) - gb[lo];
            shiftItem(item, horizontal ? delta : 0, horizontal ? 0 : delta);
            cursor = item.geometricBounds[hi];
        }
    } else {
        // equal gaps between first and last (positions preserved at ends)
        const first = sorted[0].geometricBounds;
        const last = sorted[sorted.length - 1].geometricBounds;
        const totalSize = sorted.reduce(
            (sum, i) => sum + (i.geometricBounds[hi] - i.geometricBounds[lo]), 0);
        const span = last[hi] - first[lo];
        const gap = (span - totalSize) / (sorted.length - 1);
        let cursor = first[hi];
        for (const item of sorted.slice(1, -1)) {
            const gb = item.geometricBounds;
            const delta = (cursor + gap) - gb[lo];
            shiftItem(item, horizontal ? delta : 0, horizontal ? 0 : delta);
            cursor = item.geometricBounds[hi];
        }
    }

    for (const item of sorted) {
        moved.push({ itemId: item.id, bounds: boundsToObject(item.geometricBounds) });
    }
    return { axis: horizontal ? "HORIZONTAL" : "VERTICAL", items: moved };
};

/* -------------------------------------------------------------------------
 * Multi-document
 * ---------------------------------------------------------------------- */

const getDocuments = async (command) => {
    const active = app.documents.length ? app.activeDocument.name : null;
    const docs = app.documents.everyItem().getElements().map((d) => ({
        name: d.name,
        saved: d.saved,
        modified: d.modified,
        pages: d.pages.length,
        isActive: d.name === active,
    }));
    return { documents: docs, activeDocument: active };
};

const setActiveDocument = async (command) => {
    const { name } = command.options;

    // iterate — assigning a plain object to app.activeDocument was the
    // classic ps-mcp bug; only a real Document instance works
    const match = app.documents.everyItem().getElements()
        .find((d) => d.name === name);
    if (!match) {
        const names = app.documents.everyItem().getElements().map((d) => d.name);
        throw new Error(
            `No open document named [${name}]. Open: ${names.join(", ")}`
        );
    }
    app.activeDocument = match;

    return { activeDocument: match.name, pages: match.pages.length };
};

/* -------------------------------------------------------------------------
 * Cross-document batch style
 * ---------------------------------------------------------------------- */

const batchApplyStyle = async (command) => {
    const { grepFindWhat, characterStyleName, paragraphStyleName, allOpenDocuments } =
        command.options;

    if (!grepFindWhat) {
        throw new Error(
            "batchApplyStyle requires grepFindWhat (a GREP pattern selecting the text to style)"
        );
    }
    if (!characterStyleName && !paragraphStyleName) {
        throw new Error(
            "batchApplyStyle requires characterStyleName or paragraphStyleName"
        );
    }

    const docs = allOpenDocuments
        ? app.documents.everyItem().getElements()
        : [getActiveDocument()];

    const perDocument = [];
    for (const doc of docs) {
        app.findGrepPreferences = NothingEnum.NOTHING;
        app.changeGrepPreferences = NothingEnum.NOTHING;
        try {
            app.findGrepPreferences.findWhat = grepFindWhat;
            if (characterStyleName) {
                const cs = doc.allCharacterStyles.find(
                    (s) => s.name === characterStyleName);
                if (!cs) throw new Error(`No character style [${characterStyleName}]`);
                app.changeGrepPreferences.appliedCharacterStyle = cs;
            }
            if (paragraphStyleName) {
                const ps = doc.allParagraphStyles.find(
                    (s) => s.name === paragraphStyleName);
                if (!ps) throw new Error(`No paragraph style [${paragraphStyleName}]`);
                app.changeGrepPreferences.appliedParagraphStyle = ps;
            }
            const changed = doc.changeGrep();
            perDocument.push({ document: doc.name, changedCount: changed.length });
        } catch (e) {
            perDocument.push({ document: doc.name, error: String(e) });
        } finally {
            app.findGrepPreferences = NothingEnum.NOTHING;
            app.changeGrepPreferences = NothingEnum.NOTHING;
        }
    }

    return { perDocument };
};

const commandHandlers = {
    alignItems,
    distributeItems,
    getDocuments,
    setActiveDocument,
    batchApplyStyle,
};

module.exports = { commandHandlers };
