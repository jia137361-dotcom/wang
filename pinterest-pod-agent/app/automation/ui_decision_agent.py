from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any, Literal

from playwright.async_api import Locator, Page

from app.tools.volc_client import ChatMessage, VolcClient


logger = logging.getLogger(__name__)

UIDecisionAction = Literal["click", "fill", "press_escape", "wait", "stop"]

MIN_CONFIDENCE = 0.65
MAX_CONTROLS = 60
MAX_TEXT_LENGTH = 160

BLOCKED_TEXT_PATTERNS = (
    "install now",
    "allow notifications",
    "authorize",
    "pay",
    "subscribe",
    "delete",
    "remove",
    "log out",
)
SENSITIVE_INPUT_PATTERNS = (
    "password",
    "verification",
    "verify",
    "code",
    "otp",
    "captcha",
    "credit card",
    "card number",
    "cvv",
)


@dataclass(frozen=True)
class UIControl:
    target_id: str
    selector: str
    role: str
    text: str
    aria_label: str | None
    placeholder: str | None
    disabled: bool
    visible: bool
    in_dialog: bool
    tag_name: str

    @property
    def searchable_text(self) -> str:
        return " ".join(
            item
            for item in [self.text, self.aria_label or "", self.placeholder or "", self.role, self.tag_name]
            if item
        ).lower()


@dataclass(frozen=True)
class UIDecision:
    action: UIDecisionAction
    target_id: str | None = None
    value: str | None = None
    reason: str = ""
    confidence: float = 0.0


class UIDecisionError(RuntimeError):
    pass


