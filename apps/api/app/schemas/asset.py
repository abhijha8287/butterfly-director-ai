import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import AssetKind, AssetOwnerType


class AssetBase(BaseModel):
    kind: AssetKind
    owner_type: AssetOwnerType
    owner_id: uuid.UUID
    mime_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(ge=0)


class AssetCreate(AssetBase):
    project_id: uuid.UUID
    oss_key: str = Field(min_length=1, max_length=1024)
    oss_bucket: str = Field(min_length=1, max_length=255)
    duration_seconds: Decimal | None = None
    checksum_sha256: str | None = None


class AssetRead(AssetBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    oss_key: str
    oss_bucket: str
    duration_seconds: Decimal | None
    checksum_sha256: str | None
    created_at: datetime
    updated_at: datetime
