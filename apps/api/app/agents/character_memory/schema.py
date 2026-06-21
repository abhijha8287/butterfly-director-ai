from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DriftSeverity = Literal["none", "minor", "major"]


class CharacterMemoryProfile(BaseModel):
    """Canonical trait snapshot for one character, exactly as locked in by the
    Character Architect (Character.canonical_traits). The Character Memory
    agent treats every field here as the immutable baseline a branch's
    state_diff must be checked against - it never edits these, only judges
    against them.
    """

    name: str
    role: str
    personality_traits: list[str] = Field(default_factory=list)
    motivation: str
    internal_conflict: str
    external_conflict: str
    defining_strengths: list[str] = Field(default_factory=list)
    defining_flaws: list[str] = Field(default_factory=list)
    dialogue_style: str


class BranchContext(BaseModel):
    """The target branch this run resolves character states against. Mirrors
    the fields the Timeline Generator agent already writes into
    Branch.decision_summary - this is the only other agent that reads them.
    """

    name: str
    summary: str | None = None
    initial_divergent_state: str | None = None
    delta_script: str | None = None
    affected_characters: list[str] = Field(default_factory=list)
    emotional_impact: str | None = None
    ending_divergence: str | None = None
    narrative_impact: str | None = None


class CharacterMemoryRequest(BaseModel):
    """Input contract for the Character Memory agent: one target branch plus
    the full canonical character roster for that branch's story - never raw
    text.
    """

    branch: BranchContext
    characters: list[CharacterMemoryProfile] = Field(default_factory=list)


class CharacterStateDiff(BaseModel):
    """What changed for one character in this specific universe, plus a
    drift judgment against their canonical traits. Persisted into
    CharacterBranchState.state_diff (the five descriptive fields) and
    drift_severity/drift_warning (first-class columns).
    """

    character_name: str = Field(
        description="Must exactly match one character's name from the input roster - "
        "this is how the diff is mapped back to the character it describes."
    )
    knowledge_state: str = Field(
        description="What this character now knows/believes in this branch, vs baseline. "
        "Use 'unchanged' if nothing new."
    )
    emotional_state: str = Field(description="This character's emotional state in this branch.")
    relationship_changes: list[str] = Field(default_factory=list)
    goal_shift: str = Field(
        description="How this character's immediate goal shifted for this branch. "
        "Use 'unchanged' if it did not."
    )
    physical_state: str = Field(
        description="Physical/location continuity detail relevant to this branch. "
        "Use 'unchanged' if nothing notable."
    )
    drift_severity: DriftSeverity = Field(
        description="How much this branch's portrayal of the character contradicts their "
        "canonical_traits - not how dramatic the branch is."
    )
    drift_warning: str | None = Field(
        default=None,
        description="Required when drift_severity is 'minor' or 'major': name the specific "
        "canonical trait being contradicted and how. Must be unset when drift_severity is 'none'.",
    )


class CharacterMemoryResult(BaseModel):
    """One CharacterStateDiff per character in the input roster. Downstream
    persistence consumes this object only - never the model's free-form text.
    """

    character_states: list[CharacterStateDiff] = Field(default_factory=list)
