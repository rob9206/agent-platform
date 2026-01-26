# Agent Platform

A local-first autonomous coding agent platform designed for professional software development workflows.

## Overview

This platform implements a complete agent-style coding system with the following capabilities:

**Plan → Retrieve → Patch → Test → Review → Iterate → Finalize**

Built with professional-grade reliability constraints:
- **Diff-only writes** - Models output unified diffs only, not direct file edits
- **Sandboxed execution** - Docker isolation with network controls
- **Policy-as-constitution** - YAML-based governance of permissions and checkpoints
- **Deterministic logging** - JSONL event trails + run artifacts
- **Worktree isolation** - Clean branches per run
- **Cancelable runs** - Cancel flag + dashboard controls
- **Eval harness** - Golden tasks + scoreboard for measuring performance

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Run the agent platform using the CLI:

```bash
./agentctl <command>
```

Or on Windows:

```bash
agentctl.bat <command>
```

## Architecture

The platform consists of:

1. **Gateway (FastAPI)** - OpenAI-compatible API with role-based routing
2. **Orchestrator** - Controls the coding loop with checkpoints and cancellation
3. **Tool Layer** - Retrieval, patching, dependency management, git worktrees
4. **Sandbox Runner** - Docker execution with policy enforcement
5. **Dashboard** - Live run monitoring with SSE log streaming
6. **Evals** - Task runner for measuring agent performance

## Configuration

Agent behavior is governed by `agent_policy.yaml`, which defines:
- Allowed commands
- Network rules per phase
- File access controls
- Resource limits
- Checkpoints and thresholds

## Documentation

See `CURSOR_AGENT_PLATFORM_SPEC.md` for the complete specification and design rationale.

## Development

This project follows the conventions in `.cursorrules` and uses:
- FastAPI for web services
- Pydantic for schemas
- PyYAML for policy configuration
- Docker for sandboxing
- Git worktrees for isolation

## License

MIT
