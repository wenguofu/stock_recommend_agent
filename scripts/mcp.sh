#!/bin/bash
# mcp.sh - Bash wrapper for chrome-devtools-mcp
# Reads JSON command from stdin, writes JSON response to stdout

/tmp/mcp_cmd.txt 2>/dev/null && rm -f /tmp/mcp_cmd.txt

# Write stdin to temp file
cat > /tmp/mcp_cmd.txt

# Run chrome-devtools-mcp with the command
# Use a subshell with controlled timeout
(
    timeout 35 /opt/homebrew/bin/chrome-devtools-mcp --browserUrl=http://127.0.0.1:9222 < /tmp/mcp_cmd.txt 2>/dev/null
) &
MCP_PID=$!

# Wait for output with timeout
sleep 30

# Kill if still running
if kill -0 $MCP_PID 2>/dev/null; then
    kill $MCP_PID 2>/dev/null
fi

rm -f /tmp/mcp_cmd.txt