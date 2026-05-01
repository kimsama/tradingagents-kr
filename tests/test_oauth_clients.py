"""Unit tests for OAuth token managers (PRD-1.2 §6 step 1).

Covers required scenarios:
  - missing credentials file
  - malformed credentials file
  - expired token (load + http hook)
  - happy path: required headers injected, x-api-key stripped
"""

from __future__ import annotations

import base64
import json
import time

import httpx
import pytest

from tradingagents.llm_clients.oauth import (
    AnthropicOAuthCredentials,
    AnthropicOAuthError,
    OpenAIOAuthCredentials,
    OpenAIOAuthError,
    build_anthropic_http_client,
    build_openai_http_client,
    load_anthropic_credentials,
    load_openai_credentials,
)
from tradingagents.llm_clients.oauth import anthropic_oauth, openai_oauth


# --- helpers ----------------------------------------------------------------

def _ms_from_now(seconds: int) -> int:
    return int((time.time() + seconds) * 1000)


def _make_jwt(exp_seconds_from_now: int) -> str:
    """Minimal unsigned JWT with the requested `exp` claim."""
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps({"exp": int(time.time()) + exp_seconds_from_now}).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{payload}.sig"


def _write_claude_creds(tmp_path, *, expires_at_ms: int, access_token="sk-ant-oat-test", refresh_token="rt-test"):
    creds_dir = tmp_path / ".claude"
    creds_dir.mkdir(parents=True, exist_ok=True)
    path = creds_dir / ".credentials.json"
    path.write_text(json.dumps({
        "claudeAiOauth": {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresAt": expires_at_ms,
        }
    }))
    return path


def _write_codex_creds(tmp_path, *, jwt_exp_seconds=3600, access_token=None, account_id="acc-123"):
    creds_dir = tmp_path / ".codex"
    creds_dir.mkdir(parents=True, exist_ok=True)
    path = creds_dir / "auth.json"
    token = access_token if access_token is not None else _make_jwt(jwt_exp_seconds)
    path.write_text(json.dumps({
        "tokens": {
            "access_token": token,
            "refresh_token": "rt-codex",
            "account_id": account_id,
        },
        "last_refresh": "2026-05-01T12:00:00Z",
    }))
    return path


# --- Anthropic: missing / malformed -----------------------------------------

@pytest.mark.unit
def test_anthropic_missing_file_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CREDENTIALS_FILE", raising=False)
    with pytest.raises(AnthropicOAuthError, match="not found"):
        load_anthropic_credentials(home_dir=tmp_path)


@pytest.mark.unit
def test_anthropic_malformed_json_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CREDENTIALS_FILE", raising=False)
    creds_dir = tmp_path / ".claude"
    creds_dir.mkdir()
    (creds_dir / ".credentials.json").write_text("{not json")
    with pytest.raises(AnthropicOAuthError, match="invalid JSON"):
        load_anthropic_credentials(home_dir=tmp_path)


@pytest.mark.unit
def test_anthropic_missing_oauth_block_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CREDENTIALS_FILE", raising=False)
    creds_dir = tmp_path / ".claude"
    creds_dir.mkdir()
    (creds_dir / ".credentials.json").write_text(json.dumps({"some": "other"}))
    with pytest.raises(AnthropicOAuthError, match="claudeAiOauth"):
        load_anthropic_credentials(home_dir=tmp_path)


@pytest.mark.unit
def test_anthropic_env_override_used(tmp_path, monkeypatch):
    custom = tmp_path / "elsewhere.json"
    custom.write_text(json.dumps({
        "claudeAiOauth": {
            "accessToken": "sk-ant-oat-x",
            "refreshToken": "r",
            "expiresAt": _ms_from_now(3600),
        }
    }))
    monkeypatch.setenv("CLAUDE_CREDENTIALS_FILE", str(custom))
    creds = load_anthropic_credentials(home_dir=tmp_path)
    assert creds.source_path == custom
    assert creds.access_token == "sk-ant-oat-x"


