from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_FILENAME = "solaredge2mqtt.db"


class StorageSettings(BaseModel):
    enable: bool = Field(default=True)
    path: str | None = Field(default=None)
    filename: str = Field(default=DEFAULT_FILENAME)
    retention_months: int = Field(default=0, ge=0)
    retention_raw: int = Field(default=25, ge=1)
    debounce_cycles: int = Field(default=2, ge=1)
    daily_backups: bool = Field(default=True)
    keep_backups: int = Field(default=7, ge=0)

    def resolve_path(self, config_dir: str) -> Path:
        if self.path is not None:
            return Path(self.path)

        return Path(config_dir) / self.filename

    @property
    def is_configured(self) -> bool:
        return self.enable
