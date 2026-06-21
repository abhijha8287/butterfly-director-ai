from uuid import uuid4

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
from app.agents.editor.schema import EditorAudioInput, EditorRequest, EditorResult, EditorShotInput
from app.agents.music.schema import (
    MusicAgentResult,
    MusicCue,
    MusicCueFailure,
    MusicCueResult,
    MusicRequest,
    MusicScript,
    MusicShotScript,
)
from app.agents.prompt_director.schema import (
    CharacterVisualProfile,
    PromptDirectorRequest,
    PromptDirectorResult,
    ShotContext,
    ShotPrompt,
)
from app.agents.story_architect.schema import StoryBible
from app.agents.storyboard.schema import (
    CharacterStateSummary,
    Shot,
    StoryboardRequest,
    StoryboardResult,
)
from app.agents.timeline_generator.schema import BranchDraft, TimelineGenerationResult
from app.agents.video_generation.schema import (
    ShotRenderFailure,
    ShotRenderRequest,
    ShotRenderResult,
    VideoGenerationAgentRequest,
    VideoGenerationAgentResult,
)
from app.agents.voice.schema import (
    DialogueLine,
    DialogueScript,
    ShotScript,
    VoiceAgentResult,
    VoiceCharacterProfile,
    VoiceLineFailure,
    VoiceLineResult,
    VoiceRequest,
)

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


VALID_CHARACTER_STATE_SUMMARY_KWARGS: dict[str, object] = {
    "name": "Hero",
    "role": "protagonist",
    "physical_description": "Tall, sharp-eyed.",
    "knowledge_state": "Knows help is coming.",
    "emotional_state": "Relieved but shaken.",
    "physical_state": "Minor bruising from the struggle.",
}


def make_character_state_summary(**overrides: object) -> CharacterStateSummary:
    kwargs = dict(VALID_CHARACTER_STATE_SUMMARY_KWARGS)
    kwargs.update(overrides)
    return CharacterStateSummary(**kwargs)


VALID_SHOT_KWARGS: dict[str, object] = {
    "scene": "INT. ALLEY - NIGHT",
    "shot_number": 1,
    "description": "She screams. Footsteps approach.",
    "camera": "low-angle tracking shot",
    "duration_seconds": 4.5,
    "characters_present": ["Hero"],
}


def make_shot(**overrides: object) -> Shot:
    kwargs = dict(VALID_SHOT_KWARGS)
    kwargs.update(overrides)
    return Shot(**kwargs)


def make_storyboard_request(**overrides: object) -> StoryboardRequest:
    story_bible = overrides.pop("story_bible", None) or make_story_bible()
    characters = overrides.pop("characters", None)
    if characters is None:
        characters = [make_character_state_summary()]
    defaults: dict[str, object] = {
        "branch_name": "Universe: Rescue",
        "branch_summary": "She shouts and is rescued.",
        "delta_script": "INT. ALLEY - NIGHT\nShe screams. Footsteps approach.",
    }
    defaults.update(overrides)
    return StoryboardRequest(story_bible=story_bible, characters=characters, **defaults)


def make_storyboard_result(**overrides: object) -> StoryboardResult:
    shots = overrides.pop("shots", None)
    if shots is None:
        shots = [make_shot(shot_number=1), make_shot(shot_number=2, scene="EXT. ROOFTOP - NIGHT")]
    return StoryboardResult(shots=shots, **overrides)


def make_storyboard_agent_run_result(**overrides: object) -> AgentRunResult[StoryboardResult]:
    defaults: dict[str, object] = {
        "output": make_storyboard_result(),
        "model": "qwen-plus",
        "prompt_version": "v1",
        "latency_ms": 1414,
        "attempts": 1,
        "prompt_tokens": 110,
        "completion_tokens": 120,
    }
    defaults.update(overrides)
    return AgentRunResult(**defaults)


VALID_CHARACTER_VISUAL_PROFILE_KWARGS: dict[str, object] = {
    "name": "Hero",
    "physical_description": "Tall, sharp-eyed.",
    "wardrobe_style": "Worn leather jacket.",
    "emotional_state": "Relieved but shaken.",
    "physical_state": "Minor bruising from the struggle.",
}


