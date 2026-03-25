from sqlalchemy.orm import Session

from swiss_companies.config import GlobalConfig
from swiss_companies.database import db
from swiss_companies.models import ZefixCompany


def main():
    db.setup(GlobalConfig().db_url.get_secret_value())
    with Session(db.engine) as session:
        deleted = session.query(ZefixCompany).delete()
        session.commit()
    print(f"zefix_companies truncated ({deleted:,} rows removed).")


if __name__ == "__main__":
    main()
