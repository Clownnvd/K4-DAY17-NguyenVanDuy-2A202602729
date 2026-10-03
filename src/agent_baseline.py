"""Control agent: full history scoped to one thread, no persistent profile."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import LabConfig, load_config
from memory_store import estimate_tokens, extract_profile_updates, merge_facts, offline_response
from model_provider import build_chat_model, build_live_graph

SYSTEM_PROMPT = "Chỉ trả lời dựa trên dữ liệu đã cung cấp. Không đoán thông tin chưa biết."


@dataclass
class SessionState:
    messages: list[dict[str, str]] = field(default_factory=list)
    token_usage: int = 0
    prompt_tokens_processed: int = 0


class BaselineAgent:
    def __init__(self, config: LabConfig | None = None, force_offline: bool = False):
        self.config = config or load_config()
        self.force_offline = force_offline
        self.sessions: dict[str, SessionState] = {}
        self.owners: dict[str, str] = {}
        self.langchain_agent = self._maybe_build_langchain_agent()

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        if not user_id or not thread_id or not isinstance(message, str):
            raise ValueError("Nonempty user/thread and text message required")
        if thread_id in self.owners and self.owners[thread_id] != user_id:
            raise ValueError("Thread belongs to another user")
        self.owners[thread_id] = user_id
        return self._reply_offline(thread_id, message)

    def token_usage(self, thread_id: str) -> int:
        return self.sessions.get(thread_id, SessionState()).token_usage

    def prompt_token_usage(self, thread_id: str) -> int:
        return self.sessions.get(thread_id, SessionState()).prompt_tokens_processed

    def compaction_count(self, thread_id: str) -> int:
        return 0

    def _reply_offline(self, thread_id: str, message: str) -> dict[str, Any]:
        state = self.sessions.setdefault(thread_id, SessionState())
        state.messages.append({"role": "user", "content": message})
        prompt_tokens = estimate_tokens(SYSTEM_PROMPT) + sum(estimate_tokens(m["content"]) for m in state.messages)
        if self.langchain_agent is not None:
            result = self.langchain_agent.invoke(
                {"messages": [{"role": "system", "content": SYSTEM_PROMPT}, *state.messages]},
                {"configurable": {"thread_id": thread_id}})
            answer = result["answer"]
            content = answer.content
            response = content if isinstance(content, str) else "".join(b.get("text", "") for b in content if isinstance(b, dict))
        else:
            facts = {}
            for turn in state.messages:
                if turn["role"] == "user":
                    facts = merge_facts(facts, extract_profile_updates(turn["content"]))
            response = offline_response(facts, message)
        output_tokens = estimate_tokens(response)
        state.token_usage += output_tokens
        state.prompt_tokens_processed += prompt_tokens
        state.messages.append({"role": "assistant", "content": response})
        return {"response": response, "agent_tokens": output_tokens, "prompt_tokens": prompt_tokens,
                "mode": "live" if self.langchain_agent is not None else "offline"}

    def _maybe_build_langchain_agent(self):
        if self.force_offline or not self.config.live:
            return None
        return build_live_graph(build_chat_model(self.config.model))
