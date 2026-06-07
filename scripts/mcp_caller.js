#!/usr/bin/env node
/**
 * Chrome DevTools MCP caller — sends single command, reads response, exits cleanly
 * Usage: echo '{"jsonrpc":"2.0","id":1,...}' | node mcp_caller.js
 */
const { exec } = require('child_process');

const BROWSER_URL = 'http://127.0.0.1:9222';
const MCP_BIN = '/opt/homebrew/bin/chrome-devtools-mcp';
const CALL_TIMEOUT_MS = 35000;

let input = '';
process.stdin.on('data', d => input += d.toString());
process.stdin.on('end', () => {
    try {
        const cmd = JSON.parse(input.trim());
        const p = exec(`${MCP_BIN} --browserUrl=${BROWSER_URL}`, { timeout: CALL_TIMEOUT_MS });
        let stdout = '', stderr = '';
        p.stdout.on('data', d => { stdout += d.toString(); });
        p.stderr.on('data', d => { /* ignore startup noise */ });

        const killTimer = setTimeout(() => {
            try { p.kill(); } catch(e) {}
            // Output what we have so far
            if (stdout.trim()) {
                process.stdout.write(stdout.trim().split('\n').pop() + '\n');
            }
            process.exit(0);
        }, CALL_TIMEOUT_MS - 1000);

        p.on('close', (code) => {
            clearTimeout(killTimer);
            // Parse and output the JSON result line
            const lines = stdout.trim().split('\n');
            const jsonLine = lines[lines.length - 1];
            try {
                const parsed = JSON.parse(jsonLine);
                process.stdout.write(JSON.stringify(parsed) + '\n');
            } catch(e) {
                // If no valid JSON, output last line anyway
                if (jsonLine) process.stdout.write(jsonLine + '\n');
            }
            process.exit(0);
        });

        p.stdin.write(JSON.stringify(cmd) + '\n');
        p.stdin.end();
    } catch(e) {
        process.stderr.write('ERROR:' + e.message + '\n');
        process.exit(1);
    }
});