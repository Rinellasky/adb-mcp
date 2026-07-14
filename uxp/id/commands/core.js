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

const {
    app,
    DocumentIntentOptions,
    ExportFormat,
    SaveOptions,
    PageRange,
} = require("indesign");

const {
    usePoints,
    getActiveDocument,
    getPage,
    describePageItem,
} = require("./utils.js");

/* -------------------------------------------------------------------------
 * Document lifecycle
 * ---------------------------------------------------------------------- */

const INTENTS = {
    WEB_INTENT: { intent: () => DocumentIntentOptions.WEB_INTENT, unit: "px" },
    PRINT_INTENT: { intent: () => DocumentIntentOptions.PRINT_INTENT, unit: "pt" },
    MOBILE_INTENT: { intent: () => DocumentIntentOptions.MOBILE_INTENT, unit: "px" },
};

const createDocument = async (command) => {
    const options = command.options;

    const intentName = options.intent || "WEB_INTENT";
    const intentDef = INTENTS[intentName];
    if (!intentDef) {
        throw new Error(
            `Unknown intent [${intentName}]. Valid: ${Object.keys(INTENTS).join(", ")}`
        );
    }
    const unit = intentDef.unit;

    const margins = options.margins;
    app.marginPreferences.top = `${margins.top}${unit}`;
    app.marginPreferences.bottom = `${margins.bottom}${unit}`;
    app.marginPreferences.left = `${margins.left}${unit}`;
    app.marginPreferences.right = `${margins.right}${unit}`;

    app.marginPreferences.columnCount = options.columns.count;
    app.marginPreferences.columnGutter = `${options.columns.gutter}${unit}`;

    const documentPreferences = {
        pageWidth: `${options.pageWidth}${unit}`,
        pageHeight: `${options.pageHeight}${unit}`,
        pagesPerDocument: options.pagesPerDocument,
        facingPages: options.facingPages,
        intent: intentDef.intent(),
    };

    const showingWindow = true;
    const doc = app.documents.add({ showingWindow, documentPreferences });

    return {
        name: doc.name,
        intent: intentName,
        unit: unit,
        pages: doc.pages.length,
        pageWidth: options.pageWidth,
        pageHeight: options.pageHeight,
        facingPages: options.facingPages === true,
    };
};

const openDocument = async (command) => {
    const { filePath } = command.options;
    const doc = await app.open(filePath);
    return { name: doc.name, pages: doc.pages.length };
};

const saveDocument = async (command) => {
    const doc = getActiveDocument();
    if (!doc.saved && !doc.modified) {
        return { name: doc.name, saved: true, note: "No changes to save" };
    }
    if (!doc.saved) {
        throw new Error(
            "Document has never been saved. Use saveDocumentAs with a filePath."
        );
    }
    doc.save();
    // doc.fullName is a Promise resolving to a file entry under UXP —
    // await it and use nativePath (verified live)
    let filePath = null;
    try {
        const fn = await doc.fullName;
        filePath = fn && fn.nativePath ? fn.nativePath : String(fn);
    } catch (e) { /* leave null */ }
    return { name: doc.name, filePath, saved: doc.saved };
};

const saveDocumentAs = async (command) => {
    const { filePath } = command.options;
    const doc = getActiveDocument();
    doc.save(filePath);
    return { name: doc.name, filePath: filePath, saved: doc.saved };
};

const closeDocument = async (command) => {
    const { save } = command.options;
    const doc = getActiveDocument();
    const name = doc.name;
    doc.close(save ? SaveOptions.YES : SaveOptions.NO);
    return { closed: name, remainingDocuments: app.documents.length };
};

/* -------------------------------------------------------------------------
 * Deep read + visual feedback
 * ---------------------------------------------------------------------- */

const getDocumentInfo = async (command) => {
    usePoints();

    const doc = getActiveDocument();
    const pages = [];

    for (const page of doc.pages.everyItem().getElements()) {
        const items = [];
        for (const item of page.allPageItems) {
            items.push(describePageItem(item));
        }
        pages.push({
            name: page.name,
            appliedMaster: page.appliedMaster ? page.appliedMaster.name : null,
            bounds: {
                top: page.bounds[0],
                left: page.bounds[1],
                bottom: page.bounds[2],
                right: page.bounds[3],
            },
            items,
        });
    }

    const names = (collection) =>
        collection.everyItem().getElements().map((s) => s.name);

    return {
        name: doc.name,
        saved: doc.saved,
        modified: doc.modified,
        pageCount: doc.pages.length,
        facingPages: doc.documentPreferences.facingPages,
        pages,
        paragraphStyles: names(doc.paragraphStyles),
        characterStyles: names(doc.characterStyles),
        objectStyles: names(doc.objectStyles),
        swatches: names(doc.swatches),
        layers: names(doc.layers),
        masterSpreads: names(doc.masterSpreads),
    };
};

