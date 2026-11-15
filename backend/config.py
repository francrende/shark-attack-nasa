"""Configuración centralizada del backend mediante variables de entorno."""

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Parámetros de configuración cargados desde `.env` o variables de entorno."""

    app_name: str = "Shark Attack API"
    app_version: str = "0.1.0"
    supabase_url: str = ""
    supabase_key: str = ""
    # BACK-18: secret key (sb_secret_...) para la caché persistente. Solo backend, nunca frontend.
    supabase_secret_key: str = ""
    # BACK-18: false desactiva la capa de Supabase (tests, o para aislar un problema).
    cache_persistente: bool = True
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Devuelve la lista de orígenes CORS parseada."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_supabase_configured(self) -> bool:
        """Indica si las credenciales mínimas de Supabase están configuradas."""
        return bool(self.supabase_url.strip() and self.supabase_key.strip())


@lru_cache
def get_settings() -> Settings:
    """Retorna la instancia cacheada de configuración."""
    return Settings()
