from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    attachments_dir: str
    http_host: str = "127.0.0.1"
    http_port: int = 8798
    public_base_url: str
    app_master_key: str
    session_secret: str
    ohimymind_bootstrap_admin: str = ""
    ohimymind_bootstrap_password: str = ""
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""

    @property
    def gmail_oauth_configured(self) -> bool:
        return bool(self.google_oauth_client_id.strip() and self.google_oauth_client_secret.strip())

    @property
    def cookie_secure(self) -> bool:
        return self.public_base_url.lower().startswith("https://")


settings = Settings()
