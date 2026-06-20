from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.agents.story_architect.schema import StoryBible


class DecisionDetectorRequest(BaseModel):
    """Input contract for the Decision Detector agent.

    Takes the validated StoryBible only - never raw user text. Decision points
    are derived primarily from StoryBible.story_hooks (the field Story Architect
    explicitly populates with "hooks that create branch points for the
    multiverse"), read in the context of the rest of the bible.
    """

    story_bible: StoryBible


class BranchCandidate(BaseModel):
    """One possible direction the story could take at a decision point. Each
    candidate becomes a future `branches` row once the Timeline Generator
    agent acts on it - this agent only describes the fork, it does not create it.
    """

    label: str = Field(description="Short, distinct name for this branch (e.g. 'Shout for help').")
    description: str = Field(description="What concretely happens if this candidate is taken.")
    tone_shift: str = Field(
        description="How the story's tone or stakes change relative to the StoryBible's tone."
    )
    divergence_summary: str = Field(
        description="One-paragraph summary of how this universe diverges from the others."
    )


class DecisionPoint(BaseModel):
    """A single fork in the narrative. beat_index orders decision points along
    the story's chronology (0 = earliest).
    """

    beat_index: int = Field(ge=0, description="Position of this decision along the story's timeline.")
    description: str = Field(description="The moment of decision itself, in story terms.")
    source_hook: str | None = Field(
        default=None,
        description="The StoryBible.story_hooks entry this decision was derived from, verbatim, "
        "if it maps directly to one.",
    )
    branch_candidates: list[BranchCandidate] = Field(
        description="The distinct directions the story could fork into at this decision."
    )


class DecisionList(BaseModel):
    """Full set of decision points detected for one StoryBible. An empty list
    is a valid, meaningful output - it means the story is linear and should
    terminate as a single-branch timeline, not an error to retry on.
    """

    decisions: list[DecisionPoint] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_beat_indices(self) -> DecisionList:
        indices = [d.beat_index for d in self.decisions]
        duplicates = {i for i in indices if indices.count(i) > 1}
        if duplicates:
            raise ValueError(f"DecisionList has duplicate beat_index values: {duplicates}")
        return self
