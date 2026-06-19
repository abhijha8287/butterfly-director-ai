from app.agents.base.agent_result import AgentRunResult
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
