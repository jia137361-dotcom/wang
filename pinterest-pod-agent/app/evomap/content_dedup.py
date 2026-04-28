"""content_dedup.py --- candidate-level deduplication for batch Pinterest content.

Provides ContentDeduper: stateless normalisation, hashing, and n-gram Jaccard
similarity scoring so that the variant generator can reject near-duplicate
titles and descriptions within a batch or against historical PinPerformance.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

# Common English stop-words filtered during normalisation so that small
# connective words don't inflate similarity scores.
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "can", "shall", "you", "your",
        "yours", "we", "our", "ours", "it", "its", "this", "that", "these",
        "those", "get", "got", "just", "every", "each", "all", "more", "most",
        "very", "really", "so", "such", "too", "also", "not", "no", "nor",
        "only", "own", "same", "into", "up", "out", "about", "over", "under",
        "then", "than", "now", "here", "there", "when", "where", "why", "how",
    }
)

# Title similarity threshold: reject when Jaccard >= 0.72.
TITLE_SIMILARITY_THRESHOLD: float = 0.72
# Description similarity threshold: reject when Jaccard >= 0.82.
DESC_SIMILARITY_THRESHOLD: float = 0.82


class ContentDeduper:
    """Stateless dedup engine for Pinterest title / description candidates.

    Uses character 3-grams for short text (titles) and word 2-grams for
    longer text (descriptions) so that near-duplicates are caught without
    needing an embedding model or vector store.
    """

    @staticmethod
    def normalize_text(text: str) -> str:
        """Lower-case, strip punctuation, collapse whitespace, drop stop-words."""
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        tokens = text.split()
        tokens = [t for t in tokens if t not in _STOP_WORDS]
        return " ".join(tokens)

    @staticmethod
    def stable_hash(text: str) -> str:
        """Return a hex digest of *text* for exact-match dedup."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def char_ngrams(text: str, n: int = 3) -> set[str]:
        """Sliding character n-grams (for title-level comparison)."""
        clean = re.sub(r"\s+", " ", text.strip().lower())
        if len(clean) < n:
            return {clean}
        return {clean[i : i + n] for i in range(len(clean) - n + 1)}

    @staticmethod
    def word_ngrams(text: str, n: int = 2) -> set[str]:
        """Sliding word n-grams (for description-level comparison)."""
        tokens = [t for t in re.split(r"\s+", text.strip().lower()) if t]
        if len(tokens) < n:
            return set(tokens)
        return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}

    @classmethod
    def title_similarity(cls, a: str, b: str) -> float:
        """Return Jaccard similarity of character 3-grams for two titles."""
        return cls._jaccard(cls.char_ngrams(a, 3), cls.char_ngrams(b, 3))

    @classmethod
    def description_similarity(cls, a: str, b: str) -> float:
        """Return Jaccard similarity of word 2-grams for two descriptions."""
        return cls._jaccard(cls.word_ngrams(a, 2), cls.word_ngrams(b, 2))

    def title_is_duplicate(self, candidate: str, existing: str) -> bool:
        """Return True when *candidate* is too similar to *existing*."""
        if self.stable_hash(candidate) == self.stable_hash(existing):
            return True
        return self.title_similarity(candidate, existing) >= TITLE_SIMILARITY_THRESHOLD

    def description_is_duplicate(self, candidate: str, existing: str) -> bool:
        if self.stable_hash(candidate) == self.stable_hash(existing):
            return True
        return self.description_similarity(candidate, existing) >= DESC_SIMILARITY_THRESHOLD

    def check_against_history(
        self,
        *,
        title: str,
        description: str,
        history: list[dict[str, Any]],
    ) -> tuple[bool, str]:
        """Check *title* / *description* against a list of historical records.

        Each record in *history* is expected to have ``title`` and
        ``description`` keys (at minimum).

        Returns ``(rejected, reason)``.
        """
        for idx, record in enumerate(history):
            existing_title = record.get("title", "")
            existing_desc = record.get("description", "")
            existing_pin_id = record.get("pinterest_pin_id", f"record_{idx}")

            if self.title_is_duplicate(title, existing_title):
                sim = self.title_similarity(title, existing_title)
                return True, (
                    f"Title too similar to existing Pin {existing_pin_id} "
                    f"(title_similarity={sim:.3f})"
                )
            if self.description_is_duplicate(description, existing_desc):
                sim = self.description_similarity(description, existing_desc)
                return True, (
                    f"Description too similar to existing Pin {existing_pin_id} "
                    f"(desc_similarity={sim:.3f})"
                )
        return False, ""

    def batch_dedup(
        self, candidates: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        """Remove candidates whose title or description duplicates another
        already in the batch (first-wins)."""
        seen_titles: list[str] = []
        seen_descs: list[str] = []
        kept: list[dict[str, str]] = []
        for candidate in candidates:
            title = candidate.get("title", "")
            desc = candidate.get("description", "")
            if any(self.title_is_duplicate(title, t) for t in seen_titles):
                continue
            if any(self.description_is_duplicate(desc, d) for d in seen_descs):
                continue
            kept.append(candidate)
            seen_titles.append(title)
            seen_descs.append(desc)
        return kept

    @staticmethod
    def _jaccard(a: set[str], b: set[str]) -> float:
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)
