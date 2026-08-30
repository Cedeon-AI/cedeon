"""Model/provider registry. One place resolves ``provider:model`` strings to a
configured PydanticAI model, so vendor names never leak into feature code
(docs/AI_ARCHITECTURE.md §4).

Only the Anthropic provider is wired today. Adding OpenAI / Google is a branch
here plus the matching ``pydantic-ai-slim`` extra — the ``spec`` string and this
function are the portability seam."""

from __future__ import annotations

from pydantic_ai.models import Model

from app.core.config import Settings

_SUPPORTED = ("anthropic",)


class AIProviderNotConfiguredError(RuntimeError):
    pass


def build_model(spec: str, settings: Settings) -> Model:
    """``spec`` is ``"<provider>:<model>"`` (e.g. ``anthropic:claude-opus-5``)."""
    provider, _, model_name = spec.partition(":")
    if not model_name:
        raise ValueError(f"model spec must be 'provider:model', got {spec!r}")

    if provider == "anthropic":
        from anthropic import AsyncAnthropic
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        if not settings.anthropic_api_key:
            raise AIProviderNotConfiguredError("ANTHROPIC_API_KEY is not set")
        headers = (
            {"anthropic-workspace-id": settings.anthropic_workspace_id}
            if settings.anthropic_workspace_id
            else None
        )
        client = AsyncAnthropic(api_key=settings.anthropic_api_key, default_headers=headers)
        return AnthropicModel(model_name, provider=AnthropicProvider(anthropic_client=client))

    if provider in ("openai", "google"):
        raise AIProviderNotConfiguredError(
            f"the {provider!r} provider is not wired yet — add a branch in "
            f"app/ai/models.build_model and the pydantic-ai-slim[{provider}] extra"
        )

    raise ValueError(f"unknown AI provider {provider!r}; supported: {_SUPPORTED}")