@pytest.mark.unit
def test_anthropic_legacy_path_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CREDENTIALS_FILE", raising=False)
    legacy_dir = tmp_path / ".claude"
    legacy_dir.mkdir()
    legacy = legacy_dir / "credentials.json"  # no leading dot
    legacy.write_text(json.dumps({
        "claudeAiOauth": {
            "accessToken": "sk-ant-oat-legacy",
            "refreshToken": "r",
            "expiresAt": _ms_from_now(3600),
        }
    }))
    creds = load_anthropic_credentials(home_dir=tmp_path)
    assert creds.source_path == legacy


# --- Anthropic: expired token -----------------------------------------------

@pytest.mark.unit
def test_anthropic_expired_credential_flag(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CREDENTIALS_FILE", raising=False)
    _write_claude_creds(tmp_path, expires_at_ms=_ms_from_now(-60))
    creds = load_anthropic_credentials(home_dir=tmp_path)
    assert creds.is_expired
    assert creds.seconds_until_expiry == 0


@pytest.mark.unit
def test_anthropic_expired_token_blocks_request(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CREDENTIALS_FILE", raising=False)
    _write_claude_creds(tmp_path, expires_at_ms=_ms_from_now(-60))
    client = build_anthropic_http_client(home_dir=tmp_path)
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"ok": True}))
    client._transport = transport
    with pytest.raises(AnthropicOAuthError, match="expired"):
        client.get("/v1/messages")
    client.close()


# --- Anthropic: happy path / header verification ----------------------------

@pytest.mark.unit
def test_anthropic_required_headers_injected(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CREDENTIALS_FILE", raising=False)
    _write_claude_creds(tmp_path, expires_at_ms=_ms_from_now(3600))

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"ok": True})

    client = build_anthropic_http_client(
        home_dir=tmp_path,
        extra_betas=["fine-grained-tool-streaming-2025-05-14"],
        user_agent="claude-cli/9.9.9",
    )
    client._transport = httpx.MockTransport(handler)
    # Prime an outgoing x-api-key to verify it gets stripped.
    client.headers["x-api-key"] = "should-be-removed"
    client.get("/v1/messages")
    client.close()

    h = captured["headers"]
    assert h["authorization"] == "Bearer sk-ant-oat-test"
    # Both required betas, in canonical order, plus the extra appended.
    assert h["anthropic-beta"] == (
        "claude-code-20250219,oauth-2025-04-20,fine-grained-tool-streaming-2025-05-14"
    )
    assert h["user-agent"] == "claude-cli/9.9.9"
    assert h["x-app"] == "cli"
    assert h["anthropic-dangerous-direct-browser-access"] == "true"
    assert "x-api-key" not in h


@pytest.mark.unit
def test_anthropic_dummy_key_is_obviously_fake():
    assert "placeholder" in anthropic_oauth.get_dummy_key()


# --- OpenAI / Codex: missing & malformed ------------------------------------

@pytest.mark.unit
def test_openai_missing_file_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEX_AUTH_FILE", raising=False)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "missing-codex"))
    with pytest.raises(OpenAIOAuthError, match="not found"):
        load_openai_credentials()


@pytest.mark.unit
def test_openai_malformed_json_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEX_AUTH_FILE", raising=False)
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text("not json {")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    with pytest.raises(OpenAIOAuthError, match="invalid JSON"):
        load_openai_credentials()


@pytest.mark.unit
def test_openai_missing_tokens_block_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEX_AUTH_FILE", raising=False)
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text(json.dumps({"unrelated": True}))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    with pytest.raises(OpenAIOAuthError, match="tokens"):
        load_openai_credentials()


# --- OpenAI / Codex: expiry handling ----------------------------------------

@pytest.mark.unit
def test_openai_jwt_expiry_decoded(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEX_AUTH_FILE", raising=False)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    _write_codex_creds(tmp_path, jwt_exp_seconds=120)
    creds = load_openai_credentials()
    assert not creds.is_expired
    assert 60 < creds.seconds_until_expiry <= 120


@pytest.mark.unit
def test_openai_non_jwt_falls_back_to_last_refresh(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEX_AUTH_FILE", raising=False)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    _write_codex_creds(tmp_path, access_token="opaque-not-a-jwt")
    creds = load_openai_credentials()
    # last_refresh is 2026-05-01T12:00:00Z; +1h fallback. Expiry == frozen past.
    assert creds.expires_at_ms > 0


@pytest.mark.unit
def test_openai_expired_token_blocks_request(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEX_AUTH_FILE", raising=False)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    _write_codex_creds(tmp_path, jwt_exp_seconds=-60)
    client = build_openai_http_client(home_dir=tmp_path)
    client._transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"ok": True}))
    with pytest.raises(OpenAIOAuthError, match="expired"):
        client.get("/responses")
    client.close()


