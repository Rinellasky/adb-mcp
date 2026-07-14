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
    LocationOptions,
    HorizontalOrVertical,
    PageNumberStyle,
    UIColors,
} = require("indesign");

const { usePoints, getActiveDocument, getPage, getLayerByName } = require("./utils.js");

/* -------------------------------------------------------------------------
 * Pages
 * ---------------------------------------------------------------------- */

const addPages = async (command) => {
    const { count, afterPageNumber } = command.options;

    const doc = getActiveDocument();
    const n = count ?? 1;

    let ref =
        afterPageNumber != null ? getPage(doc, afterPageNumber) : doc.pages.lastItem();

    const added = [];
    for (let i = 0; i < n; i++) {
        ref = doc.pages.add(LocationOptions.AFTER, ref);
        added.push(ref.name);
    }

    return { addedPages: added, pageCount: doc.pages.length };
};

const removePage = async (command) => {
    const { pageNumber } = command.options;

    const doc = getActiveDocument();
    if (doc.pages.length === 1) {
        throw new Error("Cannot remove the only page in the document");
    }
    const page = getPage(doc, pageNumber);
    const name = page.name;
    page.remove();

    return { removedPage: name, pageCount: doc.pages.length };
};

const duplicatePage = async (command) => {
    const { pageNumber, afterPageNumber } = command.options;

    const doc = getActiveDocument();
    const page = getPage(doc, pageNumber);
    const ref =
        afterPageNumber != null ? getPage(doc, afterPageNumber) : page;

    const dup = page.duplicate(LocationOptions.AFTER, ref);

    return { duplicatedPage: page.name, newPage: dup.name, pageCount: doc.pages.length };
};

const setPageNumbering = async (command) => {
    const { pageNumber, startAt, style, prefix } = command.options;

    const doc = getActiveDocument();
    const page = getPage(doc, pageNumber);

    const styleMap = {
        ARABIC: PageNumberStyle.ARABIC,
        LOWER_ROMAN: PageNumberStyle.LOWER_ROMAN,
        UPPER_ROMAN: PageNumberStyle.UPPER_ROMAN,
        LOWER_LETTERS: PageNumberStyle.LOWER_LETTERS,
        UPPER_LETTERS: PageNumberStyle.UPPER_LETTERS,
    };

    if (style && !styleMap[style]) {
        throw new Error(
            `Unknown numbering style [${style}]. Valid: ${Object.keys(styleMap).join(", ")}`
        );
    }

    const props = { continueNumbering: false };
    if (startAt != null) props.pageNumberStart = startAt;
    if (style) props.pageNumberStyle = styleMap[style];
    if (prefix) props.sectionPrefix = prefix;

    const section = doc.sections.add(page, props);

    return {
        sectionStartPage: page.name,
        startAt: startAt ?? 1,
        style: style ?? "ARABIC",
        prefix: prefix ?? "",
        sectionCount: doc.sections.length,
    };
};

/* -------------------------------------------------------------------------
 * Layers
 * ---------------------------------------------------------------------- */

const LAYER_COLORS = [
    "BLUE", "RED", "GREEN", "YELLOW", "MAGENTA", "CYAN", "ORANGE",
    "DARK_GREEN", "TEAL", "TAN", "BROWN", "VIOLET", "GOLD", "DARK_BLUE",
    "PINK", "LAVENDER", "BRICK_RED", "OLIVE_GREEN", "PEACH", "BURGUNDY",
    "GRASS_GREEN", "OCHRE", "PURPLE", "LIGHT_GRAY", "CHARCOAL", "GRID_GREEN",
    "GRID_ORANGE", "FIESTA", "LIGHT_OLIVE", "LIPSTICK", "CUTE_TEAL",
    "SULPHUR", "GRID_BLUE",
];

const createLayer = async (command) => {
    const { name, color } = command.options;

    const doc = getActiveDocument();

    if (doc.layers.itemByName(name).isValid) {
        throw new Error(`A layer named [${name}] already exists`);
    }

    const props = { name };
    if (color) {
        if (!LAYER_COLORS.includes(color) || !UIColors[color]) {
            throw new Error(`Unknown layer color [${color}]. Valid: ${LAYER_COLORS.join(", ")}`);
        }
        props.layerColor = UIColors[color];
    }

    const layer = doc.layers.add(props);

    return { name: layer.name, layerCount: doc.layers.length };
};

const setLayerProperties = async (command) => {
    const { layerName, newName, locked, visible, color } = command.options;

    const doc = getActiveDocument();
    const layer = getLayerByName(doc, layerName);

    if (locked != null) layer.locked = locked;
    if (visible != null) layer.visible = visible;
    if (color) {
        if (!LAYER_COLORS.includes(color) || !UIColors[color]) {
            throw new Error(`Unknown layer color [${color}]. Valid: ${LAYER_COLORS.join(", ")}`);
        }
        layer.layerColor = UIColors[color];
    }
    if (newName) layer.name = newName;

    return {
        name: layer.name,
        locked: layer.locked,
        visible: layer.visible,
    };
};

const deleteLayer = async (command) => {
    const { layerName } = command.options;

    const doc = getActiveDocument();
    if (doc.layers.length === 1) {
        throw new Error("Cannot delete the only layer in the document");
    }
    const layer = getLayerByName(doc, layerName);
    layer.remove();

    return { deletedLayer: layerName, layerCount: doc.layers.length };
};

/* -------------------------------------------------------------------------
 * Guides
 * ---------------------------------------------------------------------- */

const addGuide = async (command) => {
    usePoints();
    const { pageNumber, orientation, location } = command.options;

    const doc = getActiveDocument();
    const page = getPage(doc, pageNumber);

    const o = String(orientation).toUpperCase();
    if (o !== "HORIZONTAL" && o !== "VERTICAL") {
        throw new Error(`orientation must be HORIZONTAL or VERTICAL, got [${orientation}]`);
    }

    const guide = page.guides.add(undefined, {
        orientation:
            o === "HORIZONTAL"
                ? HorizontalOrVertical.HORIZONTAL
                : HorizontalOrVertical.VERTICAL,
        location: location,
    });

    return { pageNumber, orientation: o, location, guideCount: page.guides.length };
};

const commandHandlers = {
    addPages,
    removePage,
    duplicatePage,
    setPageNumbering,
    createLayer,
    setLayerProperties,
    deleteLayer,
    addGuide,
};

module.exports = { commandHandlers };
