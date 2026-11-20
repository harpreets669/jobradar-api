from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/jobradar"
    cors_origins: str = "http://localhost:3000"

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_async_driver(cls, v: str) -> str:
        # Railway injects plain postgresql:// — SQLAlchemy async needs +asyncpg
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()
