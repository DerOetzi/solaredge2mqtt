from pydantic import BaseModel, Field, SecretStr


class MonitoringSettings(BaseModel):
    site_id: SecretStr | None = Field(default=None)
    username: str | None = Field(default=None)
    password: SecretStr | None = Field(default=None)
    retain: bool = Field(default=False)

    @property
    def is_configured(self) -> bool:
        return all(
            [
                self.site_id is not None
                and self.site_id.get_secret_value() is not None,
                self.username is not None,
                self.password is not None
                and self.password.get_secret_value() is not None,
            ]
        )
