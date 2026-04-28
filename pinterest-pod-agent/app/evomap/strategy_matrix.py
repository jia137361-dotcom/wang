from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.global_strategy import GlobalStrategy


def get_strategy(db: Session, scope: str) -> dict:
    record = db.query(GlobalStrategy).filter(GlobalStrategy.scope == scope).one_or_none()
    return record.strategy if record else {}


def upsert_strategy(db: Session, scope: str, strategy: dict, *, version: str = "v1") -> GlobalStrategy:
    record = db.query(GlobalStrategy).filter(GlobalStrategy.scope == scope).one_or_none()
    if record is None:
        record = GlobalStrategy(scope=scope, strategy=strategy, version=version)
        db.add(record)
    else:
        record.strategy = strategy
        record.version = version
    db.commit()
    db.refresh(record)
    return record
