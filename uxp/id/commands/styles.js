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

const { app, Justification, LocationOptions } = require("indesign");

const {
    usePoints,
    getActiveDocument,
    getItemById,
    getStoryById,
    getSwatch,
} = require("./utils.js");

/* -------------------------------------------------------------------------
 * Helpers
 * ---------------------------------------------------------------------- */

const JUSTIFICATION_MAP = () => ({
    LEFT: Justification.LEFT_ALIGN,
    CENTER: Justification.CENTER_ALIGN,
    RIGHT: Justification.RIGHT_ALIGN,
    JUSTIFY: Justification.LEFT_JUSTIFIED,
    FULLY_JUSTIFY: Justification.FULLY_JUSTIFIED,
});

const STYLE_COLLECTIONS = {
    paragraph: { coll: (doc) => doc.paragraphStyles, all: (doc) => doc.allParagraphStyles, groups: (doc) => doc.paragraphStyleGroups },
    character: { coll: (doc) => doc.characterStyles, all: (doc) => doc.allCharacterStyles, groups: (doc) => doc.characterStyleGroups },
    object:    { coll: (doc) => doc.objectStyles,    all: (doc) => doc.allObjectStyles,    groups: (doc) => doc.objectStyleGroups },
    table:     { coll: (doc) => doc.tableStyles,     all: (doc) => doc.allTableStyles,     groups: (doc) => doc.tableStyleGroups },
    cell:      { coll: (doc) => doc.cellStyles,      all: (doc) => doc.allCellStyles,      groups: (doc) => doc.cellStyleGroups },
};

/**
 * Find a style by name across the top-level collection AND style groups.
 */
const findStyle = (doc, styleType, name, required = true) => {
    const def = STYLE_COLLECTIONS[styleType];
    if (!def) {
        throw new Error(
            `Unknown styleType [${styleType}]. Valid: ${Object.keys(STYLE_COLLECTIONS).join(", ")}`
        );
    }
    let style = def.coll(doc).itemByName(name);
    if (style.isValid) return style.getElements()[0];

    // search inside groups via the flat "all*" collection
    const match = def.all(doc).find((s) => s.name === name);
    if (match) return match;

    if (required) {
        const names = def.all(doc).map((s) => s.name);
        throw new Error(
            `No ${styleType} style named [${name}]. Available: ${names.join(", ")}`
        );
    }
    return null;
};

/**
 * Apply a generic properties dict onto a style, resolving *Color/*Swatch
 * values to document swatches. Advanced escape hatch for properties not in
 * the tool signature.
 */
const applyExtraProperties = (doc, style, properties) => {
    if (!properties) return [];
    const applied = [];
    for (const [key, value] of Object.entries(properties)) {
        try {
            if (typeof value === "string" && /color$/i.test(key)) {
                style[key] = getSwatch(doc, value);
            } else {
                style[key] = value;
            }
            applied.push(key);
        } catch (e) {
            throw new Error(`Cannot set style property [${key}]: ${e}`);
        }
    }
    return applied;
};

const describeParagraphStyle = (s) => {
    const out = { name: s.name, type: "paragraph" };
    try {
        out.fontFamily = s.appliedFont && s.appliedFont.fontFamily
            ? s.appliedFont.fontFamily : String(s.appliedFont);
        out.fontStyle = s.fontStyle;
        out.pointSize = s.pointSize;
        out.leading = String(s.leading);
        out.justification = String(s.justification);
        out.spaceBefore = s.spaceBefore;
        out.spaceAfter = s.spaceAfter;
        out.firstLineIndent = s.firstLineIndent;
        out.hyphenation = s.hyphenation;
        out.fillColor = s.fillColor ? s.fillColor.name : null;
        out.basedOn = s.basedOn && s.basedOn.name ? s.basedOn.name : String(s.basedOn);
        out.nextStyle = s.nextStyle && s.nextStyle.name ? s.nextStyle.name : null;
    } catch (e) {
        out.readError = String(e);
    }
    return out;
};

const describeCharacterStyle = (s) => {
    const out = { name: s.name, type: "character" };
    try {
        // character style props are "unset" unless defined — read defensively
        const safe = (k) => { try { const v = s[k]; return v && v.name ? v.name : v; } catch (e) { return undefined; } };
        out.fontFamily = safe("appliedFont");
        out.fontStyle = safe("fontStyle");
        out.pointSize = safe("pointSize");
        out.fillColor = safe("fillColor");
        out.tracking = safe("tracking");
        out.basedOn = safe("basedOn");
    } catch (e) {
        out.readError = String(e);
    }
    return out;
};

