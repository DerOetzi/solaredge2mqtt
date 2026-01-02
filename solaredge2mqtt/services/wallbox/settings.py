from pydantic import BaseModel, Field, SecretStr


class WallboxSettings(BaseModel):
    host: str = Field(None)
    password: SecretStr = Field(None)
    serial: SecretStr = SecretStr(None)
    retain: bool = Field(False)

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
