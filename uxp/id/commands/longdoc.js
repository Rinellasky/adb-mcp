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
    PageNumberStyle,
    PageReferenceType,
} = require("indesign");

const {
    usePoints,
    getActiveDocument,
    getPage,
    getStoryById,
    getItemById,
} = require("./utils.js");

/* -------------------------------------------------------------------------
 * Helpers
 * ---------------------------------------------------------------------- */

const setActivePage = (doc, pageNumber) => {
    // createTOC / index generate place at a point on the ACTIVE page
    const page = getPage(doc, pageNumber);
    try {
        if (doc.layoutWindows.length > 0) {
            doc.layoutWindows.item(0).activePage = page;
        }
    } catch (e) { /* headless-ish; placement falls back to current spread */ }
    return page;
};

const storyPlacementReport = (stories) => {
    const list = Array.isArray(stories) ? stories : [stories];
    return list.filter(Boolean).map((s) => ({
        storyId: s.id,
        overflows: s.overflows,
        frames: s.textContainers.map((f) => f.id),
    }));
};

const resolveTextAnchor = (doc, o) => {
    // a text location: storyId + characterIndex (default story start)
    const story = getStoryById(doc, o.storyId);
    const idx = o.characterIndex ?? 0;
    return { story, ip: story.insertionPoints.item(idx) };
};

/* -------------------------------------------------------------------------
 * TOC & sections
 * ---------------------------------------------------------------------- */

const createToc = async (command) => {
    usePoints();
    const { title, entries, pageNumber, placePoint, replaceExisting } =
        command.options;

    const doc = getActiveDocument();

    if (!Array.isArray(entries) || entries.length === 0) {
        throw new Error(
            'createToc requires entries: [{"styleName": "Headline", "level": 1}, ...]'
        );
    }

    const styleName = "MCP TOC Style";
    let tocStyle = doc.tocStyles.itemByName(styleName);
    if (tocStyle.isValid) {
        tocStyle.remove();
    }
    tocStyle = doc.tocStyles.add({ name: styleName, title: title ?? "Contents" });

    for (const entry of entries) {
        const para = doc.allParagraphStyles.find((s) => s.name === entry.styleName);
        if (!para) {
            throw new Error(`No paragraph style named [${entry.styleName}]`);
        }
        tocStyle.tocStyleEntries.add(entry.styleName, {
            level: entry.level ?? 1,
        });
    }

    setActivePage(doc, pageNumber ?? 1);
    const pt = placePoint ?? { x: 48, y: 48 };
    const stories = doc.createTOC(tocStyle, replaceExisting !== false,
                                  undefined, [pt.x, pt.y]);

    return { toc: storyPlacementReport(stories), tocStyle: styleName };
};

const addSection = async (command) => {
    const { pageNumber, startAt, style, prefix, includePrefix, marker,
            continueNumbering } = command.options;

    const doc = getActiveDocument();
    const page = getPage(doc, pageNumber);

    const styleMap = {
        ARABIC: () => PageNumberStyle.ARABIC,
        LOWER_ROMAN: () => PageNumberStyle.LOWER_ROMAN,
        UPPER_ROMAN: () => PageNumberStyle.UPPER_ROMAN,
        LOWER_LETTERS: () => PageNumberStyle.LOWER_LETTERS,
        UPPER_LETTERS: () => PageNumberStyle.UPPER_LETTERS,
    };
    if (style && !styleMap[style]) {
        throw new Error(
            `Unknown numbering style [${style}]. Valid: ${Object.keys(styleMap).join(", ")}`
        );
    }

    const props = { continueNumbering: continueNumbering ?? false };
    if (startAt != null) props.pageNumberStart = startAt;
    if (style) props.pageNumberStyle = styleMap[style]();
    if (prefix != null) props.sectionPrefix = prefix;
    if (includePrefix != null) props.includeSectionPrefix = includePrefix;
    if (marker != null) props.marker = marker;

    doc.sections.add(page, props);

    return {
        sectionStartPage: page.name,
        sectionCount: doc.sections.length,
        pageNamesNow: doc.pages.everyItem().getElements().map((p) => p.name),
    };
};

