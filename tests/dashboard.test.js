const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const root = path.resolve(__dirname, '..');

function dashboard() {
    const nodes = new Map();
    const plots = new Map();
    const makeNode = () => ({
        style: {}, children: [], listeners: {}, textContent: '',
        classList: { add() {}, remove() {} },
        addEventListener(name, fn) { this.listeners[name] = fn; },
        append(...children) { this.children.push(...children); },
        replaceChildren() { this.children = []; }
    });
    const context = vm.createContext({
        document: {
            getElementById(id) {
                if (!nodes.has(id)) nodes.set(id, makeNode());
                return nodes.get(id);
            },
            createElement: makeNode
        },
        window: {},
        Plotly: { react(id, traces, layout) { plots.set(id, { traces, layout }); } }
    });
    vm.runInContext(fs.readFileSync(path.join(root, 'docs/data.js'), 'utf8'), context);
    const html = fs.readFileSync(path.join(root, 'docs/index.html'), 'utf8');
    const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1];
    vm.runInContext(script, context);
    return { context, nodes, plots };
}

test('all four modes render TTR and MATTR with correct sample sizes', () => {
    const { context, plots } = dashboard();
    for (const mode of ['10', '5', '1', 'L']) {
        vm.runInContext(`setMode('${mode}')`, context);
        const { traces, layout } = plots.get('chartTTR');
        assert.equal(traces.length, 2);
        assert.deepEqual(Array.from(layout.yaxis.range), [0, 1]);
        assert.equal(layout.yaxis.fixedrange, true);
        for (const trace of traces) {
            assert.equal(trace.x.length, trace.y.length);
            assert.equal(trace.y.length, trace.customdata.length);
            assert.ok(trace.y.every(value => value === null || (value >= 0 && value <= 1)));
        }
        if (mode === 'L') {
            assert.equal(traces[0].type, 'bar');
            assert.ok(traces[0].y.every((value, i, values) => i === 0 || values[i - 1] >= value));
        }
        assert.ok(plots.get('chartPlacesHeatmap').traces[0].y.every(region => !['China', 'Chinese Mainland'].includes(region)));
    }
    vm.runInContext("setMode('10')", context);
    assert.equal(plots.get('chartTTR').traces[0].customdata[0], 232);
    assert.equal(plots.get('chartTTR').traces[1].customdata[0], 231);
});

test('ranking handles quotes and markup as text and opens the intended lyrics', () => {
    const { context, nodes } = dashboard();
    vm.runInContext(`data.songs.push({
        id: "quote'id", title: '<img src=x onerror=alert(1)>', singer: 'Singer', year: 2025,
        metrics: { ttr: 1 }, lyrics: 'Test lyrics'
    }); toggleSongs('listTTR', 'ttr', true);`, context);
    const item = nodes.get('listTTR').children.find(child => child.children[0].textContent.includes('<img'));
    assert.ok(item);
    assert.equal(item.children[0].children.length, 0);
    item.listeners.click();
    assert.equal(nodes.get('lyricsContent').innerText, 'Test lyrics');
    assert.equal(nodes.get('lyricsModal').style.display, 'block');
    vm.runInContext("toggleSongs('listTTR', 'ttr', true)", context);
    assert.equal(nodes.get('listTTR').style.display, 'none');
});

test('MATTR ranking excludes short-song null measurements', () => {
    const { context, nodes } = dashboard();
    vm.runInContext(`data.songs = [
        {id: 'short', title: 'Short', year: 2025, singer: 'S', metrics: {mattr_50: null}},
        {id: 'valid', title: 'Valid', year: 2025, singer: 'S', metrics: {mattr_50: 0.9}}
    ]; toggleSongs('listMATTR', 'mattr_50', true);`, context);
    assert.equal(nodes.get('listMATTR').children.length, 1);
    assert.match(nodes.get('listMATTR').children[0].children[0].textContent, /Valid/);
});
