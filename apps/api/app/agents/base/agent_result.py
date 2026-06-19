from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class AgentRunResult(Generic[T]):
    """Uniform envelope every agent returns, regardless of which LLM/provider it used.

    `attempts` is an upper bound, not an exact count, for paths where the retry
    loop itself can't observe how many internal attempts a sub-call made.
    """

    output: T
    model: str
    prompt_version: str
    latency_ms: int
    attempts: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    raw_output_snapshot: dict | None = None