/* -------------------------------------------------------------------------
 * Create / edit / delete
 * ---------------------------------------------------------------------- */

const createParagraphStyle = async (command) => {
    usePoints();
    const o = command.options;
    const doc = getActiveDocument();

    let style = findStyle(doc, "paragraph", o.name, false);
    const created = !style;
    if (!style) style = doc.paragraphStyles.add({ name: o.name });

    if (o.fontFamily) {
        style.appliedFont = o.fontStyle
            ? `${o.fontFamily}\t${o.fontStyle}` : o.fontFamily;
    } else if (o.fontStyle) {
        style.fontStyle = o.fontStyle;
    }
    if (o.pointSize != null) style.pointSize = o.pointSize;
    if (o.leading != null) style.leading = o.leading;
    if (o.alignment) {
        const map = JUSTIFICATION_MAP();
        if (!map[o.alignment]) {
            throw new Error(`Unknown alignment [${o.alignment}]. Valid: ${Object.keys(map).join(", ")}`);
        }
        style.justification = map[o.alignment];
    }
    if (o.spaceBefore != null) style.spaceBefore = o.spaceBefore;
    if (o.spaceAfter != null) style.spaceAfter = o.spaceAfter;
    if (o.firstLineIndent != null) style.firstLineIndent = o.firstLineIndent;
    if (o.hyphenation != null) style.hyphenation = o.hyphenation;
    if (o.fillSwatch) style.fillColor = getSwatch(doc, o.fillSwatch);
    if (o.basedOn) style.basedOn = findStyle(doc, "paragraph", o.basedOn);
    if (o.nextStyle) style.nextStyle = findStyle(doc, "paragraph", o.nextStyle);
    applyExtraProperties(doc, style, o.properties);

    return { ...describeParagraphStyle(style), created };
};

const createCharacterStyle = async (command) => {
    usePoints();
    const o = command.options;
    const doc = getActiveDocument();

    let style = findStyle(doc, "character", o.name, false);
    const created = !style;
    if (!style) style = doc.characterStyles.add({ name: o.name });

    if (o.fontFamily) {
        style.appliedFont = o.fontStyle
            ? `${o.fontFamily}\t${o.fontStyle}` : o.fontFamily;
    } else if (o.fontStyle) {
        style.fontStyle = o.fontStyle;
    }
    if (o.pointSize != null) style.pointSize = o.pointSize;
    if (o.tracking != null) style.tracking = o.tracking;
    if (o.fillSwatch) style.fillColor = getSwatch(doc, o.fillSwatch);
    if (o.basedOn) style.basedOn = findStyle(doc, "character", o.basedOn);
    applyExtraProperties(doc, style, o.properties);

    return { ...describeCharacterStyle(style), created };
};

const createObjectStyle = async (command) => {
    usePoints();
    const o = command.options;
    const doc = getActiveDocument();

    let style = findStyle(doc, "object", o.name, false);
    const created = !style;
    if (!style) style = doc.objectStyles.add({ name: o.name });

    if (o.fillSwatch) {
        try { style.enableFill = true; } catch (e) { /* older prop name */ }
        style.fillColor = getSwatch(doc, o.fillSwatch);
    }
    if (o.strokeSwatch) {
        try { style.enableStroke = true; } catch (e) { /* older prop name */ }
        style.strokeColor = getSwatch(doc, o.strokeSwatch);
    }
    if (o.strokeWeight != null) style.strokeWeight = o.strokeWeight;
    if (o.basedOn) style.basedOn = findStyle(doc, "object", o.basedOn);
    applyExtraProperties(doc, style, o.properties);

    return { name: style.name, type: "object", created };
};

const editStyleProperty = async (command) => {
    usePoints();
    const { styleType, styleName, property, value } = command.options;

    const doc = getActiveDocument();
    const style = findStyle(doc, styleType, styleName);

    let resolved = value;
    if (typeof value === "string" && /color$/i.test(property)) {
        resolved = getSwatch(doc, value);
    } else if (property === "basedOn" || property === "nextStyle") {
        resolved = findStyle(doc, styleType, value);
    } else if (property === "justification") {
        const map = JUSTIFICATION_MAP();
        resolved = map[value] ?? value;
    }

    try {
        style[property] = resolved;
    } catch (e) {
        throw new Error(`Cannot set [${property}] on ${styleType} style [${styleName}]: ${e}`);
    }

    return { name: style.name, property, value: String(style[property]) };
};

