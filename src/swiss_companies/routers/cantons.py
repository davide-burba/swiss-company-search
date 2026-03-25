from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from swiss_companies.database import get_session
from swiss_companies.models import ZefixCompany

router = APIRouter(prefix="/cantons", tags=["cantons"])


class Canton(BaseModel):
    id: str
    name: str


class City(BaseModel):
    name: str
    zip: str | None


CANTONS: dict[str, str] = {
    "AG": "Aargau",
    "AI": "Appenzell Innerrhoden",
    "AR": "Appenzell Ausserrhoden",
    "BE": "Bern",
    "BL": "Basel-Landschaft",
    "BS": "Basel-Stadt",
    "FR": "Fribourg",
    "GE": "Geneva",
    "GL": "Glarus",
    "GR": "Graubünden",
    "JU": "Jura",
    "LU": "Lucerne",
    "NE": "Neuchâtel",
    "NW": "Nidwalden",
    "OW": "Obwalden",
    "SG": "St. Gallen",
    "SH": "Schaffhausen",
    "SO": "Solothurn",
    "SZ": "Schwyz",
    "TG": "Thurgau",
    "TI": "Ticino",
    "UR": "Uri",
    "VD": "Vaud",
    "VS": "Valais",
    "ZG": "Zug",
    "ZH": "Zurich",
}


@router.get("", response_model=list[Canton])
def list_cantons() -> list[Canton]:
    return [Canton(id=code, name=name) for code, name in CANTONS.items()]


@router.get("/{canton_id}/cities", response_model=list[City])
def list_cities(
    canton_id: str,
    session: Session = Depends(get_session),
) -> list[City]:
    stmt = select(ZefixCompany.city, ZefixCompany.zip).distinct().order_by(ZefixCompany.city, ZefixCompany.zip)
    if canton_id != "-":
        stmt = stmt.where(ZefixCompany.canton == canton_id.upper())
    return [City(name=city, zip=zip_) for city, zip_ in session.execute(stmt)]
