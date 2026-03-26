import re
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sentence_transformers import SentenceTransformer
from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from swiss_companies.config import EMBEDDING_MODEL
from swiss_companies.database import get_session
from swiss_companies.models import ZefixCompany
from swiss_companies.schemas import CompanyPage

router = APIRouter(prefix="/companies", tags=["companies"])

_embedding_model: SentenceTransformer | None = None


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


@router.get("", response_model=CompanyPage)
def list_companies(
    canton: str | None = Query(None, description="Filter by canton code (e.g. ZH)"),
    city: str | None = Query(
        None, description="Filter by city name (case-insensitive)"
    ),
    legal_form: list[str] = Query(
        default=[], description="Filter by legal form code(s)"
    ),
    sector_section: str | None = Query(
        None, description="Filter by NACE section (e.g. J)"
    ),
    sector_division: str | None = Query(
        None, description="Filter by NACE division (e.g. 62)"
    ),
    q: str | None = Query(None, description="Search company (case-insensitive)"),
    search: Literal["text", "semantic", "hybrid"] = Query(
        "text", description="Search mode"
    ),
    lat: float | None = Query(None, description="Latitude for location-based search"),
    lng: float | None = Query(None, description="Longitude for location-based search"),
    radius_km: float = Query(
        10.0, gt=0, description="Search radius in km (used with lat/lng)"
    ),
    sort_by: str | None = Query(None, description="Sort field"),
    sort_order: str = Query(
        "desc", pattern="^(asc|desc)$", description="Sort direction"
    ),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> CompanyPage:
    stmt = select(ZefixCompany)

    if canton:
        stmt = stmt.where(ZefixCompany.canton == canton.upper())
    if city:
        stmt = stmt.where(ZefixCompany.city.ilike(f"%{city}%"))
    if legal_form:
        stmt = stmt.where(ZefixCompany.legal_form.in_(legal_form))
    if sector_section:
        stmt = stmt.where(ZefixCompany.sector_section == sector_section.upper())
    if sector_division:
        stmt = stmt.where(ZefixCompany.sector_division == sector_division)

    if q:
        tokens = re.sub(r"[^\w\s]", " ", q, flags=re.UNICODE).split()
        tsquery = (
            func.to_tsquery("simple", " & ".join(f"{t}:*" for t in tokens))
            if tokens
            else None
        )

        if search == "text":
            if tsquery is not None:
                stmt = stmt.where(ZefixCompany.search_vector.op("@@")(tsquery))
                stmt = stmt.order_by(func.ts_rank_cd(ZefixCompany.search_vector, tsquery).desc())

        elif search == "semantic":
            model = _get_embedding_model()
            query_vec = model.encode(q, normalize_embeddings=True).tolist()
            stmt = stmt.where(ZefixCompany.embedding.is_not(None))
            stmt = stmt.order_by(ZefixCompany.embedding.op("<=>")(query_vec))

        elif search == "hybrid":
            model = _get_embedding_model()
            query_vec = model.encode(q, normalize_embeddings=True).tolist()
            stmt = stmt.where(ZefixCompany.embedding.is_not(None))
            cosine_distance = ZefixCompany.embedding.op("<=>")(query_vec)
            semantic_score = literal(1.0) - cosine_distance
            fts_score = (
                func.ts_rank_cd(ZefixCompany.search_vector, tsquery, 32)
                if tsquery is not None
                else literal(0.0)
            )
            stmt = stmt.order_by((literal(0.5) * fts_score + literal(0.5) * semantic_score).desc())

    if lat is not None and lng is not None:
        dlat = func.radians(ZefixCompany.lat - lat)
        dlng = func.radians(ZefixCompany.lng - lng)
        a = func.sin(dlat / 2) * func.sin(dlat / 2) + func.cos(
            func.radians(lat)
        ) * func.cos(func.radians(ZefixCompany.lat)) * func.sin(dlng / 2) * func.sin(
            dlng / 2
        )
        distance_km = 6371 * 2 * func.asin(func.sqrt(a))
        stmt = stmt.where(
            ZefixCompany.lat.is_not(None),
            ZefixCompany.lng.is_not(None),
            distance_km <= radius_km,
        )

    # Default alphabetical tiebreaker
    stmt = stmt.order_by(ZefixCompany.legal_name)

    total: int = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(session.scalars(stmt.offset(offset).limit(limit)))
    return CompanyPage(items=items, total=total)
