from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from swiss_companies.database import db
from swiss_companies.routers.cantons import router as cantons_router
from swiss_companies.routers.companies import router as companies_router
from swiss_companies.routers.legal_forms import router as legal_forms_router
from swiss_companies.routers.sectors import router as sectors_router


def create_app(database_url: str) -> FastAPI:
    db.setup(database_url)
    app = FastAPI(title="Swiss Companies API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.include_router(companies_router)
    app.include_router(legal_forms_router)
    app.include_router(cantons_router)
    app.include_router(sectors_router)

    return app
