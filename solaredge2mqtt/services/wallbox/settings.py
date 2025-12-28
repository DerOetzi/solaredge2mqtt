from pydantic import BaseModel, Field, SecretStr


class WallboxSettings(BaseModel):
    host: str | None = Field(default=None)
    password: SecretStr | None = Field(default=None)
    serial: SecretStr | None = Field(default=None)
    retain: bool = Field(default=False)

    @property
    def is_configured(self) -> bool:
        return all(
            [
                self.host is not None,
                self.password is not None
                and self.password.get_secret_value() is not None,
                self.serial is not None
                and self.serial.get_secret_value() is not None,
            ]
        )
