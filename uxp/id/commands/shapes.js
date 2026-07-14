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
    ColorSpace,
    ColorModel,
    CornerOptions,
    FitOptions,
    LocationOptions,
} = require("indesign");

const {
    usePoints,
    getActiveDocument,
    getPage,
    getItemById,
    getSwatch,
    boundsToArray,
    boundsToObject,
    describePageItem,
} = require("./utils.js");

/* -------------------------------------------------------------------------
 * Helpers
 * ---------------------------------------------------------------------- */

const CORNER_OPTIONS = () => ({
    NONE: CornerOptions.NONE,
    ROUNDED: CornerOptions.ROUNDED_CORNER,
    INVERSE_ROUNDED: CornerOptions.INVERSE_ROUNDED_CORNER,
    INSET: CornerOptions.INSET_CORNER,
    BEVEL: CornerOptions.BEVEL_CORNER,
    FANCY: CornerOptions.FANCY_CORNER,
});

const applyAppearance = (doc, item, o) => {
    if (o.fillSwatch) item.fillColor = getSwatch(doc, o.fillSwatch);
    if (o.strokeSwatch) item.strokeColor = getSwatch(doc, o.strokeSwatch);
    if (o.strokeWeight != null) item.strokeWeight = o.strokeWeight;

    if (o.cornerOption) {
        const map = CORNER_OPTIONS();
        if (!map[o.cornerOption]) {
            throw new Error(
                `Unknown cornerOption [${o.cornerOption}]. Valid: ${Object.keys(map).join(", ")}`
            );
        }
        const corner = map[o.cornerOption];
        item.topLeftCornerOption = corner;
        item.topRightCornerOption = corner;
        item.bottomLeftCornerOption = corner;
        item.bottomRightCornerOption = corner;
    }

    if (o.cornerRadius != null) {
        item.topLeftCornerRadius = o.cornerRadius;
        item.topRightCornerRadius = o.cornerRadius;
        item.bottomLeftCornerRadius = o.cornerRadius;
        item.bottomRightCornerRadius = o.cornerRadius;
    }

    if (o.opacity != null) {
        item.transparencySettings.blendingSettings.opacity = o.opacity;
    }
};

/* -------------------------------------------------------------------------
 * Handlers
 * ---------------------------------------------------------------------- */

const createShape = async (command) => {
    usePoints();
    const o = command.options;
    const { pageNumber, shapeType, bounds, layerName, sides } = o;

    const doc = getActiveDocument();
    const page = getPage(doc, pageNumber);

    const props = { geometricBounds: boundsToArray(bounds) };
    if (layerName) props.itemLayer = layerName;
    if (o.name) props.name = o.name; // named items are populate_template targets

    let item;
    const type = String(shapeType).toUpperCase();
    switch (type) {
        case "RECTANGLE":
            item = page.rectangles.add(props);
            break;
        case "OVAL":
            item = page.ovals.add(props);
            break;
        case "POLYGON":
            app.polygonPreferences.numberOfSides = sides ?? 6;
            app.polygonPreferences.insetPercentage = o.starInset ?? 0;
            item = page.polygons.add(props);
            break;
        case "LINE":
            item = page.graphicLines.add(props);
            break;
        default:
            throw new Error(
                `Unknown shapeType [${shapeType}]. Valid: RECTANGLE, OVAL, POLYGON, LINE`
            );
    }

    applyAppearance(doc, item, o);

    return {
        itemId: item.id,
        type: item.constructor.name,
        bounds: boundsToObject(item.geometricBounds),
    };
};

const setItemAppearance = async (command) => {
    usePoints();
    const o = command.options;

    const doc = getActiveDocument();
    const item = getItemById(doc, o.itemId);

    applyAppearance(doc, item, o);

    return describePageItem(item);
};

const createSwatch = async (command) => {
    const { name, colorSpace, colorValue } = command.options;

    const doc = getActiveDocument();

    const space = String(colorSpace).toUpperCase();
    let spaceEnum, expected;
    if (space === "CMYK") {
        spaceEnum = ColorSpace.CMYK;
        expected = 4;
    } else if (space === "RGB") {
        spaceEnum = ColorSpace.RGB;
        expected = 3;
    } else {
        throw new Error(`Unknown colorSpace [${colorSpace}]. Valid: CMYK, RGB`);
    }

    if (!Array.isArray(colorValue) || colorValue.length !== expected) {
        throw new Error(
            `${space} colorValue must be an array of ${expected} numbers (${
                space === "CMYK" ? "0-100 each" : "0-255 each"
            })`
        );
    }

    const existing = doc.colors.itemByName(name);
    if (existing.isValid) {
        // upsert semantics
        existing.space = spaceEnum;
        existing.colorValue = colorValue;
        return { name: existing.name, colorSpace: space, colorValue, updated: true };
    }

    const color = doc.colors.add({
        name,
        model: ColorModel.PROCESS,
        space: spaceEnum,
        colorValue,
    });

    return { name: color.name, colorSpace: space, colorValue, updated: false };
};

