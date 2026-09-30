import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://eve_user:eve_password@db:5432/eve_db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkey123")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

settings = Settings()
