from pydantic import BaseModel, Field, SecretStr


class MonitoringSettings(BaseModel):
    site_id: SecretStr = SecretStr(None)
    username: str = Field(None)
    password: SecretStr = Field(None)
    retain: bool = Field(False)

    @property
    def is_configured(self) -> bool:
        return all(
            [
                self.site_id is not None,
                self.username is not None,
                self.password is not None,
            ]
        )
