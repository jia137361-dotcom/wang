from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.evomap.prompt_evolve import PromptContext, PromptEvolver
from app.schemas.evomap import PromptBuildResponse, PromptContextRequest, StrategyAdviceResponse


router = APIRouter()


@router.get("/keyword-signals")
def keyword_signals(
    niche: str | None = None,
    product_type: str | None = None,
    min_impressions: int = Query(default=100, ge=0),
    min_ctr: float = Query(default=0.01, ge=0.0),
    top_keyword_limit: int = Query(default=12, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    evolver = PromptEvolver(
        db=db,
        min_impressions=min_impressions,
        min_ctr=min_ctr,
        top_keyword_limit=top_keyword_limit,
    )
    return {
        "signals": [
            signal.model_dump()
            for signal in evolver.get_keyword_signals(niche=niche, product_type=product_type)
        ]
    }


@router.get("/strategy-advice", response_model=StrategyAdviceResponse)
def strategy_advice(
    niche: str | None = None,
    product_type: str | None = None,
    db: Session = Depends(get_db),
) -> StrategyAdviceResponse:
    evolver = PromptEvolver(db=db)
    return StrategyAdviceResponse(
        advice=evolver.generate_strategy_advice(niche=niche, product_type=product_type)
    )


@router.post("/content-brief", response_model=PromptBuildResponse)
def content_brief(payload: PromptContextRequest, db: Session = Depends(get_db)) -> PromptBuildResponse:
    evolver = PromptEvolver(db=db)
    context = _to_prompt_context(payload)
    prompt = evolver.build_content_prompt(context)
    generated_text = evolver.generate_content_brief(context) if payload.generate else None
    return PromptBuildResponse(prompt=prompt, generated_text=generated_text)


@router.post("/visual-prompt", response_model=PromptBuildResponse)
def visual_prompt(payload: PromptContextRequest, db: Session = Depends(get_db)) -> PromptBuildResponse:
    evolver = PromptEvolver(db=db)
    context = _to_prompt_context(payload)
    prompt = evolver.build_visual_prompt(context)
    generated_text = evolver.volc_client.generate_text(
        prompt,
        system_prompt="你是 Pinterest POD 视觉策略专家，会将数据反馈转化为图片 Prompt。",
        temperature=0.6,
        max_tokens=1400,
    ) if payload.generate else None
    return PromptBuildResponse(prompt=prompt, generated_text=generated_text)


def _to_prompt_context(payload: PromptContextRequest) -> PromptContext:
    return PromptContext(
        product_type=payload.product_type,
        niche=payload.niche,
        audience=payload.audience,
        season=payload.season,
        offer=payload.offer,
        destination_url=payload.destination_url,
    )
