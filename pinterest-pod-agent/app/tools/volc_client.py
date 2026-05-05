from __future__ import annotations

import logging
import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.config import get_settings


logger = logging.getLogger(__name__)

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str

    def as_payload(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class ChatCompletionResult:
    text: str
    model: str
    request_id: str | None
    usage: dict[str, int]
    raw: dict[str, Any]


class VolcEngineError(RuntimeError):
    """Raised when the Volcengine Ark API call fails."""


class VolcClient:
    """Small async/sync wrapper around Volcengine Ark's OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.volc_api_key
        self.model = model or settings.volc_model
        self.base_url = (base_url or settings.volc_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.volc_timeout_seconds
        self.max_retries = max_retries if max_retries is not None else settings.volc_max_retries

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def chat_with_metadata(
        self,
        messages: Sequence[ChatMessage | dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        response_format: dict[str, str] | None = None,
    ) -> ChatCompletionResult:
        payload = self._build_payload(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        with httpx.Client(timeout=self.timeout_seconds) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = client.post(
                        self.chat_completions_url,
                        headers=self._headers(),
                        json=payload,
                    )
                    response.raise_for_status()
                    return self._result_from_payload(response.json(), response.headers)
                except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
                    if attempt >= self.max_retries:
                        logger.exception("Volcengine Ark chat completion failed")
                        raise VolcEngineError(self._error_detail(exc)) from exc
                    time.sleep(min(2**attempt, 8))

        raise VolcEngineError("Volcengine Ark chat completion failed without a response")

    async def achat_with_metadata(
        self,
        messages: Sequence[ChatMessage | dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        response_format: dict[str, str] | None = None,
    ) -> ChatCompletionResult:
        payload = self._build_payload(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.post(
                        self.chat_completions_url,
                        headers=self._headers(),
                        json=payload,
                    )
                    response.raise_for_status()
                    return self._result_from_payload(response.json(), response.headers)
                except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
                    if attempt >= self.max_retries:
                        logger.exception("Volcengine Ark chat completion failed")
                        raise VolcEngineError(self._error_detail(exc)) from exc
                    await asyncio.sleep(min(2**attempt, 8))

        raise VolcEngineError("Volcengine Ark chat completion failed without a response")

    def chat(
        self,
        messages: Sequence[ChatMessage | dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        response_format: dict[str, str] | None = None,
    ) -> str:
        return self.chat_with_metadata(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        ).text

    async def achat(
        self,
        messages: Sequence[ChatMessage | dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        response_format: dict[str, str] | None = None,
    ) -> str:
        result = await self.achat_with_metadata(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        return result.text

    def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str = "You are a rigorous Pinterest POD marketing copy expert.",
        temperature: float = 0.7,
        max_tokens: int = 1200,
    ) -> str:
        return self.chat(
            [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=prompt),
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def agenerate_text(
        self,
        prompt: str,
        *,
        system_prompt: str = "You are a rigorous Pinterest POD marketing copy expert.",
        temperature: float = 0.7,
        max_tokens: int = 1200,
    ) -> str:
        return await self.achat(
            [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=prompt),
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        messages: Sequence[ChatMessage | dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        response_format: dict[str, str] | None,
    ) -> dict[str, Any]:
        normalized_messages = [
            message.as_payload() if isinstance(message, ChatMessage) else message
            for message in messages
        ]
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": normalized_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format
        return payload

    def _result_from_payload(self, payload: dict[str, Any], headers: httpx.Headers) -> ChatCompletionResult:
        return ChatCompletionResult(
            text=self._extract_text(payload),
            model=payload.get("model") or self.model,
            request_id=payload.get("id") or headers.get("x-request-id"),
            usage=self._extract_usage(payload),
            raw=payload,
        )

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        message = payload["choices"][0]["message"]
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            text = "\n".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") in {"text", "output_text"}
            ).strip()
            if text:
                return text
        # fallback: reasoning models put final answer in reasoning_content
        reasoning = message.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning.strip():
            return reasoning.strip()
        if isinstance(content, str):
            return content.strip()
        raise TypeError("Unsupported response content format")

    @staticmethod
    def _extract_usage(payload: dict[str, Any]) -> dict[str, int]:
        usage = payload.get("usage") or {}
        return {
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }

    @staticmethod
    def _error_detail(exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            try:
                detail = exc.response.json()
            except ValueError:
                detail = exc.response.text
            return f"HTTP {exc.response.status_code}: {detail}"
        return str(exc)
