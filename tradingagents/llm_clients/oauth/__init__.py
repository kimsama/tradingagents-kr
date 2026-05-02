"""OAuth token managers for subscription-based LLM access.

Reads credentials written by Claude Code (`~/.claude/.credentials.json`) and
Codex CLI (`~/.codex/auth.json`) so TradingAgents can route requests through
the user's Claude Pro/Max or ChatGPT subscription instead of API-key billing.

Refresh is delegated to the source CLI (Claude Code / Codex) — running
`claude` or `codex login` is the supported way to renew an expired token.
The token managers here only read.
"""

from .anthropic_oauth import (
    AnthropicOAuthError,
    AnthropicOAuthCredentials,
    build_async_http_client as build_anthropic_http_client_async,
    build_http_client as build_anthropic_http_client,
    load_credentials as load_anthropic_credentials,
)
from .openai_oauth import (
    OpenAIOAuthError,
    OpenAIOAuthCredentials,
    build_async_http_client as build_openai_http_client_async,
    build_http_client as build_openai_http_client,
    load_credentials as load_openai_credentials,
)

__all__ = [
    "AnthropicOAuthError",
    "AnthropicOAuthCredentials",
    "build_anthropic_http_client",
    "build_anthropic_http_client_async",
    "load_anthropic_credentials",
    "OpenAIOAuthError",
    "OpenAIOAuthCredentials",
    "build_openai_http_client",
    "build_openai_http_client_async",
    "load_openai_credentials",
]
