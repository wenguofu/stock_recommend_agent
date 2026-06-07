#!/usr/bin/env node
/**
 * Direct CDP caller - full control over Chrome page navigation
 * Supports sequences of CDP commands with automatic page switching
 */
const WebSocket = require('ws');
const http = require('http');

let ws = null;
let msgId = 0;

function getPages() {
    return new Promise((resolve, reject) => {
        http.get('http://127.0.0.1:9222/json', (res) => {
            let data = '';
            res.on('data', c => data += c);
            res.on('end', () => {
                try { resolve(JSON.parse(data)); }
                catch(e) { reject(e); }
            });
        }).on('error', reject);
    });
}

function send(method, params = {}) {
    return new Promise(async (resolve, reject) => {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            const pages = await getPages();
            const target = pages.find(p => p.type === 'page') || pages[0];
            if (!target) return reject(new Error('No pages'));
            ws = new WebSocket(target.webSocketDebuggerUrl, { pingInterval: 30000 });
            await new Promise(r => ws.on('open', r));
        }

        const id = ++msgId;
        ws.send(JSON.stringify({ id, method, params }));
        ws.once('message', data => {
            try { resolve(JSON.parse(data.toString())); }
            catch(e) { resolve({ id, result: null }); }
        });
    });
}

function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
}

async function runSequence(commands) {
    const results = [];
    for (const cmd of commands) {
        // Special handling for navigate - we need to find its pageId after navigation
        if (cmd.method === 'Page.navigate') {
            // Close existing ws to force reconnection to new page
            if (ws) { try { ws.terminate(); ws = null; } catch(e) {} }
        }

        const r = await send(cmd.method, cmd.params);
        results.push(r);

        // Wait between commands if specified
        if (cmd._wait) await sleep(cmd._wait);

        // Auto-wait 500ms between commands
        if (!cmd._wait) await sleep(500);
    }
    return results;
}

// Read from stdin
let input = '';
process.stdin.on('data', d => input += d.toString());
process.stdin.on('end', async () => {
    try {
        const lines = input.trim().split('\n').filter(l => l.trim());
        const results = await runSequence(lines.map(l => JSON.parse(l)));
        process.stdout.write(JSON.stringify(results) + '\n');
    } catch(e) {
        process.stderr.write('ERROR:' + e.message + '\n');
        process.exit(1);
    }
});