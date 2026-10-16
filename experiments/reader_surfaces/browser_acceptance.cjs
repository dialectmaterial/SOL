/* Explicit opt-in real-browser test; invented corpus and disposable profile only. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require(process.env.SOL_PLAYWRIGHT_MODULE || 'playwright');

(async () => {
    const artifact = process.argv[2], downloadPath = process.argv[3];
    const browser = await chromium.launch({executablePath: process.env.SOL_TEST_CHROMIUM || '/usr/bin/google-chrome',
        headless: true, chromiumSandbox: true});
    try {
        const context = await browser.newContext({offline: true, acceptDownloads: true,
            serviceWorkers: 'block', viewport: {width: 1100, height: 850}});
        const page = await context.newPage(), errors = [], requests = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('request', request => requests.push(request.url()));
        await page.goto(pathToFileURL(artifact).href);
        await page.waitForFunction(() => !!globalThis.SOLSurface);
        const result = await page.evaluate(() => {
            const api = SOLSurface, records = JSON.parse(document.getElementById('sol-data').textContent).records;
            const roots = [...document.querySelectorAll('.source')], root = roots[0], source = records[0].plain_text;
            const ensure = (condition, message) => { if (!condition) throw new Error(message); };
            let checks = 0;
            const rejects = fn => { let rejected = false; try { fn(); } catch { rejected = true; }
                ensure(rejected, 'An unsafe mapping was accepted'); checks++; };
            for (let cp = 0; cp <= Array.from(source).length; cp++) {
                const point = api.locatePoint(root, cp, source);
                ensure(api.codepointOffset(root, ...point, source) === cp, 'Codepoint round trip disagrees'); checks++;
            }
            ensure(api.codepointOffset(root, root, root.childNodes.length, source) === Array.from(source).length,
                'Element child endpoint disagrees'); checks++;
            const walker = document.createTreeWalker(root, 4);
            for (let node = walker.nextNode(); node; node = walker.nextNode()) {
                for (let i = 0; i < node.data.length - 1; i++) {
                    if (/[\uD800-\uDBFF]/.test(node.data[i]) && /[\uDC00-\uDFFF]/.test(node.data[i + 1]))
                        rejects(() => api.codepointOffset(root, node, i + 1, source));
                }
            }
            const start = Array.from(source.slice(0, source.indexOf('thought'))).length;
            const end = Array.from(source.slice(0, source.indexOf('ground') + 6)).length;
            const range = document.createRange();
            range.setStart(...api.locatePoint(root, start, source));
            range.setEnd(...api.locatePoint(root, end, source));
            getSelection().removeAllRanges(); getSelection().addRange(range);
            const packet = api.capture(getSelection(), records);
            ensure(packet.selection.start === start && packet.selection.end === end, 'Styled span drift'); checks++;
            ensure(packet.selection.text === Array.from(source).slice(start, end).join(''), 'Exact slice drift'); checks++;
            const malformed = structuredClone(packet);
            malformed.reference.reference.chain = Object.fromEntries(malformed.reference.reference.chain.map((id, i) => [i, id]));
            rejects(() => api.validatePacket(malformed, records[0]));
            const changed = structuredClone(packet); changed.selection.text += '!';
            rejects(() => api.validatePacket(changed, records[0]));
            const negative = structuredClone(packet); negative.cursor_offset = true;
            rejects(() => api.validatePacket(negative, records[0]));
            const backward = structuredClone(packet); backward.cursor_offset = start;
            api.restore(backward, records);
            ensure(api.codepointOffset(root, getSelection().focusNode, getSelection().focusOffset, source) === start,
                'Backward selection cursor lost'); checks++;
            ensure(api.capture(getSelection(), records).cursor_offset === start, 'Backward recapture cursor lost'); checks++;
            root.appendChild(document.createTextNode('altered'));
            rejects(() => api.locatePoint(root, start, source));
            root.lastChild.remove();
            const cross = document.createRange(); cross.setStart(...api.locatePoint(root, 0, source));
            cross.setEnd(...api.locatePoint(roots[1], 1, records[1].plain_text));
            rejects(() => api.capture({rangeCount:1, getRangeAt:()=>cross}, records));
            const collapsed = document.createRange(); collapsed.setStart(...api.locatePoint(root, 0, source));
            rejects(() => api.capture({rangeCount:1, getRangeAt:()=>collapsed}, records));
            ensure(document.querySelectorAll('img,iframe,object,embed').length === 0, 'Source became active markup'); checks++;
            ensure(globalThis.sourceExecuted === undefined, 'Untrusted source executed'); checks++;
            api.restore(packet, records);
            return {checks, packet};
        });
        await page.getByRole('button', {name:'Source context', exact:true}).click();
        assert(await page.locator('.provenance').first().isVisible());
        await page.getByRole('button', {name:'Source context', exact:true}).click();
        assert.equal(await page.locator('.provenance').first().isVisible(), false);
        await page.setViewportSize({width: 520, height: 700});
        assert.deepEqual(await page.evaluate(packet => {
            const records = JSON.parse(document.getElementById('sol-data').textContent).records;
            document.querySelector('.source').style.fontSize = '25px';
            SOLSurface.restore(packet, records);
            return SOLSurface.capture(getSelection(), records);
        }, result.packet), result.packet);
        await page.waitForTimeout(50);
        const downloadPromise = page.waitForEvent('download');
        await page.getByRole('button', {name:'Export selected span', exact:true}).click();
        const download = await downloadPromise; await download.saveAs(downloadPath);
        assert.deepEqual(JSON.parse(fs.readFileSync(downloadPath, 'utf8')), result.packet);
        await page.locator('#restore').setInputFiles(downloadPath);
        await page.waitForFunction(() => document.getElementById('notice').textContent.startsWith('Restored exact'));
        await page.evaluate(() => {
            const range = document.createRange(); range.selectNodeContents(document.querySelector('h1'));
            getSelection().removeAllRanges(); getSelection().addRange(range);
            document.activeElement.blur();
        });
        await page.waitForTimeout(50);
        let unexpectedDownload = false;
        const onDownload = () => { unexpectedDownload = true; };
        page.on('download', onDownload);
        await page.getByRole('button', {name:'Export selected span', exact:true}).click();
        await page.waitForFunction(() => document.getElementById('notice').textContent.includes('Choose one source'));
        await page.waitForTimeout(50); assert.equal(unexpectedDownload, false);
        page.off('download', onDownload);
        await page.setViewportSize({width:1100,height:850});
        await page.evaluate(packet => SOLSurface.restore(packet, JSON.parse(document.getElementById('sol-data').textContent).records), result.packet);
        await page.screenshot({path:process.env.SOL_READER_SURFACE_SCREENSHOT || path.join(path.dirname(artifact), 'typeset.png')});
        assert.deepEqual(errors, []);
        assert(requests.every(url => url.startsWith('file:')), 'Nonlocal resource request');
        console.log(JSON.stringify({status:'passed', browser:await browser.version(), mapping_checks:result.checks,
            download_validated:true, no_remote_requests:true, reflow_and_reverse_selection:true}));
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