def make_character_visual_profile(**overrides: object) -> CharacterVisualProfile:
    kwargs = dict(VALID_CHARACTER_VISUAL_PROFILE_KWARGS)
    kwargs.update(overrides)
    return CharacterVisualProfile(**kwargs)


VALID_SHOT_CONTEXT_KWARGS: dict[str, object] = {
    "scene": "INT. ALLEY - NIGHT",
    "shot_number": 1,
    "description": "She screams. Footsteps approach.",
    "camera": "low-angle tracking shot",
    "duration_seconds": 4.5,
}


def make_shot_context(**overrides: object) -> ShotContext:
    kwargs = dict(VALID_SHOT_CONTEXT_KWARGS)
    characters = overrides.pop("characters", None)
    if characters is None:
        characters = [make_character_visual_profile()]
    kwargs.update(overrides)
    return ShotContext(characters=characters, **kwargs)


def make_prompt_director_request(**overrides: object) -> PromptDirectorRequest:
    story_bible = overrides.pop("story_bible", None) or make_story_bible()
    shots = overrides.pop("shots", None)
    if shots is None:
        shots = [make_shot_context()]
    return PromptDirectorRequest(story_bible=story_bible, shots=shots, **overrides)


VALID_SHOT_PROMPT_KWARGS: dict[str, object] = {
    "shot_number": 1,
    "positive_prompt": "Tall, sharp-eyed woman in a worn leather jacket screams in a dark alley.",
    "negative_prompt": "extra limbs, wrong character count, text artifacts",
    "consistency_tokens": ["tall sharp-eyed woman", "worn leather jacket"],
    "style_tokens": ["high-contrast neon noir"],
}


def make_shot_prompt(**overrides: object) -> ShotPrompt:
    kwargs = dict(VALID_SHOT_PROMPT_KWARGS)
    kwargs.update(overrides)
    return ShotPrompt(**kwargs)


def make_prompt_director_result(**overrides: object) -> PromptDirectorResult:
    shot_prompts = overrides.pop("shot_prompts", None)
    if shot_prompts is None:
        shot_prompts = [make_shot_prompt(shot_number=1), make_shot_prompt(shot_number=2)]
    return PromptDirectorResult(shot_prompts=shot_prompts, **overrides)


def make_prompt_director_agent_run_result(
    **overrides: object,
) -> AgentRunResult[PromptDirectorResult]:
    defaults: dict[str, object] = {
        "output": make_prompt_director_result(),
        "model": "qwen-plus",
        "prompt_version": "v1",
        "latency_ms": 1515,
        "attempts": 1,
        "prompt_tokens": 130,
        "completion_tokens": 140,
    }
    defaults.update(overrides)
    return AgentRunResult(**defaults)


VALID_SHOT_RENDER_REQUEST_KWARGS: dict[str, object] = {
    "shot_number": 1,
    "prompt": "Tall, sharp-eyed woman in a worn leather jacket screams in a dark alley.",
    "negative_prompt": "extra limbs, wrong character count, text artifacts",
    "duration_seconds": 5,
}


def make_shot_render_request(**overrides: object) -> ShotRenderRequest:
    kwargs = dict(VALID_SHOT_RENDER_REQUEST_KWARGS)
    prompt_history_id = overrides.pop("prompt_history_id", None) or uuid4()
    kwargs.update(overrides)
    return ShotRenderRequest(prompt_history_id=prompt_history_id, **kwargs)


def make_video_generation_agent_request(**overrides: object) -> VideoGenerationAgentRequest:
    shots = overrides.pop("shots", None)
    if shots is None:
        shots = [make_shot_render_request()]
    return VideoGenerationAgentRequest(shots=shots, **overrides)


VALID_SHOT_RENDER_RESULT_KWARGS: dict[str, object] = {
    "shot_number": 1,
    "duration_seconds": 5.0,
    "provider": "wan",
    "attempts": 1,
}


