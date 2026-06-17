import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CharacterBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class CharacterCreate(CharacterBase):
    project_id: uuid.UUID
    voice_profile: dict = Field(default_factory=dict)
    canonical_traits: dict = Field(default_factory=dict)


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    visual_reference_asset_id: uuid.UUID | None = None
    voice_profile: dict | None = None
    canonical_traits: dict | None = None
    embedding_id: str | None = None


class CharacterRead(CharacterBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    visual_reference_asset_id: uuid.UUID | None
    voice_profile: dict
    canonical_traits: dict
    embedding_id: str | None
    created_at: datetime
    updated_at: datetime
