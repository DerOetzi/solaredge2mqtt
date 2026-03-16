from pydantic import BaseModel, Field, SecretStr


class MQTTClientArgs(BaseModel):
    identifier: str = Field("solaredge2mqtt")
    username: str | None = Field(None)
    password: str | None = Field(None)


class MQTTSettings(BaseModel):
    client_id: str = Field(default="solaredge2mqtt")
    broker: str
    port: int = Field(default=1883)
    username: str | None = Field(default=None)
    password: SecretStr | None = Field(default=None)
    topic_prefix: str = Field(default="solaredge")

    @property
    def kargs(self) -> MQTTClientArgs:
        return MQTTClientArgs(
            identifier=self.client_id,
            username=self.username,
            password=(
                self.password.get_secret_value()
                if self.password is not None
                else None
            ),
        )
