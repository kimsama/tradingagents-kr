# Anthropic OAuth model capture - 2026-05-02

Context: GitHub issue #1 / PRD-1.2 section 8 item 5 asked whether Claude
Code sends dated model IDs for Sonnet or Opus in OAuth mode.

## Capture method

- CLI: `claude --version` -> `2.1.126 (Claude Code)`.
- Binary: `/home/kimsama/.local/share/claude/versions/2.1.126`.
- Method: local HTTP capture server via `ANTHROPIC_BASE_URL` and
  `CLAUDE_CODE_API_BASE_URL`.
- The capture server parsed `/v1/messages` request bodies and printed only
  `model`, `max_tokens`, and `stream`; headers and OAuth tokens were not logged.

## Captured outbound model IDs

| CLI model argument | Outbound `model` | Notes |
| --- | --- | --- |
| `sonnet` | `claude-sonnet-4-6` | Current Sonnet alias target. |
| `opus` | `claude-opus-4-7` | Current Opus alias target. |
| `claude-sonnet-4-5` | `claude-sonnet-4-5` | No dated remap observed. |
| `claude-opus-4-5` | `claude-opus-4-5` | No dated remap observed. |

The Claude Code binary does contain dated strings such as
`claude-sonnet-4-5-20250929` and `claude-opus-4-5-20251101`, but they were not
emitted by the tested Sonnet/Opus request paths.

## Direct OAuth handshake result

Using TradingAgents' Anthropic OAuth HTTP client and the captured current alias
targets:

| Model | Result |
| --- | --- |
| `claude-sonnet-4-6` | `429 rate_limit_error`, message `Error`, request `req_011CacuXVv6cHVEr1AGAz5S9`. |
| `claude-opus-4-7` | `429 rate_limit_error`, message `Error`, request `req_011CacuXX7HJwkyZT2rV6ABn`. |

No model-level `422` rejection was observed for these captured IDs. The current
blocking condition is subscription/quota rate limiting, so a full success retry
needs a fresh Claude limit window.

## PRD-1.2 section 8 item 5 update

The dated model ID hypothesis is not confirmed for Claude Code 2.1.126. Current
Claude Code sends undated alias targets for the tested Sonnet and Opus paths.
PRD-1.3 should seed model mapping from captured active aliases first, and only
add dated forms after a live payload capture shows one being emitted.
