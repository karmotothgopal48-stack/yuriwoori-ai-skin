from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    backend_port: int = 8000
    database_url: str = ""
    jwt_secret: str = ""
    jwt_expires_in: int = 3600
    frontend_origin: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()