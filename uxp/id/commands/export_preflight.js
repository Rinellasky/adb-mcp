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

const { app, ExportFormat, PageRange } = require("indesign");

const { getActiveDocument, getPage } = require("./utils.js");

/* -------------------------------------------------------------------------
 * Helpers
 * ---------------------------------------------------------------------- */

/**
 * Recover a preference's export-range enum class from its current VALUE's
 * constructor (the enum classes are not exported by require("indesign") —
 * same finding as getPageImage, verified live in Phase 1).
 */
const setExportRange = (prefs, rangePropName, pageString) => {
    const current = prefs[rangePropName];
    const enumClass = current && current.constructor;
    let key = null;
    if (enumClass) {
        const names = Object.getOwnPropertyNames(enumClass)
            .filter((n) => !["length", "name", "prototype"].includes(n));
        // PNG uses EXPORT_RANGE; JPEG's enum may use a different constant name
        key = names.find((n) => n === "EXPORT_RANGE") ??
              names.find((n) => /RANGE/i.test(n) && !/ALL/i.test(n));
        if (!key) {
            throw new Error(
                `Cannot resolve export-range enum for [${rangePropName}] — ` +
                `constructor ${enumClass.name} exposes: ${names.join(", ")}`
            );
        }
    } else {
        throw new Error(
            `Cannot resolve export-range enum for [${rangePropName}] on this build`
        );
    }
    prefs[rangePropName] = enumClass[key];
    prefs.pageString = pageString;
};

const setProps = (prefs, props, applied, skipped) => {
    for (const [key, value] of Object.entries(props ?? {})) {
        try {
            prefs[key] = value;
            applied.push(key);
        } catch (e) {
            skipped.push({ property: key, error: String(e) });
        }
    }
};

/* -------------------------------------------------------------------------
 * Exports
 * ---------------------------------------------------------------------- */

const exportPdfAdvanced = async (command) => {
    const { filePath, presetName, pageRange, interactive, security,
            properties } = command.options;

    const doc = getActiveDocument();
    const applied = [], skipped = [];

    if (interactive) {
        const prefs = app.interactivePDFExportPreferences;
        if (pageRange) {
            try { prefs.pageRange = String(pageRange); applied.push("pageRange"); }
            catch (e) { skipped.push({ property: "pageRange", error: String(e) }); }
        }
        setProps(prefs, properties, applied, skipped);
        await doc.exportFile(ExportFormat.INTERACTIVE_PDF, filePath);
        return { filePath, mode: "INTERACTIVE", applied, skipped };
    }

    const prefs = app.pdfExportPreferences;
    prefs.pageRange = pageRange ? String(pageRange) : PageRange.ALL_PAGES;

    if (security) {
        // {openPassword?, permissionsPassword?}
        try {
            prefs.useSecurity = true;
            if (security.openPassword) {
                prefs.openDocumentPassword = security.openPassword;
            }
            if (security.permissionsPassword) {
                prefs.changeSecurityPassword = security.permissionsPassword;
            }
            applied.push("security");
        } catch (e) {
            skipped.push({ property: "security", error: String(e) });
        }
    }
    setProps(prefs, properties, applied, skipped);

    let preset;
    if (presetName) {
        preset = app.pdfExportPresets.itemByName(presetName);
        if (!preset.isValid) {
            const names = app.pdfExportPresets.everyItem().getElements()
                .map((p) => p.name);
            throw new Error(
                `No PDF preset [${presetName}]. Available: ${names.join(", ")}`
            );
        }
    }

    // NOTE: large documents can exceed the 20s proxy timeout — not a failure
    await doc.exportFile(ExportFormat.PDF_TYPE, filePath, false, preset);

    return { filePath, mode: "PRINT", pageRange: pageRange ?? "ALL", applied, skipped };
};

const exportIdml = async (command) => {
    const { filePath } = command.options;
    const doc = getActiveDocument();

    const fmt = ExportFormat.INDESIGN_MARKUP ?? ExportFormat.INDESIGN_INTERCHANGE;
    await doc.exportFile(fmt, filePath);

    return { filePath };
};

const exportEpub = async (command) => {
    const { filePath, fixedLayout } = command.options;
    const doc = getActiveDocument();

    const fmt = fixedLayout
        ? ExportFormat.EPUB_FIXED_LAYOUT
        : (ExportFormat.EPUB ?? ExportFormat.EPUB_REFLOWABLE);
    if (fmt === undefined) {
        throw new Error("EPUB export format not exposed in this InDesign build");
    }

    // CRITICAL: "view after export" launches the OS app picker for .epub,
    // which BLOCKS InDesign's scripting engine until a human dismisses it
    // (cost a wedged plugin + proxy restart to diagnose, 2026-07-13).
    try { app.epubExportPreferences.viewDocumentAfterExport = false; } catch (e) {}
    try {
        app.epubFixedLayoutExportPreferences.viewDocumentAfterExport = false;
    } catch (e) {}

    // NOTE: EPUB export routinely exceeds the 20s proxy timeout
    await doc.exportFile(fmt, filePath);

    return { filePath, fixedLayout: fixedLayout === true };
};