@pytest.mark.unit
def test_openai_env_override_used(tmp_path, monkeypatch):
    custom = tmp_path / "elsewhere.json"
    custom.write_text(json.dumps({
        "tokens": {
            "access_token": _make_jwt(3600),
            "refresh_token": "r",
            "account_id": "a",
        }
    }))
    monkeypatch.setenv("CODEX_AUTH_FILE", str(custom))
    creds = load_openai_credentials()
    assert creds.source_path == custom
    assert creds.account_id == "a"


# --- OpenAI / Codex: happy path / headers -----------------------------------

@pytest.mark.unit
def test_openai_required_headers_injected(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEX_AUTH_FILE", raising=False)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    _write_codex_creds(tmp_path, jwt_exp_seconds=3600)

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"ok": True})

    client = build_openai_http_client(home_dir=tmp_path)
    client._transport = httpx.MockTransport(handler)
    client.get("/responses")
    client.close()

    h = captured["headers"]
    assert h["authorization"].startswith("Bearer ")
    assert h["chatgpt-account-id"] == "acc-123"


@pytest.mark.unit
def test_openai_dummy_key_is_obviously_fake():
    assert "placeholder" in openai_oauth.get_dummy_key()


# --- Factory wiring (PRD-1.2 §6 step 4) -------------------------------------
#
# Pin the contract between create_llm_client(...) and the per-provider
# clients: auth_mode propagation through the factory, env-var fallback,
# rejection for unsupported providers, and no regression for the default
# api_key path.

from tradingagents.llm_clients.factory import create_llm_client, _resolve_auth_mode
from tradingagents.llm_clients.anthropic_client import AnthropicClient
from tradingagents.llm_clients.openai_client import OpenAIClient


@pytest.mark.unit
def test_factory_default_auth_mode_is_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_AUTH_MODE", raising=False)
    monkeypatch.delenv("OPENAI_AUTH_MODE", raising=False)
    a = create_llm_client(provider="anthropic", model="claude-opus-4-7")
    o = create_llm_client(provider="openai", model="gpt-5.4")
    assert isinstance(a, AnthropicClient) and a.auth_mode == "api_key"
    assert isinstance(o, OpenAIClient) and o.auth_mode == "api_key"


@pytest.mark.unit
def test_factory_explicit_oauth_propagates_to_anthropic_client():
    client = create_llm_client(
        provider="anthropic", model="claude-opus-4-7", auth_mode="oauth",
    )
    assert isinstance(client, AnthropicClient)
    assert client.auth_mode == "oauth"


@pytest.mark.unit
def test_factory_explicit_oauth_propagates_to_openai_client():
    client = create_llm_client(
        provider="openai", model="gpt-5.4", auth_mode="oauth",
    )
    assert isinstance(client, OpenAIClient)
    assert client.auth_mode == "oauth"
    assert client.provider == "openai"


@pytest.mark.unit
def test_factory_env_var_fallback_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AUTH_MODE", "oauth")
    client = create_llm_client(provider="anthropic", model="claude-opus-4-7")
    assert client.auth_mode == "oauth"


@pytest.mark.unit
def test_factory_env_var_fallback_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_AUTH_MODE", "oauth")
    client = create_llm_client(provider="openai", model="gpt-5.4")
    assert client.auth_mode == "oauth"


