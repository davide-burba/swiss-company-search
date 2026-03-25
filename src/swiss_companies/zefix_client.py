"""Client for the Zefix Public REST API."""

import requests

from swiss_companies.config import GlobalConfig

BASE_URL = "https://www.zefix.admin.ch/ZefixPublicREST/api/v1"


class ZefixClient:
    def __init__(self, config: GlobalConfig):
        self._session = requests.Session()
        self._session.auth = (
            config.zefix_username,
            config.zefix_password.get_secret_value(),
        )
        self._session.headers.update({"Accept": "application/json"})

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        response = self._session.get(f"{BASE_URL}{path}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, json: dict) -> dict | list:
        response = self._session.post(f"{BASE_URL}{path}", json=json, timeout=30)
        response.raise_for_status()
        return response.json()

    # --- Company endpoints ---

    def search_companies(
        self,
        name: str,
        canton: str | None = None,
        active_only: bool = True,
        max_entries: int = 50,
        offset: int = 0,
    ) -> dict:
        """Search companies by name with optional canton filter."""
        payload: dict = {
            "name": name,
            "activeOnly": active_only,
            "maxEntries": max_entries,
            "offset": offset,
        }
        if canton:
            payload["canton"] = canton.upper()
        return self._post("/company/search", payload)

    def get_company_by_uid(self, uid: str) -> dict:
        """Get company details by UID (e.g. 'CHE-123.456.789' or '123456789')."""
        return self._get(f"/company/uid/{uid}")

    def get_company_by_chid(self, chid: str) -> dict:
        """Get company details by commercial register number (CH-ID)."""
        return self._get(f"/company/chid/{chid}")

    def get_company_by_ehraid(self, ehraid: int | str) -> dict:
        """Get company details by EHRAID (electronic headquarters register ID)."""
        return self._get(f"/company/ehraid/{ehraid}")

    # --- Reference data endpoints ---

    def get_legal_forms(self) -> list:
        """Return all legal form classifications."""
        return self._get("/legalForm")

    def get_communities(self) -> list:
        """Return all community entries."""
        return self._get("/community")

    def get_registry_offices(self) -> list:
        """Return all registry offices."""
        return self._get("/registryOffice")

    def get_sogc_publications(self, uid: str) -> list:
        """Return Swiss Official Gazette of Commerce publications for a company."""
        return self._get(f"/sogcPublication/uid/{uid}")
