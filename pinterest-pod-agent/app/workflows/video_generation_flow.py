from __future__ import annotations

from dataclasses import dataclass

from app.tools.video_gen_client import GeneratedVideo, VideoGenClient


@dataclass(frozen=True)
class VideoGenerationInput:
    prompt: str
    image_url: str | None = None
    duration_seconds: int = 5
    aspect_ratio: str = "9:16"


async def generate_marketing_video(payload: VideoGenerationInput) -> GeneratedVideo:
    """自动生视频入口；具体供应商调用留给 VideoGenClient 实现。"""
    client = VideoGenClient()
    return await client.generate_video(
        prompt=payload.prompt,
        image_url=payload.image_url,
        duration_seconds=payload.duration_seconds,
        aspect_ratio=payload.aspect_ratio,
    )
