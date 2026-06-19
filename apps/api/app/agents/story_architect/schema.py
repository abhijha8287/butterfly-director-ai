from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class StoryRequest(BaseModel):
    """Input contract for the Story Architect agent."""

    prompt: str = Field(min_length=1, max_length=4000, description="The user's raw story premise.")
    target_runtime_minutes: int = Field(
        gt=0, le=180, description="Desired total runtime of the finished film, in minutes."
    )
    genre: str | None = Field(default=None, max_length=100, description="Optional genre preference.")
    style: str | None = Field(
        default=None, max_length=200, description="Optional visual/cinematic style preference."
    )


class StoryBible(BaseModel):
    """Strongly typed creative contract produced by the Story Architect agent.

    Every downstream agent (Character Architect, Decision Detector, Storyboard, ...)
    consumes this object only - never the model's free-form text.
    """

    title: str = Field(description="Working title of the film.")
    logline: str = Field(description="One or two sentence summary of the story.")
    synopsis: str = Field(description="A multi-paragraph prose summary of the full story.")
    genre: str = Field(description="Primary genre.")
    subgenre: str | None = Field(default=None, description="Secondary/sub genre, if applicable.")
    tone: str = Field(description="Overall emotional tone (e.g. 'somber and tense').")
    themes: list[str] = Field(default_factory=list, description="Central themes explored.")
    setting: str = Field(description="Where the story takes place.")
    world_description: str = Field(description="Description of the story's world/universe.")
    timeline_period: str = Field(description="When the story takes place (era, year, etc).")
    narrative_rules: list[str] = Field(
        default_factory=list, description="Hard rules the narrative must never break."
    )
    visual_style: str = Field(description="Visual aesthetic guidance for image/video generation.")
    cinematic_style: str = Field(description="Cinematic/directorial style (camera, pacing, edit).")
    target_runtime: int = Field(gt=0, description="Confirmed target runtime in minutes.")
    target_audience: str = Field(description="Intended audience for the film.")
    ending_type: str = Field(description="The nature of the ending (e.g. 'bittersweet', 'twist').")
    conflict: str = Field(description="The central dramatic conflict.")
    protagonist_summary: str = Field(description="Summary of the protagonist.")
    antagonist_summary: str | None = Field(
        default=None, description="Summary of the antagonist, if one exists."
    )
    supporting_characters_summary: list[str] = Field(
        default_factory=list, description="One summary string per supporting character."
    )
    world_constraints: list[str] = Field(
        default_factory=list, description="Constraints/limits that define the world's logic."
    )
    important_locations: list[str] = Field(
        default_factory=list, description="Key locations featured in the story."
    )
    recurring_symbols: list[str] = Field(
        default_factory=list, description="Recurring visual or narrative symbols/motifs."
    )
    story_hooks: list[str] = Field(
        default_factory=list, description="Hooks that create branch points for the multiverse."
    )
    sequel_hooks: list[str] = Field(
        default_factory=list, description="Threads left open for potential sequels."
    )

    @model_validator(mode="after")
    def _non_empty_core_fields(self) -> StoryBible:
        required_prose = {
            "title": self.title,
            "logline": self.logline,
            "synopsis": self.synopsis,
            "genre": self.genre,
            "tone": self.tone,
            "setting": self.setting,
            "conflict": self.conflict,
            "protagonist_summary": self.protagonist_summary,
        }
        blank = [name for name, value in required_prose.items() if not value.strip()]
        if blank:
            raise ValueError(f"StoryBible fields must not be blank: {', '.join(blank)}")
        return self
