from __future__ import annotations

from app.agents.story_architect.schema import StoryBible, StoryRequest
from app.core.exceptions import AgentOutputInvalidError

_RUNTIME_TOLERANCE_RATIO = 0.5


def validate_against_request(bible: StoryBible, request: StoryRequest) -> list[str]:
    """Semantic checks beyond plain Pydantic field types. Pydantic field types in
    schema.py guarantee shape; this guarantees the content actually answers the
    request. Returns non-fatal warnings; raises AgentOutputInvalidError on a hard
    contract violation (runtime wildly off what was requested).
    """
    warnings: list[str] = []

    lower = request.target_runtime_minutes * (1 - _RUNTIME_TOLERANCE_RATIO)
    upper = request.target_runtime_minutes * (1 + _RUNTIME_TOLERANCE_RATIO)
    if not (lower <= bible.target_runtime <= upper):
        raise AgentOutputInvalidError(
            f"StoryBible.target_runtime ({bible.target_runtime}) deviates too far from "
            f"the requested {request.target_runtime_minutes} minutes",
            details={"requested": request.target_runtime_minutes, "produced": bible.target_runtime},
        )

    if request.genre and request.genre.lower() not in bible.genre.lower():
        warnings.append(
            f"Requested genre '{request.genre}' is not reflected in produced genre '{bible.genre}'"
        )

    if not bible.themes:
        warnings.append("StoryBible.themes is empty")

    if not bible.story_hooks:
        warnings.append("StoryBible.story_hooks is empty - downstream branching has nothing to work with")

    return warnings
