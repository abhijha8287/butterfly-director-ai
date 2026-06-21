from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.story_architect.schema import StoryBible


class CharacterStateSummary(BaseModel):
    """Per-character continuity context for one branch. Built from the
    Character row's canonical profile, overlaid with that character's
    CharacterBranchState (Character Memory's output) if one exists for this
    branch yet - characters Character Memory hasn't resolved for this branch
    fall back to the "not yet resolved" defaults below rather than blocking
    storyboarding on a prior agent run.
    """

    name: str
    role: str
    physical_description: str
    knowledge_state: str = "Not yet resolved for this branch."
    emotional_state: str = "Not yet resolved for this branch."
    physical_state: str = "Not yet resolved for this branch."


class StoryboardRequest(BaseModel):
    """Input contract for the Storyboard agent: the StoryBible (for visual_style/
    cinematic_style/setting grounding), this branch's own name/summary/delta_script
    ("branch script" per ARCHITECTURE.md), and the per-character state described above.
    """

    story_bible: StoryBible
    branch_name: str
    branch_summary: str | None = None
    delta_script: str | None = None
    characters: list[CharacterStateSummary] = Field(default_factory=list)


class Shot(BaseModel):
    """One shot in the ordered storyboard. shot_number is the load-bearing
    ordering field downstream agents (Prompt Director, Video Generation) fan
    out per-shot on - it must be unique and contiguous from 1.
    """

    scene: str = Field(description="Scene heading, e.g. 'INT. ALLEY - NIGHT'.")
    shot_number: int = Field(ge=1, description="1-indexed position in the ordered shot list.")
    description: str = Field(description="What happens and what's visually seen in this shot.")
    camera: str = Field(description="Camera angle/movement, e.g. 'low-angle tracking shot'.")
    duration_seconds: float = Field(gt=0, description="Estimated shot duration in seconds.")
    characters_present: list[str] = Field(
        default_factory=list, description="Names of characters visible/active in this shot."
    )


class StoryboardResult(BaseModel):
    """The ordered shot list for one branch. Persisted as a `storyboard` Version
    snapshot, never directly - downstream agents consume this object only.
    """

    shots: list[Shot] = Field(default_factory=list)
