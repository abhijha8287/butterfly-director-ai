from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class VideoGenerationRequest(BaseModel):
    prompt: str
    negative_prompt: str | None = None
    duration_seconds: int | None = None
    size: str | None = None
    seed: int | None = None
    reference_image_url: str | None = None


class VideoGenerationResult(BaseModel):
    video_url: str
    duration_seconds: float | None = None
    provider: str
    raw_response: dict = Field(default_factory=dict)


class VoiceGenerationRequest(BaseModel):
    text: str
    voice: str | None = None
    audio_format: str = "mp3"
    speed: float | None = None


class VoiceGenerationResult(BaseModel):
    audio_bytes: bytes
    audio_format: str
    provider: str
    raw_response: dict = Field(default_factory=dict)


class MusicGenerationRequest(BaseModel):
    prompt: str
    mood: str | None = None
    duration_seconds: int | None = None


class MusicGenerationResult(BaseModel):
    audio_url: str | None = None
    audio_bytes: bytes | None = None
    provider: str
    raw_response: dict = Field(default_factory=dict)


class VideoGenerationProvider(ABC):
    """Strategy interface. Business logic depends only on this, never on a vendor."""

    @abstractmethod
    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult: ...


class VoiceGenerationProvider(ABC):
    """Strategy interface. Business logic depends only on this, never on a vendor."""

    @abstractmethod
    async def synthesize(self, request: VoiceGenerationRequest) -> VoiceGenerationResult: ...


class MusicGenerationProvider(ABC):
    """Strategy interface. Business logic depends only on this, never on a vendor."""

    @abstractmethod
    async def generate(self, request: MusicGenerationRequest) -> MusicGenerationResult: ...