def make_shot_render_result(**overrides: object) -> ShotRenderResult:
    # video_url defaults to a fresh URL per call (not a fixed constant) since
    # Asset.oss_key stores it directly and is unique - reusing one default
    # across multiple shots in the same test would collide on that constraint.
    kwargs = dict(VALID_SHOT_RENDER_RESULT_KWARGS)
    prompt_history_id = overrides.pop("prompt_history_id", None) or uuid4()
    video_url = overrides.pop(
        "video_url", f"https://dashscope-result.example.com/videos/{uuid4()}.mp4"
    )
    kwargs.update(overrides)
    return ShotRenderResult(prompt_history_id=prompt_history_id, video_url=video_url, **kwargs)


VALID_SHOT_RENDER_FAILURE_KWARGS: dict[str, object] = {
    "shot_number": 1,
    "attempts": 3,
    "error": "Wan video task abc123 timed out after 600.0s",
}


def make_shot_render_failure(**overrides: object) -> ShotRenderFailure:
    kwargs = dict(VALID_SHOT_RENDER_FAILURE_KWARGS)
    prompt_history_id = overrides.pop("prompt_history_id", None) or uuid4()
    kwargs.update(overrides)
    return ShotRenderFailure(prompt_history_id=prompt_history_id, **kwargs)


def make_video_generation_agent_result(**overrides: object) -> VideoGenerationAgentResult:
    rendered = overrides.pop("rendered", None)
    if rendered is None:
        rendered = [make_shot_render_result()]
    failed = overrides.pop("failed", None)
    if failed is None:
        failed = []
    return VideoGenerationAgentResult(rendered=rendered, failed=failed, **overrides)


def make_video_generation_agent_run_result(
    **overrides: object,
) -> AgentRunResult[VideoGenerationAgentResult]:
    defaults: dict[str, object] = {
        "output": make_video_generation_agent_result(),
        "model": "wan",
        "prompt_version": "n/a",
        "latency_ms": 1616,
        "attempts": 1,
    }
    defaults.update(overrides)
    return AgentRunResult(**defaults)


VALID_VOICE_CHARACTER_PROFILE_KWARGS: dict[str, object] = {
    "name": "Hero",
    "personality_traits": ["determined"],
    "dialogue_style": "Short, clipped sentences.",
    "voice_descriptor": "low warm voice",
    "emotional_state": "Relieved but shaken.",
}


def make_voice_character_profile(**overrides: object) -> VoiceCharacterProfile:
    kwargs = dict(VALID_VOICE_CHARACTER_PROFILE_KWARGS)
    kwargs.update(overrides)
    return VoiceCharacterProfile(**kwargs)


VALID_SHOT_SCRIPT_KWARGS: dict[str, object] = {
    "scene": "INT. ALLEY - NIGHT",
    "shot_number": 1,
    "description": "She screams. Footsteps approach.",
    "characters_present": ["Hero"],
}


def make_shot_script(**overrides: object) -> ShotScript:
    kwargs = dict(VALID_SHOT_SCRIPT_KWARGS)
    kwargs.update(overrides)
    return ShotScript(**kwargs)


def make_voice_request(**overrides: object) -> VoiceRequest:
    story_bible = overrides.pop("story_bible", None) or make_story_bible()
    shots = overrides.pop("shots", None)
    if shots is None:
        shots = [make_shot_script()]
    characters = overrides.pop("characters", None)
    if characters is None:
        characters = [make_voice_character_profile()]
    defaults: dict[str, object] = {"branch_name": "Universe: Rescue"}
    defaults.update(overrides)
    return VoiceRequest(story_bible=story_bible, shots=shots, characters=characters, **defaults)


VALID_DIALOGUE_LINE_KWARGS: dict[str, object] = {
    "shot_number": 1,
    "character_name": "Hero",
    "line_text": "Stay back. I know this place better than you think.",
    "delivery_note": "low, urgent whisper",
}


def make_dialogue_line(**overrides: object) -> DialogueLine:
    kwargs = dict(VALID_DIALOGUE_LINE_KWARGS)
    kwargs.update(overrides)
    return DialogueLine(**kwargs)


def make_dialogue_script(**overrides: object) -> DialogueScript:
    lines = overrides.pop("lines", None)
    if lines is None:
        lines = [make_dialogue_line()]
    return DialogueScript(lines=lines, **overrides)


