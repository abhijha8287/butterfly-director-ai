from app.agents.base.agent_result import AgentRunResult
from app.agents.character_architect.schema import CharacterProfile, CharacterRoster, VoiceProfile
from app.agents.character_memory.schema import (
    BranchContext,
    CharacterMemoryProfile,
    CharacterMemoryRequest,
    CharacterMemoryResult,
    CharacterStateDiff,
)
from app.agents.decision_detector.schema import BranchCandidate, DecisionList, DecisionPoint
from app.agents.story_architect.schema import StoryBible
from app.agents.timeline_generator.schema import BranchDraft, TimelineGenerationResult

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


VALID_BRANCH_CANDIDATE_KWARGS: dict[str, object] = {
    "label": "Shout",
    "description": "She shouts for help.",
    "tone_shift": "Tension spikes.",
    "divergence_summary": "This universe ends with rescue.",
}


def make_branch_candidate(**overrides: object) -> BranchCandidate:
    kwargs = dict(VALID_BRANCH_CANDIDATE_KWARGS)
    kwargs.update(overrides)
    return BranchCandidate(**kwargs)


VALID_DECISION_POINT_KWARGS: dict[str, object] = {
    "beat_index": 0,
    "description": "She must decide whether to shout or stay silent.",
    "source_hook": "hook",
}


def make_decision_point(**overrides: object) -> DecisionPoint:
    kwargs = dict(VALID_DECISION_POINT_KWARGS)
    branch_candidates = overrides.pop(
        "branch_candidates", [make_branch_candidate(), make_branch_candidate(label="Stay silent")]
    )
    kwargs.update(overrides)
    return DecisionPoint(branch_candidates=branch_candidates, **kwargs)


def make_decision_list(**overrides: object) -> DecisionList:
    decisions = overrides.pop("decisions", None)
    if decisions is None:
        decisions = [make_decision_point()]
    return DecisionList(decisions=decisions, **overrides)


def make_decision_agent_run_result(**overrides: object) -> AgentRunResult[DecisionList]:
    defaults: dict[str, object] = {
        "output": make_decision_list(),
        "model": "qwen-plus",
        "prompt_version": "v1",
        "latency_ms": 789,
        "attempts": 1,
        "prompt_tokens": 50,
        "completion_tokens": 60,
    }
    defaults.update(overrides)
    return AgentRunResult(**defaults)


VALID_BRANCH_DRAFT_KWARGS: dict[str, object] = {
    "candidate_label": "Shout",
    "name": "Universe: Rescue",
    "summary": "She shouts and is rescued.",
    "initial_divergent_state": "Help has been alerted.",
    "delta_script": "INT. ALLEY - NIGHT\nShe screams. Footsteps approach.",
    "affected_characters": ["Hero"],
    "affected_locations": ["Alley"],
    "emotional_impact": "Relief.",
    "ending_divergence": "A hopeful ending becomes likely.",
    "narrative_impact": "Introduces a rescuer subplot.",
}


def make_branch_draft(**overrides: object) -> BranchDraft:
    kwargs = dict(VALID_BRANCH_DRAFT_KWARGS)
    kwargs.update(overrides)
    return BranchDraft(**kwargs)


def make_timeline_generation_result(**overrides: object) -> TimelineGenerationResult:
    branches = overrides.pop("branches", None)
    if branches is None:
        branches = [
            make_branch_draft(candidate_label="Shout"),
            make_branch_draft(
                candidate_label="Stay silent",
                name="Universe: Isolation",
                summary="She stays silent and is left alone.",
            ),
        ]
    return TimelineGenerationResult(branches=branches, **overrides)


def make_timeline_agent_run_result(**overrides: object) -> AgentRunResult[TimelineGenerationResult]:
    defaults: dict[str, object] = {
        "output": make_timeline_generation_result(),
        "model": "qwen-plus",
        "prompt_version": "v1",
        "latency_ms": 1011,
        "attempts": 1,
        "prompt_tokens": 70,
        "completion_tokens": 80,
    }
    defaults.update(overrides)
    return AgentRunResult(**defaults)


VALID_CHARACTER_MEMORY_PROFILE_KWARGS: dict[str, object] = {
    "name": "Hero",
    "role": "protagonist",
    "personality_traits": ["determined"],
    "motivation": "To find the truth.",
    "internal_conflict": "Fear of repeating the past.",
    "external_conflict": "Hunted by old allies.",
    "defining_strengths": ["resourceful"],
    "defining_flaws": ["stubborn"],
    "dialogue_style": "Short, clipped sentences.",
}


def make_character_memory_profile(**overrides: object) -> CharacterMemoryProfile:
    kwargs = dict(VALID_CHARACTER_MEMORY_PROFILE_KWARGS)
    kwargs.update(overrides)
    return CharacterMemoryProfile(**kwargs)


VALID_BRANCH_CONTEXT_KWARGS: dict[str, object] = {
    "name": "Universe: Rescue",
    "summary": "She shouts and is rescued.",
    "initial_divergent_state": "Help has been alerted.",
    "delta_script": "INT. ALLEY - NIGHT\nShe screams. Footsteps approach.",
    "affected_characters": ["Hero"],
    "emotional_impact": "Relief.",
    "ending_divergence": "A hopeful ending becomes likely.",
    "narrative_impact": "Introduces a rescuer subplot.",
}


def make_branch_context(**overrides: object) -> BranchContext:
    kwargs = dict(VALID_BRANCH_CONTEXT_KWARGS)
    kwargs.update(overrides)
    return BranchContext(**kwargs)


VALID_CHARACTER_STATE_DIFF_KWARGS: dict[str, object] = {
    "character_name": "Hero",
    "knowledge_state": "Knows help is coming.",
    "emotional_state": "Relieved but shaken.",
    "relationship_changes": [],
    "goal_shift": "unchanged",
    "physical_state": "Minor bruising from the struggle.",
    "drift_severity": "none",
    "drift_warning": None,
}


def make_character_state_diff(**overrides: object) -> CharacterStateDiff:
    kwargs = dict(VALID_CHARACTER_STATE_DIFF_KWARGS)
    kwargs.update(overrides)
    return CharacterStateDiff(**kwargs)


def make_character_memory_request(**overrides: object) -> CharacterMemoryRequest:
    branch = overrides.pop("branch", None) or make_branch_context()
    characters = overrides.pop("characters", None)
    if characters is None:
        characters = [make_character_memory_profile()]
    return CharacterMemoryRequest(branch=branch, characters=characters, **overrides)


def make_character_memory_result(**overrides: object) -> CharacterMemoryResult:
    character_states = overrides.pop("character_states", None)
    if character_states is None:
        character_states = [make_character_state_diff()]
    return CharacterMemoryResult(character_states=character_states, **overrides)


def make_character_memory_agent_run_result(
    **overrides: object,
) -> AgentRunResult[CharacterMemoryResult]:
    defaults: dict[str, object] = {
        "output": make_character_memory_result(),
        "model": "qwen-plus",
        "prompt_version": "v1",
        "latency_ms": 1213,
        "attempts": 1,
        "prompt_tokens": 90,
        "completion_tokens": 100,
    }
    defaults.update(overrides)
    return AgentRunResult(**defaults)
