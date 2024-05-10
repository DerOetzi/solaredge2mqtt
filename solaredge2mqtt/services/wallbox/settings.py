from pydantic import BaseModel, Field, SecretStr


class WallboxSettings(BaseModel):
    host: str = Field(None)
    password: SecretStr = Field(None)
    serial: str = Field(None)

    @property
    def is_configured(self) -> bool:
        return all(
            [self.host is not None, self.password is not None, self.serial is not None]
        )
