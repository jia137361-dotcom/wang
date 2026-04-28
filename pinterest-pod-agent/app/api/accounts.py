from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.social_account import SocialAccount
from app.schemas.accounts import SocialAccountCreate, SocialAccountRead, SocialAccountUpdate


router = APIRouter()


@router.post("/", response_model=SocialAccountRead, status_code=status.HTTP_201_CREATED)
def create_account(payload: SocialAccountCreate, db: Session = Depends(get_db)) -> SocialAccount:
    account = SocialAccount(**payload.model_dump())
    db.add(account)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Account already exists: {payload.account_id}",
        ) from exc
    db.refresh(account)
    return account


@router.get("/", response_model=list[SocialAccountRead])
def list_accounts(
    platform: str | None = None,
    risk_status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[SocialAccount]:
    stmt = select(SocialAccount).order_by(SocialAccount.created_at.desc()).offset(offset).limit(limit)
    if platform:
        stmt = stmt.where(SocialAccount.platform == platform)
    if risk_status:
        stmt = stmt.where(SocialAccount.risk_status == risk_status)
    return list(db.scalars(stmt).all())


@router.get("/{account_id}", response_model=SocialAccountRead)
def get_account(account_id: str, db: Session = Depends(get_db)) -> SocialAccount:
    account = db.scalar(select(SocialAccount).where(SocialAccount.account_id == account_id))
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


@router.patch("/{account_id}", response_model=SocialAccountRead)
def update_account(
    account_id: str,
    payload: SocialAccountUpdate,
    db: Session = Depends(get_db),
) -> SocialAccount:
    account = db.scalar(select(SocialAccount).where(SocialAccount.account_id == account_id))
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: str, db: Session = Depends(get_db)) -> None:
    account = db.scalar(select(SocialAccount).where(SocialAccount.account_id == account_id))
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    db.delete(account)
    db.commit()
