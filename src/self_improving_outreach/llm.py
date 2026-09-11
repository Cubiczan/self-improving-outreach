"""OpenAI-compatible LLM provider resolution (OpenAI + Boundless)."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from self_improving_outreach.config import (
    DEFAULT_BOUNDLESS_BASE_URL,
    Settings,
)

logger = logging.getLogger(__name__)

PROVIDER_OPENAI = "openai"
PROVIDER_BOUNDLESS = "boundless"


def apply_llm_runtime_env(settings: Settings) -> None:
    """Point OpenAI-compatible clients (CrewAI / LiteLLM) at the effective provider.

    When Boundless is selected, copies the Boundless key into ``OPENAI_API_KEY``
    and sets ``OPENAI_BASE_URL`` / ``OPENAI_API_BASE`` so clients send
    ``Authorization: Bearer`` to ``https://api.inference.boundless.network/v1``.
    Never logs secret values.
    """
    if settings.effective_llm_provider != PROVIDER_BOUNDLESS:
        return
    key = settings.llm_api_key
    if not key:
        return
    base = settings.llm_base_url or DEFAULT_BOUNDLESS_BASE_URL
    os.environ["OPENAI_API_KEY"] = key
    os.environ["OPENAI_BASE_URL"] = base
    os.environ["OPENAI_API_BASE"] = base
    logger.info("LLM runtime using Boundless OpenAI-compatible base_url (%s)", base)


def crewai_model_name(settings: Settings) -> str:
    """LiteLLM / CrewAI model id. Boundless custom endpoints use the openai/ prefix."""
    model = settings.llm_model
    if settings.effective_llm_provider == PROVIDER_BOUNDLESS and "/" not in model:
        return f"openai/{model}"
    return model


def build_crewai_llm(settings: Settings) -> Optional[Any]:
    """Return a CrewAI ``LLM`` pointed at OpenAI or Boundless, or None if unavailable."""
    apply_llm_runtime_env(settings)
    if not settings.llm_api_key:
        return None
    try:
        from crewai import LLM
    except Exception:
        return None

    model = crewai_model_name(settings)
    kwargs: dict[str, Any] = {
        "model": model,
        "api_key": settings.llm_api_key,
    }
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
        kwargs["custom_openai"] = True
    try:
        return LLM(**kwargs)
    except TypeError:
        kwargs.pop("custom_openai", None)
        try:
            return LLM(**kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("CrewAI LLM init failed: %s", exc)
            return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("CrewAI LLM init failed: %s", exc)
        return None