const getPageImage = async (command) => {
    const { pageNumber, resolution, filePath } = command.options;

    const doc = getActiveDocument();
    const page = getPage(doc, pageNumber); // validates the page number

    // PNGOptionsExportRange is NOT exported by require("indesign") in
    // ID 2026 (verified live via debugEnums). Recover the enum class from
    // the current preference VALUE's constructor instead — enum values are
    // instances of their enum class, which carries the static constants.
    const idModule = require("indesign");
    let rangeEnum =
        idModule.PNGOptionsExportRange ??
        idModule.PNGOptionsExportRangeEnum ??
        idModule.ExportRangeOrAllPages;
    if (!rangeEnum || rangeEnum.EXPORT_RANGE === undefined) {
        const current = app.pngExportPreferences.pngExportRange;
        if (current && current.constructor &&
            current.constructor.EXPORT_RANGE !== undefined) {
            rangeEnum = current.constructor;
        }
    }
    if (!rangeEnum || rangeEnum.EXPORT_RANGE === undefined) {
        throw new Error(
            "PNG export-range enum not found on this InDesign build — " +
            "run the debugEnums command with filter 'PNG' and report the result"
        );
    }
    app.pngExportPreferences.pngExportRange = rangeEnum.EXPORT_RANGE;
    app.pngExportPreferences.pageString = page.name;
    app.pngExportPreferences.exportResolution = resolution ?? 72;
    app.pngExportPreferences.transparentBackground = false;

    await doc.exportFile(ExportFormat.PNG_FORMAT, filePath);

    return { filePath: filePath, pageNumber: pageNumber };
};

const exportPdf = async (command) => {
    const { filePath, presetName, pageRange } = command.options;

    const doc = getActiveDocument();

    app.pdfExportPreferences.pageRange = pageRange
        ? String(pageRange)
        : PageRange.ALL_PAGES;

    let preset = undefined;
    if (presetName) {
        preset = app.pdfExportPresets.itemByName(presetName);
        if (!preset.isValid) {
            const names = app.pdfExportPresets
                .everyItem()
                .getElements()
                .map((p) => p.name);
            throw new Error(
                `No PDF export preset named [${presetName}]. Available: ${names.join(", ")}`
            );
        }
    }

    // NOTE: export/packaging/preflight can exceed the 20s proxy timeout on
    // real documents — a timeout does NOT mean the export failed.
    await doc.exportFile(ExportFormat.PDF_TYPE, filePath, false, preset);

    return { filePath: filePath, pageRange: pageRange ?? "ALL" };
};

/* -------------------------------------------------------------------------
 * Health check / settings (also appended to every command response)
 * ---------------------------------------------------------------------- */

const getActiveDocumentSettings = () => {
    // Must NEVER throw — main.js appends this to every command response,
    // including when no document is open (e.g. right after closeDocument).
    try {
        if (app.documents.length === 0) {
            return null;
        }

        const document = app.activeDocument;
        const d = document.documentPreferences;

        const documentPreferences = {
            pageWidth: d.pageWidth,
            pageHeight: d.pageHeight,
            pagesPerDocument: d.pagesPerDocument,
            facingPages: d.facingPages,
            intent: String(d.intent),
        };

        const m = document.marginPreferences;
        const marginPreferences = {
            top: m.top,
            bottom: m.bottom,
            left: m.left,
            right: m.right,
            columnCount: m.columnCount,
            columnGutter: m.columnGutter,
        };

        return { name: document.name, documentPreferences, marginPreferences };
    } catch (e) {
        return { error: String(e) };
    }
};

/**
 * Introspection helper (not exposed as an MCP tool): lists the enum/class
 * names exported by require("indesign") matching a filter, with their keys.
 * Used to resolve enum-name differences between InDesign builds.
 */
const debugEnums = async (command) => {
    const filter = (command.options.filter ?? "").toLowerCase();
    const idModule = require("indesign");
    const out = {};
    for (const k of Object.keys(idModule)) {
        if (!k.toLowerCase().includes(filter)) continue;
        try {
            // Enum statics are non-enumerable — Object.keys returns [] —
            // so use getOwnPropertyNames (verified live).
            out[k] = Object.getOwnPropertyNames(idModule[k])
                .filter((n) => !["length", "name", "prototype"].includes(n))
                .slice(0, 40);
        } catch (e) {
            out[k] = String(typeof idModule[k]);
        }
        if (Object.keys(out).length >= 40) break;
    }
    return out;
};

const commandHandlers = {
    createDocument,
    debugEnums,
    openDocument,
    saveDocument,
    saveDocumentAs,
    closeDocument,
    getDocumentInfo,
    getPageImage,
    exportPdf,
    getActiveDocumentSettings: async () => getActiveDocumentSettings(),
};

module.exports = {
    commandHandlers,
    getActiveDocumentSettings,
};
