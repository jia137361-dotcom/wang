from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.evomap.strategy_matrix import upsert_strategy
from app.models.global_strategy import GlobalStrategy
from app.schemas.strategies import StrategyRead, StrategyUpsert


router = APIRouter()


@router.get("/{scope}", response_model=StrategyRead)
def get_strategy_record(scope: str, db: Session = Depends(get_db)) -> GlobalStrategy:
    record = db.scalar(select(GlobalStrategy).where(GlobalStrategy.scope == scope))
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    return record


@router.put("/{scope}", response_model=StrategyRead)
def put_strategy(scope: str, payload: StrategyUpsert, db: Session = Depends(get_db)) -> GlobalStrategy:
    return upsert_strategy(db, scope=scope, strategy=payload.strategy, version=payload.version)
