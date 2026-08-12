import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Indian School Management System API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database config: defaults to SQLite for easy local dev, but supports MySQL URL seamlessly
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./school.db")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key-change-in-production-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 24 hours

    class Config:
        case_sensitive = True

settings = Settings()
