#!/usr/bin/env python3
"""
Chrome DevTools MCP caller using PTY to ensure TTY stdin
"""
import subprocess, os, time, select, tempfile, json

CHROME_MCP = '/opt/homebrew/bin/chrome-devtools-mcp'
BROWSER_URL = 'http://127.0.0.1:9222'

def mcp_call(cmd_obj, timeout=35):
    """Send a JSON-RPC command to Chrome via chrome-devtools-mcp using PTY"""
    payload = json.dumps(cmd_obj)

    # Write command to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(payload + '\n')
        tmp = f.name

    # Create a bash script that pipes the file to chrome-devtools-mcp
    script = f'cat {tmp} | {CHROME_MCP} --browserUrl={BROWSER_URL}'

    # Use PTY to give a TTY
    master, slave = os.openpty()

    pid = os.fork()
    if pid == 0:
        # Child
        os.close(master)
        os.setsid()  # Create new session so PTY works properly
        os.dup2(slave, 0)  # stdin
        os.dup2(slave, 1)  # stdout
        os.dup2(slave, 2)  # stderr
        os.close(slave)
        os.execv('/bin/bash', ['/bin/bash', '-c', script])
        os._exit(1)
    else:
        # Parent
        os.close(slave)
        os.waitpid(pid, 0)  # Wait for child to finish writing

        # Read output from master
        out = b''
        start = time.time()
        while time.time() - start < timeout:
            ready, _, _ = select.select([master], [], [], 0.5)
            if ready:
                try:
                    chunk = os.read(master, 4096)
                    if chunk:
                        out += chunk
                    else:
                        break
                except OSError:
                    break
            if time.time() - start > timeout:
                break

        os.close(master)
        os.unlink(tmp)

        decoded = out.decode().strip()
        # Find JSON response line
        for line in reversed(decoded.split('\n')):
            line = line.strip()
            if line and line.startswith('{'):
                try:
                    return json.loads(line)
                except:
                    pass
        return None


if __name__ == '__main__':
    # Test
    r = mcp_call({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_pages","arguments":{}}})
    print(r)