from app.agents.base.agent_result import AgentRunResult
from app.agents.character_architect.schema import CharacterProfile, CharacterRoster, VoiceProfile
from app.agents.story_architect.schema import StoryBible

VALID_STORY_BIBLE_KWARGS: dict[str, object] = {
    "title": "T",
    "logline": "L",
    "synopsis": "S",
    "genre": "sci-fi",
    "tone": "moody",
    "setting": "Lab",
    "world_description": "W",
    "timeline_period": "2031",
    "visual_style": "V",
    "cinematic_style": "C",
    "target_runtime": 10,
    "target_audience": "adults",
    "ending_type": "ambiguous",
    "conflict": "X",
    "protagonist_summary": "P",
    "themes": ["a"],
    "story_hooks": ["hook"],
}


def make_story_bible(**overrides: object) -> StoryBible:
    kwargs = dict(VALID_STORY_BIBLE_KWARGS)
    kwargs.update(overrides)
    return StoryBible(**kwargs)


def make_agent_run_result(**overrides: object) -> AgentRunResult[StoryBible]:
    defaults: dict[str, object] = {
        "output": make_story_bible(),
        "model": "qwen-plus",
        "prompt_version": "v1",
        "latency_ms": 123,
        "attempts": 1,
        "prompt_tokens": 10,
        "completion_tokens": 20,
    }
    defaults.update(overrides)
    return AgentRunResult(**defaults)


VALID_VOICE_PROFILE_KWARGS: dict[str, object] = {
    "descriptor": "low warm voice",
    "tone": "calm",
    "pace": "measured",
    "pitch": "low",
}


def make_voice_profile(**overrides: object) -> VoiceProfile:
    kwargs = dict(VALID_VOICE_PROFILE_KWARGS)
    kwargs.update(overrides)
    return VoiceProfile(**kwargs)


VALID_CHARACTER_PROFILE_KWARGS: dict[str, object] = {
    "name": "Hero",
    "role": "protagonist",
    "age_range": "30s",
    "physical_description": "Tall, sharp-eyed.",
    "wardrobe_style": "Worn leather jacket.",
    "personality_traits": ["determined"],
    "backstory": "Grew up on the docks.",
    "motivation": "To find the truth.",
    "internal_conflict": "Fear of repeating the past.",
    "external_conflict": "Hunted by old allies.",
    "character_arc": "Learns to trust again.",
    "relationships": [],
    "defining_strengths": ["resourceful"],
    "defining_flaws": ["stubborn"],
    "dialogue_style": "Short, clipped sentences.",
}


def make_character_profile(**overrides: object) -> CharacterProfile:
    kwargs = dict(VALID_CHARACTER_PROFILE_KWARGS)
    voice_profile = overrides.pop("voice_profile", make_voice_profile())
    kwargs.update(overrides)
    return CharacterProfile(voice_profile=voice_profile, **kwargs)


def make_character_roster(**overrides: object) -> CharacterRoster:
    characters = overrides.pop("characters", None)
    if characters is None:
        characters = [make_character_profile()]
    return CharacterRoster(characters=characters, **overrides)


def make_character_agent_run_result(**overrides: object) -> AgentRunResult[CharacterRoster]:
    defaults: dict[str, object] = {
        "output": make_character_roster(),
        "model": "qwen-plus",
        "prompt_version": "v1",
        "latency_ms": 456,
        "attempts": 1,
        "prompt_tokens": 30,
        "completion_tokens": 40,
    }
    defaults.update(overrides)
    return AgentRunResult(**defaults)
