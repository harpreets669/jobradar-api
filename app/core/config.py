from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/jobradar"
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()
