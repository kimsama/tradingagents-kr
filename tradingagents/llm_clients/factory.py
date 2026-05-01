import os
from typing import Literal, Optional

from .base_client import BaseLLMClient

# Providers that use the OpenAI-compatible chat completions API
_OPENAI_COMPATIBLE = (
    "openai", "xai", "deepseek", "qwen", "glm", "ollama", "openrouter",
)

AuthMode = Literal["api_key", "oauth"]

# Providers that support subscription-based OAuth (PRD-1.2). Other
# providers raise if asked for OAuth — they only have API-key auth.
_OAUTH_CAPABLE = ("anthropic", "openai")


def _resolve_auth_mode(provider: str, explicit: Optional[AuthMode]) -> AuthMode:
    """Resolve auth_mode from explicit arg or provider-specific env var.

    Precedence: explicit arg > env var > "api_key" default. Env var name
    mirrors the provider, e.g. ANTHROPIC_AUTH_MODE / OPENAI_AUTH_MODE.
    """
    if explicit is not None:
        return explicit
    env_value = os.environ.get(f"{provider.upper()}_AUTH_MODE")
    if env_value:
        normalized = env_value.strip().lower()
        if normalized in ("api_key", "oauth"):
            return normalized  # type: ignore[return-value]
    return "api_key"


def create_llm_client(
    provider: str,
    model: str,
    base_url: Optional[str] = None,
    *,
    auth_mode: Optional[AuthMode] = None,
    **kwargs,
) -> BaseLLMClient:
    """Create an LLM client for the specified provider.

    Provider modules are imported lazily so that simply importing this
    factory (e.g. during test collection) does not pull in heavy LLM SDKs
    or fail when their API keys are absent.

    Args:
        provider: LLM provider name
        model: Model name/identifier
        base_url: Optional base URL for API endpoint
        auth_mode: "api_key" (default) or "oauth". OAuth is supported for
            "anthropic" (Claude Pro/Max) and "openai" (ChatGPT subscription)
            only. If omitted, falls back to ``<PROVIDER>_AUTH_MODE`` env var
            then to "api_key".
        **kwargs: Additional provider-specific arguments

    Returns:
        Configured BaseLLMClient instance

    Raises:
        ValueError: If provider is not supported, or if OAuth requested for
            a provider that does not support it.
    """
    provider_lower = provider.lower()
    resolved_auth = _resolve_auth_mode(provider_lower, auth_mode)

    if resolved_auth == "oauth" and provider_lower not in _OAUTH_CAPABLE:
        raise ValueError(
            f"auth_mode='oauth' is not supported for provider '{provider}'. "
            f"OAuth is only available for: {', '.join(_OAUTH_CAPABLE)}."
        )

    if provider_lower in _OPENAI_COMPATIBLE:
        from .openai_client import OpenAIClient
        return OpenAIClient(
            model, base_url, provider=provider_lower,
            auth_mode=resolved_auth, **kwargs,
        )

    if provider_lower == "anthropic":
        from .anthropic_client import AnthropicClient
        return AnthropicClient(model, base_url, auth_mode=resolved_auth, **kwargs)

    if provider_lower == "google":
        from .google_client import GoogleClient
        return GoogleClient(model, base_url, **kwargs)

    if provider_lower == "azure":
        from .azure_client import AzureOpenAIClient
        return AzureOpenAIClient(model, base_url, **kwargs)

    raise ValueError(f"Unsupported LLM provider: {provider}")
