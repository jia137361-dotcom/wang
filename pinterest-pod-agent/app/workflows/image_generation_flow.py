from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from app.config import get_settings
from app.tools.image_gen_client import generate_high_res_image


@dataclass(frozen=True)
class GeneratedImageAsset:
    prompt: str
    image_size: str
    source_url: str
    local_path: str
    bytes_written: int


async def generate_image_asset(prompt: str, image_size: str) -> GeneratedImageAsset:
    """生成高清图片，并下载到本地上传目录，供 Pinterest 发布任务使用。"""
    final_url = await generate_high_res_image(prompt=prompt, image_size=image_size)
    local_path, size = await download_generated_image(final_url)
    return GeneratedImageAsset(
        prompt=prompt,
        image_size=image_size,
        source_url=final_url,
        local_path=str(local_path),
        bytes_written=size,
    )


async def download_generated_image(image_url: str) -> tuple[Path, int]:
    """下载远程图片到 upload_dir；不处理任何密钥，URL 必须由上游生成。"""
    if not image_url.strip():
        raise ValueError("image_url is required")

    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        response = await client.get(image_url)
        response.raise_for_status()
        content = response.content

    suffix = _suffix_from_url_or_content_type(
        image_url,
        response.headers.get("content-type", ""),
    )
    target = upload_dir / f"generated_{uuid4().hex}{suffix}"
    await asyncio.to_thread(target.write_bytes, content)
    return target, len(content)


def _suffix_from_url_or_content_type(image_url: str, content_type: str) -> str:
    path_suffix = Path(urlparse(image_url).path).suffix.lower()
    if path_suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return path_suffix
    if "jpeg" in content_type:
        return ".jpg"
    if "webp" in content_type:
        return ".webp"
    return ".png"
