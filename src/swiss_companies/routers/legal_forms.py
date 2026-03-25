from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from swiss_companies.database import get_session
from swiss_companies.models import ZefixCompany

router = APIRouter(prefix="/legal-forms", tags=["legal-forms"])

# ECH-0097 legal form codes (v5.2.0)
LEGAL_FORMS: dict[str, str] = {
    "0101": "Sole Proprietorship",
    "0103": "General Partnership",
    "0104": "Limited Partnership",
    "0105": "Partnership Limited by Shares",
    "0106": "Stock Corporation (AG)",
    "0107": "Limited Liability Company (GmbH)",
    "0108": "Cooperative",
    "0109": "Association",
    "0110": "Foundation",
    "0111": "Foreign Branch (Registered)",
    "0113": "Special Legal Form",
    "0114": "Limited Partnership for Collective Investment",
    "0115": "Investment Company with Variable Capital (SICAV)",
    "0116": "Investment Company with Fixed Capital (SICAF)",
    "0117": "Public Law Institution",
    "0151": "Branch Office",
}


@router.get("", response_model=dict[str, str])
def list_legal_forms(session: Session = Depends(get_session)) -> dict[str, str]:
    codes_in_db = {
        row[0] for row in session.execute(select(ZefixCompany.legal_form).distinct())
    }
    return {code: label for code, label in LEGAL_FORMS.items() if code in codes_in_db}