const deleteStyle = async (command) => {
    const { styleType, styleName, replacementStyleName } = command.options;

    const doc = getActiveDocument();
    const style = findStyle(doc, styleType, styleName);

    if (replacementStyleName) {
        const replacement = findStyle(doc, styleType, replacementStyleName);
        style.remove(replacement);
    } else {
        style.remove();
    }

    return { deleted: styleName, styleType, replacedWith: replacementStyleName ?? null };
};

const createStyleGroup = async (command) => {
    const { styleType, name, styleNames } = command.options;

    const doc = getActiveDocument();
    const def = STYLE_COLLECTIONS[styleType];
    if (!def) {
        throw new Error(
            `Unknown styleType [${styleType}]. Valid: ${Object.keys(STYLE_COLLECTIONS).join(", ")}`
        );
    }

    let group = def.groups(doc).itemByName(name);
    if (!group.isValid) {
        group = def.groups(doc).add({ name });
    } else {
        group = group.getElements()[0];
    }

    const moved = [];
    for (const styleName of styleNames ?? []) {
        const style = findStyle(doc, styleType, styleName);
        style.move(LocationOptions.AT_END, group);
        moved.push(styleName);
    }

    return { group: group.name, styleType, moved };
};

const listStyles = async (command) => {
    const doc = getActiveDocument();

    const paragraph = doc.allParagraphStyles.map(describeParagraphStyle);
    const character = doc.allCharacterStyles.map(describeCharacterStyle);
    const object = doc.allObjectStyles.map((s) => ({ name: s.name, type: "object" }));
    const table = doc.allTableStyles ? doc.allTableStyles.map((s) => ({ name: s.name, type: "table" })) : [];
    const cell = doc.allCellStyles ? doc.allCellStyles.map((s) => ({ name: s.name, type: "cell" })) : [];

    return { paragraph, character, object, table, cell };
};

/* -------------------------------------------------------------------------
 * Apply
 * ---------------------------------------------------------------------- */

const storyStatus = (story) => ({
    storyId: story.id,
    overflows: story.overflows,
    frames: story.textContainers.map((f) => ({ frameId: f.id, overflows: f.overflows })),
});

const applyParagraphStyle = async (command) => {
    const { styleName, storyId, frameId, startParagraph, endParagraph,
            clearOverrides } = command.options;

    const doc = getActiveDocument();
    const style = findStyle(doc, "paragraph", styleName);

    let story;
    if (storyId != null) {
        story = getStoryById(doc, storyId);
    } else if (frameId != null) {
        story = getItemById(doc, frameId).parentStory;
    } else {
        throw new Error("applyParagraphStyle requires storyId or frameId");
    }

    let target;
    if (startParagraph != null) {
        const s = startParagraph;
        const e = endParagraph ?? s;
        if (s < 0 || e >= story.paragraphs.length || s > e) {
            throw new Error(
                `Invalid paragraph range [${s}..${e}] — story has ${story.paragraphs.length} paragraphs`
            );
        }
        target = story.paragraphs.itemByRange(s, e);
    } else {
        target = story.texts.item(0);
    }

    target.appliedParagraphStyle = style;
    if (clearOverrides) {
        try { target.clearOverrides(); } catch (e) { /* best effort */ }
    }

    return { applied: styleName, ...storyStatus(story) };
};

const applyCharacterStyle = async (command) => {
    const { styleName, storyId, startCharacter, endCharacter } = command.options;

    const doc = getActiveDocument();
    const style = findStyle(doc, "character", styleName);
    const story = getStoryById(doc, storyId);

    let target;
    if (startCharacter != null) {
        const s = startCharacter;
        const e = endCharacter ?? s;
        if (s < 0 || e >= story.characters.length || s > e) {
            throw new Error(
                `Invalid character range [${s}..${e}] — story has ${story.characters.length} characters`
            );
        }
        target = story.characters.itemByRange(s, e);
    } else {
        target = story.texts.item(0);
    }

    target.appliedCharacterStyle = style;

    return { applied: styleName, ...storyStatus(story) };
};

const applyObjectStyle = async (command) => {
    const { styleName, itemId, clearOverrides } = command.options;

    const doc = getActiveDocument();
    const style = findStyle(doc, "object", styleName);
    const item = getItemById(doc, itemId);

    item.appliedObjectStyle = style;
    if (clearOverrides) {
        try { item.clearObjectStyleOverrides(); } catch (e) { /* best effort */ }
    }

    return { applied: styleName, itemId: item.id, type: item.constructor.name };
};

const commandHandlers = {
    createParagraphStyle,
    createCharacterStyle,
    createObjectStyle,
    applyParagraphStyle,
    applyCharacterStyle,
    applyObjectStyle,
    listStyles,
    createStyleGroup,
    editStyleProperty,
    deleteStyle,
};

module.exports = { commandHandlers };
