from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from swiss_companies.database import get_session
from swiss_companies.models import ZefixCompany
from swiss_companies.noga import DIVISION_NAME, NOGA_SECTIONS

router = APIRouter(prefix="/sectors", tags=["sectors"])


class Sector(BaseModel):
    id: str
    name: str


class Division(BaseModel):
    id: str
    name: str


@router.get("", response_model=list[Sector])
def list_sectors() -> list[Sector]:
    return [Sector(id=code, name=name) for code, name, _ in NOGA_SECTIONS]


@router.get("/{section_id}/divisions", response_model=list[Division])
def list_divisions(
    section_id: str,
    session: Session = Depends(get_session),
) -> list[Division]:
    stmt = (
        select(ZefixCompany.sector_division)
        .where(ZefixCompany.sector_section == section_id.upper())
        .where(ZefixCompany.sector_division.is_not(None))
        .distinct()
        .order_by(ZefixCompany.sector_division)
    )
    return [
        Division(id=code, name=DIVISION_NAME.get(code, code))
        for code in session.scalars(stmt)
    ]
