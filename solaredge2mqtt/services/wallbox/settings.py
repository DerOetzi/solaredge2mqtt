from pydantic import BaseModel, Field, SecretStr

from solaredge2mqtt.core.exceptions import ConfigurationException


class WallboxSettings(BaseModel):
    host: str | None = Field(default=None)
    password: SecretStr | None = Field(default=None)
    serial: SecretStr | None = Field(default=None)
    retain: bool = Field(default=False)

    @property
    def password_secret(self) -> str:
        if self.password is None:
            raise ConfigurationException(
                "wallbox",
                "Wallbox password not set correctly"
            )

        return self.password.get_secret_value()

    @property
    def serial_secret(self) -> str:
        if self.serial is None:
            raise ConfigurationException(
                "wallbox",
                "Wallbox serial not set correctly"
            )

        return self.serial.get_secret_value()

    @property
    def is_configured(self) -> bool:
        return all(
            [
                self.host is not None,
                self.password is not None
                and self.password_secret,
                self.serial is not None
                and self.serial_secret,
            ]
        )
