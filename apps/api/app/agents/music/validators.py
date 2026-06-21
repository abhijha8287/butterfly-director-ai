from __future__ import annotations

from app.agents.music.schema import MusicScript, MusicShotScript
from app.core.exceptions import AgentOutputInvalidError


def validate_music_script(script: MusicScript, shots: list[MusicShotScript]) -> list[str]:
    """Hard rule: every cue's start/end shot_number must reference a real shot
    from the input, and end must not precede start - this mapping is
    load-bearing, since cues are persisted/synthesized keyed off these
    references. An empty `cues` list is structurally valid (mirrors Voice's
    zero-lines case) but only ever produces a warning, since the system
    prompt steers the model to default to scoring the whole branch.
    """
    warnings: list[str] = []
    valid_shot_numbers = {s.shot_number for s in shots}

    for cue in script.cues:
        if cue.start_shot_number not in valid_shot_numbers:
            raise AgentOutputInvalidError(
                f"MusicCue references unknown start_shot_number {cue.start_shot_number}",
                details={"valid_shot_numbers": sorted(valid_shot_numbers)},
            )
        if cue.end_shot_number not in valid_shot_numbers:
            raise AgentOutputInvalidError(
                f"MusicCue references unknown end_shot_number {cue.end_shot_number}",
                details={"valid_shot_numbers": sorted(valid_shot_numbers)},
            )
        if cue.end_shot_number < cue.start_shot_number:
            raise AgentOutputInvalidError(
                f"MusicCue's end_shot_number ({cue.end_shot_number}) precedes its "
                f"start_shot_number ({cue.start_shot_number})"
            )
        if not cue.generation_prompt.strip():
            warnings.append(
                f"Shots {cue.start_shot_number}-{cue.end_shot_number}: cue has a "
                "blank generation_prompt"
            )

    if not script.cues:
        warnings.append(
            "No music cues were extracted for this branch - it will have no score"
        )

    return warnings
