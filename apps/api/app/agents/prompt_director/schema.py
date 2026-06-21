from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.story_architect.schema import StoryBible


class CharacterVisualProfile(BaseModel):
    """Visual consistency context for one character present in a shot,
    derived from Character Architect's canonical profile (physical_description,
    wardrobe_style) overlaid with Character Memory's per-branch state
    (emotional_state, physical_state) if resolved yet for this branch.
    """

    name: str
    physical_description: str
    wardrobe_style: str
    emotional_state: str = "unchanged"
    physical_state: str = "unchanged"


class ShotContext(BaseModel):
    """One storyboard shot plus the resolved visual profile of every character
    present in it - the per-shot input the Prompt Director expands into a
    provider-ready prompt.
    """

    scene: str
    shot_number: int = Field(ge=1)
    description: str
    camera: str
    duration_seconds: float
    characters: list[CharacterVisualProfile] = Field(default_factory=list)


class PromptDirectorRequest(BaseModel):
    """Input contract for the Prompt Director agent: the StoryBible (for
    visual_style/cinematic_style grounding, reused verbatim across every shot
    for style consistency) and the full ordered list of shot contexts above.
    """

    story_bible: StoryBible
    shots: list[ShotContext] = Field(default_factory=list)


class ShotPrompt(BaseModel):
    """One provider-ready generation prompt for a single shot. positive_prompt
    is persisted as PromptHistory.rendered_prompt; everything else is packed
    into PromptHistory.input_payload - the existing `prompt_history` table
    (ARCHITECTURE.md §4.9) has no dedicated negative_prompt/token columns, and
    input_payload's documented purpose ("kept for audit/replay/cost analysis")
    is exactly the right home for them.
    """

    shot_number: int = Field(
        ge=1,
        description="Must exactly match one input shot's shot_number - this is how the "
        "prompt is mapped back to the shot it renders.",
    )
    positive_prompt: str = Field(
        description="The full provider-ready text-to-video prompt for this shot, "
        "self-contained with no other context assumed."
    )
    negative_prompt: str = Field(
        description="Concrete failure modes to avoid for THIS shot specifically."
    )
    consistency_tokens: list[str] = Field(
        default_factory=list,
        description="Short, literal phrases (character traits/wardrobe) reused verbatim "
        "across every shot featuring that character, for visual consistency.",
    )
    style_tokens: list[str] = Field(
        default_factory=list,
        description="Short, literal phrases drawn from the StoryBible's visual/cinematic "
        "style, reused verbatim across every shot in this branch.",
    )


class PromptDirectorResult(BaseModel):
    """One ShotPrompt per shot in the input storyboard. Downstream persistence
    (one PromptHistory row per shot) consumes this object only.
    """

    shot_prompts: list[ShotPrompt] = Field(default_factory=list)
