import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.agents.character_architect.schema import CharacterRole, VoiceProfile


class CharacterGenerateRequest(BaseModel):
    story_id: uuid.UUID


class CharacterProfileRead(BaseModel):
    """A single persisted character, with its full agent-produced profile
    reconstructed from the Character row's description/voice_profile/canonical_traits
    columns - the API-facing shape downstream callers actually want, not the raw dict.
    """

    model_config = ConfigDict(from_attributes=False)

    id: uuid.UUID
    story_id: uuid.UUID | None
    name: str
    role: CharacterRole
    age_range: str
    physical_description: str
    wardrobe_style: str
    personality_traits: list[str]
    backstory: str
    motivation: str
    internal_conflict: str
    external_conflict: str
    character_arc: str
    relationships: list[str]
    defining_strengths: list[str]
    defining_flaws: list[str]
    dialogue_style: str
    voice_profile: VoiceProfile
    secret: str | None
    created_at: datetime


class CharacterGenerateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    story_id: uuid.UUID
    characters: list[CharacterProfileRead]
    prompt_version: str
    model: str
    latency_ms: int
    attempts: int
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: datetime