VALID_VOICE_LINE_RESULT_KWARGS: dict[str, object] = {
    "shot_number": 1,
    "character_name": "Hero",
    "line_text": "Stay back. I know this place better than you think.",
    "delivery_note": "low, urgent whisper",
    "audio_format": "mp3",
    "provider": "dashscope",
    "attempts": 1,
}


def make_voice_line_result(**overrides: object) -> VoiceLineResult:
    kwargs = dict(VALID_VOICE_LINE_RESULT_KWARGS)
    audio_bytes = overrides.pop("audio_bytes", None)
    if audio_bytes is None:
        audio_bytes = uuid4().bytes
    kwargs.update(overrides)
    return VoiceLineResult(audio_bytes=audio_bytes, **kwargs)


VALID_VOICE_LINE_FAILURE_KWARGS: dict[str, object] = {
    "shot_number": 1,
    "character_name": "Hero",
    "line_text": "Stay back. I know this place better than you think.",
    "delivery_note": "low, urgent whisper",
    "attempts": 3,
    "error": "CosyVoice task abc123 timed out",
}


def make_voice_line_failure(**overrides: object) -> VoiceLineFailure:
    kwargs = dict(VALID_VOICE_LINE_FAILURE_KWARGS)
    kwargs.update(overrides)
    return VoiceLineFailure(**kwargs)


def make_voice_agent_result(**overrides: object) -> VoiceAgentResult:
    lines = overrides.pop("lines", None)
    if lines is None:
        lines = [make_voice_line_result()]
    failed_lines = overrides.pop("failed_lines", None)
    if failed_lines is None:
        failed_lines = []
    return VoiceAgentResult(lines=lines, failed_lines=failed_lines, **overrides)


def make_voice_agent_run_result(**overrides: object) -> AgentRunResult[VoiceAgentResult]:
    defaults: dict[str, object] = {
        "output": make_voice_agent_result(),
        "model": "qwen-plus",
        "prompt_version": "v1",
        "latency_ms": 1717,
        "attempts": 1,
        "prompt_tokens": 150,
        "completion_tokens": 160,
    }
    defaults.update(overrides)
    return AgentRunResult(**defaults)


VALID_MUSIC_SHOT_SCRIPT_KWARGS: dict[str, object] = {
    "scene": "INT. ALLEY - NIGHT",
    "shot_number": 1,
    "description": "She screams. Footsteps approach.",
    "duration_seconds": 4.5,
}


def make_music_shot_script(**overrides: object) -> MusicShotScript:
    kwargs = dict(VALID_MUSIC_SHOT_SCRIPT_KWARGS)
    kwargs.update(overrides)
    return MusicShotScript(**kwargs)


def make_music_request(**overrides: object) -> MusicRequest:
    story_bible = overrides.pop("story_bible", None) or make_story_bible()
    shots = overrides.pop("shots", None)
    if shots is None:
        shots = [make_music_shot_script()]
    defaults: dict[str, object] = {
        "branch_name": "Universe: Rescue",
        "branch_summary": "She shouts and is rescued.",
    }
    defaults.update(overrides)
    return MusicRequest(story_bible=story_bible, shots=shots, **defaults)


VALID_MUSIC_CUE_KWARGS: dict[str, object] = {
    "start_shot_number": 1,
    "end_shot_number": 1,
    "mood": "tense, rising dread",
    "tempo_bpm": 110,
    "generation_prompt": "Dark ambient drone, low strings, slow building tension, 110bpm.",
}


def make_music_cue(**overrides: object) -> MusicCue:
    kwargs = dict(VALID_MUSIC_CUE_KWARGS)
    kwargs.update(overrides)
    return MusicCue(**kwargs)


def make_music_script(**overrides: object) -> MusicScript:
    cues = overrides.pop("cues", None)
    if cues is None:
        cues = [make_music_cue()]
    return MusicScript(cues=cues, **overrides)


VALID_MUSIC_CUE_RESULT_KWARGS: dict[str, object] = {
    "start_shot_number": 1,
    "end_shot_number": 1,
    "mood": "tense, rising dread",
    "tempo_bpm": 110,
    "generation_prompt": "Dark ambient drone, low strings, slow building tension, 110bpm.",
    "provider": "happyhorse",
    "attempts": 1,
}


