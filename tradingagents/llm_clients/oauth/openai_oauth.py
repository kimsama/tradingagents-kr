"""OpenAI (ChatGPT subscription) OAuth token manager via Codex CLI auth.json.

Reads `~/.codex/auth.json` written by Codex CLI's `codex login` flow and
exposes an `httpx.Client` that injects the bearer token on every request.

File format (verified 2026-05-02 against OpenClaw v24.12.0
`store-CcnCy00h.js:155`):

    {
      "tokens": {
        "access_token": "...",        // JWT
        "refresh_token": "...",
        "account_id": "...",
        "id_token": "..."             // optional
      },
      "last_refresh": "2026-05-01T12:34:56Z"
    }

Expiry is decoded from the access_token JWT's `exp` claim. If decoding
fails, fall back to `last_refresh + 1 hour`. As with the Anthropic side we
do not refresh — `codex login` is the supported renewal path.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx


_AUTH_FILE_ENV = "CODEX_AUTH_FILE"
_CODEX_HOME_ENV = "CODEX_HOME"
_DEFAULT_CODEX_HOME = "~/.codex"
_AUTH_FILENAME = "auth.json"
_FALLBACK_TTL_S = 3600


class OpenAIOAuthError(RuntimeError):
    """Raised when Codex OAuth credentials are missing, malformed, or expired."""


@dataclass(frozen=True)
class OpenAIOAuthCredentials:
    access_token: str
    refresh_token: str
    expires_at_ms: int
    account_id: Optional[str]
    id_token: Optional[str]
    source_path: Path

    @property
    def is_expired(self) -> bool:
        return self.expires_at_ms <= _now_ms()

    @property
    def seconds_until_expiry(self) -> int:
        return max(0, (self.expires_at_ms - _now_ms()) // 1000)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _resolve_auth_path(home_dir: Optional[Path] = None) -> Path:
    override = os.environ.get(_AUTH_FILE_ENV)
    if override:
        return Path(override).expanduser()
    codex_home = os.environ.get(_CODEX_HOME_ENV) or _DEFAULT_CODEX_HOME
    base = Path(codex_home).expanduser()
    if home_dir is not None and not Path(codex_home).is_absolute() and codex_home == _DEFAULT_CODEX_HOME:
        base = home_dir / ".codex"
    return base / _AUTH_FILENAME


def _decode_jwt_exp_ms(token: str) -> Optional[int]:
    """Best-effort JWT `exp` extraction. Returns None if the token isn't a JWT."""
    parts = token.split(".")
    if len(parts) < 2:
        return None
    try:
        payload_raw = parts[1]
        # urlsafe_b64decode requires correct padding
        padded = payload_raw + "=" * (-len(payload_raw) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and exp > 0:
        return int(exp * 1000)
    return None


def _parse_last_refresh_ms(value) -> Optional[int]:
    if isinstance(value, (int, float)):
        return int(value if value > 1e12 else value * 1000)
    if isinstance(value, str):
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except ValueError:
            return None
    return None


def _parse_credentials(raw: dict, source_path: Path) -> OpenAIOAuthCredentials:
    tokens = raw.get("tokens")
    if not isinstance(tokens, dict):
        raise OpenAIOAuthError(
            f"{source_path}: missing 'tokens' object — file does not look like a Codex auth.json"
        )

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    if not isinstance(access_token, str) or not access_token:
        raise OpenAIOAuthError(f"{source_path}: tokens.access_token is missing or empty")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise OpenAIOAuthError(f"{source_path}: tokens.refresh_token is missing or empty")

    expires_at = _decode_jwt_exp_ms(access_token)
    if expires_at is None:
        last_refresh = _parse_last_refresh_ms(raw.get("last_refresh"))
        base = last_refresh if last_refresh is not None else _now_ms()
        expires_at = base + _FALLBACK_TTL_S * 1000

    account_id = tokens.get("account_id") if isinstance(tokens.get("account_id"), str) else None
    id_token = tokens.get("id_token") if isinstance(tokens.get("id_token"), str) else None

    return OpenAIOAuthCredentials(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at_ms=expires_at,
        account_id=account_id,
        id_token=id_token,
        source_path=source_path,
    )


def load_credentials(home_dir: Optional[Path] = None) -> OpenAIOAuthCredentials:
    """Load Codex CLI OAuth credentials from disk.

    Resolution:
      1. `$CODEX_AUTH_FILE` (if set, used directly)
      2. `$CODEX_HOME/auth.json`
      3. `~/.codex/auth.json`
    """
    path = _resolve_auth_path(home_dir=home_dir)
    if not path.exists():
        raise OpenAIOAuthError(
            f"Codex CLI auth file not found at {path}. "
            "Run `codex login` once to sign in with your ChatGPT subscription, then retry."
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OpenAIOAuthError(f"{path}: invalid JSON ({exc})") from exc
    if not isinstance(raw, dict):
        raise OpenAIOAuthError(f"{path}: expected JSON object at top level")
    return _parse_credentials(raw, path)


def get_dummy_key() -> str:
    """Placeholder API key for langchain client init (real auth via http_client)."""
    return "sk-codex-oauth-placeholder-not-a-real-key"


def _build_headers(credentials: OpenAIOAuthCredentials) -> dict[str, str]:
    headers = {
        "authorization": f"Bearer {credentials.access_token}",
    }
    if credentials.account_id:
        # Codex CLI sends this; some endpoints require it for subscription routing.
        headers["chatgpt-account-id"] = credentials.account_id
    return headers


class _BearerAuth(httpx.Auth):
    requires_request_body = False
    requires_response_body = False

    def __init__(self, headers: dict[str, str], credentials: OpenAIOAuthCredentials):
        self._headers = headers
        self._credentials = credentials

    def auth_flow(self, request):  # type: ignore[override]
        if self._credentials.is_expired:
            raise OpenAIOAuthError(
                f"{self._credentials.source_path}: access token expired "
                f"{(_now_ms() - self._credentials.expires_at_ms) // 1000}s ago. "
                "Run `codex login` to refresh, then retry."
            )
        request.headers.pop("api-key", None)
        for k, v in self._headers.items():
            request.headers[k] = v
        yield request


def build_http_client(
    credentials: Optional[OpenAIOAuthCredentials] = None,
    *,
    base_url: str = "https://api.openai.com/v1",
    timeout: float = 600.0,
    home_dir: Optional[Path] = None,
) -> httpx.Client:
    """Build an `httpx.Client` configured for OpenAI OAuth-mode requests."""
    creds = credentials or load_credentials(home_dir=home_dir)
    headers = _build_headers(creds)
    return httpx.Client(
        base_url=base_url,
        timeout=timeout,
        auth=_BearerAuth(headers, creds),
    )
