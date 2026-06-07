---
name: rtk-token-killer
description: "RTK (Rust Token Killer) — CLI proxy that reduces LLM token consumption by 60-90%. Wraps terminal commands (ls, git, grep, find, etc.) to produce ultra-compact output optimized for AI agent context windows."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [rtk, token, optimization, terminal, cli, proxy, context-efficiency]
---

# RTK (Rust Token Killer) — CLI Output Optimizer

RTK is a high-performance CLI proxy that sits between your terminal commands and the LLM context. It filters, compresses, and reformats command output so you use 60-90% fewer tokens on tool results.

## Prerequisites

```bash
# Install via Homebrew
brew install rtk

# Verify
rtk --version   # Should show 0.40.0+
```

## Init for Hermes (required)

```bash
rtk init --agent hermes -g --auto-patch
```

This creates:
- `~/.hermes/plugins/rtk-rewrite/` — Hermes plugin that rewrites terminal commands through RTK
- Modifies `~/.hermes/config.yaml` — enables the plugin
- After this, Hermes automatically wraps terminal commands with RTK

**Requires restart** — start a new Hermes session for the plugin to load.

## Key Commands

RTK mirrors common CLI tools with token-optimized output:

| Command | What it does |
|---------|-------------|
| `rtk ls` | Directory listing, compact format |
| `rtk tree` | Directory tree, token-optimized |
| `rtk read <file>` | Read with intelligent filtering |
| `rtk git <cmd>` | Git commands, compact output |
| `rtk grep <pat>` | Compact grep, strips whitespace |
| `rtk diff` | Ultra-condensed diff (changed lines only) |
| `rtk find <flags>` | Find files with compact tree output |
| `rtk err <cmd>` | Run command, show only errors/warnings |
| `rtk test <cmd>` | Run tests, show only failures |
| `rtk summary <cmd>` | Heuristic summary of command output |
| `rtk json <file>` | Compact JSON output |
| `rtk deps` | Project dependency summary |

## Self-Test

After initialization, verify it works:

```bash
# Hermes plugin check
ls ~/.hermes/plugins/rtk-rewrite/
# Should show __init__.py and plugin.yaml

# MCP server list check
hermes mcp list | grep rtk

# Functional test (run inside Hermes after restart)
# A simple git status should show RTK-compact output
```

## Integration with Other AI Agents

RTK supports multiple AI coding agents:

```bash
# Claude Code (default)
rtk init

# Hermes CLI
rtk init --agent hermes

# Cursor IDE
rtk init --agent cursor

# Windsurf IDE (Cascade)
rtk init --agent windsurf

# Codex CLI
rtk init --agent codex

# Cline / Roo Code
rtk init --agent cline

# Kilo Code
rtk init --agent kilocode

# Google Antigravity
rtk init --agent antigravity
```

## Ultra-Compact Mode

For maximum token savings, use ultra-compact mode on init:

```bash
rtk init --agent hermes --ultra-compact
```

This uses ASCII icons instead of Unicode and inline format instead of structured output.

## Pitfalls

1. **Plugin needs a Hermes restart** — `rtk init` writes config but the running session doesn't reload plugins mid-session. Start a new `hermes` session.
2. **Node-based MCP servers** — if you run `rtk init --agent hermes` inside a session, the output text confirms success but the change is only picked up next session.
3. **Not a Hermes MCP server** — RTK installs as a Hermes plugin (`rtk-rewrite`), not an MCP server. `hermes mcp list` won't show it.
4. **Uninstall** — `rtk init --agent hermes -g --uninstall` removes all RTK artifacts from Hermes.
