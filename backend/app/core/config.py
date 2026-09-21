from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    anthropic_api_key: str = ""
    environment: str = "development"
    backend_port: int = 8000
    database_url: str = ""
    jwt_secret: str = ""
    jwt_expires_in: int = 3600
    # Comma-separated list of allowed browser origins (CORS).
    frontend_origin: str = "http://localhost:2999,http://127.0.0.1:2999,http://localhost:3000"

    # Shopify Storefront API
    shopify_store_domain: str = ""
    shopify_storefront_access_token: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.frontend_origin.split(",") if o.strip()]


settings = Settings()
