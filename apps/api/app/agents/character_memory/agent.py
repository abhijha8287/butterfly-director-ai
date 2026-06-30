from __future__ import annotations

import json
import time
from pathlib import Path

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI

from app.agents.base.agent_result import AgentRunResult
from app.agents.base.base_agent import BaseAgent
from app.agents.base.prompt_loader import load_prompt
from app.agents.character_memory.schema import CharacterMemoryRequest, CharacterMemoryResult
from app.agents.character_memory.validators import validate_against_roster
from app.config.logging import get_logger
from app.config.settings import Settings, get_settings
from app.core.exceptions import AgentOutputInvalidError, ProviderUnavailableError
from app.integrations.llm_factory import active_model_name, get_llm

logger = get_logger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPT_VERSION = "v1"
MAX_ATTEMPTS = 3

_RETRYABLE_PARSE_ERRORS = (OutputParserException, AgentOutputInvalidError)


class CharacterMemoryAgent(BaseAgent[CharacterMemoryRequest, CharacterMemoryResult]):
    """Fifth agent in the pipeline, built on the same reference shape as the
    other four: a ChatOpenAI model pointed at DashScope, a
    PydanticOutputParser for the output contract, and a self-driven repair
    loop that feeds validation errors back to the model instead of giving up.
    Temperature is lower than the creative-drafting agents since this is a
    consistency-checking task, not a generative one.
    """

    name = "character_memory"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._parser = PydanticOutputParser(pydantic_object=CharacterMemoryResult)

    def _build_llm(self) -> ChatOpenAI:
        return get_llm(self._settings, temperature=0.4)

    def _build_messages(
        self, request: CharacterMemoryRequest, repair_note: str | None
    ) -> list[BaseMessage]:
        system_prompt = load_prompt(PROMPTS_DIR, PROMPT_VERSION, "system.txt")
        developer_prompt = load_prompt(PROMPTS_DIR, PROMPT_VERSION, "developer.txt")
        output_instructions = load_prompt(
            PROMPTS_DIR, PROMPT_VERSION, "output_instructions.txt"
        ).format(format_instructions=self._parser.get_format_instructions())

        branch_json = request.branch.model_dump_json(indent=2)
        characters_json = json.dumps(
            [c.model_dump(mode="json") for c in request.characters], indent=2
        )
        user_content = (
            f"{developer_prompt}\n\n"
            f"BranchContext:\n{branch_json}\n\n"
            f"Characters:\n{characters_json}\n\n"
            f"{output_instructions}"
        )
        if repair_note:
            user_content += f"\n\n{repair_note}"

        return [SystemMessage(content=system_prompt), HumanMessage(content=user_content)]

    async def run(self, request: CharacterMemoryRequest) -> AgentRunResult[CharacterMemoryResult]:
        llm = self._build_llm()
        start = time.perf_counter()
        last_error: Exception | None = None
        last_raw_text = ""
        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        repair_note: str | None = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            messages = self._build_messages(request, repair_note)
            ai_message = await llm.ainvoke(messages)
            last_raw_text = str(ai_message.content)

            usage = getattr(ai_message, "usage_metadata", None) or {}
            prompt_tokens = usage.get("input_tokens", prompt_tokens)
            completion_tokens = usage.get("output_tokens", completion_tokens)

            try:
                result = self._parser.parse(last_raw_text)
                validate_against_roster(result, request.characters)
            except _RETRYABLE_PARSE_ERRORS as exc:
                last_error = exc
                logger.warning(
                    "character_memory_attempt_failed",
                    attempt=attempt,
                    error=str(exc)[:300],
                )
                repair_note = (
                    f"Your previous response was invalid: {str(exc)[:500]}\n"
                    "Return a corrected JSON object that fixes this and still follows "
                    "the schema exactly. Output ONLY the corrected JSON object."
                )
                continue

            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.info("character_memory_succeeded", attempt=attempt, latency_ms=latency_ms)
            return AgentRunResult(
                output=result,
                model=active_model_name(self._settings),
                prompt_version=PROMPT_VERSION,
                latency_ms=latency_ms,
                attempts=attempt,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                raw_output_snapshot={"raw_text": last_raw_text},
            )

        raise AgentOutputInvalidError(
            f"Character Memory failed to produce a valid CharacterMemoryResult after "
            f"{MAX_ATTEMPTS} attempts: {last_error}",
            details={"raw_text": last_raw_text},
        ) from last_error
