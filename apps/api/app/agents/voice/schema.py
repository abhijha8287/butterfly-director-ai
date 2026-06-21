from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.story_architect.schema import StoryBible


class VoiceCharacterProfile(BaseModel):
    name: str
    personality_traits: list[str] = Field(default_factory=list)
    dialogue_style: str = ""
    voice_descriptor: str = ""
    emotional_state: str = "unchanged"


class ShotScript(BaseModel):
    scene: str
    shot_number: int = Field(ge=1)
    description: str
    characters_present: list[str] = Field(default_factory=list)


class VoiceRequest(BaseModel):
    story_bible: StoryBible
    branch_name: str
    delta_script: str | None = None
    shots: list[ShotScript] = Field(default_factory=list)
    characters: list[VoiceCharacterProfile] = Field(default_factory=list)


class DialogueLine(BaseModel):
    shot_number: int = Field(ge=1, description="Must exactly match one input shot's shot_number.")
    character_name: str = Field(description="Must exactly match one input character's name.")
    line_text: str = Field(
        description="The exact words this character speaks - spoken dialogue, never narration."
    )
    delivery_note: str = Field(
        description="Short performance instruction for the speech synthesizer "
        "(tone/pace/emotion), e.g. 'urgent whisper' or 'flat and detached'."
    )


class DialogueScript(BaseModel):
    """LLM output contract for the extraction phase. An empty `lines` list is
    valid - a branch with no spoken dialogue (pure action/establishing shots)
    is a legitimate output, mirroring Decision Detector's zero-decisions case.
    """

    lines: list[DialogueLine] = Field(default_factory=list)


class VoiceLineResult(BaseModel):
    shot_number: int = Field(ge=1)
    character_name: str
    line_text: str
    delivery_note: str
    audio_bytes: bytes
    audio_format: str
    provider: str
    attempts: int = Field(ge=1)


class VoiceLineFailure(BaseModel):
    shot_number: int = Field(ge=1)
    character_name: str
    line_text: str
    delivery_note: str
    attempts: int = Field(ge=1)
    error: str


class VoiceAgentResult(BaseModel):
    lines: list[VoiceLineResult] = Field(default_factory=list)
    failed_lines: list[VoiceLineFailure] = Field(default_factory=list)
