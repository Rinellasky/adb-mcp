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

const { app, SpecialCharacters, LocationOptions } = require("indesign");

const {
    usePoints,
    getActiveDocument,
    getPage,
    getStoryById,
    getItemById,
    getSwatch,
    boundsToArray,
    textFrameStatus,
} = require("./utils.js");

/* -------------------------------------------------------------------------
 * Master pages
 * ---------------------------------------------------------------------- */

const findMasterSpread = (doc, name) => {
    // accept "B-Section" or bare base name "Section"
    const masters = doc.masterSpreads.everyItem().getElements();
    const match = masters.find((m) => m.name === name || m.baseName === name);
    if (!match) {
        throw new Error(
            `No master spread named [${name}]. Available: ${masters.map((m) => m.name).join(", ")}`
        );
    }
    return match;
};

const createMasterSpread = async (command) => {
    usePoints();
    const { namePrefix, baseName, basedOnMaster, placeholders } = command.options;

    const doc = getActiveDocument();

    const props = {};
    if (namePrefix) props.namePrefix = namePrefix;
    if (baseName) props.baseName = baseName;

    const master = doc.masterSpreads.add(undefined, props);
    if (basedOnMaster) {
        master.appliedMaster = findMasterSpread(doc, basedOnMaster);
    }

    const created = [];
    for (const ph of placeholders ?? []) {
        // ph: {pageIndex (0-based within spread), bounds, type:
        //      "TEXT" | "PAGE_NUMBER" | "RECTANGLE", contents?, fillSwatch?}
        const pages = master.pages.everyItem().getElements();
        const page = pages[ph.pageIndex ?? 0];
        if (!page) {
            throw new Error(
                `Master spread has ${pages.length} page(s); pageIndex ${ph.pageIndex} is out of range`
            );
        }

        const type = String(ph.type ?? "TEXT").toUpperCase();
        if (type === "RECTANGLE") {
            const rect = page.rectangles.add({
                geometricBounds: boundsToArray(ph.bounds),
            });
            if (ph.fillSwatch) rect.fillColor = getSwatch(doc, ph.fillSwatch);
            created.push({ itemId: rect.id, type: "Rectangle" });
        } else {
            const frame = page.textFrames.add({
                geometricBounds: boundsToArray(ph.bounds),
            });
            if (type === "PAGE_NUMBER") {
                frame.insertionPoints.item(0).contents =
                    SpecialCharacters.AUTO_PAGE_NUMBER;
            } else if (ph.contents) {
                frame.contents = ph.contents;
            }
            created.push({ itemId: frame.id, type: "TextFrame" });
        }
    }

    return {
        name: master.name,
        baseName: master.baseName,
        pages: master.pages.length,
        placeholders: created,
    };
};

const applyMaster = async (command) => {
    const { masterName, startPage, endPage } = command.options;

    const doc = getActiveDocument();
    const master = masterName ? findMasterSpread(doc, masterName) : null;

    const s = startPage ?? 1;
    const e = endPage ?? s;
    const applied = [];
    for (let p = s; p <= e; p++) {
        const page = getPage(doc, p);
        page.appliedMaster = master; // null = [None]
        applied.push(page.name);
    }

    return { master: master ? master.name : null, appliedToPages: applied };
};

const overrideMasterItem = async (command) => {
    const { itemId, pageNumber } = command.options;

    const doc = getActiveDocument();
    const page = getPage(doc, pageNumber);

    // master items are NOT in doc.pageItems — search the applied master
    let masterItem = null;
    const master = page.appliedMaster;
    if (master) {
        masterItem = master.pages.everyItem().getElements()
            .flatMap((p) => p.allPageItems)
            .find((i) => i.id === parseInt(itemId));
    }
    if (!masterItem) {
        throw new Error(
            `Item [${itemId}] not found on the master applied to page ${pageNumber}` +
            (master ? ` (${master.name})` : " (page has no master)")
        );
    }

    const overridden = masterItem.override(page);

    return {
        overriddenItemId: overridden.id,
        type: overridden.constructor.name,
        pageNumber,
    };
};

/* -------------------------------------------------------------------------
 * Tables
 * ---------------------------------------------------------------------- */

