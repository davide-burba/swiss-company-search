from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class GlobalConfig(BaseSettings):
    db_host: str = Field(default="localhost")
    db_port: int = Field(default=5431)
    db_pass: SecretStr = Field(default=SecretStr("swiss"))
    db_user: str = Field(default="swiss")
    db_name: str = Field(default="swiss_companies")

    zefix_username: str = Field(default="")
    zefix_password: SecretStr = Field(default=SecretStr(""))  # type: ignore

    @computed_field  # type: ignore
    @property
    def db_url(self) -> SecretStr:
        return SecretStr(
            f"postgresql+psycopg2://{self.db_user}:{self.db_pass.get_secret_value()}@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", case_sensitive=False
    )
