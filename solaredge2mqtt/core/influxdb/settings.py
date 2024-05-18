from pydantic import BaseModel, Field, SecretStr

SECONDS_PER_DAY = 86400
SECONDS_PER_HOUR = 3600
SECONDS_PER_YEAR = SECONDS_PER_DAY * 365
SECONDS_PER_2_YEARS = SECONDS_PER_YEAR * 2


class InfluxDBSettings(BaseModel):
    host: str = Field(None)
    port: int = Field(8086)
    token: SecretStr = Field(None)
    org: str = Field(None)
    bucket: str = Field("solaredge")
    retention: int = Field(SECONDS_PER_2_YEARS)
    retention_raw: int = Field(25)

    @property
    def url(self) -> str:
        url = f"{self.host}:{self.port}"
        if not str(self.host).startswith(("http://", "https://")):
            url = f"http://{url}"

        return url

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