/* -------------------------------------------------------------------------
 * Hyperlinks, bookmarks, cross-references
 * ---------------------------------------------------------------------- */

let linkCounter = 0;
const uniqueName = (base) => `${base} ${Date.now()}_${linkCounter++}`;

const createHyperlink = async (command) => {
    const o = command.options;
    const doc = getActiveDocument();

    // destination: url OR toPageNumber
    let destination;
    if (o.url) {
        destination = doc.hyperlinkURLDestinations.add(o.url,
            { name: uniqueName("URL") });
    } else if (o.toPageNumber != null) {
        destination = doc.hyperlinkPageDestinations.add(
            getPage(doc, o.toPageNumber), { name: uniqueName("Page") });
    } else {
        throw new Error("createHyperlink requires url or toPageNumber");
    }

    // source: text range (storyId + start/end) OR page item (itemId)
    let source;
    if (o.storyId != null) {
        const story = getStoryById(doc, o.storyId);
        const s = o.startCharacter ?? 0;
        const e = o.endCharacter ?? story.characters.length - 1;
        const range = story.characters.itemByRange(s, e);
        source = doc.hyperlinkTextSources.add(range,
            { name: uniqueName("TextSrc") });
    } else if (o.itemId != null) {
        source = doc.hyperlinkPageItemSources.add(getItemById(doc, o.itemId),
            { name: uniqueName("ItemSrc") });
    } else {
        throw new Error("createHyperlink requires storyId (+range) or itemId");
    }

    const link = doc.hyperlinks.add(source, destination,
        { name: o.name ?? uniqueName("Hyperlink") });

    return {
        hyperlink: link.name,
        target: o.url ?? `page ${o.toPageNumber}`,
        hyperlinkCount: doc.hyperlinks.length,
    };
};

const createBookmark = async (command) => {
    const { pageNumber, name, parentBookmark } = command.options;

    const doc = getActiveDocument();
    const dest = doc.hyperlinkPageDestinations.add(getPage(doc, pageNumber),
        { name: uniqueName("BookmarkDest") });

    let parent = doc;
    if (parentBookmark) {
        const pb = doc.bookmarks.itemByName(parentBookmark);
        if (!pb.isValid) {
            throw new Error(`No bookmark named [${parentBookmark}]`);
        }
        parent = pb.getElements()[0];
    }

    const bm = parent.bookmarks.add(dest, { name: name ?? `Page ${pageNumber}` });

    return { bookmark: bm.name, pageNumber, bookmarkCount: doc.bookmarks.length };
};

const createCrossReference = async (command) => {
    const o = command.options;
    const doc = getActiveDocument();

    // destination paragraph: storyId + paragraphIndex
    const story = getStoryById(doc, o.destinationStoryId);
    const pIdx = o.destinationParagraph ?? 0;
    if (pIdx < 0 || pIdx >= story.paragraphs.length) {
        throw new Error(
            `destinationParagraph ${pIdx} out of range (story has ${story.paragraphs.length})`
        );
    }
    const destPara = story.paragraphs.item(pIdx);
    const destination = doc.paragraphDestinations.add(destPara,
        { name: uniqueName("XRefDest") });

    // format: built-ins like "Page Number", "Paragraph Text & Page Number"
    const formatName = o.format ?? "Page Number";
    const format = doc.crossReferenceFormats.itemByName(formatName);
    if (!format.isValid) {
        const names = doc.crossReferenceFormats.everyItem().getElements()
            .map((f) => f.name);
        throw new Error(
            `No cross-reference format [${formatName}]. Available: ${names.join(", ")}`
        );
    }

    // source: insertion point in another story
    const { ip } = resolveTextAnchor(doc, {
        storyId: o.sourceStoryId,
        characterIndex: o.sourceCharacterIndex,
    });
    const source = doc.crossReferenceSources.add(ip, format,
        { name: uniqueName("XRefSrc") });

    const link = doc.hyperlinks.add(source, destination,
        { name: o.name ?? uniqueName("XRef") });

    return { crossReference: link.name, format: formatName };
};

