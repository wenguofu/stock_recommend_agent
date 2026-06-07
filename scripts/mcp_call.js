#!/usr/bin/env node
/**
 * MCP caller - Node.js wrapper for chrome-devtools-mcp (CommonJS, no ESM issues)
 * Reads JSON command from file or stdin, writes JSON response to stdout
 */
const { spawn } = require('child_process');
const fs = require('fs');

const BROWSER_URL = 'http://127.0.0.1:9222';
const MCP = '/opt/homebrew/bin/chrome-devtools-mcp';

let input = '';
if (process.argv.length > 2 && process.argv[2]) {
    input = fs.readFileSync(process.argv[2], 'utf8');
} else {
    // Read from stdin synchronously
    const fd = require('os').platform() === 'win32' ? require('process').stdin.fd : 0;
    try {
        const buf = require('fs').readFileSync('/dev/stdin', 'utf8');
        input = buf;
    } catch(e) {
        input = '';
    }
}

input = input.trim();
if (!input) {
    process.stderr.write('No input\n');
    process.exit(1);
}

let commands;
try {
    const parsed = JSON.parse(input);
    commands = Array.isArray(parsed) ? parsed : [parsed];
} catch(e) {
    process.stderr.write('Invalid JSON: ' + e.message + '\n');
    process.exit(1);
}

function callMCP(cmd) {
    return new Promise((resolve) => {
        const p = spawn(MCP, ['--browserUrl=' + BROWSER_URL]);
        let stdout = '';
        const timer = setTimeout(() => {
            try { p.kill(); } catch(e) {}
            resolve({ error: { code: -1, message: 'timeout' } });
        }, 30000);
        p.stdout.on('data', d => { stdout += d.toString(); });
        p.on('close', () => {
            clearTimeout(timer);
            const lines = stdout.trim().split('\n').filter(l => l.trim());
            const jsonLine = lines[lines.length - 1] || '';
            try {
                resolve(JSON.parse(jsonLine));
            } catch(e) {
                resolve({ error: { code: -2, message: 'parse failed' } });
            }
        });
        p.on('error', e => {
            clearTimeout(timer);
            resolve({ error: { code: -3, message: e.message } });
        });
        setTimeout(() => {
            try {
                p.stdin.write(JSON.stringify(cmd) + '\n');
                p.stdin.end();
            } catch(e) {
                clearTimeout(timer);
                resolve({ error: { code: -4, message: e.message } });
            }
        }, 500);
    });
}

// Run sequentially
(async () => {
    const results = [];
    for (const cmd of commands) {
        const r = await callMCP(cmd);
        results.push(r);
    }
    const output = results.length === 1 ? results[0] : results;
    process.stdout.write(JSON.stringify(output) + '\n');
    process.exit(0);
})();