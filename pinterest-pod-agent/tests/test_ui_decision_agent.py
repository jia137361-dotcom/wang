import pytest

from app.automation.ui_decision_agent import UIDecision, UIDecisionAgent, UIDecisionError, UIControl


def _control(
    *,
    target_id: str = "control_1",
    text: str = "Close",
    role: str = "button",
    disabled: bool = False,
) -> UIControl:
    return UIControl(
        target_id=target_id,
        selector="[data-ai-target='1']",
        role=role,
        text=text,
        aria_label=None,
        placeholder=None,
        disabled=disabled,
        visible=True,
        in_dialog=True,
        tag_name="button",
    )


def test_blocks_install_now_click() -> None:
    agent = UIDecisionAgent(volc_client=object())
    controls = [_control(text="Install now")]
    with pytest.raises(UIDecisionError):
        agent.enforce_safety(
            UIDecision(action="click", target_id="control_1", confidence=0.95),
            controls,
        )


def test_blocks_low_confidence() -> None:
    agent = UIDecisionAgent(volc_client=object())
    controls = [_control(text="Close")]
    with pytest.raises(UIDecisionError):
        agent.enforce_safety(
            UIDecision(action="click", target_id="control_1", confidence=0.2),
            controls,
        )


def test_allows_safe_close_click() -> None:
    agent = UIDecisionAgent(volc_client=object())
    controls = [_control(text="Close")]
    decision = agent.enforce_safety(
        UIDecision(action="click", target_id="control_1", confidence=0.95),
        controls,
    )
    assert decision.action == "click"


def test_allows_press_escape_without_target() -> None:
    agent = UIDecisionAgent(volc_client=object())
    decision = agent.enforce_safety(
        UIDecision(action="press_escape", confidence=0.95),
        [],
    )
    assert decision.action == "press_escape"
