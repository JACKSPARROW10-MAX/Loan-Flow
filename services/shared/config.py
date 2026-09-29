"""
LoanFlow – Shared configuration loaded from environment variables.
Every service imports from here.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Supabase / Database ──
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # ── Upstash Redis ──
    upstash_redis_url: str = "redis://localhost:6379/0"
    upstash_redis_token: str = ""

    # ── Auth / JWT ──
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    csrf_secret: str = "dev-csrf-secret-change-me"

    # ── Storage ──
    storage_bucket: str = "loanflow-docs"

    # ── Service URLs ──
    auth_service_url: str = "http://localhost:8001"
    loan_app_service_url: str = "http://localhost:8002"
    document_service_url: str = "http://localhost:8003"
    kyc_service_url: str = "http://localhost:8004"
    risk_service_url: str = "http://localhost:8005"
    audit_service_url: str = "http://localhost:8006"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
