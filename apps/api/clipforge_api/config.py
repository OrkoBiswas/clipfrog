from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_url: str = "http://localhost:3000"
    database_url: str = "postgresql+psycopg://clipforge:clipforge_local@127.0.0.1:55432/clipforge"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint: str = "http://localhost:9000"
    s3_public_endpoint: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_bucket: str = "clipforge"
    s3_access_key_id: str = "clipforge_local"
    s3_secret_access_key: str = "clipforge_local_password"
    s3_force_path_style: bool = True
    cookie_secure: bool = False
    session_days: int = 14
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    mail_from: str = "hello@clipforge.local"
    max_upload_bytes: int = 5 * 1024**3
    max_source_duration_minutes: int = 120
    default_clip_limit: int = 100
    media_retention_days: int = Field(default=0, ge=0, le=3650)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_creator: str = ""
    stripe_price_pro: str = ""

    @property
    def trusted_origins(self) -> list[str]:
        """Treat loopback names as aliases only for a loopback-configured app."""
        origin = self.app_url.rstrip("/")
        parsed = urlsplit(origin)
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            return [origin]
        port = f":{parsed.port}" if parsed.port else ""
        return [f"{parsed.scheme}://{host}{port}" for host in ("localhost", "127.0.0.1", "[::1]")]


@lru_cache
def settings() -> Settings:
    return Settings()
