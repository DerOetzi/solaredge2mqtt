from pydantic import BaseModel, Field, SecretStr

from solaredge2mqtt.core.exceptions import ConfigurationException


class MonitoringSettings(BaseModel):
    site_id: SecretStr | None = Field(default=None)
    username: str | None = Field(default=None)
    password: SecretStr | None = Field(default=None)
    retain: bool = Field(default=False)

    @property
    def site_id_secret(self) -> str:
        if self.site_id is None:
            raise ConfigurationException(
                "monitoring", "Site ID is not set correctly")

        return self.site_id.get_secret_value()

    @property
    def password_secret(self) -> str:
        if self.password is None:
            raise ConfigurationException(
                "monitoring", "Monitoring password is not set correctly"
            )

        return self.password.get_secret_value()

    @property
    def is_configured(self) -> bool:
        return all(
            [
                self.site_id is not None
                and bool(self.site_id_secret),
                self.username is not None,
                self.password is not None
                and bool(self.password_secret),
            ]
        )