const placeImage = async (command) => {
    usePoints();
    const { pageNumber, filePath, bounds, frameId, fitOption } = command.options;

    const doc = getActiveDocument();

    const fitMap = {
        PROPORTIONALLY: FitOptions.PROPORTIONALLY,
        FILL_PROPORTIONALLY: FitOptions.FILL_PROPORTIONALLY,
        CONTENT_TO_FRAME: FitOptions.CONTENT_TO_FRAME,
        FRAME_TO_CONTENT: FitOptions.FRAME_TO_CONTENT,
        CENTER_CONTENT: FitOptions.CENTER_CONTENT,
    };
    const fitName = fitOption ?? "FILL_PROPORTIONALLY";
    if (!fitMap[fitName]) {
        throw new Error(
            `Unknown fitOption [${fitOption}]. Valid: ${Object.keys(fitMap).join(", ")}`
        );
    }

    let frame;
    if (frameId != null) {
        frame = getItemById(doc, frameId);
    } else {
        if (!bounds) {
            throw new Error("placeImage requires bounds (or an existing frameId)");
        }
        const page = getPage(doc, pageNumber);
        frame = page.rectangles.add({ geometricBounds: boundsToArray(bounds) });
    }

    const placed = frame.place(filePath);
    frame.fit(fitMap[fitName]);

    return {
        frameId: frame.id,
        placedType: placed && placed[0] ? placed[0].constructor.name : null,
        bounds: boundsToObject(frame.geometricBounds),
        fit: fitName,
    };
};

const transformItem = async (command) => {
    usePoints();
    const { itemId, moveBy, moveTo, width, height, rotation } = command.options;

    const doc = getActiveDocument();
    const item = getItemById(doc, itemId);

    if (moveTo) {
        item.move([moveTo.x, moveTo.y]);
    }
    if (moveBy) {
        item.move(undefined, [moveBy.x ?? 0, moveBy.y ?? 0]);
    }

    if (width != null || height != null) {
        const gb = item.geometricBounds; // [top, left, bottom, right]
        const newBottom = height != null ? gb[0] + height : gb[2];
        const newRight = width != null ? gb[1] + width : gb[3];
        item.geometricBounds = [gb[0], gb[1], newBottom, newRight];
    }

    if (rotation != null) {
        item.rotationAngle = rotation;
    }

    return describePageItem(item);
};

const duplicateItem = async (command) => {
    usePoints();
    const { itemId, toPageNumber, offset } = command.options;

    const doc = getActiveDocument();
    const item = getItemById(doc, itemId);

    let dup;
    if (toPageNumber != null) {
        const page = getPage(doc, toPageNumber);
        dup = item.duplicate(page);
    } else {
        dup = item.duplicate(undefined, [offset?.x ?? 12, offset?.y ?? 12]);
    }

    return describePageItem(dup);
};

const groupItems = async (command) => {
    usePoints();
    const { itemIds, ungroupItemId } = command.options;

    const doc = getActiveDocument();

    if (ungroupItemId != null) {
        const group = getItemById(doc, ungroupItemId);
        if (group.constructor.name !== "Group") {
            throw new Error(`Item [${ungroupItemId}] is not a Group`);
        }
        const childIds = group.pageItems.everyItem().getElements().map((i) => i.id);
        group.ungroup();
        return { ungrouped: true, itemIds: childIds };
    }

    if (!Array.isArray(itemIds) || itemIds.length < 2) {
        throw new Error("groupItems requires an itemIds array with at least 2 ids");
    }

    const items = itemIds.map((id) => getItemById(doc, id));
    const parentPage = items[0].parentPage;
    const group = parentPage.groups.add(items);

    return describePageItem(group);
};

const commandHandlers = {
    createShape,
    setItemAppearance,
    createSwatch,
    placeImage,
    transformItem,
    duplicateItem,
    groupItems,
};

module.exports = { commandHandlers };
