"""Tests for ContentVariantGenerator --- batch peer dedup and candidate selection."""

import pytest

from app.evomap.content_variant_generator import ContentVariantGenerator, VariantResult


# Unit tests that don't need a DB session: internal helpers.
class TestCheckBatchPeers:
    def test_empty_peers_passes(self) -> None:
        rejected, reason = ContentVariantGenerator._check_batch_peers(
            "Some Title", "Some Description", []
        )
        assert rejected is False
        assert reason == ""

    def test_duplicate_title_rejected(self) -> None:
        peers = [{"title": "Custom Pet Gift Ideas", "description": "A unique desc."}]
        rejected, reason = ContentVariantGenerator._check_batch_peers(
            "Custom Pet Gift Ideas", "Another unique desc.", peers
        )
        assert rejected is True
        assert "title" in reason.lower()

    def test_duplicate_description_rejected(self) -> None:
        # Two descriptions that share most of their word 2-grams.
        desc_a = (
            "This custom pet portrait makes the perfect gift for dog lovers. "
            "Each print is made to order with premium materials and ships free."
        )
        desc_b = (
            "This custom pet portrait makes the perfect gift for cat lovers. "
            "Each print is made to order with premium materials and ships free."
        )
        peers = [{"title": "Unique Title", "description": desc_a}]
        rejected, reason = ContentVariantGenerator._check_batch_peers(
            "Another Unique Title",
            desc_b,
            peers,
        )
        assert rejected is True

    def test_different_content_passes(self) -> None:
        peers = [{"title": "Pet Gift Ideas", "description": "Custom pet portrait gifts."}]
        rejected, reason = ContentVariantGenerator._check_batch_peers(
            "Kitchen Hacks 2026",
            "Best budget kitchen storage solutions for small apartments.",
            peers,
        )
        assert rejected is False


class TestVariantResult:
    def test_rejected_variant_has_reason(self) -> None:
        result = VariantResult(
            accepted=False,
            reason="All candidates failed dedup",
            candidate_trace=[
                {"title": "dup1", "rejected_by": "history", "reject_reason": "sim=0.85"}
            ],
        )
        assert result.accepted is False
        assert len(result.candidate_trace) == 1
        assert result.candidate_trace[0]["rejected_by"] == "history"

    def test_accepted_variant_has_hashes(self) -> None:
        result = VariantResult(
            accepted=True,
            title="Best Pet Gift",
            description="A unique description.",
            title_hash="abc123",
            description_hash="def456",
            content_hash="789abc",
            content_batch_id="batch001",
            angle="gift_idea",
        )
        assert result.accepted is True
        assert result.title_hash == "abc123"
        assert result.content_batch_id == "batch001"
        assert result.angle == "gift_idea"