const getTable = (doc, storyId, tableIndex) => {
    const story = getStoryById(doc, storyId);
    const idx = tableIndex ?? 0;
    if (idx < 0 || idx >= story.tables.length) {
        throw new Error(
            `Story ${storyId} has ${story.tables.length} table(s); tableIndex ${idx} is out of range`
        );
    }
    return { story, table: story.tables.item(idx) };
};

const createTable = async (command) => {
    usePoints();
    const { storyId, frameId, pageNumber, bounds, data, headerRows,
            columnWidths } = command.options;

    const doc = getActiveDocument();

    if (!Array.isArray(data) || data.length === 0 || !Array.isArray(data[0])) {
        throw new Error("createTable requires data as a non-empty 2D array [[row],[row],...]");
    }

    // resolve the insertion point: existing story, existing frame, or a new
    // frame from pageNumber+bounds
    let story;
    if (storyId != null) {
        story = getStoryById(doc, storyId);
    } else if (frameId != null) {
        story = getItemById(doc, frameId).parentStory;
    } else if (pageNumber != null && bounds) {
        const page = getPage(doc, pageNumber);
        const frame = page.textFrames.add({
            geometricBounds: boundsToArray(bounds),
        });
        story = frame.parentStory;
    } else {
        throw new Error(
            "createTable requires storyId, frameId, or pageNumber+bounds"
        );
    }

    const nHeader = headerRows ?? 0;
    const table = story.insertionPoints.item(-1).tables.add({
        headerRowCount: nHeader,
        bodyRowCount: data.length - nHeader,
        columnCount: data[0].length,
    });

    // fill contents row-major (rows collection includes header rows first)
    for (let r = 0; r < data.length; r++) {
        for (let c = 0; c < data[r].length; c++) {
            table.rows.item(r).cells.item(c).contents = String(data[r][c]);
        }
    }

    if (Array.isArray(columnWidths)) {
        columnWidths.forEach((w, i) => {
            if (w != null && i < table.columns.length) {
                table.columns.item(i).width = w;
            }
        });
    }

    const frames = story.textContainers;
    return {
        storyId: story.id,
        tableIndex: story.tables.length - 1,
        rows: table.rows.length,
        columns: table.columns.length,
        headerRows: nHeader,
        overflows: story.overflows,
        frameId: frames.length ? frames[0].id : null,
    };
};

const setCellContents = async (command) => {
    const { storyId, tableIndex, cells } = command.options;

    const doc = getActiveDocument();
    const { story, table } = getTable(doc, storyId, tableIndex);

    if (!Array.isArray(cells) || cells.length === 0) {
        throw new Error(
            'setCellContents requires cells: [{"row": r, "column": c, "contents": "..."}, ...]'
        );
    }

    const updated = [];
    for (const cell of cells) {
        const { row, column, contents } = cell;
        if (row == null || column == null ||
            row >= table.rows.length || column >= table.columns.length) {
            throw new Error(
                `Cell [${row},${column}] out of range — table is ` +
                `${table.rows.length}x${table.columns.length} (0-based)`
            );
        }
        table.rows.item(row).cells.item(column).contents = String(contents);
        updated.push([row, column]);
    }

    return { updatedCells: updated.length, overflows: story.overflows };
};

const addTableRowsColumns = async (command) => {
    const { storyId, tableIndex, addRows, addColumns, position } = command.options;

    const doc = getActiveDocument();
    const { table } = getTable(doc, storyId, tableIndex);

    const loc = String(position ?? "END").toUpperCase() === "BEGINNING"
        ? LocationOptions.AT_BEGINNING : LocationOptions.AT_END;

    for (let i = 0; i < (addRows ?? 0); i++) table.rows.add(loc);
    for (let i = 0; i < (addColumns ?? 0); i++) table.columns.add(loc);

    return { rows: table.rows.length, columns: table.columns.length };
};

