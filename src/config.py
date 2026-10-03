"""Shared paths and explicit offline-by-default configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from model_provider import ProviderConfig, normalize_provider


@dataclass
class LabConfig:
    base_dir: Path
    data_dir: Path
    state_dir: Path
    compact_threshold_tokens: int
    compact_keep_messages: int
    model: ProviderConfig
    judge_model: ProviderConfig
    live: bool = False


def _provider(prefix: str = "LLM", fallback: ProviderConfig | None = None) -> ProviderConfig:
    provider = normalize_provider(os.getenv(f"{prefix}_PROVIDER", fallback.provider if fallback else "openai"))
    defaults = {"openai": "gpt-4o-mini", "custom": "configured-model",
                "gemini": "gemini-2.5-flash", "anthropic": "claude-sonnet-4-5",
                "ollama": "llama3.2", "openrouter": "openrouter/free"}
    key_names = {"openai": "OPENAI_API_KEY", "custom": "CUSTOM_API_KEY",
                 "gemini": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY",
                 "ollama": "OLLAMA_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
    base_names = {"custom": "CUSTOM_BASE_URL", "ollama": "OLLAMA_BASE_URL"}
    default_model = fallback.model_name if fallback and fallback.provider == provider else defaults[provider]
    return ProviderConfig(provider, os.getenv(f"{prefix}_MODEL", default_model),
                          float(os.getenv(f"{prefix}_TEMPERATURE", "0")),
                          os.getenv(key_names[provider]),
                          os.getenv(base_names.get(provider, f"{provider.upper()}_BASE_URL")))


def load_config(base_dir: Path | None = None) -> LabConfig:
    root = (base_dir or Path(__file__).resolve().parent.parent).resolve()
    load_dotenv(root / ".env", override=False)
    threshold = int(os.getenv("COMPACT_THRESHOLD_TOKENS", "1200"))
    keep = int(os.getenv("COMPACT_KEEP_MESSAGES", "4"))
    if threshold < 32 or keep < 1:
        raise ValueError("Compact threshold >= 32 and keep_messages >= 1 required")
    state_dir = root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    model = _provider()
    mode = os.getenv("LLM_MODE", "offline").lower()
    if mode not in {"offline", "live"}:
        raise ValueError("LLM_MODE must be offline or live")
    return LabConfig(root, root / "data", state_dir, threshold, keep,
                     model, _provider("JUDGE", model), live=mode == "live")
