#!/usr/bin/env node
/** CDP F10 Fetcher - robust version */
const http = require('http');
const WebSocket = require('ws');

function getWsUrl(contains) {
    return new Promise((resolve) => {
        http.get('http://127.0.0.1:9222/json', res => {
            let d = '';
            res.on('data', c => d += c);
            res.on('end', () => {
                try {
                    const pages = JSON.parse(d);
                    const t = pages.find(p => contains ? p.url.includes(contains) : true);
                    resolve(t ? t.webSocketDebuggerUrl : null);
                } catch(e) { resolve(null); }
            });
        }).on('error', () => resolve(null));
    });
}

function cdpCmd(wsUrl, method, params = {}) {
    return new Promise((resolve) => {
        const ws = new WebSocket(wsUrl, { pingInterval: 30000 });
        const id = 99;
        const onMsg = (data) => {
            try {
                const r = JSON.parse(data.toString());
                if (r.id === id) { ws.removeListener('message', onMsg); ws.close(); resolve(r); }
            } catch(e) {}
        };
        ws.on('message', onMsg);
        ws.on('error', () => resolve({ error: 'ws error' }));
        ws.on('open', () => {
            ws.send(JSON.stringify({ id, method, params }));
        });
        setTimeout(() => { try { ws.close(); } catch(e) {} resolve({ error: 'timeout' }); }, 27000);
    });
}

async function pageText(url) {
    // Find F10 page WS
    const wsUrl = await getWsUrl('emweb.securities.eastmoney.com/pc_hsf10');
    if (!wsUrl) { console.error('No F10 page found'); return ''; }

    // Navigate on existing WS (don't close first - navigate then evaluate)
    await cdpCmd(wsUrl, 'Page.navigate', { url });

    // Wait for SPA
    await new Promise(r => setTimeout(r, 22000));

    // Evaluate on SAME WS (navigation happened on this connection)
    const r = await cdpCmd(wsUrl, 'Runtime.evaluate', {
        expression: 'document.body ? document.body.innerText : ""',
        returnByValue: true
    });

    return r.result?.result?.value || '';
}

async function main() {
    const [, , code='002463', prefix='SZ'] = process.argv;
    const base = `https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=${prefix}${code}&color=b`;
    try {
        const hxtc = await pageText(`${base}#/hxtc`);
        const gsgk = await pageText(`${base}#/gsgk`);
        const ylyc = await pageText(`${base}#/ylyc`);
        process.stdout.write(JSON.stringify({ code, hxtc, gsgk, ylyc }) + '\n');
    } catch(e) {
        process.stdout.write(JSON.stringify({ error: e.message }) + '\n');
    }
    process.exit(0);
}

main();