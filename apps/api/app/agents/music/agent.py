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
from app.agents.music.schema import (
    MusicAgentResult,
    MusicCue,
    MusicCueFailure,
    MusicCueResult,
    MusicRequest,
    MusicScript,
)
from app.agents.music.validators import validate_music_script
from app.config.logging import get_logger
from app.config.settings import Settings, get_settings
from app.core.exceptions import AgentOutputInvalidError, ProviderUnavailableError
from app.integrations.llm_factory import active_model_name, get_llm
from app.integrations.providers.base import MusicGenerationProvider
from app.integrations.providers.base import MusicGenerationRequest as ProviderMusicRequest
from app.integrations.providers.factory import get_music_provider

logger = get_logger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPT_VERSION = "v1"
MAX_ATTEMPTS = 3
MAX_SYNTHESIS_ATTEMPTS = 3

_RETRYABLE_PARSE_ERRORS = (OutputParserException, AgentOutputInvalidError)


class MusicAgent(BaseAgent[MusicRequest, MusicAgentResult]):
    """Tenth agent in the pipeline. Like Voice, combines an LLM call (writes
    MusicCues - mood/tempo/a provider-ready generation prompt for a
    contiguous range of shots) with a provider call per cue in one run().
    Unlike Voice, the provider is genuinely optional: ARCHITECTURE.md frames
    Music's output as "generation prompts (and/or generated stems if
    provider supports it)", and MUSIC_PROVIDER defaults to "none" (no real
    DashScope music provider exists in this build). When no provider is
    configured, every cue is still extracted and persisted with its
    prompt/mood/tempo - synthesis is simply skipped, never treated as a
    failure.
    """

    name = "music"

    def __init__(
        self,
        settings: Settings | None = None,
        provider: MusicGenerationProvider | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._parser = PydanticOutputParser(pydantic_object=MusicScript)
        self._provider = provider if provider is not None else get_music_provider(self._settings)

    def _build_llm(self) -> ChatOpenAI:
        return get_llm(self._settings, temperature=0.7)

    def _build_messages(
        self, request: MusicRequest, repair_note: str | None
    ) -> list[BaseMessage]:
        system_prompt = load_prompt(PROMPTS_DIR, PROMPT_VERSION, "system.txt")
        developer_prompt = load_prompt(PROMPTS_DIR, PROMPT_VERSION, "developer.txt")
        output_instructions = load_prompt(
            PROMPTS_DIR, PROMPT_VERSION, "output_instructions.txt"
        ).format(format_instructions=self._parser.get_format_instructions())

        bible_json = request.story_bible.model_dump_json(indent=2)
        shots_json = "\n".join(s.model_dump_json(indent=2) for s in request.shots)
        branch_json = json.dumps(
            {"name": request.branch_name, "summary": request.branch_summary}, indent=2
        )
        user_content = (
            f"{developer_prompt}\n\n"
            f"StoryBible:\n{bible_json}\n\n"
            f"Branch:\n{branch_json}\n\n"
            f"Shots:\n{shots_json}\n\n"
            f"{output_instructions}"
        )
        if repair_note:
            user_content += f"\n\n{repair_note}"

        return [SystemMessage(content=system_prompt), HumanMessage(content=user_content)]

    async def _extract_score(self, request: MusicRequest) -> tuple[MusicScript, dict]:
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
                validate_music_script(script, request.shots)
            except _RETRYABLE_PARSE_ERRORS as exc:
                last_error = exc
                logger.warning(
                    "music_score_attempt_failed", attempt=attempt, error=str(exc)[:300]
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
            f"Music agent failed to produce a valid MusicScript after "
            f"{MAX_ATTEMPTS} attempts: {last_error}",
            details={"raw_text": last_raw_text},
        ) from last_error

    async def run(self, request: MusicRequest) -> AgentRunResult[MusicAgentResult]:
        start = time.perf_counter()
        script, extraction_meta = await self._extract_score(request)

        if self._provider is None:
            cues = [
                MusicCueResult(
                    start_shot_number=cue.start_shot_number,
                    end_shot_number=cue.end_shot_number,
                    mood=cue.mood,
                    tempo_bpm=cue.tempo_bpm,
                    generation_prompt=cue.generation_prompt,
                    attempts=0,
                )
                for cue in script.cues
            ]
            failed: list[MusicCueFailure] = []
        else:
            outcomes = await asyncio.gather(
                *(self._synthesize_cue(cue) for cue in script.cues)
            )
            cues = [o for o in outcomes if isinstance(o, MusicCueResult)]
            failed = [o for o in outcomes if isinstance(o, MusicCueFailure)]

        output = MusicAgentResult(cues=cues, failed_cues=failed)

        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "music_succeeded",
            latency_ms=latency_ms,
            cue_count=len(cues),
            failed_count=len(failed),
        )
        return AgentRunResult(
            output=output,
            model=active_model_name(self._settings),
            prompt_version=PROMPT_VERSION,
            latency_ms=latency_ms,
            attempts=extraction_meta["attempts"],
            prompt_tokens=extraction_meta["prompt_tokens"],
            completion_tokens=extraction_meta["completion_tokens"],
            raw_output_snapshot={"raw_text": extraction_meta["raw_text"]},
        )

    async def _synthesize_cue(self, cue: MusicCue) -> MusicCueResult | MusicCueFailure:
        assert self._provider is not None
        prompt = cue.generation_prompt
        last_error: Exception | None = None

        for attempt in range(1, MAX_SYNTHESIS_ATTEMPTS + 1):
            try:
                result = await self._provider.generate(
                    ProviderMusicRequest(prompt=prompt, mood=cue.mood)
                )
            except ProviderUnavailableError as exc:
                last_error = exc
                logger.warning(
                    "music_cue_attempt_failed",
                    start_shot_number=cue.start_shot_number,
                    end_shot_number=cue.end_shot_number,
                    attempt=attempt,
                    error=str(exc)[:300],
                )
                if attempt == 1:
                    prompt = cue.generation_prompt[: max(len(cue.generation_prompt) // 2, 20)]
                continue

            return MusicCueResult(
                start_shot_number=cue.start_shot_number,
                end_shot_number=cue.end_shot_number,
                mood=cue.mood,
                tempo_bpm=cue.tempo_bpm,
                generation_prompt=cue.generation_prompt,
                audio_url=result.audio_url,
                audio_bytes=result.audio_bytes,
                provider=result.provider,
                attempts=attempt,
            )

        return MusicCueFailure(
            start_shot_number=cue.start_shot_number,
            end_shot_number=cue.end_shot_number,
            mood=cue.mood,
            tempo_bpm=cue.tempo_bpm,
            generation_prompt=cue.generation_prompt,
            attempts=MAX_SYNTHESIS_ATTEMPTS,
            error=str(last_error),
        )
