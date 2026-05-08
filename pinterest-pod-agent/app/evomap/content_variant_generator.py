"""content_variant_generator.py --- multi-candidate generation with dedup gate.

ContentVariantGenerator calls PromptEvolver for 8 candidate variants, runs
each through ContentDeduper against historical PinPerformance records and
within-batch peers, and returns the first accepted candidate.  If all fail
it triggers one retry round; if that also fails it returns a failure reason
so the caller can mark the job as failed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evomap.content_dedup import ContentDeduper
from app.evomap.prompt_evolve import PromptContext, PromptEvolver
from app.models.pin_performance import PinPerformance


@dataclass
class VariantResult:
    """Outcome of a single candidate selection round."""

    accepted: bool
    title: str = ""
    description: str = ""
    keywords: str = "[]"
    tagged_topics: str = "[]"
    angle: str = ""
    style_variant: str = ""
    title_hash: str = ""
    description_hash: str = ""
    content_hash: str = ""
    content_batch_id: str = ""
    reason: str = ""
    similarity: float = 0.0
    # per-candidate trace data for debugging
    candidate_trace: list[dict[str, Any]] = field(default_factory=list)


class ContentVariantGenerator:
    """Produces and deduplicates Pinterest content variants.

    Coordinates PromptEvolver (generation), ContentDeduper (similarity
    checks), and PinPerformance (historical lookup) so that each publish
    job receives a unique-enough title and description.
    """

    def __init__(
        self,
        db: Session,
        *,
        dedup_window_days: int = 30,
        max_retry_rounds: int = 1,
    ) -> None:
        self.db = db
        self.dedup = ContentDeduper()
        self.dedup_window_days = dedup_window_days
        self.max_retry_rounds = max_retry_rounds

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def select_best_candidate(
        self,
        context: PromptContext,
        *,
        account_id: str,
        evolver: PromptEvolver | None = None,
        content_batch_id: str | None = None,
    ) -> VariantResult:
        """Generate candidates and return the first that passes all dedup gates.

        Returns ``VariantResult(accepted=False, reason=...)`` when every
        candidate (including one retry round) fails dedup.
        """
        evolver = evolver or PromptEvolver(db=self.db)
        batch_id = content_batch_id or uuid.uuid4().hex[:12]

        history = self._load_history(account_id, context)
        batch_peers: list[dict[str, str]] = []
        all_traces: list[dict[str, Any]] = []

        for round_idx in range(self.max_retry_rounds + 1):
            candidates = evolver.generate_multi_candidates(context)
            if not candidates:
                return VariantResult(
                    accepted=False,
                    reason="LLM returned no candidates; check model availability",
                    candidate_trace=all_traces,
                )

            # within-batch dedup
            candidates = self.dedup.batch_dedup(candidates)
            if not candidates:
                if round_idx < self.max_retry_rounds:
                    continue
                return VariantResult(
                    accepted=False,
                    reason="All candidates were duplicates within the batch",
                    candidate_trace=all_traces,
                )

            for candidate in candidates:
                round_trace = dict(candidate)
                title = candidate["title"]
                description = candidate["description"]

                # 1) batch peer check
                peer_rejected, peer_reason = self._check_batch_peers(
                    title, description, batch_peers
                )
                if peer_rejected:
                    round_trace["rejected_by"] = "batch_peer"
                    round_trace["reject_reason"] = peer_reason
                    all_traces.append(round_trace)
                    continue

                # 2) historical check
                hist_rejected, hist_reason = self.dedup.check_against_history(
                    title=title, description=description, history=history
                )
                if hist_rejected:
                    round_trace["rejected_by"] = "history"
                    round_trace["reject_reason"] = hist_reason
                    all_traces.append(round_trace)
                    continue

                # accepted
                title_hash = self.dedup.stable_hash(title)
                desc_hash = self.dedup.stable_hash(description)
                content_hash = self.dedup.stable_hash(f"{title}|{description}")

                batch_peers.append({"title": title, "description": description})

                return VariantResult(
                    accepted=True,
                    title=title,
                    description=description,
                    keywords=candidate.get("keywords", "[]"),
                    tagged_topics=candidate.get("tagged_topics", "[]"),
                    angle=candidate.get("angle", ""),
                    style_variant=candidate.get("style_variant", ""),
                    title_hash=title_hash,
                    description_hash=desc_hash,
                    content_hash=content_hash,
                    content_batch_id=batch_id,
                    reason="accepted",
                    candidate_trace=all_traces,
                )

            # all candidates in this round rejected; loop to retry or fall through
            all_traces.append(
                {"round": round_idx, "candidates_checked": len(candidates)}
            )

        return VariantResult(
            accepted=False,
            reason=(
                "All candidates failed dedup after retries. "
                "Consider broadening niche or angle variety."
            ),
            candidate_trace=all_traces,
        )

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _load_history(
        self, account_id: str, context: PromptContext
    ) -> list[dict[str, Any]]:
        cutoff = datetime.now(UTC) - timedelta(days=self.dedup_window_days)
        rows = self.db.scalars(
            select(PinPerformance)
            .where(
                PinPerformance.account_id == account_id,
                PinPerformance.niche == context.niche,
                PinPerformance.product_type == context.product_type,
                PinPerformance.published_at >= cutoff,
            )
            .order_by(PinPerformance.published_at.desc())
            .limit(60)
        ).all()
        return [
            {
                "title": r.title,
                "description": r.description,
                "pinterest_pin_id": r.pinterest_pin_id or "",
                "published_at": r.published_at.isoformat() if r.published_at else "",
            }
            for r in rows
        ]

    @staticmethod
    def _check_batch_peers(
        title: str,
        description: str,
        peers: list[dict[str, str]],
    ) -> tuple[bool, str]:
        dedup = ContentDeduper()
        for i, peer in enumerate(peers):
            if dedup.title_is_duplicate(title, peer.get("title", "")):
                sim = dedup.title_similarity(title, peer["title"])
                return True, f"Duplicate title vs batch peer {i} (sim={sim:.3f})"
            if dedup.description_is_duplicate(description, peer.get("description", "")):
                sim = dedup.description_similarity(description, peer["description"])
                return True, f"Duplicate description vs batch peer {i} (sim={sim:.3f})"
        return False, ""
