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
    Justification,
    VerticalJustification,
    AutoSizingTypeEnum,
} = require("indesign");

const {
    usePoints,
    getActiveDocument,
    getPage,
    getItemById,
    getStoryById,
    getSwatch,
    boundsToArray,
    textFrameStatus,
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

/**
 * Overset status for every frame of a story (spans threading).
 */
const storyStatus = (story) => {
    const frames = story.textContainers.map((f) => ({
        frameId: f.id,
        overflows: f.overflows,
    }));
    return {
        storyId: story.id,
        overflows: story.overflows,
        frames,
    };
};

/**
 * Resolve a text range within a story.
 * rangeType: "story" (default) | "paragraphs" | "characters"
 * start/end are 0-based, end-inclusive indices.
 */
const resolveRange = (story, rangeType, start, end) => {
    const type = rangeType ?? "story";

    if (type === "story") {
        return story.texts.item(0);
    }

    const collection =
        type === "paragraphs" ? story.paragraphs : story.characters;

    if (type !== "paragraphs" && type !== "characters") {
        throw new Error(
            `Unknown rangeType [${rangeType}]. Valid: story, paragraphs, characters`
        );
    }

    const s = start ?? 0;
    const e = end ?? collection.length - 1;
    if (s < 0 || e >= collection.length || s > e) {
        throw new Error(
            `Invalid ${type} range [${s}..${e}] — story has ${collection.length} ${type}`
        );
    }

    return collection.itemByRange(s, e);
};

/* -------------------------------------------------------------------------
 * Handlers
 * ---------------------------------------------------------------------- */

const createTextFrame = async (command) => {
    usePoints();
    const { pageNumber, bounds, contents, layerName, name } = command.options;

    const doc = getActiveDocument();
    const page = getPage(doc, pageNumber);

    const props = {
        geometricBounds: boundsToArray(bounds),
        contents: contents ?? "",
    };
    if (layerName) {
        props.itemLayer = layerName;
    }
    if (name) {
        props.name = name; // named frames are populate_template targets
    }

    const frame = page.textFrames.add(props);

    return textFrameStatus(frame);
};

const setTextContents = async (command) => {
    const { storyId, frameId, contents } = command.options;

    const doc = getActiveDocument();

    let story;
    if (storyId != null) {
        story = getStoryById(doc, storyId);
    } else if (frameId != null) {
        story = getItemById(doc, frameId).parentStory;
    } else {
        throw new Error("setTextContents requires storyId or frameId");
    }

    story.contents = contents;

    return storyStatus(story);
};

const insertText = async (command) => {
    const { storyId, text, position } = command.options;

    const doc = getActiveDocument();
    const story = getStoryById(doc, storyId);

    let ip;
    if (position == null || position === "end") {
        ip = story.insertionPoints.item(-1);
    } else if (position === "start") {
        ip = story.insertionPoints.item(0);
    } else {
        const idx = parseInt(position);
        if (isNaN(idx) || idx < 0 || idx >= story.insertionPoints.length) {
            throw new Error(
                `Invalid position [${position}] — story has ${story.insertionPoints.length} insertion points`
            );
        }
        ip = story.insertionPoints.item(idx);
    }

    ip.contents = text;

    return storyStatus(story);
};

const getStoryContents = async (command) => {
    const { storyId } = command.options;

    const doc = getActiveDocument();
    const story = getStoryById(doc, storyId);

    return {
        storyId: story.id,
        contents: story.contents,
        length: story.characters.length,
        paragraphCount: story.paragraphs.length,
        overflows: story.overflows,
        frames: story.textContainers.map((f) => f.id),
    };
};

const threadTextFrames = async (command) => {
    const { fromFrameId, toFrameId } = command.options;

    const doc = getActiveDocument();
    const fromFrame = getItemById(doc, fromFrameId);
    const toFrame = getItemById(doc, toFrameId);

    if (toFrame.parentStory.characters.length > 0) {
        throw new Error(
            `Target frame [${toFrameId}] already contains text — threading would discard it. Use an empty frame.`
        );
    }

    fromFrame.nextTextFrame = toFrame;

    return storyStatus(fromFrame.parentStory);
};

const setTextFrameOptions = async (command) => {
    usePoints();
    const {
        frameId,
        columnCount,
        columnGutter,
        insetSpacing,
        verticalJustification,
        autoSize,
    } = command.options;

    const doc = getActiveDocument();
    const frame = getItemById(doc, frameId);
    const prefs = frame.textFramePreferences;

    if (columnCount != null) prefs.textColumnCount = columnCount;
    if (columnGutter != null) prefs.textColumnGutter = columnGutter;

    if (insetSpacing != null) {
        // number = uniform inset; object = per-side
        if (typeof insetSpacing === "number") {
            prefs.insetSpacing = insetSpacing;
        } else {
            prefs.insetSpacing = [
                insetSpacing.top ?? 0,
                insetSpacing.left ?? 0,
                insetSpacing.bottom ?? 0,
                insetSpacing.right ?? 0,
            ];
        }
    }

    if (verticalJustification) {
        const map = {
            TOP: VerticalJustification.TOP_ALIGN,
            CENTER: VerticalJustification.CENTER_ALIGN,
            BOTTOM: VerticalJustification.BOTTOM_ALIGN,
            JUSTIFY: VerticalJustification.JUSTIFY_ALIGN,
        };
        if (!map[verticalJustification]) {
            throw new Error(
                `Unknown verticalJustification [${verticalJustification}]. Valid: ${Object.keys(map).join(", ")}`
            );
        }
        prefs.verticalJustification = map[verticalJustification];
    }

    if (autoSize) {
        const map = {
            OFF: AutoSizingTypeEnum.OFF,
            HEIGHT_ONLY: AutoSizingTypeEnum.HEIGHT_ONLY,
            WIDTH_ONLY: AutoSizingTypeEnum.WIDTH_ONLY,
            HEIGHT_AND_WIDTH: AutoSizingTypeEnum.HEIGHT_AND_WIDTH,
            HEIGHT_AND_WIDTH_PROPORTIONALLY:
                AutoSizingTypeEnum.HEIGHT_AND_WIDTH_PROPORTIONALLY,
        };
        if (!map[autoSize]) {
            throw new Error(
                `Unknown autoSize [${autoSize}]. Valid: ${Object.keys(map).join(", ")}`
            );
        }
        prefs.autoSizingType = map[autoSize];
    }

    return textFrameStatus(frame);
};

const styleTextRange = async (command) => {
    usePoints();
    const {
        storyId,
        rangeType,
        start,
        end,
        fontFamily,
        fontStyle,
        pointSize,
        leading,
        alignment,
        spaceBefore,
        spaceAfter,
        firstLineIndent,
        tracking,
    } = command.options;

    const doc = getActiveDocument();
    const story = getStoryById(doc, storyId);
    const range = resolveRange(story, rangeType, start, end);

    if (fontFamily) {
        // "Family\tStyle" form lets one assignment set both when style given
        range.appliedFont = fontStyle ? `${fontFamily}\t${fontStyle}` : fontFamily;
    } else if (fontStyle) {
        try {
            range.fontStyle = fontStyle;
        } catch (e) {
            let family = "?";
            try { family = range.appliedFont.fontFamily; } catch (e2) {}
            throw new Error(
                `Font style [${fontStyle}] is not available for font [${family}]. ` +
                `Pass fontFamily explicitly, or use a style that face actually has ` +
                `(e.g. "Semibold" instead of "Bold" for some families).`
            );
        }
    }

    if (pointSize != null) range.pointSize = pointSize;
    if (leading != null) range.leading = leading;
    if (tracking != null) range.tracking = tracking;

    if (alignment) {
        const map = JUSTIFICATION_MAP();
        if (!map[alignment]) {
            throw new Error(
                `Unknown alignment [${alignment}]. Valid: ${Object.keys(map).join(", ")}`
            );
        }
        range.justification = map[alignment];
    }

    if (spaceBefore != null) range.spaceBefore = spaceBefore;
    if (spaceAfter != null) range.spaceAfter = spaceAfter;
    if (firstLineIndent != null) range.firstLineIndent = firstLineIndent;

    return storyStatus(story);
};

const setTextColor = async (command) => {
    const { storyId, rangeType, start, end, swatchName } = command.options;

    const doc = getActiveDocument();
    const story = getStoryById(doc, storyId);
    const range = resolveRange(story, rangeType, start, end);
    const swatch = getSwatch(doc, swatchName);

    range.fillColor = swatch;

    return storyStatus(story);
};

const commandHandlers = {
    createTextFrame,
    setTextContents,
    insertText,
    getStoryContents,
    threadTextFrames,
    setTextFrameOptions,
    styleTextRange,
    setTextColor,
};

module.exports = { commandHandlers };
