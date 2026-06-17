from __future__ import annotations

import asyncio
import json
import time
import uuid

import websockets

from app.config.logging import get_logger
from app.config.settings import Settings
from app.core.exceptions import ProviderUnavailableError
from app.integrations.providers.base import (
    VoiceGenerationProvider,
    VoiceGenerationRequest,
    VoiceGenerationResult,
)

logger = get_logger(__name__)

_WS_PATH = "/api-ws/v1/inference/"


class DashScopeTTSProvider(VoiceGenerationProvider):
    """Real DashScope CosyVoice TTS provider. CosyVoice has no synchronous REST API -
    only WebSocket (run-task / continue-task / finish-task protocol).

    Verified against https://www.alibabacloud.com/help/en/model-studio/cosyvoice-websocket-api
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._ws_url = settings.dashscope_ws_base_url.rstrip("/") + _WS_PATH
        self._api_key = settings.dashscope_api_key

    async def synthesize(self, request: VoiceGenerationRequest) -> VoiceGenerationResult:
        if not self._api_key:
            raise ProviderUnavailableError("DASHSCOPE_API_KEY is not configured")

        task_id = str(uuid.uuid4())
        audio_chunks: list[bytes] = []
        deadline = time.monotonic() + self._settings.provider_poll_timeout_seconds
        final_event: dict = {}

        try:
            async with websockets.connect(
                self._ws_url,
                additional_headers={"Authorization": f"bearer {self._api_key}"},
                max_size=None,
            ) as ws:
                await ws.send(
                    json.dumps(
                        {
                            "header": {
                                "action": "run-task",
                                "task_id": task_id,
                                "streaming": "duplex",
                            },
                            "payload": {
                                "task_group": "audio",
                                "task": "tts",
                                "function": "SpeechSynthesizer",
                                "model": self._settings.cosyvoice_model,
                                "parameters": {
                                    "text_type": "PlainText",
                                    "voice": request.voice or self._settings.cosyvoice_default_voice,
                                    "format": request.audio_format,
                                },
                                "input": {},
                            },
                        }
                    )
                )

                started = False
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ProviderUnavailableError(f"CosyVoice task {task_id} timed out")

                    message = await asyncio.wait_for(ws.recv(), timeout=remaining)

                    if isinstance(message, bytes):
                        audio_chunks.append(message)
                        continue

                    event = json.loads(message)
                    event_name = event.get("header", {}).get("event")

                    if event_name == "task-started" and not started:
                        started = True
                        await ws.send(
                            json.dumps(
                                {
                                    "header": {
                                        "action": "continue-task",
                                        "task_id": task_id,
                                        "streaming": "duplex",
                                    },
                                    "payload": {"input": {"text": request.text}},
                                }
                            )
                        )
                        await ws.send(
                            json.dumps(
                                {
                                    "header": {
                                        "action": "finish-task",
                                        "task_id": task_id,
                                        "streaming": "duplex",
                                    },
                                    "payload": {"input": {}},
                                }
                            )
                        )
                    elif event_name == "task-finished":
                        final_event = event
                        break
                    elif event_name == "task-failed":
                        raise ProviderUnavailableError(
                            f"CosyVoice task {task_id} failed: "
                            f"{event['header'].get('error_message')}",
                            details={"raw_event": event},
                        )
        except (OSError, asyncio.TimeoutError, websockets.exceptions.WebSocketException) as exc:
            raise ProviderUnavailableError(f"CosyVoice WebSocket error: {exc}") from exc

        logger.info("dashscope_tts_task_succeeded", task_id=task_id, audio_chunks=len(audio_chunks))

        return VoiceGenerationResult(
            audio_bytes=b"".join(audio_chunks),
            audio_format=request.audio_format,
            provider="dashscope",
            raw_response=final_event,
        )
