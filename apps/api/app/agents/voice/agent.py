from __future__ import annotations

import asyncio
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
from app.agents.voice.schema import (
    DialogueLine,
    DialogueScript,
    VoiceAgentResult,
    VoiceLineFailure,
    VoiceLineResult,
    VoiceRequest,
)
from app.agents.voice.validators import validate_dialogue_script
from app.config.logging import get_logger
from app.config.settings import Settings, get_settings
from app.core.exceptions import AgentOutputInvalidError, ProviderUnavailableError
from app.integrations.providers.base import VoiceGenerationProvider
from app.integrations.providers.base import VoiceGenerationRequest as ProviderVoiceRequest
from app.integrations.providers.factory import get_voice_provider

logger = get_logger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPT_VERSION = "v1"
MAX_ATTEMPTS = 3
MAX_SYNTHESIS_ATTEMPTS = 3

_RETRYABLE_PARSE_ERRORS = (OutputParserException, AgentOutputInvalidError)


class VoiceAgent(BaseAgent[VoiceRequest, VoiceAgentResult]):
    """Ninth agent in the pipeline, and the first to combine both halves of
    the reference pattern in one run(): an LLM call (ChatOpenAI +
    PydanticOutputParser + self-driven repair loop, identical shape to the
    six text agents) writes DialogueLines from the branch's shots/script/
    characters, then a provider call per line (VoiceGenerationProvider,
    identical shape to Video Generation's per-shot fan-out) actually
    synthesizes each line's audio. A line that exhausts its synthesis
    attempts is reported as a failure alongside whatever other lines
    synthesized fine, rather than failing the whole batch - the same
    graceful-degradation choice Video Generation makes per shot.
    """

    name = "voice"

    def __init__(
        self,
        settings: Settings | None = None,
        provider: VoiceGenerationProvider | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._parser = PydanticOutputParser(pydantic_object=DialogueScript)
        self._provider = provider or get_voice_provider(self._settings)

    def _build_llm(self) -> ChatOpenAI:
        if not self._settings.dashscope_api_key:
            raise ProviderUnavailableError("DASHSCOPE_API_KEY is not configured")
        return ChatOpenAI(
            model=self._settings.qwen_model,
            api_key=self._settings.dashscope_api_key,
            base_url=f"{self._settings.dashscope_base_url}/compatible-mode/v1",
            temperature=0.6,
        )

    def _build_messages(
        self, request: VoiceRequest, repair_note: str | None
    ) -> list[BaseMessage]:
        system_prompt = load_prompt(PROMPTS_DIR, PROMPT_VERSION, "system.txt")
        developer_prompt = load_prompt(PROMPTS_DIR, PROMPT_VERSION, "developer.txt")
        output_instructions = load_prompt(
            PROMPTS_DIR, PROMPT_VERSION, "output_instructions.txt"
        ).format(format_instructions=self._parser.get_format_instructions())

        bible_json = request.story_bible.model_dump_json(indent=2)
        shots_json = "\n".join(s.model_dump_json(indent=2) for s in request.shots)
        characters_json = "\n".join(c.model_dump_json(indent=2) for c in request.characters)
        branch_json = json.dumps(
            {"name": request.branch_name, "delta_script": request.delta_script}, indent=2
        )
        user_content = (
            f"{developer_prompt}\n\n"
            f"StoryBible:\n{bible_json}\n\n"
            f"Branch:\n{branch_json}\n\n"
            f"Shots:\n{shots_json}\n\n"
            f"Characters:\n{characters_json}\n\n"
            f"{output_instructions}"
        )
        if repair_note:
            user_content += f"\n\n{repair_note}"

        return [SystemMessage(content=system_prompt), HumanMessage(content=user_content)]

    async def _extract_dialogue(self, request: VoiceRequest) -> tuple[DialogueScript, dict]:
        llm = self._build_llm()
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
                script = self._parser.parse(last_raw_text)
                validate_dialogue_script(script, request.shots, request.characters)
            except _RETRYABLE_PARSE_ERRORS as exc:
                last_error = exc
                logger.warning(
                    "voice_dialogue_attempt_failed", attempt=attempt, error=str(exc)[:300]
                )
                repair_note = (
                    f"Your previous response was invalid: {str(exc)[:500]}\n"
                    "Return a corrected JSON object that fixes this and still follows "
                    "the schema exactly. Output ONLY the corrected JSON object."
                )
                continue

            return script, {
                "attempts": attempt,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "raw_text": last_raw_text,
            }

        raise AgentOutputInvalidError(
            f"Voice agent failed to produce a valid DialogueScript after "
            f"{MAX_ATTEMPTS} attempts: {last_error}",
            details={"raw_text": last_raw_text},
        ) from last_error

    async def run(self, request: VoiceRequest) -> AgentRunResult[VoiceAgentResult]:
        start = time.perf_counter()
        script, extraction_meta = await self._extract_dialogue(request)

        outcomes = await asyncio.gather(*(self._synthesize_line(line) for line in script.lines))
        lines = [o for o in outcomes if isinstance(o, VoiceLineResult)]
        failed = [o for o in outcomes if isinstance(o, VoiceLineFailure)]
        output = VoiceAgentResult(lines=lines, failed_lines=failed)

        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "voice_succeeded",
            latency_ms=latency_ms,
            line_count=len(lines),
            failed_count=len(failed),
        )
        return AgentRunResult(
            output=output,
            model=self._settings.qwen_model,
            prompt_version=PROMPT_VERSION,
            latency_ms=latency_ms,
            attempts=extraction_meta["attempts"],
            prompt_tokens=extraction_meta["prompt_tokens"],
            completion_tokens=extraction_meta["completion_tokens"],
            raw_output_snapshot={"raw_text": extraction_meta["raw_text"]},
        )

    async def _synthesize_line(self, line: DialogueLine) -> VoiceLineResult | VoiceLineFailure:
        text = line.line_text
        last_error: Exception | None = None

        for attempt in range(1, MAX_SYNTHESIS_ATTEMPTS + 1):
            try:
                result = await self._provider.synthesize(
                    ProviderVoiceRequest(text=text, audio_format="mp3")
                )
            except ProviderUnavailableError as exc:
                last_error = exc
                logger.warning(
                    "voice_line_attempt_failed",
                    shot_number=line.shot_number,
                    character_name=line.character_name,
                    attempt=attempt,
                    error=str(exc)[:300],
                )
                if attempt == 1:
                    text = line.line_text[: max(len(line.line_text) // 2, 20)]
                continue

            return VoiceLineResult(
                shot_number=line.shot_number,
                character_name=line.character_name,
                line_text=line.line_text,
                delivery_note=line.delivery_note,
                audio_bytes=result.audio_bytes,
                audio_format=result.audio_format,
                provider=result.provider,
                attempts=attempt,
            )

        return VoiceLineFailure(
            shot_number=line.shot_number,
            character_name=line.character_name,
            line_text=line.line_text,
            delivery_note=line.delivery_note,
            attempts=MAX_SYNTHESIS_ATTEMPTS,
            error=str(last_error),
        )
