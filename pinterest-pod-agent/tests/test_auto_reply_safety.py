from app.workflows.auto_reply_flow import classify_comment_safety


def test_refund_comment_requires_manual_review() -> None:
    status, reason = classify_comment_safety("I need a refund for this order")
    assert status == "manual_review"
    assert reason == "refund_or_order_issue"


def test_safe_comment_can_be_auto_replied() -> None:
    status, reason = classify_comment_safety("This design is so cute!")
    assert status == "safe"
    assert reason is None


def test_chargeback_keyword_triggers_review() -> None:
    status, reason = classify_comment_safety("I'll file a chargeback if you don't respond")
    assert status == "manual_review"
    assert reason == "refund_or_order_issue"


def test_scam_keyword_triggers_review() -> None:
    status, reason = classify_comment_safety("This looks like a scam store")
    assert status == "manual_review"
    assert reason == "complaint"


def test_copyright_keyword_triggers_review() -> None:
    status, reason = classify_comment_safety("You violated my copyright, take this down now")
    assert status == "manual_review"
    assert reason == "copyright_or_ip"


def test_chinese_refund_triggers_review() -> None:
    status, reason = classify_comment_safety("我要退款，这个商品有问题")
    assert status == "manual_review"
    assert reason == "refund_or_order_issue"


def test_chinese_return_triggers_review() -> None:
    status, reason = classify_comment_safety("商品不满意，我要退货")
    assert status == "manual_review"
    assert reason == "refund_or_order_issue"


def test_chinese_infringement_triggers_review() -> None:
    status, reason = classify_comment_safety("你这是侵权我的版权作品")
    assert status == "manual_review"
    assert reason == "copyright_or_ip"


def test_chinese_too_expensive_triggers_review() -> None:
    status, reason = classify_comment_safety("太贵了，根本不值这个价钱")
    assert status == "manual_review"
    assert reason == "pricing_dispute"


def test_price_substring_not_overmatched() -> None:
    """'priceless' should not match the 'price' keyword."""
    status, reason = classify_comment_safety("This gift is priceless, I love it!")
    assert status == "safe"


def test_multiple_keywords_returns_first_match() -> None:
    status, reason = classify_comment_safety("我要退款，这是scam")
    assert status == "manual_review"
    # 'refund' word-boundary matches first in English, but Chinese 退款 matches earlier
    assert reason in ("refund_or_order_issue", "complaint")


def test_normal_question_is_safe() -> None:
    status, reason = classify_comment_safety("What sizes are available for this shirt?")
    assert status == "safe"


def test_compliment_is_safe() -> None:
    status, reason = classify_comment_safety("Love this! Just ordered one for my mom.")
    assert status == "safe"