/* -------------------------------------------------------------------------
 * Index
 * ---------------------------------------------------------------------- */

const getIndex = (doc) => {
    return doc.indexes.length > 0 ? doc.indexes.item(0) : doc.indexes.add();
};

const addIndexEntry = async (command) => {
    const { term, storyId, characterIndex, subTerm } = command.options;

    const doc = getActiveDocument();
    const index = getIndex(doc);

    let topic = index.topics.itemByName(term);
    if (!topic.isValid) {
        topic = index.topics.add(term);
    } else {
        topic = topic.getElements()[0];
    }
    if (subTerm) {
        let sub = topic.topics.itemByName(subTerm);
        topic = sub.isValid ? sub.getElements()[0] : topic.topics.add(subTerm);
    }

    const { ip } = resolveTextAnchor(doc, { storyId, characterIndex });
    topic.pageReferences.add(ip, PageReferenceType.CURRENT_PAGE);

    return {
        term: subTerm ? `${term} > ${subTerm}` : term,
        topicCount: index.topics.length,
    };
};

const generateIndex = async (command) => {
    usePoints();
    const { pageNumber, placePoint } = command.options;

    const doc = getActiveDocument();
    if (doc.indexes.length === 0) {
        throw new Error("No index entries yet — call addIndexEntry first");
    }

    const page = setActivePage(doc, pageNumber ?? doc.pages.length);
    const pt = placePoint ?? { x: 48, y: 48 };
    const stories = doc.indexes.item(0).generate(page, [pt.x, pt.y]);

    return { index: storyPlacementReport(stories) };
};

/* -------------------------------------------------------------------------
 * Books (feature-detected — Books may not be exposed in InDesign UXP)
 * ---------------------------------------------------------------------- */

const requireBooks = () => {
    if (!app.books || typeof app.books.add !== "function") {
        throw new Error(
            "The Books API (app.books) is not exposed in this InDesign UXP build"
        );
    }
};

const createBook = async (command) => {
    const { filePath } = command.options;
    requireBooks();

    const book = app.books.add(filePath);
    return { book: book.name, filePath, documents: book.bookContents.length };
};

const manageBook = async (command) => {
    const { bookName, action, documentPath, styleSourceIndex, outputPath } =
        command.options;
    requireBooks();

    let book;
    if (bookName) {
        book = app.books.itemByName(bookName);
        if (!book.isValid) {
            throw new Error(
                `No open book named [${bookName}]. Open books: ${app.books.everyItem().getElements().map((b) => b.name).join(", ") || "none"}`
            );
        }
        book = book.getElements()[0];
    } else if (app.books.length > 0) {
        book = app.books.item(0);
    } else {
        throw new Error("No book is open — create one with createBook first");
    }

    const act = String(action).toUpperCase();
    if (act === "ADD_DOCUMENT") {
        if (!documentPath) throw new Error("ADD_DOCUMENT requires documentPath");
        book.bookContents.add(documentPath);
    } else if (act === "SYNCHRONIZE") {
        if (styleSourceIndex != null) {
            book.styleSourceDocument = book.bookContents.item(styleSourceIndex);
        }
        book.synchronize();
    } else if (act === "EXPORT_PDF") {
        if (!outputPath) throw new Error("EXPORT_PDF requires outputPath");
        const { ExportFormat } = require("indesign");
        // NOTE: can exceed the 20s proxy timeout — timeout != failure
        book.exportFile(ExportFormat.PDF_TYPE, outputPath);
    } else if (act === "SAVE") {
        book.save();
    } else if (act === "LIST") {
        // fallthrough to the common return below
    } else {
        throw new Error(
            `Unknown action [${action}]. Valid: ADD_DOCUMENT, SYNCHRONIZE, EXPORT_PDF, SAVE, LIST`
        );
    }

    return {
        book: book.name,
        action: act,
        documents: book.bookContents.everyItem().getElements().map((c) => c.name),
    };
};

const commandHandlers = {
    createToc,
    addSection,
    createHyperlink,
    createBookmark,
    createCrossReference,
    addIndexEntry,
    generateIndex,
    createBook,
    manageBook,
};

module.exports = { commandHandlers };
