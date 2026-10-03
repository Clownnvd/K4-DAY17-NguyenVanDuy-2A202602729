"""Lazy provider construction; never contact a provider in offline mode."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProviderConfig:
    provider: str
    model_name: str
    temperature: float
    api_key: str | None = field(default=None, repr=False)
    base_url: str | None = None


def normalize_provider(value: str) -> str:
    normalized = value.strip().lower()
    aliases = {"anthorpic": "anthropic", "google": "gemini", "google-genai": "gemini",
               "openai-compatible": "custom"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"openai", "custom", "gemini", "anthropic", "ollama", "openrouter"}:
        raise ValueError(f"Unsupported provider: {value!r}")
    return normalized


def build_chat_model(config: ProviderConfig):
    provider = normalize_provider(config.provider)
    common = {"model": config.model_name, "temperature": config.temperature}
    if provider != "ollama" and not config.api_key:
        raise ValueError(f"API key required for live provider {provider}")
    if provider in {"openai", "custom"}:
        from langchain_openai import ChatOpenAI
        if provider == "custom" and not config.base_url:
            raise ValueError("CUSTOM_BASE_URL required for custom provider")
        return ChatOpenAI(**common, api_key=config.api_key, base_url=config.base_url)
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(**common, api_key=config.api_key)
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(**common, api_key=config.api_key, base_url=config.base_url)
    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(**common, base_url=config.base_url or "http://127.0.0.1:11434")
    from langchain_openrouter import ChatOpenRouter
    return ChatOpenRouter(**common, api_key=config.api_key)


def build_live_graph(model):
    """One model node; checkpoint is scoped by caller's user/thread identity.

    Messages are replaced, not appended by a reducer: Advanced's curated compact
    context is the ONLY history sent to the model, avoiding hidden history growth.
    """
    from typing import TypedDict
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph

    class TurnState(TypedDict):
        messages: list
        answer: object

    def respond(state):
        return {"answer": model.invoke(state["messages"])}

    graph = StateGraph(TurnState)
    graph.add_node("respond", respond)
    graph.add_edge(START, "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=InMemorySaver())
