#!/usr/bin/env node
/**
 * Simple robust MCP caller using exec
 * Usage: echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{...}}' | node mcp_simple.js
 */
const { exec } = require('child_process');
const fs = require('fs');

const MCP = '/opt/homebrew/bin/chrome-devtools-mcp';
const BROWSER_URL = 'http://127.0.0.1:9222';

// Read from stdin
let input = '';
process.stdin.setEncoding('utf8');
await new Promise(resolve => {
    process.stdin.on('data', d => input += d);
    process.stdin.on('end', resolve);
    setTimeout(resolve, 3000);
});

input = input.trim();
if (!input) {
    process.stderr.write('No input\n');
    process.exit(1);
}

let cmd;
try {
    cmd = JSON.parse(input);
} catch(e) {
    process.stderr.write('Invalid JSON\n');
    process.exit(1);
}

// Execute with bash -c and pipe
const script = `echo '${input}' | ${MCP} --browserUrl=${BROWSER_URL}`;

const p = exec(script, { timeout: 35000 });
let out = '', err = '';

p.stdout.on('data', d => { out += d.toString(); });
p.stderr.on('data', d => { /* ignore startup noise */ });

// Wait for process to complete (or timeout kills it)
p.on('close', (code) => {
    // Output the result - look for the JSON response line
    const lines = out.trim().split('\n').filter(l => l.trim());
    // Skip non-JSON lines (stderr noise, info messages)
    for (const l of lines) {
        try {
            const parsed = JSON.parse(l);
            if (parsed.id === cmd.id) {
                process.stdout.write(JSON.stringify(parsed) + '\n');
                process.exit(0);
            }
        } catch(e) {
            // Not JSON, skip
        }
    }
    // If no JSON found but we got output, output last line
    if (lines.length > 0) {
        process.stdout.write(lines[lines.length - 1] + '\n');
    }
    process.exit(0);
});