class UIDecisionAgent:
    """LLM-backed DOM decision helper for bounded UI actions."""

    def __init__(
        self,
        *,
        volc_client: VolcClient | None = None,
        min_confidence: float = MIN_CONFIDENCE,
    ) -> None:
        self.volc_client = volc_client or VolcClient()
        self.min_confidence = min_confidence

    async def collect_controls(self, page: Page) -> list[UIControl]:
        controls: list[UIControl] = []
        candidates = page.locator(
            "button, [role='button'], a, input, textarea, select, [role='menuitem'], [role='option']"
        )
        count = min(await candidates.count(), MAX_CONTROLS)
        for index in range(count):
            locator = candidates.nth(index)
            try:
                if not await locator.is_visible(timeout=500):
                    continue
                control = await self._control_from_locator(locator, index)
                if control:
                    controls.append(control)
            except Exception:
                continue
        return controls

    async def decide(
        self,
        *,
        stage: str,
        objective: str,
        controls: list[UIControl],
    ) -> UIDecision:
        if not controls:
            return UIDecision(action="wait", reason="No visible controls were available", confidence=0.7)

        prompt = self._build_prompt(stage=stage, objective=objective, controls=controls)
        try:
            text = await self.volc_client.achat(
                [
                    ChatMessage(
                        role="system",
                        content=(
                            "You are a cautious UI automation decision engine. "
                            "Return only JSON with action, target_id, value, reason, confidence. "
                            "Never choose risky actions such as installing extensions, payment, deletion, logout, "
                            "authorization, notifications, password, verification, captcha, or account security."
                        ),
                    ),
                    ChatMessage(role="user", content=prompt),
                ],
                temperature=0.0,
                max_tokens=600,
                response_format={"type": "json_object"},
            )
            return self._parse_decision(text)
        except Exception:
            logger.exception("AI UI decision failed")
            return UIDecision(action="stop", reason="AI decision call failed", confidence=1.0)

    async def execute(self, page: Page, decision: UIDecision, controls: list[UIControl]) -> bool:
        self._validate_decision(decision, controls)
        if decision.action == "wait":
            await page.wait_for_timeout(1_000)
            return True
        if decision.action == "press_escape":
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
            return True
        if decision.action == "stop":
            return False

        control = self._find_control(decision.target_id, controls)
        locator = page.locator(control.selector).first
        if decision.action == "click":
            await locator.click()
            await page.wait_for_timeout(500)
            return True
        if decision.action == "fill":
            if decision.value is None:
                raise UIDecisionError("fill action requires value")
            await locator.fill(decision.value)
            await page.wait_for_timeout(300)
            return True
        raise UIDecisionError(f"Unsupported AI UI action: {decision.action}")

    def enforce_safety(self, decision: UIDecision, controls: list[UIControl]) -> UIDecision:
        self._validate_decision(decision, controls)
        return decision

    async def _control_from_locator(self, locator: Locator, index: int) -> UIControl | None:
        tag_name = await locator.evaluate("el => el.tagName.toLowerCase()")
        role = await locator.get_attribute("role") or tag_name
        text = (await locator.inner_text(timeout=500) if tag_name not in {"input", "textarea"} else "") or ""
        text = " ".join(text.split())[:MAX_TEXT_LENGTH]
        aria_label = await locator.get_attribute("aria-label")
        placeholder = await locator.get_attribute("placeholder")
        disabled_attr = await locator.get_attribute("disabled")
        aria_disabled = await locator.get_attribute("aria-disabled")
        disabled = disabled_attr is not None or aria_disabled == "true"
        try:
            enabled = await locator.is_enabled(timeout=500)
            disabled = disabled or not enabled
        except Exception:
            pass
        in_dialog = await locator.evaluate("el => Boolean(el.closest('[role=\"dialog\"]'))")
        selector = f"[data-ai-target='{index}']"
        await locator.evaluate("(el, value) => el.setAttribute('data-ai-target', value)", str(index))
        return UIControl(
            target_id=f"control_{index}",
            selector=selector,
            role=role,
            text=text,
            aria_label=aria_label,
            placeholder=placeholder,
            disabled=disabled,
            visible=True,
            in_dialog=bool(in_dialog),
            tag_name=tag_name,
        )

    def _build_prompt(self, *, stage: str, objective: str, controls: list[UIControl]) -> str:
        payload = {
            "stage": stage,
            "objective": objective,
            "allowed_actions": ["click", "fill", "press_escape", "wait", "stop"],
            "hard_rules": [
                "Only choose a target_id from controls.",
                "Do not click Install now, Allow notifications, Authorize, Pay, Subscribe, Delete, Remove, Log out.",
                "Do not fill passwords, verification codes, captcha, payment, or account security fields.",
                "If a pop-up blocks the publish form and no safe close button exists, choose press_escape.",
                "If uncertain, choose stop.",
            ],
            "controls": [asdict(control) for control in controls],
            "response_schema": {
                "action": "click|fill|press_escape|wait|stop",
                "target_id": "control id or null",
                "value": "fill value or null",
                "reason": "short reason",
                "confidence": "0.0 to 1.0",
            },
        }
        return json.dumps(payload, ensure_ascii=False)

    def _parse_decision(self, text: str) -> UIDecision:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise UIDecisionError(f"AI returned invalid JSON: {text}") from exc
        action = payload.get("action")
        if action not in {"click", "fill", "press_escape", "wait", "stop"}:
            raise UIDecisionError(f"AI returned invalid action: {action}")
        confidence = float(payload.get("confidence") or 0.0)
        return UIDecision(
            action=action,
            target_id=payload.get("target_id"),
            value=payload.get("value"),
            reason=str(payload.get("reason") or ""),
            confidence=confidence,
        )

    def _validate_decision(self, decision: UIDecision, controls: list[UIControl]) -> None:
        if decision.confidence < self.min_confidence:
            raise UIDecisionError(f"AI decision confidence too low: {decision.confidence}")
        if decision.action in {"wait", "press_escape", "stop"}:
            return
        control = self._find_control(decision.target_id, controls)
        if control.disabled:
            raise UIDecisionError(f"AI selected disabled control: {control.target_id}")
        text = control.searchable_text
        if any(pattern in text for pattern in BLOCKED_TEXT_PATTERNS):
            raise UIDecisionError(f"AI selected blocked control text: {text}")
        if decision.action == "fill" and any(pattern in text for pattern in SENSITIVE_INPUT_PATTERNS):
            raise UIDecisionError(f"AI selected sensitive input: {text}")

    @staticmethod
    def _find_control(target_id: str | None, controls: list[UIControl]) -> UIControl:
        if not target_id:
            raise UIDecisionError("AI action requires target_id")
        for control in controls:
            if control.target_id == target_id:
                return control
        raise UIDecisionError(f"AI selected unknown target_id: {target_id}")
