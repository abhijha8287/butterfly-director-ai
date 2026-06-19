from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from app.agents.base.agent_result import AgentRunResult

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """Reference shape every agent in app/agents/ follows.

    Each agent owns its own schema.py (input/output Pydantic contract),
    prompts/<version>/ (system, developer, output_instructions), and
    validators.py (semantic checks beyond plain field types). `run()` is the
    only entry point downstream code (services, graph nodes) calls.
    """

    name: str

    @abstractmethod
    async def run(self, request: InputT) -> AgentRunResult[OutputT]: ...
