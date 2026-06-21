import enum

from sqlalchemy import Enum as SAEnum


def pg_enum(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda obj: [member.value for member in obj],
    )


class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    ARCHIVED = "archived"


class StoryStatus(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class TimelineStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"


class BranchStatus(str, enum.Enum):
    PENDING = "pending"
    PRODUCING = "producing"
    COMPLETED = "completed"
    FAILED = "failed"
    PRUNED = "pruned"


class MovieStatus(str, enum.Enum):
    QUEUED = "queued"
    STORYBOARDING = "storyboarding"
    RENDERING = "rendering"
    SCORING = "scoring"
    ASSEMBLING = "assembling"
    COMPLETED = "completed"
    FAILED = "failed"


class AssetKind(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    JSON = "json"


class AssetOwnerType(str, enum.Enum):
    MOVIE = "movie"
    CHARACTER = "character"
    SHOT = "shot"
    VOICE = "voice"
    MUSIC = "music"
    STORYBOARD = "storyboard"
    STORY = "story"


class JobType(str, enum.Enum):
    STORY_GENERATION = "story_generation"
    DECISION_DETECTION = "decision_detection"
    TIMELINE_BRANCH = "timeline_branch"
    STORYBOARD = "storyboard"
    VIDEO_RENDER = "video_render"
    VOICE_SYNTHESIS = "voice_synthesis"
    MUSIC_GENERATION = "music_generation"
    EDITING = "editing"
    MAINTENANCE = "maintenance"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class AgentLogStatus(str, enum.Enum):
    SUCCESS = "success"
    ERROR = "error"
    VALIDATION_FAILED = "validation_failed"


class PromptStage(str, enum.Enum):
    STORY = "story"
    STORYBOARD = "storyboard"
    SHOT_PROMPT = "shot_prompt"
    VIDEO = "video"
    VOICE = "voice"
    MUSIC = "music"


class PromptProvider(str, enum.Enum):
    QWEN = "qwen"
    WAN = "wan"
    HAPPYHORSE = "happyhorse"


class DriftSeverity(str, enum.Enum):
    NONE = "none"
    MINOR = "minor"
    MAJOR = "major"
