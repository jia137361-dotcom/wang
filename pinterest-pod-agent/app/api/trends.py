from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.workflows.trend_scout import get_recorded_trends, record_manual_trends


router = APIRouter()


class TrendKeywordsPayload(BaseModel):
    keywords: list[str] = Field(min_length=1)
    source: str = "manual"


@router.post("/{scope}")
def record_trends(scope: str, payload: TrendKeywordsPayload, db: Session = Depends(get_db)) -> dict:
    return record_manual_trends(db, scope=scope, keywords=payload.keywords, source=payload.source)


@router.get("/{scope}")
def get_trends(scope: str, db: Session = Depends(get_db)) -> dict:
    return {"scope": scope, "keywords": get_recorded_trends(db, scope=scope)}
