import ssl
from typing import Any

from aiomqtt import TLSParameters
from pydantic import BaseModel, Field, SecretStr


class MQTTClientArgs(BaseModel):
    identifier: str = Field(default="solaredge2mqtt")
    username: str | None = Field(default=None)
    password: str | None = Field(default=None)


class MQTTSettings(BaseModel):
    client_id: str = Field(default="solaredge2mqtt")
    broker: str
    port: int = Field(default=1883)
    username: str | None = Field(default=None)
    password: SecretStr | None = Field(default=None)
    topic_prefix: str = Field(default="solaredge")
    use_tls: bool = Field(default=False)
    ca_certs: str | None = Field(default=None)
    tls_verify: bool | None = Field(default=True)

    @property
    def kargs(self) -> dict[str, Any]:

        client_args = MQTTClientArgs(
            identifier=self.client_id,
            username=self.username,
            password=(
                self.password.get_secret_value() if self.password is not None else None
            ),
        ).model_dump()

        if self.use_tls:
            client_args["tls_params"] = TLSParameters(
                ca_certs=self.ca_certs,
                cert_reqs=ssl.CERT_REQUIRED if self.tls_verify else ssl.CERT_NONE,
            )
        else:
            client_args["tls_params"] = None

        return client_args
