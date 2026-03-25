from pydantic import BaseModel, computed_field


class CompanyPage(BaseModel):
    items: list["ZefixCompany"]
    total: int


class ZefixCompany(BaseModel):
    model_config = {"from_attributes": True}

    uid: str
    org: str
    legal_name: str
    legal_form: str
    canton: str
    city: str
    street: str | None = None
    zip: str | None = None
    description: str | None = None
    description_lang: str | None = None
    description_en: str | None = None
    sector_section: str | None = None
    sector_division: str | None = None
    lat: float | None = None
    lng: float | None = None

    @computed_field
    @property
    def cantonal_excerpt_url(self) -> str:
        uid = f"{self.uid[:3]}-{self.uid[3:6]}.{self.uid[6:9]}.{self.uid[9:12]}"
        match self.canton:
            case "FR":
                return f"https://adm.appls.fr.ch/hrcmatic/extract?companyOfsUid={uid}"
            case "GE":
                return f"http://app2.ge.ch/ecohrcinternet/extract?lang=FR&companyOfsUid={uid}"
            case "NE":
                return f"https://rcnet.ne.ch/extract?companyOfsUid={uid}"
            case "VD":
                return f"https://prestations.vd.ch/pub/101266/extract?lang=FR&companyOfsUid={uid}"
            case "VS":
                return (
                    f"https://vc.chregister.ch/cr-portal/auszug/auszug.xhtml?uid={uid}"
                )
            case _:
                return f"https://{self.canton.lower()}.chregister.ch/cr-portal/auszug/auszug.xhtml?uid={uid}"
