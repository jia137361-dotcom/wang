from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.evomap.prompt_evolve import PromptContext, PromptEvolver, prompt_context_from_request
from app.models.content_template import ContentTemplate
from app.schemas.evomap import (
    ContentTemplateRead,
    ContentTemplateUpsert,
    PromptBuildResponse,
    PromptContextRequest,
    StrategyAdviceResponse,
)


router = APIRouter()


@router.get("/templates", response_model=list[ContentTemplateRead])
def list_templates(
    scope: str | None = None,
    template_type: str | None = Query(default=None, pattern="^(title_description|image_prompt)$"),
    db: Session = Depends(get_db),
) -> list[ContentTemplate]:
    stmt = select(ContentTemplate).order_by(ContentTemplate.scope, ContentTemplate.template_type)
    if scope:
        stmt = stmt.where(ContentTemplate.scope == scope)
    if template_type:
        stmt = stmt.where(ContentTemplate.template_type == template_type)
    return list(db.scalars(stmt).all())


@router.put("/templates", response_model=ContentTemplateRead)
def upsert_template(payload: ContentTemplateUpsert, db: Session = Depends(get_db)) -> ContentTemplate:
    template = db.scalar(
        select(ContentTemplate).where(
            ContentTemplate.scope == payload.scope,
            ContentTemplate.template_type == payload.template_type,
        )
    )
    if template is None:
        template = ContentTemplate(
            scope=payload.scope,
            template_type=payload.template_type,
            template_text=payload.template_text,
            is_active=payload.is_active,
        )
        db.add(template)
    else:
        template.template_text = payload.template_text
        template.is_active = payload.is_active
    db.commit()
    db.refresh(template)
    return template


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
    context = prompt_context_from_request(payload)
    prompt = evolver.build_content_prompt(context)
    generated_text = evolver.generate_content_brief(context) if payload.generate else None
    return PromptBuildResponse(prompt=prompt, generated_text=generated_text)


@router.post("/visual-prompt", response_model=PromptBuildResponse)
def visual_prompt(payload: PromptContextRequest, db: Session = Depends(get_db)) -> PromptBuildResponse:
    evolver = PromptEvolver(db=db)
    context = prompt_context_from_request(payload)
    prompt = evolver.build_visual_prompt(context)
    generated_text = evolver.volc_client.generate_text(
        prompt,
        system_prompt="你是 Pinterest POD 视觉策略专家，会将数据反馈转化为图片 Prompt。",
        temperature=0.6,
        max_tokens=1400,
    ) if payload.generate else None
    return PromptBuildResponse(prompt=prompt, generated_text=generated_text)


