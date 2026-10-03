"""Reproducible offline evaluation; reference answers stay outside agents."""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from tabulate import tabulate

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config
from memory_store import fold


@dataclass
class BenchmarkRow:
    agent_name: str
    agent_tokens_only: int
    prompt_tokens_processed: int
    recall_score: float
    response_quality: float
    memory_growth_bytes: int
    compactions: int


def load_conversations(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Dataset must be a list")
    for conversation in data:
        if not all(k in conversation for k in ("id", "user_id", "turns", "recall_questions")):
            raise ValueError("Incomplete conversation")
    return data


def recall_points(answer: str, expected: list[str]) -> float:
    if not expected:
        return 0.0
    hits = sum(fold(item) in fold(answer) for item in expected)
    return 1.0 if hits == len(expected) else 0.5 if hits else 0.0


def heuristic_quality(answer: str, expected: list[str]) -> float:
    """Proxy: expected fact coverage, with a verbosity penalty beyond 600 chars.

    This is NOT an LLM judge, fluency measurement or independent grounding score.
    """
    if not expected:
        return 0.0
    coverage = sum(fold(item) in fold(answer) for item in expected) / len(expected)
    return coverage * min(1.0, 600 / max(len(answer), 1))


def run_agent_benchmark(agent_name: str, agent, conversations: list[dict[str, Any]], config) -> BenchmarkRow:
    users = {c["user_id"] for c in conversations}
    initial_bytes = sum(agent.memory_file_size(u) for u in users) if isinstance(agent, AdvancedAgent) else 0
    threads, recalls, qualities, observations = [], [], [], []
    for index, conversation in enumerate(conversations):
        thread = f"conversation:{index}:{conversation['id']}"
        threads.append(thread)
        for message in conversation["turns"]:
            agent.reply(conversation["user_id"], thread, message)
        recall_thread = f"recall:{index}:{conversation['id']}"
        threads.append(recall_thread)
        for question in conversation["recall_questions"]:
            response = agent.reply(conversation["user_id"], recall_thread, question["question"])["response"]
            recall = recall_points(response, question["expected_contains"])
            quality = heuristic_quality(response, question["expected_contains"])
            recalls.append(recall)
            qualities.append(quality)
            observations.append({"conversation": conversation["id"], "thread": recall_thread,
                                 "question": question["question"], "response": response,
                                 "expected_contains": question["expected_contains"],
                                 "recall": recall, "quality_proxy": quality})
    final_bytes = sum(agent.memory_file_size(u) for u in users) if isinstance(agent, AdvancedAgent) else 0
    agent.benchmark_observations = observations
    return BenchmarkRow(agent_name, sum(agent.token_usage(t) for t in threads),
                        sum(agent.prompt_token_usage(t) for t in threads),
                        sum(recalls) / len(recalls) if recalls else 0,
                        sum(qualities) / len(qualities) if qualities else 0,
                        final_bytes - initial_bytes, sum(agent.compaction_count(t) for t in threads))


def format_rows(rows: list[BenchmarkRow]) -> str:
    return tabulate([[r.agent_name, r.agent_tokens_only, r.prompt_tokens_processed,
                      f"{r.recall_score:.1%}", f"{r.response_quality:.1%}",
                      r.memory_growth_bytes, r.compactions] for r in rows],
                    headers=["Agent", "Agent tokens only", "Prompt tokens processed", "Cross-session recall",
                             "Response quality", "Memory growth (bytes)", "Compactions"], tablefmt="github")


def run_suite(config, filename: str):
    dataset = load_conversations(config.data_dir / filename)
    with TemporaryDirectory(prefix="lab17-benchmark-") as temporary:
        clean = replace(config, state_dir=Path(temporary), live=False)
        baseline, advanced = BaselineAgent(clean, True), AdvancedAgent(clean, True)
        rows = [run_agent_benchmark("Baseline", baseline, dataset, clean),
                run_agent_benchmark("Advanced", advanced, dataset, clean)]
        without_compact = AdvancedAgent(replace(clean, state_dir=Path(temporary) / "ablation",
                                                compact_threshold_tokens=10**9), True)
        ablation = run_agent_benchmark("Advanced - no compact", without_compact, dataset, clean)
        return rows, ablation, {"Baseline": baseline.benchmark_observations,
                                "Advanced": advanced.benchmark_observations}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    config = load_config()
    result = {"mode": "offline", "quality": "heuristic fact-coverage proxy; not an LLM judge",
              "token_estimator": "ceil(len(text.strip()) / 4); includes system+profile+summary+recent context",
              "token_counts_include_recall_turns": True,
              "settings": {"threshold": config.compact_threshold_tokens, "keep": config.compact_keep_messages},
              "suites": {}}
    for title, filename in [("Standard Benchmark", "conversations.json"),
                            ("Long-Context Stress Benchmark", "advanced_long_context.json")]:
        rows, ablation, observations = run_suite(config, filename)
        print("\n" + title)
        print(format_rows(rows))
        result["suites"][title] = {"rows": [asdict(r) for r in rows], "no_compact": asdict(ablation),
                                  "recall_answers": observations,
                                  "dataset_sha256": hashlib.sha256((config.data_dir / filename).read_bytes()).hexdigest()}
    artifacts = config.base_dir / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "benchmark_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                                     encoding="utf-8")
    print("\nOffline deterministic benchmark. Scores are capability checks, not real-model performance.")


if __name__ == "__main__":
    main()