def make_music_cue_result(**overrides: object) -> MusicCueResult:
    kwargs = dict(VALID_MUSIC_CUE_RESULT_KWARGS)
    kwargs.update(overrides)
    return MusicCueResult(**kwargs)


VALID_MUSIC_CUE_FAILURE_KWARGS: dict[str, object] = {
    "start_shot_number": 1,
    "end_shot_number": 1,
    "mood": "tense, rising dread",
    "tempo_bpm": 110,
    "generation_prompt": "Dark ambient drone, low strings, slow building tension, 110bpm.",
    "attempts": 3,
    "error": "HappyHorse task abc123 timed out",
}


def make_music_cue_failure(**overrides: object) -> MusicCueFailure:
    kwargs = dict(VALID_MUSIC_CUE_FAILURE_KWARGS)
    kwargs.update(overrides)
    return MusicCueFailure(**kwargs)


def make_music_agent_result(**overrides: object) -> MusicAgentResult:
    cues = overrides.pop("cues", None)
    if cues is None:
        cues = [make_music_cue_result()]
    failed_cues = overrides.pop("failed_cues", None)
    if failed_cues is None:
        failed_cues = []
    return MusicAgentResult(cues=cues, failed_cues=failed_cues, **overrides)


def make_music_agent_run_result(**overrides: object) -> AgentRunResult[MusicAgentResult]:
    defaults: dict[str, object] = {
        "output": make_music_agent_result(),
        "model": "qwen-plus",
        "prompt_version": "v1",
        "latency_ms": 1717,
        "attempts": 1,
        "prompt_tokens": 150,
        "completion_tokens": 160,
    }
    defaults.update(overrides)
    return AgentRunResult(**defaults)


VALID_EDITOR_SHOT_INPUT_KWARGS: dict[str, object] = {
    "shot_number": 1,
    "video_url": "https://example.com/shot1.mp4",
    "duration_seconds": 4.5,
}


def make_editor_shot_input(**overrides: object) -> EditorShotInput:
    kwargs = dict(VALID_EDITOR_SHOT_INPUT_KWARGS)
    kwargs.update(overrides)
    return EditorShotInput(**kwargs)


VALID_EDITOR_AUDIO_INPUT_KWARGS: dict[str, object] = {
    "source": "/app/media/voice/line1.mp3",
    "start_offset_seconds": 0.0,
    "kind": "voice",
}


def make_editor_audio_input(**overrides: object) -> EditorAudioInput:
    kwargs = dict(VALID_EDITOR_AUDIO_INPUT_KWARGS)
    kwargs.update(overrides)
    return EditorAudioInput(**kwargs)


def make_editor_request(**overrides: object) -> EditorRequest:
    shots = overrides.pop("shots", None)
    if shots is None:
        shots = [make_editor_shot_input()]
    audio_tracks = overrides.pop("audio_tracks", None)
    if audio_tracks is None:
        audio_tracks = []
    defaults: dict[str, object] = {"output_path": "/app/media/editor/output.mp4"}
    defaults.update(overrides)
    return EditorRequest(shots=shots, audio_tracks=audio_tracks, **defaults)


VALID_EDITOR_RESULT_KWARGS: dict[str, object] = {
    "output_path": "/app/media/editor/output.mp4",
    "duration_seconds": 9.5,
    "provider": "ffmpeg",
    "shot_count": 1,
    "audio_track_count": 0,
}


def make_editor_result(**overrides: object) -> EditorResult:
    kwargs = dict(VALID_EDITOR_RESULT_KWARGS)
    kwargs.update(overrides)
    return EditorResult(**kwargs)


def make_editor_agent_run_result(**overrides: object) -> AgentRunResult[EditorResult]:
    defaults: dict[str, object] = {
        "output": make_editor_result(),
        "model": "ffmpeg",
        "prompt_version": "n/a",
        "latency_ms": 4200,
        "attempts": 1,
    }
    defaults.update(overrides)
    return AgentRunResult(**defaults)
