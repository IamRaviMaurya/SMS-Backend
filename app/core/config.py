import os
import warnings
from typing import List
from pydantic_settings import BaseSettings

_DEFAULT_SECRET = "super-secret-key-change-in-production-2026"


class Settings(BaseSettings):
    PROJECT_NAME: str = "Indian School Management System API"
    VERSION: str = "1.1.0"
    API_V1_STR: str = "/api/v1"
    ENV: str = os.getenv("ENV", "development")

    # Database config: defaults to SQLite for easy local dev, but supports MySQL URL seamlessly
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./school.db")

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", _DEFAULT_SECRET)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24)))

    # Comma-separated list of allowed browser origins. "*" only for local development.
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    # Root domain used for slug-based subdomain tenant resolution (e.g. greenwood.sms.com)
    TENANT_ROOT_DOMAIN: str = os.getenv("TENANT_ROOT_DOMAIN", "")

    # Bootstrap Super Admin (seeded by migrate/seed scripts, never used as a login backdoor)
    SUPER_ADMIN_EMAIL: str = os.getenv("SUPER_ADMIN_EMAIL", "admin@gmail.com")
    SUPER_ADMIN_PASSWORD: str = os.getenv("SUPER_ADMIN_PASSWORD", "Admin@123")

    class Config:
        case_sensitive = True

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()

if settings.SECRET_KEY == _DEFAULT_SECRET and settings.ENV.lower() not in ("development", "dev", "local", "test"):
    warnings.warn("SECRET_KEY is the insecure default. Set the SECRET_KEY environment variable in production.")
