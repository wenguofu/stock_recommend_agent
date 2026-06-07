#!/usr/bin/env node
/**
 * MCP wrapper - accepts JSON command on stdin, outputs JSON response on stdout
 * Uses exec which works correctly from shell
 */
const { exec } = require('child_process');
const fs = require('fs');

// Read single line command
let input = '';
process.stdin.setEncoding('utf8');
await new Promise(resolve => {
    const chunks = [];
    process.stdin.on('data', d => chunks.push(d));
    process.stdin.on('end', () => { input = chunks.join(''); resolve(); });
    setTimeout(() => resolve(), 2000);
});

input = input.trim();
if (!input) { process.exit(1); }

let cmd;
try { cmd = JSON.parse(input); } catch(e) { process.exit(1); }

// Use exec with bash -c
const script = `echo '${input.replace(/'/g, "'\\''")}' | /opt/homebrew/bin/chrome-devtools-mcp --browserUrl=http://127.0.0.1:9222`;

const child = exec(script, { timeout: 30000 });
let out = '', err = '';
child.stdout.on('data', d => { out += d.toString(); });
child.stderr.on('data', d => { /* startup noise */ });
child.on('close', () => {
    // Parse last line as JSON
    const lines = out.trim().split('\n').filter(l => l.trim() && l.startsWith('{'));
    if (lines.length > 0) {
        try {
            const parsed = JSON.parse(lines[lines.length - 1]);
            process.stdout.write(JSON.stringify(parsed) + '\n');
        } catch(e) {}
    }
    process.exit(0);
});