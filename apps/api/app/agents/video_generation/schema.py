from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class ShotRenderRequest(BaseModel):
    shot_number: int = Field(ge=1)
    prompt_history_id: uuid.UUID
    prompt: str
    negative_prompt: str = ""
    duration_seconds: int | None = None


class VideoGenerationAgentRequest(BaseModel):
    shots: list[ShotRenderRequest] = Field(default_factory=list)


class ShotRenderResult(BaseModel):
    shot_number: int = Field(ge=1)
    prompt_history_id: uuid.UUID
    video_url: str
    duration_seconds: float | None = None
    provider: str
    attempts: int = Field(ge=1)
    raw_response: dict = Field(default_factory=dict)


class ShotRenderFailure(BaseModel):
    shot_number: int = Field(ge=1)
    prompt_history_id: uuid.UUID
    attempts: int = Field(ge=1)
    error: str


class VideoGenerationAgentResult(BaseModel):
    rendered: list[ShotRenderResult] = Field(default_factory=list)
    failed: list[ShotRenderFailure] = Field(default_factory=list)
