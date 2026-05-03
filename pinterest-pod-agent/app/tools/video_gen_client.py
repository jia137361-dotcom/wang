"""Video generation client stub.

Replace with a real provider (Runway, Pika, etc.) when needed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GeneratedVideo:
    video_url: str = ""
    local_path: str = ""
    duration_seconds: int = 0
    provider: str = "not_configured"


class VideoGenerationNotConfigured(RuntimeError):
    """Raised when video generation is requested but no provider is configured."""


class VideoGenClient:
    """Stub client that raises when called; replace with real implementation."""

    async def generate_video(
        self,
        prompt: str,
        image_url: str | None = None,
        duration_seconds: int = 5,
        aspect_ratio: str = "9:16",
    ) -> GeneratedVideo:
        raise VideoGenerationNotConfigured(
            "Video generation is not configured. Set VIDEO_PROVIDER_API_KEY in .env "
            "and replace app/tools/video_gen_client.py with a real provider client."
        )

    def generate_placeholder(self, prompt: str) -> dict[str, str]:
        return {"status": "not_configured", "prompt": prompt}
