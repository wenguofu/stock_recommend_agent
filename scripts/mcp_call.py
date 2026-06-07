#!/usr/bin/env python3
"""
Chrome DevTools MCP caller - reliable subprocess approach
"""
import subprocess, os, time, select, json, tempfile, signal

CHROME_MCP = '/opt/homebrew/bin/chrome-devtools-mcp'
BROWSER_URL = 'http://127.0.0.1:9222'
TIMEOUT = 30

def mcp_bash(cmd_obj):
    """
    Send command via chrome-devtools-mcp, read response, always clean up.
    Uses shell pipe with select-based reading and explicit kill.
    """
    payload = json.dumps(cmd_obj)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(payload)
        tmp = f.name

    # Use shell=True but read in select loop
    p = subprocess.Popen(
        f'cat {tmp} | {CHROME_MCP} --browserUrl={BROWSER_URL}',
        shell=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    out = b''
    err = b''
    start = time.time()

    while time.time() - start < TIMEOUT:
        if p.poll() is not None:
            # Process ended
            break

        ready, _, _ = select.select([p.stdout, p.stderr], [], [], 0.5)
        for f in ready:
            try:
                chunk = os.read(f.fileno(), 8192)
                if chunk:
                    if f == p.stdout:
                        out += chunk
                    else:
                        err += chunk
            except OSError:
                pass

        # Check if we got complete response (has newline JSON)
        decoded = out.decode('utf8', errors='ignore')
        if '\n' in decoded:
            # Got response line - try to parse
            for line in reversed(decoded.strip().split('\n')):
                line = line.strip()
                if line and line.startswith('{'):
                    try:
                        result = json.loads(line)
                        # Found valid JSON - we're done
                        os.unlink(tmp)
                        try:
                            p.kill()
                        except:
                            pass
                        return result
                    except:
                        pass

    # Timeout or no valid response - kill and return what we have
    try:
        p.kill()
    except:
        pass

    os.unlink(tmp)

    # Try to extract any JSON from output
    decoded = out.decode('utf8', errors='ignore')
    for line in reversed(decoded.strip().split('\n')):
        line = line.strip()
        if line and line.startswith('{'):
            try:
                return json.loads(line)
            except:
                pass

    return None


if __name__ == '__main__':
    r = mcp_bash({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_pages","arguments":{}}})
    print(r)