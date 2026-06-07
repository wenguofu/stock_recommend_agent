#!/usr/bin/env node
/**
 * CDP direct caller - bypasses chrome-devtools-mcp
 */
const http = require('http');
const WebSocket = require('ws');

let ws = null;
let msgId = 0;

function getWsUrl() {
    return new Promise((resolve, reject) => {
        http.get('http://127.0.0.1:9222/json', res => {
            let data = '';
            res.on('data', c => data += c);
            res.on('end', () => {
                try {
                    const pages = JSON.parse(data);
                    const t = pages.find(p => p.type === 'page') || pages[0];
                    resolve(t.webSocketDebuggerUrl);
                } catch(e) { reject(e); }
            });
        }).on('error', reject);
    });
}

function sendCDP(method, params = {}) {
    return new Promise(async (resolve) => {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            const url = await getWsUrl();
            ws = new WebSocket(url, { pingInterval: 30000 });
            await new Promise(r => ws.on('open', r));
        }
        const id = ++msgId;
        const handler = (data) => {
            try {
                const resp = JSON.parse(data.toString());
                if (resp.id === id) {
                    ws.removeListener('message', handler);
                    resolve(resp);
                }
            } catch(e) {}
        };
        ws.on('message', handler);
        ws.send(JSON.stringify({ id, method, params }));
        setTimeout(() => resolve({ id, error: 'timeout' }), 28000);
    });
}

async function main() {
    let input = '';
    process.stdin.setEncoding('utf8');
    await new Promise(r => {
        process.stdin.on('data', d => input += d);
        process.stdin.on('end', r);
        setTimeout(r, 3000);
    });
    input = input.trim();
    if (!input) process.exit(1);

    const cmd = JSON.parse(input);
    const { method, params, _wait } = cmd;

    const result = await sendCDP(method, params);

    // If navigate and _wait specified, wait then get DOM snapshot
    if (method === 'Page.navigate' && _wait && _wait > 0) {
        await new Promise(r => setTimeout(r, _wait));
        // Use Runtime.evaluate to get accessible text
        const snap = await sendCDP('Runtime.evaluate', {
            expression: 'JSON.stringify(document.title + " | " + document.body ? document.body.innerText.substring(0,1000) : "")',
            returnByValue: true
        });
        process.stdout.write(JSON.stringify(snap) + '\n');
    } else {
        process.stdout.write(JSON.stringify(result) + '\n');
    }

    if (ws) ws.close();
    process.exit(0);
}

main().catch(e => { console.error(e.message); process.exit(1); });