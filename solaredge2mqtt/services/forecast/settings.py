from pathlib import Path

import platformdirs
from pydantic import BaseModel, DirectoryPath, Field, field_validator


class ForecastSettings(BaseModel):
    enable: bool = Field(False)
    hyperparametertuning: bool = Field(False)
    cachingdir: DirectoryPath | None = Field(
        default=str(Path(platformdirs.user_cache_dir("se2mqtt_forecast")))
    )
    retain: bool = Field(False)

    @property
    def is_configured(self) -> bool:
        return self.enable

    @property
    def is_caching_enabled(self) -> bool:
        return self.cachingdir is not None

    @field_validator("cachingdir")
    def ensure_secure_cache(cls, v: str | None, values: dict) -> str | None:
        if not values.get("enable", False) or v is None:
            return None

        path = Path(v).resolve()

        path.mkdir(parents=True, exist_ok=True, mode=0o700)

        if path.stat().st_mode & 0o077:
            raise ValueError(f"Insecure cache directory permissions: {path}")

        return str(path)
