from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.character_architect.agent import CharacterArchitectAgent
from app.agents.character_architect.schema import CharacterRequest, CharacterRoster
from app.agents.story_architect.agent import StoryArchitectAgent
from app.agents.story_architect.schema import StoryBible, StoryRequest


class StoryCreationState(TypedDict, total=False):
    """Graph state covering the narrative-foundation stage: Story Architect ->
    Character Architect. Each node's generation metadata is kept under its own
    key (story_* / character_*) since the two agents run separately and report
    separate latency/token/attempt counts. Future agents (Decision Detector,
    Storyboard, ...) extend this same state and add edges after
    "character_architect" rather than replacing this graph.
    """

    request: StoryRequest
    story_bible: StoryBible
    story_model: str
    story_prompt_version: str
    story_latency_ms: int
    story_attempts: int
    story_prompt_tokens: int | None
    story_completion_tokens: int | None

    character_roster: CharacterRoster
    character_model: str
    character_prompt_version: str
    character_latency_ms: int
    character_attempts: int
    character_prompt_tokens: int | None
    character_completion_tokens: int | None


async def story_architect_node(state: StoryCreationState) -> dict:
    agent = StoryArchitectAgent()
    result = await agent.run(state["request"])
    return {
        "story_bible": result.output,
        "story_model": result.model,
        "story_prompt_version": result.prompt_version,
        "story_latency_ms": result.latency_ms,
        "story_attempts": result.attempts,
        "story_prompt_tokens": result.prompt_tokens,
        "story_completion_tokens": result.completion_tokens,
    }


async def character_architect_node(state: StoryCreationState) -> dict:
    agent = CharacterArchitectAgent()
    result = await agent.run(CharacterRequest(story_bible=state["story_bible"]))
    return {
        "character_roster": result.output,
        "character_model": result.model,
        "character_prompt_version": result.prompt_version,
        "character_latency_ms": result.latency_ms,
        "character_attempts": result.attempts,
        "character_prompt_tokens": result.prompt_tokens,
        "character_completion_tokens": result.completion_tokens,
    }


def build_story_creation_graph() -> CompiledStateGraph:
    graph = StateGraph(StoryCreationState)
    graph.add_node("story_architect", story_architect_node)
    graph.add_node("character_architect", character_architect_node)
    graph.add_edge(START, "story_architect")
    graph.add_edge("story_architect", "character_architect")
    graph.add_edge("character_architect", END)
    return graph.compile()
