"""Tests for ContentDeduper --- exact-match, near-duplicate, and safe-variant checks."""

import pytest

from app.evomap.content_dedup import ContentDeduper, TITLE_SIMILARITY_THRESHOLD


@pytest.fixture
def deduper() -> ContentDeduper:
    return ContentDeduper()


# ---------------------------------------------------------------------------
# normalisation
# ---------------------------------------------------------------------------


class TestNormalizeText:
    def test_lower_case_and_strip(self, deduper: ContentDeduper) -> None:
        assert deduper.normalize_text("  Custom Pet Gift Ideas  ") == "custom pet gift ideas"

    def test_removes_punctuation(self, deduper: ContentDeduper) -> None:
        result = deduper.normalize_text("Best Gift! For Pet Lovers? Yes.")
        # punctuation stripped, stop-words removed
        assert "best" in result
        assert "gift" in result
        assert "pet" in result
        assert "lovers" in result
        assert "!" not in result
        assert "?" not in result

    def test_removes_stop_words(self, deduper: ContentDeduper) -> None:
        result = deduper.normalize_text("the best gift for a pet lover")
        assert "the" not in result.split()
        assert "for" not in result.split()
        assert "a" not in result.split()


# ---------------------------------------------------------------------------
# hashing
# ---------------------------------------------------------------------------


class TestStableHash:
    def test_same_text_same_hash(self, deduper: ContentDeduper) -> None:
        assert deduper.stable_hash("Custom Pet Gift") == deduper.stable_hash("Custom Pet Gift")

    def test_different_text_different_hash(self, deduper: ContentDeduper) -> None:
        assert deduper.stable_hash("Custom Pet Gift") != deduper.stable_hash("Dog Mom Shirt")


# ---------------------------------------------------------------------------
# title similarity (character 3-grams)
# ---------------------------------------------------------------------------


class TestTitleSimilarity:
    def test_exact_match_is_one(self, deduper: ContentDeduper) -> None:
        s = deduper.title_similarity("Custom Pet Gift Ideas for Pet Lovers",
                                     "Custom Pet Gift Ideas for Pet Lovers")
        assert s == 1.0

    def test_completely_different_is_low(self, deduper: ContentDeduper) -> None:
        s = deduper.title_similarity("Dog Mom Shirt Design", "Budget Kitchen Gadgets")
        assert s < 0.3

    def test_near_duplicate_is_high(self, deduper: ContentDeduper) -> None:
        s = deduper.title_similarity(
            "Custom Pet Gift Ideas for Pet Lovers",
            "Custom Pet Gift Ideas for Dog Lovers",
        )
        # only one word changed, should be very high
        assert s > 0.7


# ---------------------------------------------------------------------------
# title_is_duplicate
# ---------------------------------------------------------------------------


class TestTitleIsDuplicate:
    def test_exact_match_rejected(self, deduper: ContentDeduper) -> None:
        assert deduper.title_is_duplicate(
            "Custom Pet Gift Ideas for Pet Lovers",
            "Custom Pet Gift Ideas for Pet Lovers",
        ) is True

    def test_minor_rewrite_rejected(self, deduper: ContentDeduper) -> None:
        """A lightly rewritten title should still be flagged as duplicate."""
        sim = deduper.title_similarity(
            "Custom Pet Gift Ideas for Pet Lovers",
            "Custom Pet Gift Ideas for Dog Lovers",
        )
        # With one word changed, similarity must be above threshold
        assert sim >= TITLE_SIMILARITY_THRESHOLD, f"Expected sim >= {TITLE_SIMILARITY_THRESHOLD}, got {sim}"
        rejected = deduper.title_is_duplicate(
            "Custom Pet Gift Ideas for Pet Lovers",
            "Custom Pet Gift Ideas for Dog Lovers",
        )
        assert rejected is True

    def test_different_angle_title_passes(self, deduper: ContentDeduper) -> None:
        """Completely different niche angles should pass dedup."""
        rejected = deduper.title_is_duplicate(
            "10 Cute Pet Memorial Gifts That Help With Grief",
            "Best Budget Kitchen Hacks for Small Apartments",
        )
        assert rejected is False

    def test_same_hash_rejected(self, deduper: ContentDeduper) -> None:
        assert deduper.title_is_duplicate("abc", "abc") is True


# ---------------------------------------------------------------------------
# description similarity
# ---------------------------------------------------------------------------


class TestDescriptionSimilarity:
    def test_same_opening_rejected(self, deduper: ContentDeduper) -> None:
        desc_a = (
            "Looking for the perfect gift for a dog lover? "
            "This custom pet portrait poster makes a thoughtful present "
            "for birthdays, holidays, or just because."
        )
        desc_b = (
            "Looking for the perfect gift for a cat lover? "
            "This custom pet portrait poster makes a thoughtful present "
            "for birthdays, holidays, or just because."
        )
        assert deduper.description_is_duplicate(desc_a, desc_b) is True

    def test_different_structure_passes(self, deduper: ContentDeduper) -> None:
        desc_a = "Looking for the perfect gift for a dog lover? This custom poster is perfect."
        desc_b = "Transform your kitchen with these budget-friendly storage solutions. "
        desc_b += "Each organizer is designed to maximize small spaces without "
        desc_b += "sacrificing style."
        assert deduper.description_is_duplicate(desc_a, desc_b) is False


# ---------------------------------------------------------------------------
# check_against_history
# ---------------------------------------------------------------------------


class TestCheckAgainstHistory:
    def test_empty_history_passes(self, deduper: ContentDeduper) -> None:
        rejected, reason = deduper.check_against_history(
            title="Unique Title Here",
            description="A unique description.",
            history=[],
        )
        assert rejected is False
        assert reason == ""

    def test_duplicate_title_in_history_rejected(self, deduper: ContentDeduper) -> None:
        history = [
            {"title": "Custom Pet Gift Ideas for Pet Lovers", "description": "Some desc."}
        ]
        rejected, reason = deduper.check_against_history(
            title="Custom Pet Gift Ideas for Pet Lovers",
            description="A totally different description that shouldn't trigger.",
            history=history,
        )
        assert rejected is True
        assert "title_similarity" in reason


# ---------------------------------------------------------------------------
# batch_dedup
# ---------------------------------------------------------------------------


class TestBatchDedup:
    def test_exact_duplicates_removed(self, deduper: ContentDeduper) -> None:
        candidates = [
            {"title": "A", "description": "desc A"},
            {"title": "A", "description": "desc A"},  # exact dup
            {"title": "B", "description": "desc B"},
        ]
        kept = deduper.batch_dedup(candidates)
        assert len(kept) == 2

    def test_all_unique_kept(self, deduper: ContentDeduper) -> None:
        candidates = [
            {"title": "Unique Title One", "description": "Description alpha."},
            {"title": "Different Title Two", "description": "Description beta."},
        ]
        kept = deduper.batch_dedup(candidates)
        assert len(kept) == 2

    def test_near_duplicate_title_removed(self, deduper: ContentDeduper) -> None:
        candidates = [
            {"title": "Custom Pet Gift Ideas for Pet Lovers", "description": "desc A"},
            {"title": "Custom Pet Gift Ideas for Dog Lovers", "description": "desc B"},
        ]
        sim = deduper.title_similarity(
            "Custom Pet Gift Ideas for Pet Lovers",
            "Custom Pet Gift Ideas for Dog Lovers",
        )
        kept = deduper.batch_dedup(candidates)
        assert sim >= TITLE_SIMILARITY_THRESHOLD, f"Expected sim >= {TITLE_SIMILARITY_THRESHOLD}, got {sim}"
        assert len(kept) == 1
