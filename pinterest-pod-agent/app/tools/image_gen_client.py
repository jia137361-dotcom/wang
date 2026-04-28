from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

try:
    import fal_client
except ImportError:  # pragma: no cover - depends on optional runtime package.
    fal_client = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)

BASE_IMAGE_ENDPOINT = "fal-ai/flux/schnell"
UPSCALE_ENDPOINT = "fal-ai/esrgan"
DEFAULT_UPSCALE_SCALE = 4
DEFAULT_TIMEOUT_SECONDS = 180.0
DEFAULT_START_TIMEOUT_SECONDS = 30.0


class ImageGenerationError(RuntimeError):
    """Raised when the Fal.ai image generation pipeline fails."""


class ImageGenClient:
    """Fal.ai client for the two-step image pipeline.

    The Fal API key is intentionally not represented in code. fal_client reads
    credentials from the runtime environment, usually FAL_KEY.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        start_timeout_seconds: float = DEFAULT_START_TIMEOUT_SECONDS,
        upscale_scale: int = DEFAULT_UPSCALE_SCALE,
        client: Any | None = None,
    ) -> None:
        if upscale_scale not in {2, 4}:
            raise ValueError("upscale_scale must be 2 or 4")

        self.timeout_seconds = timeout_seconds
        self.start_timeout_seconds = start_timeout_seconds
        self.upscale_scale = upscale_scale
        self.client = client or _build_fal_async_client(timeout_seconds)

    async def generate_high_res_image(self, prompt: str, image_size: str) -> str:
        """严格执行底图生成 -> ESRGAN 放大，返回最终高清图片 URL。"""
        prompt = prompt.strip()
        image_size = image_size.strip()
        if not prompt:
            raise ValueError("prompt is required")
        if not image_size:
            raise ValueError("image_size is required")

        try:
            # 整条流水线加总超时，避免 API 或 Celery worker 被无限挂起。
            async with asyncio.timeout(self.timeout_seconds):
                base_image_url = await self._generate_base_image(prompt, image_size)
                if not base_image_url:
                    raise ImageGenerationError("Base image generation returned an empty URL")

                final_image_url = await self._upscale_image(base_image_url)
                if not final_image_url:
                    raise ImageGenerationError("ESRGAN upscaling returned an empty URL")

                return final_image_url
        except Exception:
            logger.exception("Fal.ai high-resolution image pipeline failed")
            raise

    async def _generate_base_image(self, prompt: str, image_size: str) -> str:
        """步骤 1：使用低成本 flux/schnell 生成基础图片。"""
        try:
            result = await self.client.subscribe(
                BASE_IMAGE_ENDPOINT,
                arguments={
                    "prompt": prompt,
                    "image_size": image_size,
                    "num_images": 1,
                    "num_inference_steps": 4,
                    "enable_safety_checker": True,
                    "output_format": "png",
                },
                with_logs=True,
                start_timeout=self.start_timeout_seconds,
                client_timeout=self.timeout_seconds,
            )

            if _has_nsfw_concept(result):
                raise ImageGenerationError("Base image generation was blocked by safety checks")

            image_url = _extract_flux_image_url(result)
            if not image_url:
                raise ImageGenerationError(f"Base image generation returned no URL: {result!r}")

            logger.info("Fal.ai base image generated", extra={"endpoint": BASE_IMAGE_ENDPOINT})
            return image_url
        except Exception:
            logger.exception("Fal.ai base image generation failed")
            raise

    async def _upscale_image(self, image_url: str) -> str:
        """步骤 2：只使用基础版 ESRGAN，将第一步 URL 放大 4 倍。"""
        if not image_url:
            raise ImageGenerationError("image_url is required before ESRGAN upscaling")

        try:
            result = await self.client.subscribe(
                UPSCALE_ENDPOINT,
                arguments={
                    "image_url": image_url,
                    "scale": self.upscale_scale,
                    "model": "RealESRGAN_x4plus",
                    "output_format": "png",
                },
                with_logs=True,
                start_timeout=self.start_timeout_seconds,
                client_timeout=self.timeout_seconds,
            )

            final_url = _extract_esrgan_image_url(result)
            if not final_url:
                raise ImageGenerationError(f"ESRGAN upscaling returned no URL: {result!r}")

            logger.info("Fal.ai image upscaled", extra={"endpoint": UPSCALE_ENDPOINT})
            return final_url
        except Exception:
            logger.exception("Fal.ai ESRGAN upscaling failed")
            raise

    def generate_placeholder(self, prompt: str) -> dict[str, str]:
        """Compatibility shim for callers that still use the old placeholder."""
        return {"status": "not_configured", "prompt": prompt}


async def generate_high_res_image(prompt: str, image_size: str) -> str:
    """模块级主函数，供 API、workflow 或 Celery wrapper 调用。"""
    client = ImageGenClient()
    return await client.generate_high_res_image(prompt, image_size)


def _build_fal_async_client(timeout_seconds: float) -> Any:
    if fal_client is None:
        raise RuntimeError("fal-client is not installed. Install it with: pip install fal-client")
    return fal_client.AsyncClient(default_timeout=timeout_seconds)


def _extract_flux_image_url(result: Mapping[str, Any]) -> str:
    images = result.get("images") or []
    if not isinstance(images, list) or not images:
        return ""

    first_image = images[0]
    if not isinstance(first_image, Mapping):
        return ""

    return str(first_image.get("url") or "").strip()


def _extract_esrgan_image_url(result: Mapping[str, Any]) -> str:
    image = result.get("image") or {}
    if not isinstance(image, Mapping):
        return ""

    return str(image.get("url") or "").strip()


def _has_nsfw_concept(result: Mapping[str, Any]) -> bool:
    flags = result.get("has_nsfw_concepts") or []
    if not isinstance(flags, list):
        return False
    return any(bool(flag) for flag in flags)