@pytest.mark.unit
def test_factory_explicit_arg_overrides_env_var(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AUTH_MODE", "oauth")
    client = create_llm_client(
        provider="anthropic", model="claude-opus-4-7", auth_mode="api_key",
    )
    assert client.auth_mode == "api_key"


@pytest.mark.unit
def test_factory_env_var_invalid_falls_back_to_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AUTH_MODE", "garbage")
    assert _resolve_auth_mode("anthropic", None) == "api_key"


@pytest.mark.unit
@pytest.mark.parametrize(
    "provider", ["google", "azure", "xai", "deepseek", "qwen", "glm", "openrouter", "ollama"],
)
def test_factory_oauth_rejected_for_unsupported_provider(provider):
    with pytest.raises(ValueError, match="oauth"):
        create_llm_client(provider=provider, model="some-model", auth_mode="oauth")


@pytest.mark.unit
def test_openai_client_rejects_oauth_for_non_openai_provider():
    """Belt-and-suspenders: even if factory bypassed, client guards itself."""
    with pytest.raises(ValueError, match="provider='openai'"):
        OpenAIClient(model="grok-4", provider="xai", auth_mode="oauth")


# --- get_llm() injection through factory (PRD-1.2 §6 step 4) ----------------

@pytest.mark.unit
def test_factory_anthropic_oauth_get_llm_constructs(tmp_path, monkeypatch):
    """Factory + oauth → get_llm() builds langchain wrapper without error.

    No real HTTP call is made; we just verify the wrapper accepts the OAuth
    http_client + dummy api_key kwargs the client injects.
    """
    monkeypatch.delenv("CLAUDE_CREDENTIALS_FILE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_claude_creds(tmp_path, expires_at_ms=_ms_from_now(3600))

    client = create_llm_client(
        provider="anthropic", model="claude-opus-4-7", auth_mode="oauth",
    )
    llm = client.get_llm()
    assert llm.model == "claude-opus-4-7"


@pytest.mark.unit
def test_anthropic_oauth_http_client_reaches_sdk(tmp_path, monkeypatch):
    """Regression: langchain_anthropic._client must use OUR http_client.

    Without the NormalizedChatAnthropic._client override, langchain builds
    its own httpx client and discards the OAuth one — silently breaking auth.
    We assert the underlying anthropic.Client was constructed with our
    OAuth httpx.Client instance, not a fresh one.
    """
    monkeypatch.delenv("CLAUDE_CREDENTIALS_FILE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_claude_creds(tmp_path, expires_at_ms=_ms_from_now(3600))

    client = create_llm_client(
        provider="anthropic", model="claude-opus-4-7", auth_mode="oauth",
    )
    llm = client.get_llm()
    # Trigger _client cached_property build
    sdk_client = llm._client
    # The Anthropic SDK exposes the underlying httpx client as `_client`.
    underlying_httpx = getattr(sdk_client, "_client", None)
    assert underlying_httpx is llm._oauth_http_client, (
        "OAuth httpx client was not propagated to the Anthropic SDK — "
        "langchain wrapper is silently discarding it."
    )


@pytest.mark.unit
def test_anthropic_api_key_mode_uses_default_sdk_client(monkeypatch):
    """Regression: api_key mode must NOT trigger the OAuth http_client path."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    client = create_llm_client(
        provider="anthropic", model="claude-opus-4-7", auth_mode="api_key",
    )
    llm = client.get_llm()
    assert llm._oauth_http_client is None
    # _client should construct via langchain's default helper, not crash.
    assert llm._client is not None


@pytest.mark.unit
def test_factory_openai_oauth_disables_responses_api(tmp_path, monkeypatch):
    """OAuth mode must NOT set use_responses_api=True (PRD §8 open question #2).

    Codex subscription tokens are only confirmed to work on Chat Completions;
    forcing /v1/responses risks breaking the round.
    """
    monkeypatch.delenv("CODEX_AUTH_FILE", raising=False)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    _write_codex_creds(tmp_path, jwt_exp_seconds=3600)

    client = create_llm_client(
        provider="openai", model="gpt-5.4", auth_mode="oauth",
    )
    llm = client.get_llm()
    assert getattr(llm, "use_responses_api", False) is not True


@pytest.mark.unit
def test_factory_openai_api_key_keeps_responses_api(monkeypatch):
    """Regression guard: api_key path for native openai still uses Responses API."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    client = create_llm_client(
        provider="openai", model="gpt-5.4", auth_mode="api_key",
    )
    llm = client.get_llm()
    assert getattr(llm, "use_responses_api", False) is True
