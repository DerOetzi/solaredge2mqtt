from pydantic import BaseModel, Field, PrivateAttr, SecretStr

from solaredge2mqtt.core.exceptions import ConfigurationException
from solaredge2mqtt.core.logging import logger

SECONDS_PER_DAY = 86400
SECONDS_PER_HOUR = 3600
SECONDS_PER_YEAR = SECONDS_PER_DAY * 365
SECONDS_PER_2_YEARS = SECONDS_PER_YEAR * 2


class InfluxDBClientParams(BaseModel):
    url: str
    token: str
    org: str


class InfluxDBSettings(BaseModel):
    host: str | None = Field(default=None)
    port: int = Field(default=8086)
    token: SecretStr | None = Field(default=None)
    org: str | None = Field(default=None)
    bucket: str = Field(default="solaredge")
    retention: int = Field(default=SECONDS_PER_2_YEARS)
    retention_raw: int = Field(default=25)

    _url: str | None = PrivateAttr(default=None)

    @property
    def url(self) -> str:
        if self._url is None:
            if self.host is None:
                raise ConfigurationException("influxdb", "No InfluxDB host set.")

            self._url = f"{self.host}:{self.port}"

            if self._url.startswith("http://"):  # noqa: S5332 - User explicitly configured this
                logger.info("InfluxDB uses unsecured HTTP connection.")
            elif not str(self.host).startswith("https://"):
                self._url = f"https://{self._url}"

        return self._url

    @property
    def client_params(self) -> InfluxDBClientParams:
        if self.token is None or self.org is None:
            raise ConfigurationException(
                "influxdb", "Token and org must be set for client parameters"
            )

        return InfluxDBClientParams(
            url=self.url,
            token=self.token.get_secret_value(),
            org=self.org,
        )

    @property
    def is_configured(self) -> bool:
        return all(
            [
                self.host is not None,
                self.port is not None,
                self.token is not None,
                self.org is not None,
            ]
        )
