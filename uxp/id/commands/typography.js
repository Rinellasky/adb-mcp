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
    SpecialCharacters,
    TextWrapModes,
    AnchorPosition,
    AnchoredRelativeTo,
    ListType,
    SingleWordJustification,
} = require("indesign");

const {
    usePoints,
    getActiveDocument,
    getItemById,
    getStoryById,
    boundsToArray,
} = require("./utils.js");

/* -------------------------------------------------------------------------
 * Helpers
 * ---------------------------------------------------------------------- */

const findParagraphStyle = (doc, name) => {
    const match = doc.allParagraphStyles.find((s) => s.name === name);
    if (!match) {
        throw new Error(`No paragraph style named [${name}]`);
    }
    return match;
};

const findCharacterStyle = (doc, name) => {
    const match = doc.allCharacterStyles.find((s) => s.name === name);
    if (!match) {
        throw new Error(`No character style named [${name}]`);
    }
    return match;
};

/**
 * Resolve the styling target: a paragraph style (styleName) or a paragraph
 * range of a story (storyId + optional start/end paragraph indices).
 */
const resolveTarget = (doc, o) => {
    if (o.styleName) {
        return { target: findParagraphStyle(doc, o.styleName), story: null };
    }
    if (o.storyId != null) {
        const story = getStoryById(doc, o.storyId);
        let target;
        if (o.startParagraph != null) {
            const s = o.startParagraph;
            const e = o.endParagraph ?? s;
            if (s < 0 || e >= story.paragraphs.length || s > e) {
                throw new Error(
                    `Invalid paragraph range [${s}..${e}] — story has ${story.paragraphs.length} paragraphs`
                );
            }
            target = story.paragraphs.itemByRange(s, e);
        } else {
            target = story.texts.item(0);
        }
        return { target, story };
    }
    throw new Error("Requires styleName (a paragraph style) or storyId");
};

const storyStatus = (story) => story ? {
    storyId: story.id,
    overflows: story.overflows,
} : {};

/* -------------------------------------------------------------------------
 * Handlers
 * ---------------------------------------------------------------------- */

const setBaselineGrid = async (command) => {
    usePoints();
    const { start, increment, shown, viewThreshold } = command.options;

    const doc = getActiveDocument();
    const prefs = doc.gridPreferences;

    if (start != null) prefs.baselineStart = start;
    if (increment != null) prefs.baselineDivision = increment;
    if (shown != null) prefs.baselinesShown = shown;
    if (viewThreshold != null) prefs.baselineViewThreshold = viewThreshold;

    return {
        baselineStart: prefs.baselineStart,
        baselineDivision: prefs.baselineDivision,
        baselinesShown: prefs.baselinesShown,
    };
};

const setAlignToBaseline = async (command) => {
    const o = command.options;
    const doc = getActiveDocument();
    const { target, story } = resolveTarget(doc, o);

    target.alignToBaseline = o.align !== false;

    return { alignToBaseline: o.align !== false, ...storyStatus(story) };
};

const setTextWrap = async (command) => {
    usePoints();
    const { itemId, mode, offsets } = command.options;

    const doc = getActiveDocument();
    const item = getItemById(doc, itemId);

    const map = {
        NONE: TextWrapModes.NONE,
        BOUNDING_BOX: TextWrapModes.BOUNDING_BOX_TEXT_WRAP,
        CONTOUR: TextWrapModes.CONTOUR,
        JUMP_OBJECT: TextWrapModes.JUMP_OBJECT_TEXT_WRAP,
        NEXT_COLUMN: TextWrapModes.NEXT_COLUMN_TEXT_WRAP,
    };
    const m = String(mode ?? "BOUNDING_BOX").toUpperCase();
    if (!map[m]) {
        throw new Error(`Unknown wrap mode [${mode}]. Valid: ${Object.keys(map).join(", ")}`);
    }

    item.textWrapPreferences.textWrapMode = map[m];
    if (offsets != null) {
        // number = uniform; object = per side
        item.textWrapPreferences.textWrapOffset = (typeof offsets === "number")
            ? [offsets, offsets, offsets, offsets]
            : [offsets.top ?? 0, offsets.left ?? 0,
               offsets.bottom ?? 0, offsets.right ?? 0];
    }

    return { itemId: item.id, mode: m };
};

const createAnchoredObject = async (command) => {
    usePoints();
    const { storyId, characterIndex, type, width, height, contents,
            position, yOffset } = command.options;

    const doc = getActiveDocument();
    const story = getStoryById(doc, storyId);

    const idx = characterIndex ?? -1;
    const ip = story.insertionPoints.item(idx);

    const w = width ?? 100;
    const h = height ?? 100;
    const t = String(type ?? "TEXT_FRAME").toUpperCase();

    let obj;
    if (t === "RECTANGLE") {
        obj = ip.rectangles.add({ geometricBounds: [0, 0, h, w] });
    } else if (t === "TEXT_FRAME") {
        obj = ip.textFrames.add({ geometricBounds: [0, 0, h, w] });
        if (contents) obj.contents = contents;
    } else {
        throw new Error(`Unknown type [${type}]. Valid: TEXT_FRAME, RECTANGLE`);
    }

    const pos = String(position ?? "INLINE").toUpperCase();
    const posMap = {
        INLINE: AnchorPosition.INLINE_POSITION,
        ABOVE_LINE: AnchorPosition.ABOVE_LINE,
        ANCHORED: AnchorPosition.ANCHORED,
    };
    if (!posMap[pos]) {
        throw new Error(`Unknown position [${position}]. Valid: ${Object.keys(posMap).join(", ")}`);
    }
    obj.anchoredObjectSettings.anchoredPosition = posMap[pos];
    if (yOffset != null && pos === "INLINE") {
        obj.anchoredObjectSettings.anchorYoffset = yOffset;
    }

    return {
        anchoredItemId: obj.id,
        type: obj.constructor.name,
        position: pos,
        storyOverflows: story.overflows,
    };
};

