import logging

from swiss_companies.app import create_app
from swiss_companies.config import GlobalConfig

logging.basicConfig(level=logging.INFO)

config = GlobalConfig()
app = create_app(database_url=config.db_url.get_secret_value())
