from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.decision_detector.schema import DecisionPoint
from app.agents.story_architect.schema import StoryBible


class TimelineGeneratorRequest(BaseModel):
    """Input contract for the Timeline Generator agent.

    Takes the validated StoryBible (for grounding) and exactly one DecisionPoint
    (already detected by the Decision Detector) - never raw text. The agent
    expands that single decision's branch_candidates into concrete universes.
    """

    story_bible: StoryBible
    decision: DecisionPoint


class BranchDraft(BaseModel):
    """One concrete universe spun out of a single branch_candidate.

    The five scoring fields (affected_characters, affected_locations,
    emotional_impact, ending_divergence, narrative_impact) are written directly
    into Branch.decision_summary on persistence - they are exactly the keys the
    existing Butterfly Score engine (app/services/timeline_scoring_service.py)
    already reads, so populating them here is what makes scores stop being
    structural-baseline-only.
    """

    candidate_label: str = Field(
        description="Must exactly match one branch_candidate.label from the decision - "
        "this is how the draft is mapped back to the candidate it expands."
    )
    name: str = Field(description="Short branch name, e.g. 'Universe 3: Time Loop Collapse'.")
    summary: str = Field(description="Multi-sentence prose summary of this universe.")
    initial_divergent_state: str = Field(
        description="The concrete facts that are now different immediately after the decision."
    )
    delta_script: str = Field(
        description="A short script excerpt (scene heading + action/dialogue) covering what "
        "happens immediately after the decision in this universe."
    )
    affected_characters: list[str] = Field(
        default_factory=list, description="Names of characters meaningfully affected."
    )
    affected_locations: list[str] = Field(
        default_factory=list, description="Locations meaningfully affected or newly introduced."
    )
    emotional_impact: str = Field(description="The emotional shift this universe represents.")
    ending_divergence: str = Field(
        description="How this universe's likely ending differs from the StoryBible's ending_type."
    )
    narrative_impact: str = Field(description="How significantly this reshapes the plot going forward.")


class TimelineGenerationResult(BaseModel):
    """One BranchDraft per branch_candidate in the source decision. Downstream
    persistence consumes this object only - never the model's free-form text.
    """

    branches: list[BranchDraft] = Field(default_factory=list)
