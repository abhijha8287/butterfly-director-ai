from __future__ import annotations

import asyncio
from pathlib import Path

from app.config.settings import Settings, get_settings
from app.core.exceptions import ProviderUnavailableError
from app.integrations.providers.base import (
    EditorComposeProvider,
    EditorComposeRequest,
    EditorComposeResult,
)


class FfmpegEditorComposeProvider(EditorComposeProvider):
    """Shells out to a local ffmpeg binary - the only real implementation of
    EditorComposeProvider, since ARCHITECTURE.md specifies ffmpeg composition
    specifically rather than naming swappable vendors (unlike Wan/CosyVoice/
    HappyHorse). Builds one filter_complex graph per call:

      - every shot video is scaled/padded to a common 1280x720@30fps surface
        and concatenated (video-only - shots' own audio, if any, is dropped,
        since dialogue/music are mixed in separately as their own layers)
      - every audio track is time-shifted into place with `adelay` at its
        precomputed start_offset_ms, then combined with `amix`
      - video and (if any) mixed audio are muxed into one output file

    ffmpeg can read both local file paths and http(s) URLs directly as `-i`
    inputs, so shot videos (Wan's presigned video_url, never downloaded - see
    README's Known Limitations) and voice/music tracks (local files under
    MEDIA_ROOT) are passed through unchanged, with no separate download step.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def compose(self, request: EditorComposeRequest) -> EditorComposeResult:
        if not request.shot_video_urls:
            raise ProviderUnavailableError("EditorComposeRequest has no shot videos to assemble")

        await asyncio.to_thread(
            lambda: Path(request.output_path).parent.mkdir(parents=True, exist_ok=True)
        )

        args = self._build_ffmpeg_args(request)
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise ProviderUnavailableError(
                f"ffmpeg exited with code {process.returncode}: "
                f"{stderr.decode(errors='replace')[-2000:]}"
            )

        duration = await self._probe_duration(request.output_path)
        return EditorComposeResult(
            output_path=request.output_path,
            duration_seconds=duration,
            provider="ffmpeg",
        )

    def _build_ffmpeg_args(self, request: EditorComposeRequest) -> list[str]:
        video_inputs = request.shot_video_urls
        audio_inputs = request.audio_tracks

        args = [self._settings.ffmpeg_binary, "-y"]
        for url in video_inputs:
            args += ["-i", url]
        for track in audio_inputs:
            args += ["-i", track.source]

        filter_parts: list[str] = []
        scaled_labels: list[str] = []
        for i in range(len(video_inputs)):
            label = f"v{i}"
            filter_parts.append(f"[{i}:v]scale=1280:720,setsar=1,fps=30[{label}]")
            scaled_labels.append(f"[{label}]")
        filter_parts.append(
            f"{''.join(scaled_labels)}concat=n={len(video_inputs)}:v=1:a=0[outv]"
        )

        map_args = ["-map", "[outv]"]
        if audio_inputs:
            audio_labels: list[str] = []
            for i, track in enumerate(audio_inputs):
                input_index = len(video_inputs) + i
                label = f"a{i}"
                filter_parts.append(
                    f"[{input_index}:a]adelay={track.start_offset_ms}:all=1[{label}]"
                )
                audio_labels.append(f"[{label}]")
            filter_parts.append(
                f"{''.join(audio_labels)}amix=inputs={len(audio_inputs)}:"
                "dropout_transition=0:normalize=0[outa]"
            )
            map_args += ["-map", "[outa]"]

        args += ["-filter_complex", ";".join(filter_parts)]
        args += map_args
        args += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
        if audio_inputs:
            args += ["-c:a", "aac"]
        args += ["-shortest", request.output_path]
        return args

    async def _probe_duration(self, path: str) -> float | None:
        process = await asyncio.create_subprocess_exec(
            self._settings.ffprobe_binary,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        if process.returncode != 0:
            return None
        try:
            return float(stdout.decode().strip())
        except ValueError:
            return None
