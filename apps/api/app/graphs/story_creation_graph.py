from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.story_architect.agent import StoryArchitectAgent
from app.agents.story_architect.schema import StoryBible, StoryRequest


class StoryCreationState(TypedDict, total=False):
    """Graph state. Today this has exactly one node (story_architect); future
    agents (Character Architect, Decision Detector, ...) extend this same state
    and add edges after "story_architect" rather than replacing this graph.
    """

    request: StoryRequest
    story_bible: StoryBible
    model: str
    prompt_version: str
    latency_ms: int
    attempts: int
    prompt_tokens: int | None
    completion_tokens: int | None


async def story_architect_node(state: StoryCreationState) -> dict:
    agent = StoryArchitectAgent()
    result = await agent.run(state["request"])
    return {
        "story_bible": result.output,
        "model": result.model,
        "prompt_version": result.prompt_version,
        "latency_ms": result.latency_ms,
        "attempts": result.attempts,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
    }


def build_story_creation_graph() -> CompiledStateGraph:
    graph = StateGraph(StoryCreationState)
    graph.add_node("story_architect", story_architect_node)
    graph.add_edge(START, "story_architect")
    graph.add_edge("story_architect", END)
    return graph.compile()
