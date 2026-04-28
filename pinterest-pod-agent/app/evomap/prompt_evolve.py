from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pin_performance import PinPerformance
from app.tools.volc_client import VolcClient


class KeywordSignal(BaseModel):
    keyword: str
    weight: float = Field(ge=0.0)
    avg_ctr: float = Field(ge=0.0)
    sample_size: int = Field(ge=0)


@dataclass(frozen=True)
class PromptContext:
    product_type: str
    niche: str
    audience: str
    season: str | None = None
    offer: str | None = None
    destination_url: str | None = None


class PromptEvolver:
    """Builds prompts by feeding historical performance back into generation."""

    def __init__(
        self,
        db: Session,
        volc_client: VolcClient | None = None,
        *,
        min_impressions: int = 100,
        min_ctr: float = 0.01,
        top_keyword_limit: int = 12,
    ) -> None:
        self.db = db
        self.volc_client = volc_client or VolcClient()
        self.min_impressions = min_impressions
        self.min_ctr = min_ctr
        self.top_keyword_limit = top_keyword_limit

    def get_keyword_signals(
        self,
        *,
        niche: str | None = None,
        product_type: str | None = None,
    ) -> list[KeywordSignal]:
        stmt = select(PinPerformance).where(PinPerformance.impressions >= self.min_impressions)
        if niche:
            stmt = stmt.where(PinPerformance.niche == niche)
        if product_type:
            stmt = stmt.where(PinPerformance.product_type == product_type)

        rows = self.db.scalars(stmt).all()
        if not rows:
            return []

        click_weighted: Counter[str] = Counter()
        impressions: Counter[str] = Counter()
        samples: Counter[str] = Counter()

        for row in rows:
            if self._row_ctr(row) < self.min_ctr:
                continue
            keyword_list = row.keywords or []
            if not keyword_list:
                keyword_list = self._keywords_from_strategy(row.strategy_snapshot)
            for keyword in keyword_list:
                normalized = self._normalize_keyword(keyword)
                if not normalized:
                    continue
                click_weighted[normalized] += row.clicks
                impressions[normalized] += row.impressions
                samples[normalized] += 1

        signals: list[KeywordSignal] = []
        for keyword, total_impressions in impressions.items():
            if total_impressions <= 0:
                continue
            avg_ctr = click_weighted[keyword] / total_impressions
            signals.append(
                KeywordSignal(
                    keyword=keyword,
                    weight=round(avg_ctr * min(samples[keyword], 10), 6),
                    avg_ctr=round(avg_ctr, 6),
                    sample_size=samples[keyword],
                )
            )

        return sorted(signals, key=lambda item: item.weight, reverse=True)[: self.top_keyword_limit]

    def build_content_prompt(self, context: PromptContext) -> str:
        signals = self.get_keyword_signals(
            niche=context.niche,
            product_type=context.product_type,
        )
        keyword_text = self._format_signals(signals)
        season_text = context.season or "no seasonal theme"
        offer_text = context.offer or "no discount specified"
        destination_text = context.destination_url or "to be filled before publish"

        return f"""
You are generating Pinterest Pin copy for a POD (print-on-demand) product.
Use the EvoMap historical feedback signals below to guide word choice.

Product type: {context.product_type}
Niche / market: {context.niche}
Target audience: {context.audience}
Season / occasion: {season_text}
Offer / promo: {offer_text}
Destination URL: {destination_text}

EvoMap high-CTR keyword signals (weighted by click feedback):
{keyword_text}

Requirements:
1. Output valid JSON only. No markdown fences, no extra commentary.
2. The JSON object must contain a "candidates" array with exactly 8 entries.
3. Each candidate is an object with these keys:
   - "title": Pinterest title, max 95 chars, attention-grabbing.
   - "description": SEO description, 350-500 chars, naturally weaving in 2-3
     high-weight keywords.
   - "keywords": array of 5-10 string keywords/tags.
   - "angle": one of "gift_idea", "room_decor", "personalized_keepsake",
     "seasonal_trend", "buyer_pain_point", "aesthetic_lifestyle",
     "budget_friendly", "problem_solver".
   - "style_variant": a short label describing the tonal / structural
     variation from the other candidates (e.g. "question-led headline",
     "numeric list hook", "emotional story opening", "bold claim + proof").

4. The 8 candidates MUST vary across these dimensions:
   - Different opening sentence structures (no shared first 5 words).
   - Different angles (at least 5 distinct angle values across the set).
   - Different keyword ordering — don't list the same top-3 keywords in
     the same order for any two candidates.
   - Avoid reusing template phrases from previous batch generations.
   - At least one candidate should be a "gift_idea" angle.
   - At least one candidate should target a specific buyer pain point.
   - At least one candidate should use a seasonal or occasion-driven hook.

5. All titles and descriptions must be in English.
""".strip()

    def build_visual_prompt(self, context: PromptContext) -> str:
        signals = self.get_keyword_signals(
            niche=context.niche,
            product_type=context.product_type,
        )
        keyword_text = self._format_signals(signals)

        return f"""
You are generating image-generation prompts for a POD (print-on-demand) product.
Translate the high-CTR keyword signals below into visual direction.

Product type: {context.product_type}
Niche / market: {context.niche}
Target audience: {context.audience}
EvoMap keyword signals:
{keyword_text}

Output:
1. 3 English image-generation prompts suitable for Pinterest vertical format.
2. For each prompt, describe composition, main subject, colour palette,
   typography style, and the best POD product carrier (poster, mug, t-shirt, etc.).
3. Avoid trademarked characters, celebrity likeness, copyrighted mascots,
   and misleading claims.
""".strip()

    def generate_content_brief(self, context: PromptContext) -> str:
        prompt = self.build_content_prompt(context)
        return self.volc_client.generate_text(
            prompt,
            system_prompt="你是 Pinterest POD 增长专家，会把历史点击反馈转化为可执行文案策略。",
            temperature=0.65,
            max_tokens=1600,
        )

    async def agenerate_content_brief(self, context: PromptContext) -> str:
        prompt = self.build_content_prompt(context)
        return await self.volc_client.agenerate_text(
            prompt,
            system_prompt="你是 Pinterest POD 增长专家，会把历史点击反馈转化为可执行文案策略。",
            temperature=0.65,
            max_tokens=1600,
        )

    def generate_strategy_advice(
        self,
        *,
        niche: str | None = None,
        product_type: str | None = None,
    ) -> str:
        signals = self.get_keyword_signals(niche=niche, product_type=product_type)
        prompt = f"""
请基于以下 Pinterest POD 历史反馈信号，给出下一轮 Prompt 优化建议。

范围：
- niche: {niche or "全部"}
- product_type: {product_type or "全部"}

关键词表现：
{self._format_signals(signals)}

请输出：
1. 应提高权重的关键词/视觉元素。
2. 应降低权重或避免的表达方式。
3. 下一轮标题、描述、图片 Prompt 的具体调整建议。
4. 需要继续采样验证的数据假设。
""".strip()
        return self.volc_client.generate_text(
            prompt,
            system_prompt="你是 EvoMap 策略分析智能体，只基于数据反馈提出 Prompt 优化建议。",
            temperature=0.4,
            max_tokens=1400,
        )

    def generate_multi_candidates(self, context: PromptContext) -> list[dict[str, str]]:
        """Generate multiple varied content candidates via LLM.

        Returns a list of dicts with keys: title, description, keywords,
        angle, style_variant.  On parse failure returns an empty list.
        """
        import json as _json

        prompt = self.build_content_prompt(context)
        raw = self.volc_client.generate_text(
            prompt,
            system_prompt=(
                "You are a rigorous Pinterest POD growth expert. "
                "Always output valid JSON matching the requested schema exactly."
            ),
            temperature=0.75,
            max_tokens=3200,
        )
        return self._parse_candidates(raw)

    async def agenerate_multi_candidates(
        self, context: PromptContext
    ) -> list[dict[str, str]]:
        import json as _json

        prompt = self.build_content_prompt(context)
        raw = await self.volc_client.agenerate_text(
            prompt,
            system_prompt=(
                "You are a rigorous Pinterest POD growth expert. "
                "Always output valid JSON matching the requested schema exactly."
            ),
            temperature=0.75,
            max_tokens=3200,
        )
        return self._parse_candidates(raw)

    @staticmethod
    def _parse_candidates(raw: str) -> list[dict[str, str]]:
        import json as _json

        raw = raw.strip()
        # strip markdown fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines)

        try:
            data = _json.loads(raw)
        except _json.JSONDecodeError:
            return []

        items = data.get("candidates") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []

        required = {"title", "description"}
        result: list[dict[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if not all(k in item for k in required):
                continue
            result.append(
                {
                    "title": str(item.get("title", "")),
                    "description": str(item.get("description", "")),
                    "keywords": _json.dumps(
                        item.get("keywords") if isinstance(item.get("keywords"), list) else []
                    ),
                    "angle": str(item.get("angle", "")),
                    "style_variant": str(item.get("style_variant", "")),
                }
            )
        return result

    @staticmethod
    def _normalize_keyword(keyword: Any) -> str:
        if not isinstance(keyword, str):
            return ""
        return " ".join(keyword.lower().strip().split())

    @staticmethod
    def _row_ctr(row: PinPerformance) -> float:
        if row.ctr > 0:
            return row.ctr
        if row.impressions <= 0:
            return 0.0
        return row.clicks / row.impressions

    @staticmethod
    def _keywords_from_strategy(strategy_snapshot: dict[str, Any] | None) -> list[str]:
        if not strategy_snapshot:
            return []
        keywords = strategy_snapshot.get("keywords") or strategy_snapshot.get("keyword_weights") or []
        if isinstance(keywords, dict):
            return list(keywords.keys())
        if isinstance(keywords, list):
            return [item for item in keywords if isinstance(item, str)]
        return []

    @staticmethod
    def _format_signals(signals: list[KeywordSignal]) -> str:
        if not signals:
            return "- 暂无足够历史数据，请采用通用 Pinterest SEO 最佳实践，并标记为待验证假设。"
        return "\n".join(
            f"- {signal.keyword}: weight={signal.weight}, avg_ctr={signal.avg_ctr}, samples={signal.sample_size}"
            for signal in signals
        )