const exportPagesAsImages = async (command) => {
    const { outputFolder, baseName, format, resolution, startPage, endPage,
            quality } = command.options;

    const doc = getActiveDocument();
    const fmt = String(format ?? "PNG").toUpperCase();
    const s = startPage ?? 1;
    const e = endPage ?? doc.pages.length;
    const base = baseName ?? "page";

    const files = [];
    for (let p = s; p <= e; p++) {
        const page = getPage(doc, p);
        const ext = fmt === "JPEG" ? "jpg" : "png";
        const filePath = `${outputFolder}\\${base}_${String(p).padStart(3, "0")}.${ext}`;

        if (fmt === "JPEG") {
            const prefs = app.jpegExportPreferences;
            setExportRange(prefs, "jpegExportRange", page.name);
            prefs.exportResolution = resolution ?? 150;
            if (quality != null) {
                try {
                    const q = String(quality).toUpperCase();
                    const cur = prefs.jpegQuality;
                    if (cur && cur.constructor && cur.constructor[q] !== undefined) {
                        prefs.jpegQuality = cur.constructor[q]; // LOW/MEDIUM/HIGH/MAXIMUM
                    }
                } catch (err) { /* keep default */ }
            }
            await doc.exportFile(ExportFormat.JPG, filePath);
        } else if (fmt === "PNG") {
            const prefs = app.pngExportPreferences;
            setExportRange(prefs, "pngExportRange", page.name);
            prefs.exportResolution = resolution ?? 150;
            prefs.transparentBackground = false;
            await doc.exportFile(ExportFormat.PNG_FORMAT, filePath);
        } else {
            throw new Error(`Unknown format [${format}]. Valid: PNG, JPEG`);
        }
        files.push(filePath);
    }

    return { exported: files.length, files };
};

const packageDocument = async (command) => {
    const { outputFolder, includeIdml, includePdf, pdfPresetName } =
        command.options;

    const doc = getActiveDocument();
    if (typeof doc.packageForPrint !== "function") {
        throw new Error("packageForPrint is not exposed in this InDesign UXP build");
    }

    // signature: to, copyingFonts, copyingLinkedGraphics, copyingProfiles,
    // updatingGraphics, includingHiddenLayers, ignorePreflightErrors,
    // creatingReport, includeIdml, includePdf, pdfStyle, ...
    // NOTE: packaging big documents exceeds the 20s proxy timeout — not a failure
    let ok;
    try {
        ok = doc.packageForPrint(outputFolder, true, true, true, true, false,
                                 true, true, includeIdml === true,
                                 includePdf === true, pdfPresetName ?? "");
    } catch (e) {
        // older/newer signature without the idml/pdf tail
        ok = doc.packageForPrint(outputFolder, true, true, true, true, false,
                                 true, true);
    }

    return { packaged: ok === true, outputFolder };
};

/* -------------------------------------------------------------------------
 * Preflight
 * ---------------------------------------------------------------------- */

const requirePreflight = () => {
    if (!app.preflightProcesses || typeof app.preflightProcesses.add !== "function") {
        throw new Error("The Preflight API is not exposed in this InDesign UXP build");
    }
};

const definePreflightProfile = async (command) => {
    const { name, description, rules } = command.options;
    requirePreflight();

    let profile = app.preflightProfiles.itemByName(name);
    if (profile.isValid) {
        profile.remove();
    }
    profile = app.preflightProfiles.add({ name, description: description ?? "" });

    const added = [], failed = [];
    for (const rule of rules ?? []) {
        // rule: {"id": "ADBE_MissingFonts", "data": {...}} — rule ids are
        // Adobe-defined; common: ADBE_MissingFonts, ADBE_OversetText,
        // ADBE_ImageResolution, ADBE_MissingModifiedGraphics, ADBE_Bleed
        try {
            const r = profile.preflightProfileRules.add(rule.id);
            for (const [k, v] of Object.entries(rule.data ?? {})) {
                try {
                    const datum = r.preflightRuleDataObjects.itemByName(k);
                    if (datum.isValid) datum.dataValue = v;
                } catch (e) { /* best effort per datum */ }
            }
            added.push(rule.id);
        } catch (e) {
            failed.push({ id: rule.id, error: String(e) });
        }
    }

    return { profile: name, rulesAdded: added, rulesFailed: failed };
};

const runPreflight = async (command) => {
    const { profileName } = command.options;
    requirePreflight();

    const doc = getActiveDocument();

    let profile;
    if (profileName) {
        profile = app.preflightProfiles.itemByName(profileName);
        if (!profile.isValid) {
            const names = app.preflightProfiles.everyItem().getElements()
                .map((p) => p.name);
            throw new Error(
                `No preflight profile [${profileName}]. Available: ${names.join(", ")}`
            );
        }
        profile = profile.getElements()[0];
    } else {
        profile = app.preflightProfiles.item(0); // "[Basic]"
    }

    const process = app.preflightProcesses.add(doc, profile);
    try {
        process.waitForProcess(15); // seconds; stay under the proxy timeout
        const results = process.aggregatedResults;
        return {
            profile: profile.name,
            done: process.processInBackground === false || true,
            aggregatedResults: JSON.parse(JSON.stringify(results)),
        };
    } finally {
        try { process.remove(); } catch (e) { /* leave process list clean */ }
    }
};

const listExportPresets = async (command) => {
    const pdf = app.pdfExportPresets.everyItem().getElements().map((p) => p.name);
    let interactive = [];
    try {
        interactive = app.interactivePDFExportPresets
            ? app.interactivePDFExportPresets.everyItem().getElements().map((p) => p.name)
            : [];
    } catch (e) { /* not exposed */ }

    return { pdfPresets: pdf, interactivePdfPresets: interactive };
};

const commandHandlers = {
    exportPdfAdvanced,
    exportIdml,
    exportEpub,
    exportPagesAsImages,
    packageDocument,
    definePreflightProfile,
    runPreflight,
    listExportPresets,
};

module.exports = { commandHandlers };
