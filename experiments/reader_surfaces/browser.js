/* Fixed offline research adapter. Canonical text is data, never executable HTML. */
(() => {
    "use strict";
    const fail = message => { throw new Error(message); };
    const exactKeys = (value, keys) => value && typeof value === "object" && !Array.isArray(value)
        && Object.keys(value).sort().join("|") === [...keys].sort().join("|");
    const same = (a, b) => {
        if (a === b) return true;
        if (!a || !b || typeof a !== "object" || typeof b !== "object") return false;
        if (Array.isArray(a) !== Array.isArray(b)) return false;
        const keys = Object.keys(a);
        return keys.length === Object.keys(b).length && keys.every(key => Object.hasOwn(b, key) && same(a[key], b[key]));
    };
    function verifiedRoot(root, source) {
        if (!root || root.textContent !== source) fail("Displayed text disagrees with canonical source; mapping refused.");
    }
    function codepointOffset(root, node, offset, source) {
        verifiedRoot(root, source);
        if (!node || !(node === root || root.contains(node)) || !Number.isSafeInteger(offset) || offset < 0)
            fail("Endpoint is outside the source passage.");
        const isText = node.nodeType === 3;
        if (!(isText || node.nodeType === 1) || offset > (isText ? node.data.length : node.childNodes.length))
            fail("Invalid DOM endpoint.");
        if (isText && offset > 0 && offset < node.data.length
            && /[\uD800-\uDBFF]/.test(node.data[offset - 1]) && /[\uDC00-\uDFFF]/.test(node.data[offset]))
            fail("An endpoint splits a Unicode surrogate pair.");
        const prefix = root.ownerDocument.createRange();
        prefix.setStart(root, 0);
        prefix.setEnd(node, offset);
        const text = prefix.toString();
        const cp = Array.from(text).length;
        if (Array.from(source).slice(0, cp).join("") !== text) fail("Endpoint has no exact source-codepoint boundary.");
        return cp;
    }
    function locatePoint(root, cp, source) {
        verifiedRoot(root, source);
        const chars = Array.from(source);
        if (!Number.isSafeInteger(cp) || cp < 0 || cp > chars.length) fail("Position is outside the source passage.");
        let remaining = chars.slice(0, cp).join("").length;
        const walker = root.ownerDocument.createTreeWalker(root, 4);
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            if (remaining <= node.data.length) return [node, remaining];
            remaining -= node.data.length;
        }
        if (!source && cp === 0) return [root, 0];
        fail("Source position cannot be reconstructed.");
    }
    function sourceRoot(node) {
        return (node?.nodeType === 1 ? node : node?.parentElement)?.closest(".source[data-record-id]");
    }
    function recordFor(root, records) {
        const record = records.find(item => item.id === root?.dataset.recordId);
        if (!record) fail("No canonical record for this endpoint.");
        verifiedRoot(root, record.plain_text);
        return record;
    }
    function capture(selection, records, positionOnly = false) {
        if (!selection || selection.rangeCount !== 1) fail("Choose one source passage first.");
        const range = selection.getRangeAt(0);
        const root = sourceRoot(range.startContainer);
        if (!root || root !== sourceRoot(range.endContainer)) fail("Selections across passages are not supported by this proof.");
        const record = recordFor(root, records);
        const start = codepointOffset(root, range.startContainer, range.startOffset, record.plain_text);
        const end = codepointOffset(root, range.endContainer, range.endOffset, record.plain_text);
        if (!positionOnly && start === end) fail("Select a nonempty phrase inside one passage.");
        const text = Array.from(record.plain_text).slice(start, end).join("");
        if (range.toString() !== text) fail("Selected text has no exact source span.");
        const focus = selection.focusNode
            ? codepointOffset(root, selection.focusNode, selection.focusOffset, record.plain_text) : end;
        if (![start, end].includes(focus)) fail("Selection focus disagrees with its source boundaries.");
        const binding = record.reference.reference;
        return {
            reference: record.reference,
            selection: positionOnly ? null : {
                requested_id: binding.requested_id, target_id: binding.target_id,
                start, end, text, content_sha256: binding.content_sha256,
                plain_text_sha256: record.plain_text_sha256
            },
            cursor_offset: focus
        };
    }
    function validatePacket(packet, record) {
        if (!exactKeys(packet, ["reference", "selection", "cursor_offset"]) || !same(packet.reference, record.reference))
            fail("Packet does not bind this exported corpus generation and source record.");
        const cursor = packet.cursor_offset, length = Array.from(record.plain_text).length;
        if (!Number.isSafeInteger(cursor) || cursor < 0 || cursor > length) fail("Invalid source cursor.");
        if (packet.selection === null) return packet;
        const span = packet.selection, binding = record.reference.reference;
        if (!exactKeys(span, ["requested_id", "target_id", "start", "end", "text", "content_sha256", "plain_text_sha256"])
            || span.requested_id !== binding.requested_id || span.target_id !== binding.target_id
            || span.content_sha256 !== binding.content_sha256 || span.plain_text_sha256 !== record.plain_text_sha256
            || !Number.isSafeInteger(span.start) || !Number.isSafeInteger(span.end)
            || span.start < 0 || span.start >= span.end || span.end > length
            || Array.from(record.plain_text).slice(span.start, span.end).join("") !== span.text
            || ![span.start, span.end].includes(cursor)) fail("Selection identity, source text, or codepoint span disagrees.");
        return packet;
    }
    function restore(packet, records, doc = document) {
        const record = records.find(item => item.id === packet?.reference?.reference?.target_id);
        if (!record) fail("That record is outside this bounded sample.");
        validatePacket(packet, record);
        const root = [...doc.querySelectorAll(".source[data-record-id]")].find(el => el.dataset.recordId === record.id);
        verifiedRoot(root, record.plain_text);
        const start = packet.selection?.start ?? packet.cursor_offset;
        const end = packet.selection?.end ?? packet.cursor_offset;
        const range = doc.createRange();
        range.setStart(...locatePoint(root, start, record.plain_text));
        range.setEnd(...locatePoint(root, end, record.plain_text));
        const selection = doc.defaultView.getSelection();
        selection.removeAllRanges();
        if (packet.selection && packet.cursor_offset === start) {
            selection.setBaseAndExtent(range.endContainer, range.endOffset, range.startContainer, range.startOffset);
        } else selection.addRange(range);
        root.focus({preventScroll: true});
        range.startContainer.parentElement?.scrollIntoView({block: "center"});
        return record.id;
    }
    globalThis.SOLSurface = {codepointOffset, locatePoint, capture, validatePacket, restore};

    function start() {
        const data = document.getElementById("sol-data");
        if (!data) return;
        const records = JSON.parse(data.textContent).records;
        const notice = document.getElementById("notice");
        const show = message => { notice.textContent = message; };
        document.getElementById("context").addEventListener("click", event => {
            const visible = document.body.classList.toggle("show-context");
            event.target.setAttribute("aria-pressed", String(visible));
        });
        try {
            for (const root of document.querySelectorAll(".source[data-record-id]")) recordFor(root, records);
        } catch (error) {
            show(error.message);
            for (const button of document.querySelectorAll("button,input")) button.disabled = true;
            return;
        }
        // Buttons receive focus without destroying the last exact reading Range.
        let remembered = null;
        document.addEventListener("selectionchange", () => {
            const selection = getSelection();
            if (selection.rangeCount === 1 && sourceRoot(selection.getRangeAt(0).startContainer)) {
                remembered = {range: selection.getRangeAt(0).cloneRange(), focusNode: selection.focusNode, focusOffset: selection.focusOffset};
            } else if (!document.activeElement?.closest("nav")) remembered = null;
        });
        document.addEventListener("pointerdown", event => {
            if (!event.target.closest(".source,nav")) remembered = null;
        });
        const currentSelection = () => ({rangeCount: remembered ? 1 : 0, getRangeAt: () => remembered.range,
            focusNode: remembered?.focusNode, focusOffset: remembered?.focusOffset});
        const exportPacket = positionOnly => {
            try {
                const packet = capture(currentSelection(), records, positionOnly);
                const target = records.find(record => record.id === packet.reference.reference.target_id);
                validatePacket(packet, target);
                const blob = new Blob([JSON.stringify(packet, null, 2)], {type: "application/json"});
                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.download = positionOnly ? "sol-research-position.json" : "sol-research-selection.json";
                link.click();
                setTimeout(() => URL.revokeObjectURL(url), 1000);
                show("Exported a local research packet. Python validation is still required; no workspace was saved.");
            } catch (error) { show(error.message); }
        };
        document.getElementById("export-selection").addEventListener("click", () => exportPacket(false));
        document.getElementById("export-position").addEventListener("click", () => exportPacket(true));
        document.getElementById("restore").addEventListener("change", async event => {
            try {
                const file = event.target.files[0];
                if (!file || file.size > 1024 * 1024) fail("Choose one research packet smaller than 1 MiB.");
                restore(JSON.parse(await file.text()), records);
                show("Restored exact source position within this exported snapshot. Nothing was saved.");
            } catch (error) { show(error.message); }
            finally { event.target.value = ""; }
        });
    }
    if (typeof document !== "undefined") start();
})();
