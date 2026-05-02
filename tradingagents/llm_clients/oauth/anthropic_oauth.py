"""Anthropic OAuth token manager (Claude Pro/Max subscription).

Reads the credentials file written by Claude Code and exposes an
`httpx.Client` preconfigured with the headers Anthropic requires for an
OAuth bearer token. Refresh is intentionally NOT performed here — when the
token has expired we raise so the user can run `claude` once and have the
CLI rotate the file. This mirrors how Codex/Gemini adapters work today.

Required headers (verified 2026-05-02 against OpenClaw v24.12.0 — same
transport code path as claude-cli; see PRD-1.2 §5.5):

    Authorization: Bearer <access_token>
    anthropic-beta: claude-code-20250219,oauth-2025-04-20[,<extra-betas>]
    user-agent: claude-cli/<version>
    x-app: cli
    anthropic-dangerous-direct-browser-access: true

`x-api-key` must NOT be set — it conflicts with OAuth-mode auth on the
Anthropic backend.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import httpx


_REQUIRED_BETAS = ("claude-code-20250219", "oauth-2025-04-20")
_DEFAULT_USER_AGENT = "claude-cli/1.0.0"

# Lookup order for the credentials file. Claude Code writes the leading-dot
# variant; older docs / forks reference the no-dot variant. We accept both.
_CREDENTIAL_PATH_ENV = "CLAUDE_CREDENTIALS_FILE"
_CREDENTIAL_RELATIVE_PATHS = (
    Path(".claude") / ".credentials.json",
    Path(".claude") / "credentials.json",
    Path(".config") / "claude" / "credentials.json",
)


class AnthropicOAuthError(RuntimeError):
    """Raised when OAuth credentials are missing, malformed, or expired."""


@dataclass(frozen=True)
class AnthropicOAuthCredentials:
    access_token: str
    refresh_token: Optional[str]
    expires_at_ms: int
    source_path: Path

    @property
    def is_expired(self) -> bool:
        return self.expires_at_ms <= _now_ms()

    @property
    def seconds_until_expiry(self) -> int:
        return max(0, (self.expires_at_ms - _now_ms()) // 1000)

    def __repr__(self) -> str:
        refresh_token = "'<redacted>'" if self.refresh_token else "None"
        return (
            f"{type(self).__name__}("
            "access_token='<redacted>', "
            f"refresh_token={refresh_token}, "
            f"expires_at_ms={self.expires_at_ms!r}, "
            f"source_path={self.source_path!r})"
        )


def _now_ms() -> int:
    return int(time.time() * 1000)


def _candidate_paths(home_dir: Optional[Path] = None) -> Iterable[Path]:
    override = os.environ.get(_CREDENTIAL_PATH_ENV)
    if override:
        yield Path(override).expanduser()
    base = home_dir or Path.home()
    for rel in _CREDENTIAL_RELATIVE_PATHS:
        yield base / rel


def _parse_credentials(raw: dict, source_path: Path) -> AnthropicOAuthCredentials:
    block = raw.get("claudeAiOauth")
    if not isinstance(block, dict):
        raise AnthropicOAuthError(
            f"{source_path}: missing 'claudeAiOauth' object — file does not look "
            "like a Claude Code credentials.json"
        )

    access_token = block.get("accessToken")
    expires_at = block.get("expiresAt")
    refresh_token = block.get("refreshToken")

    if not isinstance(access_token, str) or not access_token:
        raise AnthropicOAuthError(f"{source_path}: claudeAiOauth.accessToken is missing or empty")
    if not isinstance(expires_at, (int, float)) or expires_at <= 0:
        raise AnthropicOAuthError(
            f"{source_path}: claudeAiOauth.expiresAt is missing or not a positive number"
        )

    return AnthropicOAuthCredentials(
        access_token=access_token,
        refresh_token=refresh_token if isinstance(refresh_token, str) and refresh_token else None,
        expires_at_ms=int(expires_at),
        source_path=source_path,
    )


def load_credentials(home_dir: Optional[Path] = None) -> AnthropicOAuthCredentials:
    """Load Claude Code OAuth credentials from disk.

    Search order:
      1. `$CLAUDE_CREDENTIALS_FILE` (if set)
      2. `~/.claude/.credentials.json` (current claude-cli default)
      3. `~/.claude/credentials.json` (legacy / forks)
      4. `~/.config/claude/credentials.json`

    Raises:
        AnthropicOAuthError: no candidate path exists, the file is malformed,
            or required fields are missing.
    """
    tried: list[Path] = []
    for path in _candidate_paths(home_dir):
        tried.append(path)
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AnthropicOAuthError(f"{path}: invalid JSON ({exc})") from exc
        if not isinstance(raw, dict):
            raise AnthropicOAuthError(f"{path}: expected JSON object at top level")
        return _parse_credentials(raw, path)

    formatted = "\n  - ".join(str(p) for p in tried)
    raise AnthropicOAuthError(
        "Claude Code OAuth credentials not found. Looked at:\n  - "
        + formatted
        + "\nRun `claude` (Claude Code CLI) once to sign in, then retry."
    )


def get_dummy_key() -> str:
    """Return a placeholder API key for langchain client init.

    `langchain_anthropic.ChatAnthropic` requires `api_key` to pass startup
    validation, but our custom `httpx.Client` injects the real bearer token
    on every request and strips `x-api-key`. Returning a clearly-fake string
    helps if it ever leaks into logs.
    """
    return "sk-ant-oauth-placeholder-not-a-real-key"


def _build_headers(
    credentials: AnthropicOAuthCredentials,
    *,
    extra_betas: Iterable[str] = (),
    user_agent: Optional[str] = None,
) -> dict[str, str]:
    betas = list(_REQUIRED_BETAS)
    for b in extra_betas:
        if b and b not in betas:
            betas.append(b)
    return {
        "authorization": f"Bearer {credentials.access_token}",
        "anthropic-beta": ",".join(betas),
        "user-agent": user_agent or _DEFAULT_USER_AGENT,
        "x-app": "cli",
        "anthropic-dangerous-direct-browser-access": "true",
    }


class _StripApiKeyAuth(httpx.Auth):
    """httpx auth hook: enforce OAuth headers and remove conflicting x-api-key.

    Re-reads credentials before each request would let us pick up
    out-of-band rotations by claude-cli. For now we keep the snapshot taken
    at client build time — Step 1 of the PRD doesn't include refresh — but
    we still raise loudly if the snapshot is already past its expiry so the
    failure mode is "401 with a confusing body" → "AnthropicOAuthError with
    actionable message" instead.
    """

    requires_request_body = False
    requires_response_body = False

    def __init__(self, headers: dict[str, str], credentials: AnthropicOAuthCredentials):
        self._headers = headers
        self._credentials = credentials

    def auth_flow(self, request):  # type: ignore[override]
        if self._credentials.is_expired:
            raise AnthropicOAuthError(
                f"{self._credentials.source_path}: access token expired "
                f"{(_now_ms() - self._credentials.expires_at_ms) // 1000}s ago. "
                "Run `claude` to refresh, then retry."
            )
        request.headers.pop("x-api-key", None)
        for k, v in self._headers.items():
            request.headers[k] = v
        yield request


def build_http_client(
    credentials: Optional[AnthropicOAuthCredentials] = None,
    *,
    base_url: str = "https://api.anthropic.com",
    extra_betas: Iterable[str] = (),
    user_agent: Optional[str] = None,
    timeout: float = 600.0,
    home_dir: Optional[Path] = None,
    transport: Optional[httpx.BaseTransport] = None,
) -> httpx.Client:
    """Build an `httpx.Client` configured for Anthropic OAuth-mode requests.

    The returned client is suitable for passing to `langchain_anthropic`
    via `ChatAnthropic(http_client=...)`.
    """
    creds = credentials or load_credentials(home_dir=home_dir)
    headers = _build_headers(creds, extra_betas=extra_betas, user_agent=user_agent)
    return httpx.Client(
        base_url=base_url,
        timeout=timeout,
        auth=_StripApiKeyAuth(headers, creds),
        transport=transport,
    )


def build_async_http_client(
    credentials: Optional[AnthropicOAuthCredentials] = None,
    *,
    base_url: str = "https://api.anthropic.com",
    extra_betas: Iterable[str] = (),
    user_agent: Optional[str] = None,
    timeout: float = 600.0,
    home_dir: Optional[Path] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> httpx.AsyncClient:
    """Build an async `httpx.AsyncClient` configured for Anthropic OAuth."""
    creds = credentials or load_credentials(home_dir=home_dir)
    headers = _build_headers(creds, extra_betas=extra_betas, user_agent=user_agent)
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=timeout,
        auth=_StripApiKeyAuth(headers, creds),
        transport=transport,
    )
