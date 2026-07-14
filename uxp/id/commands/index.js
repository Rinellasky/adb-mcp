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

const { app } = require("indesign");

const core = require("./core.js");
const pages = require("./pages.js");
const text = require("./text.js");
const shapes = require("./shapes.js");
const styles = require("./styles.js");
const findchange = require("./findchange.js");
const mastersTables = require("./masters_tables.js");
const typography = require("./typography.js");
const longdoc = require("./longdoc.js");
const mergeTemplates = require("./merge_templates.js");
const exportPreflight = require("./export_preflight.js");
const geometryDocs = require("./geometry_docs.js");

const commandHandlers = {
    ...core.commandHandlers,
    ...pages.commandHandlers,
    ...text.commandHandlers,
    ...shapes.commandHandlers,
    ...styles.commandHandlers,
    ...findchange.commandHandlers,
    ...mastersTables.commandHandlers,
    ...typography.commandHandlers,
    ...longdoc.commandHandlers,
    ...mergeTemplates.commandHandlers,
    ...exportPreflight.commandHandlers,
    ...geometryDocs.commandHandlers,
};

const parseAndRouteCommand = async (command) => {
    let action = command.action;

    let f = commandHandlers[action];

    if (typeof f !== "function") {
        throw new Error(`Unknown Command: ${action}`);
    }

    console.log(f.name || action);
    return f(command);
};

/**
 * Commands that do NOT require an open document.
 */
const requiresActiveDocument = (command) => {
    return ![
        "createDocument", "openDocument", "getActiveDocumentSettings",
        "openAsTemplate", "createBook", "manageBook", "getDocuments",
        "setActiveDocument", "listExportPresets", "debugEnums",
    ].includes(command.action);
};

const checkRequiresActiveDocument = async (command) => {
    if (!requiresActiveDocument(command)) {
        return;
    }

    if (app.documents.length === 0) {
        throw new Error(
            `${command.action} : Requires an open InDesign document`
        );
    }
};

module.exports = {
    getActiveDocumentSettings: core.getActiveDocumentSettings,
    checkRequiresActiveDocument,
    parseAndRouteCommand,
};