const mergeCells = async (command) => {
    const { storyId, tableIndex, startRow, startColumn, endRow, endColumn } =
        command.options;

    const doc = getActiveDocument();
    const { table } = getTable(doc, storyId, tableIndex);

    const from = table.rows.item(startRow).cells.item(startColumn);
    const to = table.rows.item(endRow).cells.item(endColumn);
    from.merge(to);

    return {
        merged: `[${startRow},${startColumn}]..[${endRow},${endColumn}]`,
        rows: table.rows.length,
        columns: table.columns.length,
    };
};

const createTableStyle = async (command) => {
    const o = command.options;
    const doc = getActiveDocument();

    let style = doc.tableStyles.itemByName(o.name);
    const created = !style.isValid;
    if (created) {
        style = doc.tableStyles.add({ name: o.name });
    } else {
        style = style.getElements()[0];
    }

    // properties passthrough — table style props vary a lot; resolve swatches
    for (const [key, value] of Object.entries(o.properties ?? {})) {
        try {
            style[key] = (typeof value === "string" && /color$/i.test(key))
                ? getSwatch(doc, value) : value;
        } catch (e) {
            throw new Error(`Cannot set table style property [${key}]: ${e}`);
        }
    }

    return { name: style.name, created };
};

const createCellStyle = async (command) => {
    const o = command.options;
    const doc = getActiveDocument();

    let style = doc.cellStyles.itemByName(o.name);
    const created = !style.isValid;
    if (created) {
        style = doc.cellStyles.add({ name: o.name });
    } else {
        style = style.getElements()[0];
    }

    if (o.fillSwatch) style.fillColor = getSwatch(doc, o.fillSwatch);
    if (o.fillTint != null) style.fillTint = o.fillTint;
    for (const [key, value] of Object.entries(o.properties ?? {})) {
        try {
            style[key] = (typeof value === "string" && /color$/i.test(key))
                ? getSwatch(doc, value) : value;
        } catch (e) {
            throw new Error(`Cannot set cell style property [${key}]: ${e}`);
        }
    }

    return { name: style.name, created };
};

const applyTableStyle = async (command) => {
    const { storyId, tableIndex, tableStyleName, region, cellStyleName,
            alternatingFills } = command.options;

    const doc = getActiveDocument();
    const { table } = getTable(doc, storyId, tableIndex);

    const out = { applied: [] };

    if (tableStyleName) {
        const style = doc.tableStyles.itemByName(tableStyleName);
        if (!style.isValid) {
            throw new Error(`No table style named [${tableStyleName}]`);
        }
        table.appliedTableStyle = style;
        out.applied.push(`table:${tableStyleName}`);
    }

    if (cellStyleName) {
        const cstyle = doc.cellStyles.itemByName(cellStyleName);
        if (!cstyle.isValid) {
            throw new Error(`No cell style named [${cellStyleName}]`);
        }
        const target = String(region ?? "ALL").toUpperCase();
        let cells;
        if (target === "HEADER") {
            cells = [];
            for (let r = 0; r < table.headerRowCount; r++) {
                cells.push(...table.rows.item(r).cells.everyItem().getElements());
            }
        } else {
            cells = table.cells.everyItem().getElements();
        }
        for (const cell of cells) cell.appliedCellStyle = cstyle;
        out.applied.push(`cell:${cellStyleName} (${target})`);
    }

    if (alternatingFills) {
        // {swatch, tint?, frequency?} — apply to every 2nd body row directly
        const swatch = getSwatch(doc, alternatingFills.swatch);
        const freq = alternatingFills.frequency ?? 2;
        const startRow = table.headerRowCount;
        for (let r = startRow; r < table.rows.length; r++) {
            if ((r - startRow) % freq === freq - 1) {
                for (const cell of table.rows.item(r).cells.everyItem().getElements()) {
                    cell.fillColor = swatch;
                    if (alternatingFills.tint != null) {
                        cell.fillTint = alternatingFills.tint;
                    }
                }
            }
        }
        out.applied.push(`alternatingFills:${alternatingFills.swatch}`);
    }

    return out;
};

const commandHandlers = {
    createMasterSpread,
    applyMaster,
    overrideMasterItem,
    createTable,
    setCellContents,
    addTableRowsColumns,
    mergeCells,
    createTableStyle,
    createCellStyle,
    applyTableStyle,
};

module.exports = { commandHandlers };
