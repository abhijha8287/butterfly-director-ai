from __future__ import annotations


def strip_thinking_tags(text: str) -> str:
    """Remove thinking content from reasoning models (Qwen3, DeepSeek-R1).

    Handles three cases:
    1. Properly closed: <think>...</think>{json} → takes text after last </think>
    2. Unclosed tag:    <think>...{json}         → finds first { or [ and takes from there
    3. No tags:         {json}                   → returned as-is
    """
    last_close = text.lower().rfind("</think>")
    if last_close != -1:
        return text[last_close + len("</think>"):].strip()

    # Model opened <think> but never closed it — scan for the JSON start
    if "<think>" in text.lower():
        for i, ch in enumerate(text):
            if ch in ("{", "["):
                return text[i:].strip()

    return text.strip()
