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

const { getActiveDocument, getStoryById } = require("./utils.js");

/* -------------------------------------------------------------------------
 * Helpers
 * ---------------------------------------------------------------------- */

/**
 * ALWAYS reset find/change preferences before AND after every operation —
 * stale preferences silently corrupt later searches (Architecture Note in
 * the roadmap; this is the #1 classic InDesign scripting bug).
 */
const resetTextPrefs = () => {
    app.findTextPreferences = NothingEnum.NOTHING;
    app.changeTextPreferences = NothingEnum.NOTHING;
};

const resetGrepPrefs = () => {
    app.findGrepPreferences = NothingEnum.NOTHING;
    app.changeGrepPreferences = NothingEnum.NOTHING;
};

const findStyleForPrefs = (doc, styleType, name) => {
    const coll = styleType === "character"
        ? doc.allCharacterStyles : doc.allParagraphStyles;
    const match = coll.find((s) => s.name === name);
    if (!match) {
        throw new Error(
            `No ${styleType} style named [${name}]. Available: ${coll.map((s) => s.name).join(", ")}`
        );
    }
    return match;
};

const getScope = (doc, storyId) => {
    return storyId != null ? getStoryById(doc, storyId) : doc;
};

const describeMatch = (t, contextChars) => {
    const out = { contents: String(t.contents).substring(0, 200) };
    try {
        out.storyId = t.parentStory.id;
        out.index = t.characters.item(0).index;
        out.length = t.characters.length;
    } catch (e) { /* zero-length or odd match */ }
    if (contextChars) {
        try {
            const story = t.parentStory;
            const start = Math.max(0, out.index - contextChars);
            const end = Math.min(story.characters.length - 1,
                                 out.index + out.length + contextChars - 1);
            out.context = String(
                story.characters.itemByRange(start, end).contents
            ).substring(0, 400);
        } catch (e) { /* best effort */ }
    }
    return out;
};

const MAX_MATCHES = 200;

/* -------------------------------------------------------------------------
 * Literal text find/change
 * ---------------------------------------------------------------------- */

const findText = async (command) => {
    const { findWhat, caseSensitive, wholeWord, storyId } = command.options;

    const doc = getActiveDocument();
    resetTextPrefs();
    try {
        app.findChangeTextOptions.caseSensitive = caseSensitive ?? false;
        app.findChangeTextOptions.wholeWord = wholeWord ?? false;
        app.findTextPreferences.findWhat = findWhat;

        const found = getScope(doc, storyId).findText();
        return {
            count: found.length,
            truncated: found.length > MAX_MATCHES,
            matches: found.slice(0, MAX_MATCHES).map((t) => describeMatch(t, 40)),
        };
    } finally {
        resetTextPrefs();
    }
};

const changeText = async (command) => {
    const { findWhat, changeTo, caseSensitive, wholeWord, storyId } = command.options;

    const doc = getActiveDocument();
    resetTextPrefs();
    try {
        app.findChangeTextOptions.caseSensitive = caseSensitive ?? false;
        app.findChangeTextOptions.wholeWord = wholeWord ?? false;
        app.findTextPreferences.findWhat = findWhat;
        app.changeTextPreferences.changeTo = changeTo;

        const changed = getScope(doc, storyId).changeText();
        return { changedCount: changed.length };
    } finally {
        resetTextPrefs();
    }
};

/* -------------------------------------------------------------------------
 * GREP
 * ---------------------------------------------------------------------- */

const findGrep = async (command) => {
    const { findWhat, storyId, contextChars } = command.options;

    const doc = getActiveDocument();
    resetGrepPrefs();
    try {
        app.findGrepPreferences.findWhat = findWhat;

        const found = getScope(doc, storyId).findGrep();
        return {
            count: found.length,
            truncated: found.length > MAX_MATCHES,
            matches: found.slice(0, MAX_MATCHES).map((t) =>
                describeMatch(t, contextChars ?? 40)),
        };
    } finally {
        resetGrepPrefs();
    }
};

const changeGrep = async (command) => {
    const { findWhat, changeTo, storyId, appliedCharacterStyle,
            appliedParagraphStyle } = command.options;

    const doc = getActiveDocument();
    resetGrepPrefs();
    try {
        app.findGrepPreferences.findWhat = findWhat;
        if (changeTo != null) {
            app.changeGrepPreferences.changeTo = changeTo;
        }
        if (appliedCharacterStyle) {
            app.changeGrepPreferences.appliedCharacterStyle =
                findStyleForPrefs(doc, "character", appliedCharacterStyle);
        }
        if (appliedParagraphStyle) {
            app.changeGrepPreferences.appliedParagraphStyle =
                findStyleForPrefs(doc, "paragraph", appliedParagraphStyle);
        }
        if (changeTo == null && !appliedCharacterStyle && !appliedParagraphStyle) {
            throw new Error(
                "changeGrep requires changeTo and/or a style to apply"
            );
        }

        const changed = getScope(doc, storyId).changeGrep();
        return { changedCount: changed.length };
    } finally {
        resetGrepPrefs();
    }
};

const grepApplyStyle = async (command) => {
    // convenience wrapper: apply a style to every regex match, keeping text
    const { findWhat, characterStyle, paragraphStyle, storyId } = command.options;

    if (!characterStyle && !paragraphStyle) {
        throw new Error("grepApplyStyle requires characterStyle or paragraphStyle");
    }

    return changeGrep({
        options: {
            findWhat,
            storyId,
            appliedCharacterStyle: characterStyle,
            appliedParagraphStyle: paragraphStyle,
        },
    });
};

const findChangeReport = async (command) => {
    // dry run: counts per pattern, nothing is changed
    const { patterns, storyId } = command.options;

    if (!Array.isArray(patterns) || patterns.length === 0) {
        throw new Error("findChangeReport requires a non-empty patterns array");
    }

    const doc = getActiveDocument();
    const report = [];
    for (const pattern of patterns) {
        resetGrepPrefs();
        try {
            app.findGrepPreferences.findWhat = pattern;
            const found = getScope(doc, storyId).findGrep();
            report.push({ pattern, count: found.length });
        } catch (e) {
            report.push({ pattern, error: String(e) });
        } finally {
            resetGrepPrefs();
        }
    }

    return { report };
};

const commandHandlers = {
    findText,
    changeText,
    findGrep,
    changeGrep,
    grepApplyStyle,
    findChangeReport,
};

module.exports = { commandHandlers };
