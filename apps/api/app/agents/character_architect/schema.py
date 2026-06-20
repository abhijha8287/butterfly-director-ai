from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.agents.story_architect.schema import StoryBible

CharacterRole = Literal["protagonist", "antagonist", "supporting"]


class CharacterRequest(BaseModel):
    """Input contract for the Character Architect agent.

    Takes the validated StoryBible only - never raw user text - matching the
    Story Architect's contract that downstream agents consume structured
    output exclusively.
    """

    story_bible: StoryBible


class VoiceProfile(BaseModel):
    """Descriptor a future Voice Agent (CosyVoice) maps onto an actual voice id."""

    descriptor: str = Field(
        description="Free-text description of the voice (timbre, accent, register)."
    )
    tone: str = Field(description="Emotional tone of the character's typical delivery.")
    pace: str = Field(description="Speaking pace (e.g. 'measured', 'rapid-fire').")
    pitch: str = Field(description="Relative pitch (e.g. 'low and gravelly', 'bright and high').")


class CharacterProfile(BaseModel):
    """Strongly typed, deep character profile produced by the Character Architect.

    Every field here exists to keep this character consistent across every
    branch of the multiverse: physical_description and voice_profile feed
    video/voice generation prompts directly; the rest forms the canonical
    trait set a future Character Memory agent checks branch states against.
    """

    name: str = Field(description="Character's full name as used in the story.")
    role: CharacterRole = Field(description="Narrative role this character plays.")
    age_range: str = Field(description="Approximate age or age range (e.g. '30s', '8 years old').")
    physical_description: str = Field(
        description="Concrete, visually specific description for image/video generation "
        "consistency (build, face, hair, distinguishing features)."
    )
    wardrobe_style: str = Field(description="Default wardrobe/costume style and palette.")
    personality_traits: list[str] = Field(
        default_factory=list, description="Defining personality traits."
    )
    backstory: str = Field(description="History that explains who this character is now.")
    motivation: str = Field(description="What this character wants and why.")
    internal_conflict: str = Field(description="The character's internal/psychological conflict.")
    external_conflict: str = Field(description="The character's external/interpersonal conflict.")
    character_arc: str = Field(description="How this character changes over the story.")
    relationships: list[str] = Field(
        default_factory=list,
        description="One sentence per relationship, naming the other character.",
    )
    defining_strengths: list[str] = Field(default_factory=list)
    defining_flaws: list[str] = Field(default_factory=list)
    dialogue_style: str = Field(
        description="How this character speaks: vocabulary, rhythm, verbal tics."
    )
    voice_profile: VoiceProfile
    secret: str | None = Field(
        default=None, description="Hidden information revealed over the course of the story, if any."
    )


class CharacterRoster(BaseModel):
    """Full cast produced from one StoryBible. Downstream agents (Storyboard,
    Video, Voice, Character Memory) consume this object only.
    """

    characters: list[CharacterProfile] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_names_and_single_protagonist(self) -> CharacterRoster:
        names = [c.name.strip().lower() for c in self.characters]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise ValueError(f"CharacterRoster has duplicate character names: {duplicates}")

        protagonists = [c for c in self.characters if c.role == "protagonist"]
        if len(protagonists) != 1:
            raise ValueError(
                f"CharacterRoster must have exactly one protagonist, found {len(protagonists)}"
            )
        return self
