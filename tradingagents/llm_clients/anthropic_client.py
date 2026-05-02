from functools import cached_property
from typing import Any, Literal, Optional

import anthropic
from langchain_anthropic import ChatAnthropic
from pydantic import PrivateAttr

from .base_client import BaseLLMClient, normalize_content
from .validators import validate_model

_PASSTHROUGH_KWARGS = (
    "timeout", "max_retries", "api_key", "max_tokens",
    "callbacks", "http_client", "http_async_client", "effort",
)


class NormalizedChatAnthropic(ChatAnthropic):
    """ChatAnthropic with normalized content + injected SDK http clients.

    Two reasons this subclass exists:
      1. Claude responses with extended thinking / tool use come back as a
         list of typed blocks; we flatten to a string for downstream agents.
      2. OAuth mode and explicit ``http_client`` kwargs require custom httpx
         clients. ``langchain_anthropic.ChatAnthropic._client`` always builds
         its own httpx client and overrides anything we pass via
         ``model_kwargs``, silently dropping our auth hook. We override
         ``_client``/``_async_client`` to substitute injected clients.
    """

    # PrivateAttr keeps these off the request payload (Pydantic excludes them
    # from model_dump). Public httpx clients are not JSON-serializable anyway.
    _oauth_http_client: Optional[Any] = PrivateAttr(default=None)
    _oauth_http_async_client: Optional[Any] = PrivateAttr(default=None)

    def invoke(self, input, config=None, **kwargs):
        return normalize_content(super().invoke(input, config, **kwargs))

    def _get_client_params(self) -> dict[str, Any]:
        client_params = getattr(self, "_client_params", None)
        if client_params is None:
            raise RuntimeError(
                "langchain_anthropic.ChatAnthropic no longer exposes _client_params; "
                "TradingAgents' injected http_client path needs updating."
            )
        return client_params

    @cached_property
    def _client(self) -> "anthropic.Client":  # type: ignore[override]
        if self._oauth_http_client is None:
            return super()._client  # default langchain behavior
        client_params = self._get_client_params()
        return anthropic.Client(**{**client_params, "http_client": self._oauth_http_client})

    @cached_property
    def _async_client(self) -> "anthropic.AsyncClient":  # type: ignore[override]
        if self._oauth_http_async_client is None:
            if self._oauth_http_client is not None:
                from .oauth.anthropic_oauth import AnthropicOAuthError
                raise AnthropicOAuthError(
                    "Anthropic OAuth async http client was not configured; "
                    "async OAuth calls are unavailable until this client is wired."
                )
            return super()._async_client
        client_params = self._get_client_params()
        return anthropic.AsyncClient(
            **{**client_params, "http_client": self._oauth_http_async_client}
        )


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic Claude models."""

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        *,
        auth_mode: Literal["api_key", "oauth"] = "api_key",
        **kwargs,
    ):
        super().__init__(model, base_url, **kwargs)
        self.auth_mode = auth_mode

    def get_llm(self) -> Any:
        """Return configured ChatAnthropic instance."""
        self.warn_if_unknown_model()
        llm_kwargs = {"model": self.model}
        injected_http_client = None
        injected_http_async_client = None

        if self.auth_mode == "oauth":
            from .oauth import build_anthropic_http_client, build_anthropic_http_client_async
            from .oauth.anthropic_oauth import get_dummy_key
            injected_http_client = build_anthropic_http_client()
            injected_http_async_client = build_anthropic_http_client_async()
            # langchain_anthropic ignores a kwarg-supplied http_client; we
            # attach it as a PrivateAttr after construction (see
            # NormalizedChatAnthropic._client).
            llm_kwargs.setdefault("api_key", get_dummy_key())
        elif self.base_url:
            llm_kwargs["base_url"] = self.base_url

        for key in _PASSTHROUGH_KWARGS:
            if key in self.kwargs:
                # In oauth mode, never let a stray API key from kwargs override
                # the dummy placeholder — that would re-enable x-api-key auth.
                if self.auth_mode == "oauth" and key == "api_key":
                    continue
                # http_client(_async) flow through PrivateAttr, not kwargs.
                if key == "http_client":
                    if self.auth_mode != "oauth":
                        injected_http_client = self.kwargs[key]
                    continue
                if key == "http_async_client":
                    if self.auth_mode != "oauth":
                        injected_http_async_client = self.kwargs[key]
                    continue
                llm_kwargs[key] = self.kwargs[key]

        llm = NormalizedChatAnthropic(**llm_kwargs)
        if injected_http_client is not None:
            llm._oauth_http_client = injected_http_client
        if injected_http_async_client is not None:
            llm._oauth_http_async_client = injected_http_async_client
        return llm

    def validate_model(self) -> bool:
        """Validate model for Anthropic."""
        return validate_model("anthropic", self.model)
