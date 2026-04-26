# Epistemic Debt Compiler

**Epistemic Debt Compiler** is a CLI gatekeeper that tracks uncertain agent reasoning and blocks high-risk actions until evidence is provided.

## Problem

Coding agents do not just suggest code anymore. They edit files, run commands, and make decisions inside the development loop.

The failure mode is not only bad code. It is **unsupported reasoning**:

- "This is probably the root cause."
- "This should work now."
- "I think this config is the issue, I'll change it."

Each claim may look harmless, but once an agent starts acting on top of earlier guesses, those guesses compound. In multi-step or multi-agent workflows, that uncertainty propagates into edits, commands, and approvals.

Today, developers usually have three bad options:

- read every agent message and manually judge confidence
- trust the agent and accept the risk
- avoid agent autonomy entirely

Epistemic Debt Compiler turns that hidden risk into something explicit, measurable, and gateable.

## Core Concept: Epistemic Debt

**Epistemic debt** is the accumulated risk created when an agent acts on claims that are not yet backed by evidence.

In this project, epistemic debt is:

- detected from language such as hedging, assumptions, or unverified claims
- increased by risky actions such as editing sensitive files or changing code without tests
- stored as local debt events in `.edc/debt.json`
- reduced only when the agent or user provides evidence such as tests, code references, logs, or documentation

The key idea is simple:

> We do not stop agents from acting. We stop them from acting without evidence.

## Main Commands

```bash
debt init
debt watch --file examples/session_safe.json
debt ls
debt explain <event-id>
debt repay <event-id> --test "pytest -q"
debt judge
debt dashboard
```

### What each command does

- `debt init`: initialize `.edc/` and optionally install a Claude Code hook
- `debt watch`: analyze an agent session from JSON or stdin and register debt events
- `debt ls`: list current unresolved debt
- `debt explain`: show details for a specific debt item
- `debt repay`: submit evidence and reduce or resolve debt
- `debt judge`: return the current verdict for whether the agent should proceed
- `debt dashboard`: launch a real-time tmux monitoring dashboard

### Connecting directly to agent sessions

Instead of passing a file, you can connect directly to a live or recorded agent session by session ID:

```bash
# Claude Code
debt watch-claude --session <session-id>

# OpenAI Codex
debt watch-codex --session <session-id>

# Google Gemini
debt watch-gemini --session <session-id>
```

### Real-time dashboard

Monitor debt accumulation live as an agent works:

```bash
# Latest Claude session in current project
debt dashboard --type claude

# Specific Codex session
debt dashboard --type codex <session-id>

# Specific Gemini session
debt dashboard --type gemini <session-id>
```

The dashboard runs inside tmux and updates in real time as new debt events are detected.

## Installation

### Requirements

- Python 3.11+

### Local install

```bash
git clone <repo-url>
cd Epistemic_Debt_Compiler
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Then initialize project state:

```bash
debt init --no-hook
```

## Example Run

Analyze a recorded agent session:

```bash
debt watch --file examples/demo_oauth/session_demo.json
```

Typical flow:

1. The agent says something uncertain such as "this is probably the issue."
2. `debt watch` records epistemic debt.
3. The agent attempts a risky action like editing an auth file without tests.
4. `debt judge` returns `EVIDENCE_REQUIRED`, `APPROVAL_REQUIRED`, or `BLOCK`.
5. `debt repay` submits evidence, for example a passing test.
6. `debt judge` moves back toward `ALLOW`.

Example:

```bash
debt watch --file examples/demo_oauth/session_demo.json
debt ls
debt judge
debt repay <event-id> --test "bash tests/run_oauth_tests.sh"
debt judge
```

## Why This Is Different From Lint / Policy / Eval Tools

Most existing tools check one of these:

- **Lint/static analysis**: is the code syntactically or stylistically valid?
- **Policy engines**: is this action allowed by predefined rules?
- **Eval frameworks**: did the model produce a good outcome on a benchmark?

Epistemic Debt Compiler checks something else:

- **Was the agent justified in acting the way it did, at this moment, with the evidence it had?**

That difference matters:

- it evaluates the **reasoning-to-action gap**, not just the final code
- it works **during execution**, not only before or after
- it produces a **local runtime gate**, not just a report
- it treats uncertainty as a **tracked liability** that must be repaid with evidence

In short, this project is closer to a runtime trust layer for agentic coding than to a traditional linter or benchmark.

## Roadmap

- replace rule-only classification with hybrid LLM + rule classification
- support more agent environments beyond Claude Code hooks
- add team-level policy profiles and project-specific thresholds
- persist debt to SQLite or a service backend for multi-agent coordination
- generate PR or CI reports for auditability
- learn from repayment patterns to calibrate risk scoring over time

## Hackathon Pitch

Epistemic Debt Compiler makes agent uncertainty operational.

Instead of asking developers to read every speculative agent message, it detects unsupported claims, assigns a risk score, and gates risky actions until evidence is attached. The result is a simple but powerful control layer for autonomous coding workflows: agents can move fast, but not blindly.

## Status

Hackathon MVP built with:

- Python 3.11+
- Typer
- Rich
- Pydantic

Core behavior is rule-driven and configured through `rules.json`.
