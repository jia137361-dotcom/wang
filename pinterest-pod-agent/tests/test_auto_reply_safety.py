from app.workflows.auto_reply_flow import classify_comment_safety


def test_refund_comment_requires_manual_review() -> None:
    status, reason = classify_comment_safety("I need a refund for this order")

    assert status == "manual_review"
    assert reason == "refund_or_order_issue"


def test_safe_comment_can_be_auto_replied() -> None:
    status, reason = classify_comment_safety("This design is so cute!")

    assert status == "safe"
    assert reason is None