const insertSpecialCharacter = async (command) => {
    const { storyId, character, position } = command.options;

    const doc = getActiveDocument();
    const story = getStoryById(doc, storyId);

    const key = String(character).toUpperCase();
    const value = SpecialCharacters[key];
    if (value === undefined) {
        const names = Object.getOwnPropertyNames(SpecialCharacters)
            .filter((n) => !["length", "name", "prototype"].includes(n));
        throw new Error(
            `Unknown special character [${character}]. Common: AUTO_PAGE_NUMBER, ` +
            `NEXT_PAGE_NUMBER, PREVIOUS_PAGE_NUMBER, SECTION_MARKER, BULLET_CHARACTER, ` +
            `COPYRIGHT_SYMBOL, REGISTERED_TRADEMARK, EM_DASH, EN_DASH, EM_SPACE, EN_SPACE, ` +
            `COLUMN_BREAK, FRAME_BREAK, PAGE_BREAK, FOOTNOTE_SYMBOL. ` +
            `All (${names.length}): ${names.join(", ")}`
        );
    }

    let ip;
    if (position == null || position === "end") {
        ip = story.insertionPoints.item(-1);
    } else if (position === "start") {
        ip = story.insertionPoints.item(0);
    } else {
        ip = story.insertionPoints.item(parseInt(position));
    }
    ip.contents = value;

    return { inserted: key, storyId: story.id, overflows: story.overflows };
};

const setBulletsNumbering = async (command) => {
    const o = command.options;
    const doc = getActiveDocument();
    const { target, story } = resolveTarget(doc, o);

    const listMap = {
        BULLETS: ListType.BULLET_LIST,
        NUMBERS: ListType.NUMBERED_LIST,
        NONE: ListType.NO_LIST,
    };
    const lt = String(o.listType ?? "BULLETS").toUpperCase();
    if (!listMap[lt]) {
        throw new Error(`Unknown listType [${o.listType}]. Valid: ${Object.keys(listMap).join(", ")}`);
    }
    target.bulletsAndNumberingListType = listMap[lt];

    if (o.numberingExpression && lt === "NUMBERS") {
        target.numberingExpression = o.numberingExpression; // e.g. "^#.^t"
    }
    if (o.restartNumbering != null && lt === "NUMBERS") {
        target.numberingContinue = !o.restartNumbering;
    }
    if (o.leftIndent != null) target.leftIndent = o.leftIndent;
    if (o.firstLineIndent != null) target.firstLineIndent = o.firstLineIndent;

    return { listType: lt, ...storyStatus(story) };
};

const setDropCap = async (command) => {
    const o = command.options;
    const doc = getActiveDocument();
    const { target, story } = resolveTarget(doc, o);

    target.dropCapLines = o.lines ?? 3;
    target.dropCapCharacters = o.characters ?? 1;
    if (o.characterStyle) {
        target.dropCapStyle = findCharacterStyle(doc, o.characterStyle);
    }

    return {
        dropCapLines: o.lines ?? 3,
        dropCapCharacters: o.characters ?? 1,
        ...storyStatus(story),
    };
};

const setHyphenationJustification = async (command) => {
    const o = command.options;
    const doc = getActiveDocument();
    const { target, story } = resolveTarget(doc, o);

    if (o.hyphenation != null) target.hyphenation = o.hyphenation;
    if (o.hyphenateWordsLongerThan != null) {
        target.hyphenateWordsLongerThan = o.hyphenateWordsLongerThan;
    }
    if (o.hyphenationZone != null) target.hyphenationZone = o.hyphenationZone;
    if (o.hyphenLadderLimit != null) target.hyphenationLadderLimit = o.hyphenLadderLimit;
    if (o.hyphenateCapitalizedWords != null) {
        target.hyphenateCapitalizedWords = o.hyphenateCapitalizedWords;
    }

    if (o.minimumWordSpacing != null) target.minimumWordSpacing = o.minimumWordSpacing;
    if (o.desiredWordSpacing != null) target.desiredWordSpacing = o.desiredWordSpacing;
    if (o.maximumWordSpacing != null) target.maximumWordSpacing = o.maximumWordSpacing;
    if (o.minimumLetterSpacing != null) target.minimumLetterSpacing = o.minimumLetterSpacing;
    if (o.desiredLetterSpacing != null) target.desiredLetterSpacing = o.desiredLetterSpacing;
    if (o.maximumLetterSpacing != null) target.maximumLetterSpacing = o.maximumLetterSpacing;

    if (o.singleWordJustification) {
        const map = {
            LEFT: SingleWordJustification.LEFT_ALIGN,
            CENTER: SingleWordJustification.CENTER_ALIGN,
            RIGHT: SingleWordJustification.RIGHT_ALIGN,
            JUSTIFY: SingleWordJustification.FULLY_JUSTIFIED,
        };
        const swj = String(o.singleWordJustification).toUpperCase();
        if (!map[swj]) {
            throw new Error(
                `Unknown singleWordJustification [${o.singleWordJustification}]. Valid: ${Object.keys(map).join(", ")}`
            );
        }
        target.singleWordJustification = map[swj];
    }

    return { updated: true, ...storyStatus(story) };
};

const commandHandlers = {
    setBaselineGrid,
    setAlignToBaseline,
    setTextWrap,
    createAnchoredObject,
    insertSpecialCharacter,
    setBulletsNumbering,
    setDropCap,
    setHyphenationJustification,
};

module.exports = { commandHandlers };
